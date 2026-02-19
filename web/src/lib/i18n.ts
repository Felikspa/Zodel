export type Locale = "en" | "zh-CN";

export type DictKey =
  | "app.title"
  | "nav.chat"
  | "nav.rag"
  | "nav.flows"
  | "chat.newChat"
  | "chat.mode"
  | "chat.model"
  | "chat.settings"
  | "chat.placeholder"
  | "chat.send"
  | "chat.voice"
  | "rag.title"
  | "flows.title";

const dict: Record<Locale, Record<DictKey, string>> = {
  en: {
    "app.title": "ZODEL",
    "nav.chat": "Chat",
    "nav.rag": "RAG",
    "nav.flows": "Flows",
    "chat.newChat": "New chat",
    "chat.mode": "Mode",
    "chat.model": "Model",
    "chat.settings": "Settings",
    "chat.placeholder": "Message ZODEL…",
    "chat.send": "Send",
    "chat.voice": "Voice",
    "rag.title": "RAG",
    "flows.title": "Flows (Zflow)"
  },
  "zh-CN": {
    "app.title": "ZODEL",
    "nav.chat": "聊天",
    "nav.rag": "知识库",
    "nav.flows": "工作流",
    "chat.newChat": "新对话",
    "chat.mode": "模式",
    "chat.model": "模型",
    "chat.settings": "设置",
    "chat.placeholder": "输入消息…",
    "chat.send": "发送",
    "chat.voice": "语音",
    "rag.title": "RAG 知识库",
    "flows.title": "工作流（Zflow）"
  }
};

export function t(locale: Locale, key: DictKey): string {
  return dict[locale]?.[key] ?? dict.en[key] ?? key;
}

