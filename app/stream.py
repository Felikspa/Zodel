"""
流式处理核心模块。

本模块定义了 StreamHandler 类，它负责处理所有与 LLM 模型的实时流式交互。
它作为 UI 和底层模型提供商之间的桥梁。
"""

import re
from typing import Dict, Generator, List, Tuple, Optional, Union
import gradio as gr

from .helper import extract_model_name, get_embeddings, get_model_type, infer_provider_from_model, stream_chat
from .config import DEFAULT_SYSTEM_PROMPT,logger
from .zflow_runner import ZflowRunner

class StreamHandler:
    """
    管理与 LLM 的流式通信，并根据用户选择的模式（手动、自动、Zflow）进行调度。
    """
    def __init__(self, default_provider: str = 'ollama_local'):
        self.default_provider = default_provider

    def _find_chat(self, title: str, chats: List[Dict]) -> Optional[Dict]:
        """在 chats 列表中根据 title 查找对应的会话。"""
        for chat in chats:
            if chat.get("title") == title:
                return chat
        return None

    def _handle_classification(
        self, 
        msg: str,
        classifier_model: str, 
        custom_labels: List[str], 
        output_models: List[str], 
        custom_classifier_prompt: Optional[str]
    ) -> Tuple[str, str]:
        """
        执行分类逻辑，返回最终选择的模型和一条通知消息。
        :return: (final_model_name, notification_message)
        """
        # 1. 校验输入和设定回退模型
        if not classifier_model:
            raise ValueError("请在设置中选择一个分类模型 (Classifier Model)。")
        if not output_models or not custom_labels:
            raise ValueError("请在设置中至少定义一条有效的分类规则。")
        if len(custom_labels) != len(output_models):
            raise ValueError(f"自定义标签数量 ({len(custom_labels)}) 与响应模型数量 ({len(output_models)}) 必须一一对应。")

        default_fallback_model = output_models[0]
        model_map = dict(zip(custom_labels, output_models))

        # 2. 构建分类器 Prompt
        labels_str = ', '.join(custom_labels)
        if custom_classifier_prompt:
            final_classifier_prompt = custom_classifier_prompt
            if "respond only" not in final_classifier_prompt.lower():
                 final_classifier_prompt += f" Respond ONLY with one of the following words: {labels_str}."
        else:
            final_classifier_prompt = (
                f"You are a routing agent. Classify the user's prompt. "
                f"Respond ONLY with one of the following single words: {labels_str}."
            )

        # 3. 调用分类模型（同步执行）
        classifier_messages = [
            {"role": "system", "content": final_classifier_prompt},
            {"role": "user", "content": msg}
        ]
        classifier_name_pure = extract_model_name(classifier_model)
        classifier_provider = infer_provider_from_model(classifier_model)

        try:
            classification_stream = stream_chat(classifier_provider, classifier_name_pure, classifier_messages)
            classification = "".join(list(classification_stream)).strip().lower()
        except Exception as e:
            notification = f"**[⚠️ 路由回退]** 分类模型API通信失败: {e}。已回退到默认模型 ({default_fallback_model})。\n\n"
            return default_fallback_model, notification

        # 4. 根据分类结果选择模型
        if classification in model_map:
            return model_map[classification], "" # 分类成功，无通知
        else:
            notification = (
                f"**[⚠️ 路由回退]** 分类模型返回了非预期的标签: `{classification}`。"
                f"预期标签: {labels_str}。已回退到默认模型 ({default_fallback_model})。\n\n"
            )
            return default_fallback_model, notification

    def _handle_zflow(self, zflow_code: str) -> Generator[str, None, None]:
        """
        实例化 ZflowRunner 并流式执行 Zflow 代码。

        Args:
            zflow_code (str): 从用户输入框获取的完整 Zflow 脚本。

        Returns:
            Generator[str, None, None]: 一个生成器，逐步 yield Zflow 执行过程中的输出文本。
        """
        yield f"**[Zflow Workflow executing...]**\n```zflow\n{zflow_code}\n```\n\n"

        # 实例化 ZflowRunner，并将核心的 stream_chat 函数作为回调传入
        runner = ZflowRunner(
            stream_callback=stream_chat,
            embedding_callback=get_embeddings
        )

        try:
            yield from runner.execute_stream(code=zflow_code)
        except Exception as e:
            yield f"\n\n**[Critical Zflow Error]** An unexpected error occurred during execution: {e}"

    def _stream_response(
        self,
        current_chat: Dict,
        model_to_use: str,
        system_prompt: str,
        display_prefix: str = ""
    ) -> Generator[Tuple[List[Tuple[str, str]], gr.update], None, None]:
        """
        接收最终确定的模型，准备消息并流式返回响应给 Gradio Chatbot。

        Args:
            current_chat (Dict): 当前正在进行的会话对象。
            model_to_use (str): 最终确定用于本次响应的、带前缀的模型名称。
            system_prompt (str): 本次对话使用的系统提示。
            display_prefix (str, optional): 需要在模型响应前额外显示的通知信息 (例如，路由回退警告)。

        Returns:
            Generator[Tuple[List[Tuple[str, str]], gr.update], None, None]: 
                一个生成器，每次 yield 当前会话的 history 和一个空的 gr.update 对象。
        """
        history = current_chat["history"]
        user_msg = history[-1][0] # 获取最新的用户输入

        # 准备 API 请求的消息列表 (messages)
        messages = [{"role": "system", "content": system_prompt}]
        for turn in history[:-1]: # 遍历除当前轮次外的所有历史记录
            turn_user_msg, turn_assistant_msg = turn
            if turn_user_msg:
                messages.append({"role": "user", "content": turn_user_msg})
            if turn_assistant_msg:
                # 在将历史记录发送给模型前，清理掉我们自己添加的显示前缀 (如 **[ModelA]:**)。
                # 这确保了模型接收到的是纯净的对话内容。
                content_for_api = re.sub(r'\*\*\[.*?\]\*\*:\s*', '', turn_assistant_msg)
                messages.append({"role": "assistant", "content": content_for_api})
        
        # 将当前用户的提问添加到消息列表的末尾
        messages.append({"role": "user", "content": user_msg})

        # --- 开始向 UI 流式输出 ---
        
        # 组合最终的显示前缀，包括通知和模型名称
        final_display_prefix = f"{display_prefix}**[{model_to_use}]**: "
        full_response = final_display_prefix
        history[-1] = (user_msg, full_response)
        yield history, gr.update() # 初始更新，立即在界面上显示前缀

        # 发起真正的流式 API 请求
        try:
            model_name_pure = extract_model_name(model_to_use)
            provider = infer_provider_from_model(model_to_use)
            
            # 检查模型类型，防止在普通聊天中使用 Embedding 模型
            if get_model_type(model_name_pure) != 'chat':
                raise ValueError(f"Model '{model_name_pure}' is an embedding model and cannot be used for chat.")

            # 组合最终的显示前缀
            final_display_prefix = f"{display_prefix}**[{model_to_use}]**: "

            # 调用核心流式函数
            stream = stream_chat(provider, model_name_pure, messages)
            
            for content_chunk in stream:
                full_response += content_chunk
                history[-1] = (user_msg, full_response)
                yield history, gr.update() # 持续将新收到的 token 更新到 UI

        except Exception as e:
            # 如果 API 调用失败，将错误信息显示在 UI 上
            error_message = f"{final_display_prefix} API request failed: {e}"
            history[-1] = (user_msg, error_message)
            yield history, gr.update()

    def input_msg(
        self,
        msg: str,
        title: str,
        chats: List[Dict],
        global_model: str,
        system_prompt: Optional[str],
        classifier_model: str,
        output_models: List[str],
        custom_labels: List[str],
        custom_classifier_prompt: Optional[str]
    ) -> Generator[Tuple[List[Tuple[str, str]], Union[gr.update, str]], None, None]:
        """
        处理用户输入的总入口和调度器。

        Args:
            msg (str): 用户在输入框中输入的文本。
            title (str): 当前选择的会话标题。
            chats (List[Dict]): 包含所有会话的完整状态列表。
            global_model (str): 用户在主模型选择器中选择的模式 ('Auto-selected', 'Zflow', 或具体模型名称)。
            system_prompt (Optional[str]): 当前的系统提示。
            classifier_model (str): 设置中指定的分类器模型。
            output_models (List[str]): 设置中定义的、与标签对应的输出模型列表。
            custom_labels (List[str]): 设置中定义的自定义标签列表。
            custom_classifier_prompt (Optional[str]): 设置中定义的自定义分类器提示。

        Returns:
            Generator[...]: 一个生成器，Gradio 用它来流式更新 chatbot 和 user_input 组件。
        """
        system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        
        if not msg or not msg.strip():
            current_chat = self._find_chat(title, chats)
            yield current_chat["history"] if current_chat else [], gr.update()
            return
        
        current_chat = self._find_chat(title, chats)
        if not current_chat:
            logger.error(f"Chat with title '{title}' not found.")
            yield [], "Error: Chat not found." # 向用户显示错误
            return

        # --- 统一处理用户输入的初始显示 ---
        
        # Zflow 模式下，将用户输入的代码块格式化以优化显示
        display_msg = f"```zflow\n{msg}\n```" if global_model == "Zflow" else msg
        
        current_chat["history"].append((display_msg, None))
        yield current_chat["history"], "" # 立即显示用户输入，并清空输入框

        # --- 核心路由与执行逻辑 ---
        try:
            if global_model == "Zflow":
                # Zflow 模式下，'msg' 就是完整的 Zflow 代码
                full_response = ""
                history = current_chat["history"]
                for chunk in self._handle_zflow(zflow_code=msg):
                    full_response += chunk
                    history[-1] = (display_msg, full_response)
                    yield history, gr.update()
            
            elif global_model == "Auto-selected":
                final_model, notification = self._handle_classification(
                    msg, classifier_model, custom_labels, output_models, custom_classifier_prompt
                )
                yield from self._stream_response(current_chat, final_model, system_prompt, display_prefix=notification)

            else:
                # 手动选择模型模式
                yield from self._stream_response(current_chat, global_model, system_prompt)

        except Exception as e:
            # 捕获所有执行流程中的意外错误，并报告给用户
            error_message = f"An unexpected error occurred: {e}"
            current_chat["history"][-1] = (display_msg, error_message)
            yield current_chat["history"], gr.update()