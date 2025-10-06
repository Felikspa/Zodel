"""
Gradio 用户界面构建模块。

本模块定义了 GradioApp 类，负责搭建应用的完整前端界面，
包括聊天窗口、侧边栏、设置面板，并绑定所有组件的回调函数。
"""

import time
import gradio as gr
from .helper import get_all_models
from .chat_manager import ChatManager
from .stream import StreamHandler
from .config import DEFAULT_SYSTEM_PROMPT

class GradioApp:
    """负责搭建 Gradio UI 并将前端组件与后端逻辑绑定。"""

    def __init__(self):
        """
        初始化 GradioApp 类。
        - 获取所有可用模型。
        - 设置 UI 的默认值和主题。
        - 实例化后端处理器 (ChatManager, StreamHandler)。
        """

        # 1. 获取所有模型列表
        self.models = get_all_models()
        
        # 2. 确保模型列表非空，并确定所有核心 State 的默认值
        if not self.models:
            self.models = ["Ollama:default-model"]

        self.guaranteed_default_model = self.models[0]
        
        # 3. 确定全局模型选择器的列表和默认值
        
        self.models_with_auto = ["Auto-selected"] + self.models

        # 4. 在模型列表末尾添加 "Zflow" 选项
        if "Zflow" not in self.models_with_auto:
             self.models_with_auto.append("Zflow")

        self.default_model_for_global = self.models_with_auto[0] # Auto-selected 或第一个模型
        
        self.initial_chats = ChatManager.init_chats(self.default_model_for_global)
        self.stream_handler = StreamHandler()

        self.theme = gr.themes.Ocean(
            primary_hue="rose",
            secondary_hue="pink",
            text_size=gr.themes.Size(lg="20px", md="18px", sm="16px", xl="26px", xs="14px", xxl="30px", xxs="12px"),
            font=[gr.themes.GoogleFont('Times New Roman'), 'ui-sans-serif', 'system-ui', 'sans-serif'],
        )

    @staticmethod
    def _get_js_code() -> str:
        """简单的 JS（切换 body dark class）"""
        return """() => { document.body.classList.toggle('dark'); }"""

    # --- Helper function: Process fixed rule inputs and validate data ---
    def save_settings_data(
        self, 
        system_prompt: str, 
        classifier_model: str, 
        classifier_prompt: str, 
        label1: str, model1: str, 
        label2: str, model2: str, 
        label3: str, model3: str, 
        label4: str, model4: str, 
        label5: str, model5: str
    ):
        """
        处理并验证从设置面板提交的分类规则数据。

        Args:
            system_prompt (str): 全局系统提示。
            classifier_model (str): 用于分类的模型。
            classifier_prompt (str): 自定义的分类器提示。
            label1..5 (str): 用户定义的标签。
            model1..5 (str): 与标签对应的输出模型。

        Returns:
            Tuple: 一个元组，包含所有更新后的状态值，用于更新 Gradio State。
        
        Raises:
            gr.Error: 如果规则配置无效（例如，标签重复、模型不存在等）。
        """
        labels = []
        models = []
        valid_models = set(self.models)
        
        rule_pairs = [
            (label1, model1), (label2, model2), (label3, model3), (label4, model4), (label5, model5),
        ]
        
        for i, (label_input, model_input) in enumerate(rule_pairs):
            label = label_input.strip().lower()
            model = model_input.strip()

            # Case 1: Both fields are empty (Skip optional rule)
            if not label and not model:
                continue
            
            # Case 2: Incomplete rule definition (one field is empty, the other is not)
            if not label or not model:
                raise gr.Error(f"Rule {i+1}: Both the Label and the Output Model must be defined, or both must be left empty.")
            
            # Case 3: Validation on defined rule
            if label in labels:
                raise gr.Error(f"Duplicate label detected: '{label}'.")
            
            if model not in valid_models:
                raise gr.Error(f"Output Model '{model}' is invalid. Please select an accurate model name from the list.")

            # If valid and complete, append
            labels.append(label)
            models.append(model)
        
        # Final check: Must define at least one rule
        if not labels or not models:
             raise gr.Error("Configuration list is empty. Please define at least one valid label and model pair.")
        
        # Return state update values
        return (
            system_prompt, 
            gr.update(value=f"Settings saved successfully! Configured {len(labels)} classification rules."), 
            classifier_model, 
            labels, 
            models,
            classifier_prompt,
        )

    # -----------------------------------------------

    def build(self):
        js_code = self._get_js_code()
        
        # Initial rule data and states
        initial_label_1 = "nonlogical"
        initial_label_2 = "logical"
        initial_model_default = self.guaranteed_default_model
        
        # Initialize the state based on the first two rules
        initial_labels_state = [initial_label_1, initial_label_2]
        initial_models_state = [initial_model_default, initial_model_default]

        # -----------------------------------------------

        with gr.Blocks(js=js_code, theme=self.theme) as app:
            
            # --- Settings Panel (Settings Group) ---
            with gr.Row():
                with gr.Group(visible=False, elem_id='settings_group') as settings_group:
                    
                    # Basic Settings
                    system_prompt_text = gr.Textbox(value=DEFAULT_SYSTEM_PROMPT, label="System Prompt", lines=1)
                    dark_mode = gr.Button("Dark Mode")
                    
                    
                    # Classifier Model
                    classifier_model_dropdown = gr.Dropdown(choices=self.models, value=self.guaranteed_default_model, label="Classifier Model")
                    
                    # Custom Classifier Prompt
                    custom_classifier_prompt_text = gr.Textbox(
                        value="", 
                        label="Classifier System Prompt", 
                        lines=2,
                        placeholder="Leave blank to use the default prompt."
                    )
                    
                    gr.Markdown("---")
                    gr.Markdown("### Dynamic Classification Rules")
                    gr.Markdown(
                        "The model corresponding to the first rule will be used as the **Default Model** for errors or unrecognized labels."
                    )

                    rule_inputs = []

                    #Collapsible Section
                    with gr.Accordion("Custom Labels", open=False):
                    # Rule 1 (Default/Fallback)
                        with gr.Row():
                            label1 = gr.Textbox(value=initial_label_1, label="Rule 1 Label", scale=1)
                            model1 = gr.Dropdown(choices=self.models, value=initial_model_default, label="Rule 1 Output Model", scale=2)
                            rule_inputs.extend([label1, model1])

                        # Rule 2 (Second primary rule)
                        with gr.Row():
                            label2 = gr.Textbox(value=initial_label_2, label="Rule 2 Label", scale=1)
                            model2 = gr.Dropdown(choices=self.models, value=initial_model_default, label="Rule 2 Output Model", scale=2)
                            rule_inputs.extend([label2, model2])

                        # Rule 3
                        with gr.Row():
                            label3 = gr.Textbox(value="", label="Rule 3 Label", scale=1)
                            model3 = gr.Dropdown(choices=self.models, value=initial_model_default, label="Rule 3 Output Model", scale=2)
                            rule_inputs.extend([label3, model3])
                        
                        # Rule 4
                        with gr.Row():
                            label4 = gr.Textbox(value="", label="Rule 4 Label", scale=1)
                            model4 = gr.Dropdown(choices=self.models, value=initial_model_default, label="Rule 4 Output Model", scale=2)
                            rule_inputs.extend([label4, model4])

                        # Rule 5
                        with gr.Row():
                            label5 = gr.Textbox(value="", label="Rule 5 Label", scale=1)
                            model5 = gr.Dropdown(choices=self.models, value=initial_model_default, label="Rule 5 Output Model", scale=2)
                            rule_inputs.extend([label5, model5])
                    
                    save_settings = gr.Button("Save", elem_id='save_settings')
                    save_note = gr.Markdown('Settings saved successfully.')

            with gr.Row():
                # --- Sidebar ---
                with gr.Column(min_width=50, scale=1, elem_id='left_col') as left_col:
                    gr.Markdown("<font size=6 face='Times New Roman'>ZODEL</font>")
                    new_chat_btn = gr.Button("New Chat")
                    chat_selector = gr.Radio(choices=[c["title"] for c in self.initial_chats], value=self.initial_chats[0]["title"], label="Chats")
                    delete_chat_btn = gr.Button("Delete Chat", elem_id='delete_chat_btn')
                
                # --- Main Chat Area ---
                with gr.Column(scale=7):
                    with gr.Row(scale=1):
                        with gr.Column(scale=1, min_width=25):
                            toggle_sidebar_btn = gr.Button("Toggle", elem_id='toggle_sidebar_btn')
                        with gr.Column(scale=14, min_width=25):
                            # Global Model Selector
                            model_selector = gr.Dropdown(choices=self.models_with_auto, value=self.default_model_for_global, show_label=False, interactive=True)
                        with gr.Column(scale=1, min_width=25):
                            settings_btn = gr.Button("...", elem_id='settings')
                    
                    chatbot = gr.Chatbot(height=650, elem_id='chatbot', show_label=False)
                    
                    with gr.Row(min_height=50):
                        user_input = gr.Textbox(scale=11, show_label=False, placeholder="Ask anything", lines=1, max_lines=3)
                        send_btn = gr.Button("Send", scale=1, min_width=25)

            # --- State Management ---
            chats_state = gr.State(self.initial_chats)
            sidebar_visible_state = gr.State(True)
            settings_visible_state = gr.State(False)
            
            # State variables for dynamic configuration
            system_prompt_state = gr.State(DEFAULT_SYSTEM_PROMPT)
            classifier_model_state = gr.State(initial_model_default)
            custom_labels_state = gr.State(initial_labels_state)
            output_models_state = gr.State(initial_models_state)
            custom_classifier_prompt_state = gr.State("")
            def on_model_selector_change(selected_model):
                if selected_model == "Zflow":
                    return gr.update(
                        placeholder="Enter your Zflow code here...\ne.g., A=model_name\ni='question'\ni->A_p",
                        lines=5,  # 允许多行输入
                        max_lines=20
                    )
                else:
                    return gr.update(
                        placeholder="Ask anything...",
                        lines=1,
                        max_lines=3
                    )
            model_selector.change(fn=on_model_selector_change, inputs=[model_selector], outputs=[user_input])

            # --- Binding Callbacks ---
            dark_mode.click(None, [], [], js=js_code)
            
            new_chat_btn.click(fn=lambda chats, m: ChatManager.new_chat(chats, m),
                               inputs=[chats_state, model_selector],
                               outputs=[chat_selector, chatbot, chats_state])
            
            chat_selector.change(fn=lambda title, chats: ChatManager.select_chat(title, chats),
                                 inputs=[chat_selector, chats_state],
                                 outputs=[chatbot])
            
            toggle_sidebar_btn.click(fn=lambda visible: (gr.update(visible=not visible), not visible),
                                     inputs=[sidebar_visible_state],
                                     outputs=[left_col, sidebar_visible_state])
            
            settings_btn.click(fn=lambda visible: (gr.update(visible=not visible), not visible),
                               inputs=[settings_visible_state],
                               outputs=[settings_group, settings_visible_state])
            
            save_settings_inputs = [system_prompt_text, classifier_model_dropdown, custom_classifier_prompt_text] + rule_inputs
            save_settings_outputs = [
                system_prompt_state, 
                save_note, 
                classifier_model_state, 
                custom_labels_state, 
                output_models_state, 
                custom_classifier_prompt_state,
            ]
            
            save_settings.click(
                fn=self.save_settings_data,
                inputs=save_settings_inputs,
                outputs=save_settings_outputs
            ).then(time.sleep(3)).then(fn=lambda: gr.update(value=""), outputs=[save_note])
            
            delete_chat_btn.click(fn=lambda sel, chats: ChatManager.delete_chat(sel, chats),
                                  inputs=[chat_selector, chats_state],
                                  outputs=[chats_state, chat_selector, chatbot])

            send_inputs = [
                user_input, 
                chat_selector, 
                chats_state, 
                model_selector, 
                system_prompt_state, 
                classifier_model_state, 
                output_models_state, 
                custom_labels_state,
                custom_classifier_prompt_state,
            ]
            
            # 注意：StreamHandler.input_msg 必须是生成器函数
            send_btn.click(fn=self.stream_handler.input_msg,
                            inputs=send_inputs,
                            # 修正: 直接更新 chatbot 和 user_input
                            outputs=[chatbot, user_input])
            
            user_input.submit(fn=self.stream_handler.input_msg,
                                inputs=send_inputs,
                                # 修正: 直接更新 chatbot 和 user_input
                                outputs=[chatbot, user_input])
            
        return app