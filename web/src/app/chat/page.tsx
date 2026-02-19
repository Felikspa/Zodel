/* eslint-disable @next/next/no-img-element */
"use client";

import React, { useEffect, useMemo, useRef, useState } from "react";
import { fetchSse, type SseMessage } from "@/lib/sse";
import { t } from "@/lib/i18n";
import { useI18n, useTheme } from "@/app/providers";

type ChatMessage = { role: "user" | "assistant"; content: string; model?: string };

const API_BASE = process.env.NEXT_PUBLIC_ZODEL_API_BASE ?? "http://127.0.0.1:8000";

type ConversationSummary = { id: number; title: string; is_archived?: boolean };

// Local storage types for anonymous users
type LocalConversation = { id: string; title: string; messages: ChatMessage[]; createdAt: string; updatedAt: string; is_archived?: boolean };

export default function ChatPage() {
  const { locale, setLocale } = useI18n();
  const { theme, toggleTheme } = useTheme();

  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");

  const [model, setModel] = useState<string>("Ollama:default-model");
  const [mode, setMode] = useState<"chat" | "auto" | "zflow">("chat");

  const [availableModels, setAvailableModels] = useState<{ id: string; provider: string; name: string }[]>([]);
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelsError, setModelsError] = useState<string | null>(null);

  const [user, setUser] = useState<{ id: number; username: string; locale: string } | null>(null);
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [conversationId, setConversationId] = useState<number | null>(null);

  // Local state for anonymous users
  const [localConversations, setLocalConversations] = useState<LocalConversation[]>([]);
  const [localConversationId, setLocalConversationId] = useState<string | null>(null);

  const [settingsOpen, setSettingsOpen] = useState(false);
  const [systemPrompt, setSystemPrompt] = useState("");
  const [enableMemory, setEnableMemory] = useState(true);

  const [ragEnabled, setRagEnabled] = useState(false);
  const [ragCorpora, setRagCorpora] = useState<{ corpus_id: string; name: string }[]>([]);
  const [ragCorpusId, setRagCorpusId] = useState("");
  const [ragEmbeddingModel, setRagEmbeddingModel] = useState("");
  const [ragTopK, setRagTopK] = useState(5);

  const [autoRoutingAdvanced, setAutoRoutingAdvanced] = useState(false);
  const [classifierModel, setClassifierModel] = useState("");
  const [outputModelsText, setOutputModelsText] = useState("");
  const [labelsText, setLabelsText] = useState("");
  const [customClassifierPrompt, setCustomClassifierPrompt] = useState("");

  const [busy, setBusy] = useState(false);
  const [recording, setRecording] = useState(false);
  const [voiceMode, setVoiceMode] = useState(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<BlobPart[]>([]);
  const endRef = useRef<HTMLDivElement | null>(null);
  const messagesRef = useRef<ChatMessage[]>([]);

  // Keep ref in sync with messages state
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  const historyTurns = useMemo(() => {
    const turns: { user: string; assistant: string }[] = [];
    let lastUser = "";
    for (const m of messages) {
      if (m.role === "user") lastUser = m.content;
      if (m.role === "assistant") {
        turns.push({ user: lastUser, assistant: m.content });
        lastUser = "";
      }
    }
    return turns;
  }, [messages]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  // Load user from localStorage (login page stores token & user)
  useEffect(() => {
    try {
      const raw = localStorage.getItem("zodel_user");
      if (!raw) return;
      const parsed = JSON.parse(raw) as { id?: number; username?: string; locale?: string };
      if (parsed && typeof parsed.id === "number") {
        setUser({ id: parsed.id, username: parsed.username || "User", locale: parsed.locale || "en" });
      }
    } catch {
      // ignore
    }
  }, []);

  // Load local conversations from localStorage for anonymous users
  useEffect(() => {
    if (user) return; // Only use localStorage when not logged in
    try {
      const raw = localStorage.getItem("zodel_local_conversations");
      if (raw) {
        const parsed = JSON.parse(raw) as LocalConversation[];
        setLocalConversations(parsed);
        if (!localConversationId && parsed[0]) {
          setLocalConversationId(parsed[0].id);
        }
      }
    } catch {
      // ignore
    }
  }, [user]);

  // Save local conversations to localStorage
  function saveLocalConversations(convs: LocalConversation[]) {
    try {
      localStorage.setItem("zodel_local_conversations", JSON.stringify(convs));
    } catch {
      // ignore
    }
  }

  // Load conversations for current user
  async function refreshConversations(nextUser = user) {
    if (!nextUser) return;
    try {
      const token = localStorage.getItem("zodel_token");
      const res = await fetch(`${API_BASE}/api/conversations?user_id=${nextUser.id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined
      });
      if (!res.ok) return;
      const data: { conversations?: ConversationSummary[] } = await res.json();
      const list = data.conversations ?? [];
      setConversations(list);
      if (!conversationId && list[0]) {
        setConversationId(list[0].id);
      }
    } catch {
      // soft fail
    }
  }

  useEffect(() => {
    void refreshConversations();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  // Load models and restore last-used model
  useEffect(() => {
    let cancelled = false;
    async function loadModels() {
      setModelsLoading(true);
      setModelsError(null);
      try {
        const res = await fetch(`${API_BASE}/api/models`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: { models?: { id: string; provider: string; name: string }[] } = await res.json();
        if (cancelled) return;
        const list = data.models ?? [];
        setAvailableModels(list);

        const stored = localStorage.getItem("zodel_model");
        if (stored) {
          setModel(stored);
        } else if (list.length > 0) {
          setModel(list[0].id);
        }
      } catch (e) {
        if (cancelled) return;
        const msg = e instanceof Error ? e.message : String(e);
        setModelsError(msg);
      } finally {
        if (!cancelled) {
          setModelsLoading(false);
        }
      }
    }
    void loadModels();
    return () => {
      cancelled = true;
    };
  }, []);

  // Persist selected model
  useEffect(() => {
    if (model) {
      localStorage.setItem("zodel_model", model);
    }
  }, [model]);

  // Load RAG corpora when settings first opened
  useEffect(() => {
    if (!settingsOpen) return;
    if (ragCorpora.length > 0) return;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/rag/corpora`);
        if (!res.ok) return;
        const data: { corpora?: { corpus_id: string; name: string }[] } = await res.json();
        const list = data.corpora ?? [];
        setRagCorpora(list);
        if (!ragCorpusId && list[0]) {
          setRagCorpusId(list[0].corpus_id);
        }
      } catch {
        // ignore
      }
    })();
  }, [settingsOpen, ragCorpusId, ragCorpora.length]);

  async function newConversation() {
    if (busy) return;

    // If user is logged in, use API
    if (user) {
      try {
        setBusy(true);
        const token = localStorage.getItem("zodel_token");
        const res = await fetch(`${API_BASE}/api/conversations`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {})
          },
          body: JSON.stringify({ user_id: user.id, title: "New chat" })
        });
        const data = await res.json();
        if (!res.ok) {
          setMessages((prev) => [
            ...prev,
            { role: "assistant", content: `Failed to create conversation: ${(data.detail ?? "unknown").toString()}` }
          ]);
          return;
        }
        const conv = data.conversation as ConversationSummary | undefined;
        if (conv) {
          setConversations((prev) => [conv, ...prev]);
          setConversationId(conv.id);
          setMessages([]);
        } else {
          await refreshConversations(user);
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setMessages((prev) => [...prev, { role: "assistant", content: `Failed to create conversation: ${msg}` }]);
      } finally {
        setBusy(false);
      }
    } else {
      // Use localStorage for anonymous users
      const now = new Date().toISOString();
      const newConv: LocalConversation = {
        id: `local_${Date.now()}`,
        title: "New chat",
        messages: [],
        createdAt: now,
        updatedAt: now
      };
      setLocalConversations((prev) => {
        const updated = [newConv, ...prev];
        saveLocalConversations(updated);
        return updated;
      });
      setLocalConversationId(newConv.id);
      setMessages([]);
    }
  }

  async function loadConversationMessages(id: number) {
    // Handle local conversations
    if (!user) {
      const localConv = localConversations.find(c => c.id === String(id));
      if (localConv) {
        setMessages(localConv.messages);
      }
      return;
    }

    // Handle remote conversations
    try {
      const token = localStorage.getItem("zodel_token");
      const res = await fetch(`${API_BASE}/api/conversations/${id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined
      });
      if (!res.ok) return;
      const data: {
        messages?: { role: "user" | "assistant"; content: string }[];
      } = await res.json();
      const msgs = (data.messages ?? []).map((m) => ({
        role: m.role,
        content: m.content
      })) as ChatMessage[];
      setMessages(msgs);
    } catch {
      // ignore
    }
  }

  async function send() {
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);

    setMessages((prev) => [...prev, { role: "user", content: text }, { role: "assistant", content: "" }]);

    try {
      if (mode === "zflow") {
        for await (const evt of fetchSse(`${API_BASE}/api/zflow/execute`, {
          method: "POST",
          body: JSON.stringify({ script: text })
        })) {
          if (evt.type === "delta") {
            const text = (evt as { type: "delta"; text: string }).text;
            setMessages((prev) => {
              const next = [...prev];
              for (let i = next.length - 1; i >= 0; i--) {
                if (next[i].role === "assistant") {
                  next[i] = { ...next[i], content: next[i].content + text };
                  break;
                }
              }
              return next;
            });
          } else if (evt.type === "error") {
            setMessages((prev) => {
              const next = [...prev];
              for (let i = next.length - 1; i >= 0; i--) {
                if (next[i].role === "assistant") {
                  next[i] = { ...next[i], content: `Error: ${(evt as any).message}` };
                  break;
                }
              }
              return next;
            });
          }
        }
        return;
      }

      const useMemory = enableMemory && user && conversationId;

      let routing: any = undefined;
      if (mode === "auto") {
        if (autoRoutingAdvanced) {
          const labels = labelsText
            .split(",")
            .map((s) => s.trim())
            .filter(Boolean);
          const outputModels = outputModelsText
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean);
          routing = {
            classifier_model: classifierModel || model,
            labels: labels.length ? labels : ["nonlogical", "logical"],
            output_models: outputModels.length ? outputModels : [model, model],
            custom_classifier_prompt: customClassifierPrompt || ""
          };
        } else {
          routing = {
            classifier_model: model,
            labels: ["nonlogical", "logical"],
            output_models: [model, model],
            custom_classifier_prompt: ""
          };
        }
      }

      const rag =
        ragEnabled && ragCorpusId && ragEmbeddingModel
          ? {
              enabled: true,
              corpus_id: ragCorpusId,
              embedding_model: ragEmbeddingModel,
              top_k: ragTopK
            }
          : undefined;

      const body: any = {
        message: text,
        history: historyTurns,
        mode,
        model: mode === "chat" ? model : undefined,
        routing,
        rag
      };

      if (useMemory) {
        body.user = { id: user!.id, username: user!.username, locale: user!.locale };
        body.conversation_id = conversationId!;
      }

      if (systemPrompt.trim()) {
        body.system_prompt = systemPrompt.trim();
      }

      const token = localStorage.getItem("zodel_token");
      let currentModel = "";
      for await (const evt of fetchSse(`${API_BASE}/api/chat`, {
        method: "POST",
        body: JSON.stringify(body),
        headers: token ? { Authorization: `Bearer ${token}` } : undefined
      })) {
        if (evt.type === "model_info") {
          currentModel = (evt as { type: "model_info"; model: string }).model;
          // Update the last assistant message with the model info
          setMessages((prev) => {
            const next = [...prev];
            for (let i = next.length - 1; i >= 0; i--) {
              if (next[i].role === "assistant") {
                next[i] = { ...next[i], model: currentModel };
                break;
              }
            }
            return next;
          });
        } else if (evt.type === "delta") {
          const text = (evt as { type: "delta"; text: string }).text;
          setMessages((prev) => {
            const next = [...prev];
            for (let i = next.length - 1; i >= 0; i--) {
              if (next[i].role === "assistant") {
                next[i] = { ...next[i], content: next[i].content + text };
                break;
              }
            }
            return next;
          });
        } else if (evt.type === "error") {
          setMessages((prev) => {
            const next = [...prev];
            for (let i = next.length - 1; i >= 0; i--) {
              if (next[i].role === "assistant") {
                next[i] = { ...next[i], content: `Error: ${(evt as any).message}` };
                break;
              }
            }
            return next;
          });
        }
      }

      // Save to localStorage for anonymous users
      if (!user && localConversationId) {
        setLocalConversations((prev) => {
          const updated = prev.map((conv) => {
            if (conv.id === localConversationId) {
              return {
                ...conv,
                messages: messagesRef.current,
                updatedAt: new Date().toISOString()
              };
            }
            return conv;
          });
          saveLocalConversations(updated);
          return updated;
        });
      }

      if (voiceMode) {
        const lastAssistant = [...messages, { role: "user", content: text }]
          .reverse()
          .find((m) => m.role === "assistant")?.content;
        const assistantText = lastAssistant ?? "";
        if (assistantText.trim()) {
          const res = await fetch(`${API_BASE}/api/voice/tts`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: assistantText })
          });
          if (res.ok) {
            const buf = await res.arrayBuffer();
            const blob = new Blob([buf], { type: "audio/mpeg" });
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.onended = () => URL.revokeObjectURL(url);
            void audio.play();
          }
        }
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setMessages((prev) => [...prev, { role: "assistant", content: `Error: ${msg}` }]);
    } finally {
      setBusy(false);
    }
  }

  async function startRecording() {
    if (recording || busy) return;
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const rec = new MediaRecorder(stream);
    recordedChunksRef.current = [];
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunksRef.current.push(e.data);
    };
    rec.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(recordedChunksRef.current, { type: rec.mimeType || "audio/webm" });
      try {
        const fd = new FormData();
        fd.append("audio", blob, "recording.webm");
        const res = await fetch(`${API_BASE}/api/voice/stt`, { method: "POST", body: fd });
        const data = await res.json();
        if (res.ok) {
          const tt = (data.text ?? "").toString();
          setInput(tt);
          if (voiceMode && tt.trim()) {
            setTimeout(() => {
              void send();
            }, 0);
          }
        } else setInput(`(STT error) ${(data.detail ?? "unknown").toString()}`);
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        setInput(`(STT error) ${msg}`);
      } finally {
        setRecording(false);
      }
    };
    mediaRecorderRef.current = rec;
    setRecording(true);
    rec.start();
  }

  function stopRecording() {
    if (!recording) return;
    mediaRecorderRef.current?.stop();
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  }

  const composerPlaceholder = mode === "zflow" ? "Enter your Zflow code..." : t(locale, "chat.placeholder");

  return (
    <div className="h-screen w-full bg-neutral-950 text-neutral-100">
      <div className="flex h-full">
        {/* Sidebar */}
        <aside
          className={[
            "border-r border-neutral-800 bg-neutral-950/60 backdrop-blur",
            sidebarOpen ? "w-48" : "w-0 overflow-hidden"
          ].join(" ")}
        >
          <div className="flex h-full flex-col">
            <div className="flex items-center justify-between p-3">
              <div className="text-lg font-semibold tracking-wide">{t(locale, "app.title")}</div>
              <button
                className="rounded-md border border-neutral-800 px-2 py-1 text-sm hover:bg-neutral-900"
                onClick={() => setSidebarOpen(false)}
              >
                Hide
              </button>
            </div>
            <div className="px-3 pb-3 space-y-2">
              <button
                className="w-full rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-900 disabled:opacity-60"
                onClick={() => void newConversation()}
                disabled={busy}
              >
                {t(locale, "chat.newChat")}
              </button>
              <button
                className="w-full rounded-md border border-neutral-800 px-3 py-2 text-sm hover:bg-neutral-900"
                onClick={() => window.location.href = "/knowledge"}
              >
                Knowledge
              </button>
              <button
                className="w-full rounded-md border border-neutral-800 px-3 py-2 text-sm hover:bg-neutral-900"
                onClick={() => window.location.href = "/agents"}
              >
                Agents
              </button>
            </div>
            <div className="flex-1 overflow-auto px-2">
              <div className="px-2 py-2 text-xs text-neutral-400">
                {user ? "Conversations" : "Local Conversations"}
              </div>
              <div className="space-y-1 px-2 pb-6">
                {!user && localConversations.length === 0 && (
                  <div className="text-xs text-neutral-500">No conversations yet.</div>
                )}
                {user && conversations.length === 0 && (
                  <div className="text-xs text-neutral-500">No conversations yet.</div>
                )}
                {/* Show remote conversations when logged in */}
                {user && conversations.map((c) => (
                  <button
                    key={c.id}
                    className={[
                      "w-full rounded-md px-3 py-2 text-left text-sm",
                      c.id === conversationId ? "bg-neutral-900 border border-neutral-700" : "hover:bg-neutral-900"
                    ].join(" ")}
                    onClick={() => {
                      if (busy) return;
                      setConversationId(c.id);
                      void loadConversationMessages(c.id);
                    }}
                    disabled={busy}
                  >
                    <div className="truncate">{c.title}</div>
                  </button>
                ))}
                {/* Show local conversations when not logged in */}
                {!user && localConversations.map((c) => (
                  <button
                    key={c.id}
                    className={[
                      "w-full rounded-md px-3 py-2 text-left text-sm",
                      c.id === localConversationId ? "bg-neutral-900 border border-neutral-700" : "hover:bg-neutral-900"
                    ].join(" ")}
                    onClick={() => {
                      if (busy) return;
                      setLocalConversationId(c.id);
                      void loadConversationMessages(Number(c.id));
                    }}
                    disabled={busy}
                  >
                    <div className="truncate">{c.title}</div>
                  </button>
                ))}
              </div>
            </div>
            <div className="border-t border-neutral-800 p-3 text-xs text-neutral-500">
              API: <span className="text-neutral-300">{API_BASE}</span>
            </div>
          </div>
        </aside>

        {/* Main */}
        <main className="relative flex flex-1 flex-col">
          {/* Top bar */}
          <div className="flex items-center gap-2 border-b border-neutral-800 bg-neutral-950/60 px-3 py-2 backdrop-blur">
            <button
              className="rounded-md border border-neutral-800 px-2 py-1 text-sm hover:bg-neutral-900"
              onClick={() => setSidebarOpen((v) => !v)}
            >
              {sidebarOpen ? "☰" : "☰"}
            </button>
            <div className="flex items-center gap-2">
              <label className="text-xs text-neutral-400">{t(locale, "chat.mode")}</label>
              <select
                className="rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1 text-sm"
                value={mode}
                onChange={(e) => setMode(e.target.value as "chat" | "auto" | "zflow")}
              >
                <option value="chat">Chat</option>
                <option value="auto">Auto Route</option>
                <option value="zflow">Zflow</option>
              </select>
            </div>
            <div className="flex items-center gap-2">
              <label className="text-xs text-neutral-400">{t(locale, "chat.voice")}</label>
              <button
                className={[
                  "rounded-md border border-neutral-800 px-2 py-1 text-sm hover:bg-neutral-900",
                  voiceMode ? "bg-neutral-900" : ""
                ].join(" ")}
                onClick={() => setVoiceMode((v) => !v)}
              >
                {voiceMode ? "On" : "Off"}
              </button>
            </div>
            {mode !== "zflow" && (
              <div className="flex items-center gap-2">
                <label className="text-xs text-neutral-400">{t(locale, "chat.model")}</label>
                {availableModels.length > 0 ? (
                  <select
                    className="w-72 rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1 text-sm"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                  >
                    {availableModels.map((m) => (
                      <option key={m.id} value={m.id}>
                        {m.provider}: {m.name}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    className="w-72 rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1 text-sm"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="Ollama:llama3.1"
                  />
                )}
                {modelsLoading ? (
                  <span className="text-[10px] text-neutral-500">Loading…</span>
                ) : modelsError ? (
                  <span className="text-[10px] text-red-500">Models error</span>
                ) : null}
              </div>
            )}
            <div className="ml-auto flex items-center gap-2">
              <button
                className="rounded-md border border-neutral-800 px-2 py-1 text-sm hover:bg-neutral-900"
                onClick={toggleTheme}
                title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
              >
                {theme === "dark" ? "Light" : "Dark"}
              </button>
              <select
                className="rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1 text-sm"
                value={locale}
                onChange={(e) => setLocale(e.target.value as any)}
                title="Language"
              >
                <option value="en">EN</option>
                <option value="zh-CN">中文</option>
              </select>
              <button
                className="rounded-md border border-neutral-800 px-2 py-1 text-sm hover:bg-neutral-900"
                onClick={() => setSettingsOpen((v) => !v)}
              >
                {t(locale, "chat.settings")}
              </button>
            </div>
          </div>

          {/* Settings panel */}
          {settingsOpen && (
            <div className="absolute right-4 top-14 z-20 w-96 rounded-xl border border-neutral-800 bg-neutral-950 p-4 text-xs shadow-xl">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">Settings</div>
                <button
                  className="rounded-md border border-neutral-800 px-2 py-1 text-[11px] hover:bg-neutral-900"
                  onClick={() => setSettingsOpen(false)}
                >
                  Close
                </button>
              </div>

              <div className="mt-3 space-y-3">
                <div>
                  <div className="mb-1 font-medium">System prompt</div>
                  <textarea
                    className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-xs outline-none focus:border-neutral-600"
                    rows={3}
                    value={systemPrompt}
                    onChange={(e) => setSystemPrompt(e.target.value)}
                    placeholder="Optional system-level instructions for the assistant."
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium">Memory</div>
                    <div className="text-[11px] text-neutral-500">
                      Use server-side conversations &amp; summaries.
                    </div>
                  </div>
                  <button
                    className={[
                      "rounded-md border border-neutral-800 px-2 py-1 text-[11px] hover:bg-neutral-900",
                      enableMemory ? "bg-neutral-900" : ""
                    ].join(" ")}
                    onClick={() => setEnableMemory((v) => !v)}
                  >
                    {enableMemory ? "On" : "Off"}
                  </button>
                </div>

                <div className="border-t border-neutral-800 pt-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">RAG</div>
                      <div className="text-[11px] text-neutral-500">
                        Retrieve from knowledge corpora before answering.
                      </div>
                    </div>
                    <button
                      className={[
                        "rounded-md border border-neutral-800 px-2 py-1 text-[11px] hover:bg-neutral-900",
                        ragEnabled ? "bg-neutral-900" : ""
                      ].join(" ")}
                      onClick={() => setRagEnabled((v) => !v)}
                    >
                      {ragEnabled ? "On" : "Off"}
                    </button>
                  </div>

                  {ragEnabled && (
                    <div className="mt-2 space-y-2">
                      <div>
                        <div className="mb-1">Corpus</div>
                        <select
                          className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1 text-xs"
                          value={ragCorpusId}
                          onChange={(e) => setRagCorpusId(e.target.value)}
                        >
                          <option value="">Select corpus…</option>
                          {ragCorpora.map((c) => (
                            <option key={c.corpus_id} value={c.corpus_id}>
                              {c.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <div className="mb-1">Embedding model</div>
                        <input
                          className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1 text-xs"
                          value={ragEmbeddingModel}
                          onChange={(e) => setRagEmbeddingModel(e.target.value)}
                          placeholder="Cloud:text-embedding-3-small"
                        />
                      </div>
                      <div>
                        <div className="mb-1">Top K</div>
                        <input
                          type="number"
                          min={1}
                          max={20}
                          className="w-20 rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1 text-xs"
                          value={ragTopK}
                          onChange={(e) => setRagTopK(Number(e.target.value) || 5)}
                        />
                      </div>
                    </div>
                  )}
                </div>

                <div className="border-t border-neutral-800 pt-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-medium">Auto routing</div>
                      <div className="text-[11px] text-neutral-500">
                        Advanced classifier / labels / output models.
                      </div>
                    </div>
                    <button
                      className={[
                        "rounded-md border border-neutral-800 px-2 py-1 text-[11px] hover:bg-neutral-900",
                        autoRoutingAdvanced ? "bg-neutral-900" : ""
                      ].join(" ")}
                      onClick={() => setAutoRoutingAdvanced((v) => !v)}
                    >
                      {autoRoutingAdvanced ? "Advanced" : "Basic"}
                    </button>
                  </div>

                  {autoRoutingAdvanced && (
                    <div className="mt-2 space-y-2">
                      <div>
                        <div className="mb-1">Classifier model</div>
                        <input
                          className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1 text-xs"
                          value={classifierModel}
                          onChange={(e) => setClassifierModel(e.target.value)}
                          placeholder="OpenAI:gpt-4o-mini"
                        />
                      </div>
                      <div>
                        <div className="mb-1">Labels (comma separated)</div>
                        <input
                          className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-1 text-xs"
                          value={labelsText}
                          onChange={(e) => setLabelsText(e.target.value)}
                          placeholder="nonlogical, logical"
                        />
                      </div>
                      <div>
                        <div className="mb-1">Output models (one per line)</div>
                        <textarea
                          className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-xs outline-none focus:border-neutral-600"
                          rows={2}
                          value={outputModelsText}
                          onChange={(e) => setOutputModelsText(e.target.value)}
                          placeholder={"OpenAI:gpt-4o\nOpenAI:gpt-4o-mini"}
                        />
                      </div>
                      <div>
                        <div className="mb-1">Custom classifier prompt</div>
                        <textarea
                          className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-xs outline-none focus:border-neutral-600"
                          rows={2}
                          value={customClassifierPrompt}
                          onChange={(e) => setCustomClassifierPrompt(e.target.value)}
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Messages */}
          <div className="flex-1 overflow-auto px-4 py-6">
            <div className="mx-auto flex w-full max-w-3xl flex-col gap-4">
              {messages.length === 0 ? (
                <div className="rounded-xl border border-neutral-800 bg-neutral-950 p-6">
                  <div className="text-xl font-semibold">What can I help with?</div>
                  <div className="mt-2 text-sm text-neutral-400">
                    This is the new ZODEL chat UI (GPT-like layout). Connect the API and start chatting.
                  </div>
                </div>
              ) : null}
              {messages.map((m, idx) => (
                <div
                  key={idx}
                  className={["flex", m.role === "user" ? "justify-end" : "justify-start"].join(" ")}
                >
                  <div>
                    <div
                      className={[
                        "max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed",
                        m.role === "user"
                          ? "bg-neutral-100 text-neutral-950"
                          : "bg-neutral-900 text-neutral-100 border border-neutral-800"
                      ].join(" ")}
                    >
                      {m.content || (m.role === "assistant" && busy && idx === messages.length - 1 ? "…" : "")}
                    </div>
                    {m.role === "assistant" && m.model && (
                      <div className="mt-1 px-4 text-xs text-neutral-500">
                        Model: {m.model}
                      </div>
                    )}
                  </div>
                </div>
              ))}
              <div ref={endRef} />
            </div>
          </div>

          {/* Composer */}
          <div className="border-t border-neutral-800 bg-neutral-950/60 px-4 py-4 backdrop-blur">
            <div className="mx-auto flex w-full max-w-3xl gap-3">
              <button
                className={[
                  "h-[52px] w-[52px] rounded-xl border border-neutral-800 text-sm hover:bg-neutral-900",
                  recording ? "bg-red-950 border-red-800" : ""
                ].join(" ")}
                onClick={() => (recording ? stopRecording() : void startRecording())}
                disabled={busy}
                title={recording ? "Stop recording" : "Start recording"}
              >
                {recording ? "■" : "🎙"}
              </button>
              <textarea
                className="min-h-[52px] flex-1 resize-none rounded-xl border border-neutral-800 bg-neutral-950 px-4 py-3 text-sm outline-none focus:border-neutral-600"
                placeholder={composerPlaceholder}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                disabled={busy}
                rows={mode === "zflow" ? 6 : 3}
              />
              <button
                className="h-[52px] w-24 rounded-xl bg-neutral-100 text-sm font-medium text-neutral-900 disabled:opacity-50"
                onClick={() => void send()}
                disabled={busy || !input.trim()}
              >
                {t(locale, "chat.send")}
              </button>
            </div>
            <div className="mx-auto mt-2 w-full max-w-3xl text-[11px] text-neutral-500">
              Enter to send, Shift+Enter for newline.
            </div>
          </div>
        </main>
      </div>
    </div>
  );
}

