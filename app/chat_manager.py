"""
聊天会话数据管理模块。

本模块提供了一个 ChatManager 类，其中包含一系列静态方法，
用于管理聊天会话列表的增、删、查等纯数据操作。
会话历史 (history) 采用 Gradio Chatbot 组件所需的元组列表格式:
List[Tuple[str | None, str | None]]
"""

from typing import List, Dict, Tuple
import gradio as gr


class ChatManager:
    """一个纯静态方法的工具类，用于封装所有与聊天会话状态相关的操作。"""

    @staticmethod
    def init_chats(default_model: str) -> List[Dict]:
        """
        初始化聊天会话列表，确保至少包含一个默认会话。

        Args:
            default_model (str): 新会话默认绑定的模型名称。

        Returns:
            List[Dict]: 包含一个初始会话字典的列表。
        """
        return [{"title": "Chat 1", "history": [], "model": default_model}]

    @staticmethod
    def new_chat(
        chats_list: List[Dict], 
        model_choice: str
    ) -> Tuple[gr.update, gr.update, List[Dict]]:
        """
        在会话列表中创建一个新的聊天，并返回用于更新 Gradio UI 的组件。

        Args:
            chats_list (List[Dict]): 当前所有会话的状态列表。
            model_choice (str): 新聊天绑定的模型。

        Returns:
            Tuple[gr.update, gr.update, List[Dict]]: 
                - 用于更新聊天选择器 (Radio) 的 gr.update 对象。
                - 用于清空聊天机器人 (Chatbot) 的 gr.update 对象。
                - 更新后的完整会话列表。
        """
        new_title = f"Chat {len(chats_list) + 1}"
        chats_list.append({"title": new_title, "history": [], "model": model_choice})
        
        all_titles = [c["title"] for c in chats_list]
        
        return gr.update(choices=all_titles, value=new_title), gr.update(value=[]), chats_list

    @staticmethod
    def select_chat(title: str, chats_list: List[Dict]) -> gr.update:
        """
        根据标题在会话列表中查找并返回对应的聊天记录。

        Args:
            title (str): 被选中的会话标题。
            chats_list (List[Dict]): 当前所有会话的状态列表。

        Returns:
            gr.update: 用于更新聊天机器人 (Chatbot) 内容的 gr.update 对象。
        """
        for chat in chats_list:
            if chat["title"] == title:
                return gr.update(value=chat.get("history", []))
        return gr.update(value=[]) # 如果找不到，返回空列表

    @staticmethod
    def delete_chat(
        selected_title: str, 
        chats: List[Dict]
    ) -> Tuple[List[Dict], gr.update, gr.update]:
        """
        删除指定的会话。如果删除后列表为空，则重新创建一个默认会话。

        Args:
            selected_title (str): 希望删除的会话标题。
            chats (List[Dict]): 当前所有会话的状态列表。

        Returns:
            Tuple[List[Dict], gr.update, gr.update]:
                - 更新后的完整会話列表。
                - 用于更新聊天选择器 (Radio) 的 gr.update 对象。
                - 用于更新聊天机器人 (Chatbot) 的 gr.update 对象。
        """
        # 如果只有一个会话，不允许删除，直接返回原状态
        if len(chats) <= 1:
            return chats, gr.update(), gr.update()
            
        new_chats = [c for c in chats if c["title"] != selected_title]
        
        # 确定删除后要显示的会话
        new_selected_title = new_chats[0]["title"]
        new_history = new_chats[0].get("history", [])
        all_titles = [c["title"] for c in new_chats]
        
        return new_chats, gr.update(choices=all_titles, value=new_selected_title), gr.update(value=new_history)