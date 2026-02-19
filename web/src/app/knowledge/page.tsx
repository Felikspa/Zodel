"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { t } from "@/lib/i18n";
import { useI18n } from "@/app/providers";

const API_BASE = process.env.NEXT_PUBLIC_ZODEL_API_BASE ?? "http://127.0.0.1:8000";

type KnowledgeBase = {
  id: number;
  name: string;
  description: string;
  embedding_model: string;
  document_count?: number;
  created_at: string;
  updated_at: string;
};

type KnowledgeDocument = {
  id: number;
  source_name: string;
  file_type: string;
  chunk_count: number;
  created_at: string;
};

  // Local storage types for anonymous users
type LocalKnowledgeBase = {
  id: string;
  name: string;
  description: string;
  embedding_model: string;
  documents: LocalDocument[];
  created_at: string;
  updated_at: string;
};

type LocalDocument = {
  id: string;
  source_name: string;
  file_type: string;
  chunk_count: number;
  text: string;
  created_at: string;
};

export default function KnowledgePage() {
  const { locale } = useI18n();
  const router = useRouter();

  const [user, setUser] = useState<{ id: number; username: string; locale: string } | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [localKnowledgeBases, setLocalKnowledgeBases] = useState<LocalKnowledgeBase[]>([]);
  const [selectedKB, setSelectedKB] = useState<KnowledgeBase | LocalKnowledgeBase | null>(null);
  const [documents, setDocuments] = useState<KnowledgeDocument[]>([]);
  const [localDocuments, setLocalDocuments] = useState<LocalDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form states
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newKBName, setNewKBName] = useState("");
  const [newKBDescription, setNewKBDescription] = useState("");
  const [newKBEmbeddingModel, setNewKBEmbeddingModel] = useState("Cloud:text-embedding-3-small");

  const [showAddDocForm, setShowAddDocForm] = useState(false);
  const [docSourceName, setDocSourceName] = useState("");
  const [docText, setDocText] = useState("");

  // Load user from localStorage (optional - works without login)
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

  // Load local knowledge bases from localStorage
  useEffect(() => {
    if (user) return; // Use server-side when logged in
    try {
      const raw = localStorage.getItem("zodel_local_knowledge_bases");
      if (raw) {
        const parsed = JSON.parse(raw) as LocalKnowledgeBase[];
        setLocalKnowledgeBases(parsed);
      }
    } catch {
      // ignore
    }
  }, [user]);

  // Save local knowledge bases to localStorage
  function saveLocalKnowledgeBases(kbs: LocalKnowledgeBase[]) {
    try {
      localStorage.setItem("zodel_local_knowledge_bases", JSON.stringify(kbs));
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (user) {
      loadKnowledgeBases();
    }
  }, [user]);

  // Show local knowledge bases when not logged in
  useEffect(() => {
    if (!user && localKnowledgeBases.length > 0) {
      // Set the first one as selected if none selected
      if (!selectedKB) {
        setSelectedKB(localKnowledgeBases[0]);
        setLocalDocuments(localKnowledgeBases[0].documents || []);
      }
    }
  }, [localKnowledgeBases, user, selectedKB]);

  async function loadKnowledgeBases() {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("zodel_token");
      const res = await fetch(`${API_BASE}/api/knowledge?user_id=${user.id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined
      });
      if (!res.ok) throw new Error("Failed to load knowledge bases");
      const data = await res.json();
      setKnowledgeBases(data.knowledge_bases || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  async function loadDocuments(kbId: number) {
    if (!user) return;
    try {
      const token = localStorage.getItem("zodel_token");
      const res = await fetch(`${API_BASE}/api/knowledge/${kbId}/documents`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined
      });
      if (!res.ok) throw new Error("Failed to load documents");
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function createKnowledgeBase() {
    if (!newKBName.trim()) return;

    // If user is logged in, use API
    if (user) {
      setLoading(true);
      try {
        const token = localStorage.getItem("zodel_token");
        const res = await fetch(`${API_BASE}/api/knowledge`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {})
          },
          body: JSON.stringify({
            user_id: user.id,
            name: newKBName.trim(),
            description: newKBDescription.trim(),
            embedding_model: newKBEmbeddingModel
          })
        });
        if (!res.ok) throw new Error("Failed to create knowledge base");
        await loadKnowledgeBases();
        setShowCreateForm(false);
        setNewKBName("");
        setNewKBDescription("");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    } else {
      // Use localStorage for anonymous users
      const now = new Date().toISOString();
      const newKB: LocalKnowledgeBase = {
        id: `local_${Date.now()}`,
        name: newKBName.trim(),
        description: newKBDescription.trim(),
        embedding_model: newKBEmbeddingModel,
        documents: [],
        created_at: now,
        updated_at: now
      };
      setLocalKnowledgeBases((prev) => {
        const updated = [newKB, ...prev];
        saveLocalKnowledgeBases(updated);
        return updated;
      });
      setSelectedKB(newKB);
      setLocalDocuments([]);
      setShowCreateForm(false);
      setNewKBName("");
      setNewKBDescription("");
    }
  }

  async function deleteKnowledgeBase(kbId: number | string) {
    if (!confirm("Are you sure you want to delete this knowledge base?")) return;

    // If user is logged in, use API
    if (user && typeof kbId === "number") {
      setLoading(true);
      try {
        const token = localStorage.getItem("zodel_token");
        const res = await fetch(`${API_BASE}/api/knowledge/${kbId}`, {
          method: "DELETE",
          headers: token ? { Authorization: `Bearer ${token}` } : undefined
        });
        if (!res.ok) throw new Error("Failed to delete knowledge base");
        await loadKnowledgeBases();
        if (selectedKB && "id" in selectedKB && selectedKB.id === kbId) {
          setSelectedKB(null);
          setDocuments([]);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    } else if (!user && typeof kbId === "string") {
      // Use localStorage for anonymous users
      setLocalKnowledgeBases((prev) => {
        const updated = prev.filter(kb => kb.id !== kbId);
        saveLocalKnowledgeBases(updated);
        return updated;
      });
      if (selectedKB && "id" in selectedKB && selectedKB.id === kbId) {
        setSelectedKB(null);
        setLocalDocuments([]);
      }
    }
  }

  async function addDocument() {
    if (!selectedKB || !docText.trim() || !docSourceName.trim()) return;

    // If user is logged in, use API
    if (user && "id" in selectedKB && typeof selectedKB.id === "number") {
      setLoading(true);
      try {
        const token = localStorage.getItem("zodel_token");
        const res = await fetch(`${API_BASE}/api/knowledge/${selectedKB.id}/documents`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {})
          },
          body: JSON.stringify({
            source_name: docSourceName.trim(),
            text: docText,
            embedding_model: selectedKB.embedding_model || newKBEmbeddingModel
          })
        });
        if (!res.ok) throw new Error("Failed to add document");
        await loadDocuments(selectedKB.id);
        setShowAddDocForm(false);
        setDocSourceName("");
        setDocText("");
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    } else if (!user && "id" in selectedKB && typeof selectedKB.id === "string") {
      // Use localStorage for anonymous users
      const now = new Date().toISOString();
      const newDoc: LocalDocument = {
        id: `doc_${Date.now()}`,
        source_name: docSourceName.trim(),
        file_type: "text",
        chunk_count: Math.ceil(docText.length / 500),
        text: docText,
        created_at: now
      };

      setLocalKnowledgeBases((prev) => {
        const updated = prev.map(kb => {
          if (kb.id === selectedKB.id) {
            return {
              ...kb,
              documents: [...kb.documents, newDoc],
              updated_at: now
            };
          }
          return kb;
        });
        saveLocalKnowledgeBases(updated);
        return updated;
      });

      setLocalDocuments(prev => [...prev, newDoc]);
      setShowAddDocForm(false);
      setDocSourceName("");
      setDocText("");
    }
  }

  function selectKB(kb: KnowledgeBase | LocalKnowledgeBase) {
    setSelectedKB(kb);
    if (user && "id" in kb && typeof kb.id === "number") {
      loadDocuments(kb.id);
    } else if (!user && "id" in kb && typeof kb.id === "string") {
      setLocalDocuments(kb.documents || []);
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <div className="flex">
        {/* Sidebar */}
        <div className="w-64 border-r border-neutral-800 bg-neutral-950/60 p-4">
          <div className="flex items-center justify-between mb-4">
            <h1 className="text-xl font-semibold">Knowledge</h1>
            <button
              onClick={() => router.push("/chat")}
              className="text-sm text-neutral-400 hover:text-neutral-200"
            >
              Back
            </button>
          </div>

          <button
            onClick={() => setShowCreateForm(true)}
            className="w-full bg-neutral-100 text-neutral-900 py-2 px-4 rounded-md font-medium mb-4"
          >
            + New Knowledge Base
          </button>

          {loading && <div className="text-sm text-neutral-400">Loading...</div>}

          {/* Show server-side knowledge bases when logged in */}
          {user && knowledgeBases.length > 0 && (
            <div className="space-y-2 mb-4">
              <div className="text-xs text-neutral-500 uppercase tracking-wide px-2">Server Knowledge Bases</div>
              {knowledgeBases.map((kb) => (
                <div
                  key={kb.id}
                  className={`p-3 rounded-md cursor-pointer ${
                    selectedKB && "id" in selectedKB && selectedKB.id === kb.id
                      ? "bg-neutral-900 border border-neutral-700"
                      : "hover:bg-neutral-900 border border-transparent"
                  }`}
                  onClick={() => selectKB(kb)}
                >
                  <div className="font-medium truncate">{kb.name}</div>
                  <div className="text-xs text-neutral-400 truncate">{kb.description || "No description"}</div>
                </div>
              ))}
            </div>
          )}

          {/* Show local knowledge bases when not logged in */}
          {!user && localKnowledgeBases.length > 0 && (
            <div className="space-y-2 mb-4">
              <div className="text-xs text-neutral-500 uppercase tracking-wide px-2">Local Knowledge Bases</div>
              {localKnowledgeBases.map((kb) => (
                <div
                  key={kb.id}
                  className={`p-3 rounded-md cursor-pointer ${
                    selectedKB && "id" in selectedKB && selectedKB.id === kb.id
                      ? "bg-neutral-900 border border-neutral-700"
                      : "hover:bg-neutral-900 border border-transparent"
                  }`}
                  onClick={() => selectKB(kb)}
                >
                  <div className="font-medium truncate">{kb.name}</div>
                  <div className="text-xs text-neutral-400 truncate">{kb.description || "No description"}</div>
                </div>
              ))}
            </div>
          )}

          {((user && knowledgeBases.length === 0) || (!user && localKnowledgeBases.length === 0)) && !loading && (
            <div className="text-sm text-neutral-500 mt-4">
              No knowledge bases yet. Create one to get started.
            </div>
          )}
        </div>

        {/* Main Content */}
        <div className="flex-1 p-6">
          {showCreateForm && (
            <div className="mb-6 p-4 border border-neutral-800 rounded-lg bg-neutral-900/50">
              <h2 className="text-lg font-medium mb-4">Create Knowledge Base</h2>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-neutral-400 mb-1">Name</label>
                  <input
                    type="text"
                    value={newKBName}
                    onChange={(e) => setNewKBName(e.target.value)}
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    placeholder="My Knowledge Base"
                  />
                </div>
                <div>
                  <label className="block text-sm text-neutral-400 mb-1">Description</label>
                  <textarea
                    value={newKBDescription}
                    onChange={(e) => setNewKBDescription(e.target.value)}
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    rows={2}
                    placeholder="Optional description"
                  />
                </div>
                <div>
                  <label className="block text-sm text-neutral-400 mb-1">Embedding Model</label>
                  <input
                    type="text"
                    value={newKBEmbeddingModel}
                    onChange={(e) => setNewKBEmbeddingModel(e.target.value)}
                    className="w-full bg-neutral-950 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    placeholder="Cloud:text-embedding-3-small"
                  />
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={createKnowledgeBase}
                    disabled={loading || !newKBName.trim()}
                    className="bg-neutral-100 text-neutral-900 py-2 px-4 rounded-md text-sm font-medium disabled:opacity-50"
                  >
                    Create
                  </button>
                  <button
                    onClick={() => setShowCreateForm(false)}
                    className="border border-neutral-800 py-2 px-4 rounded-md text-sm hover:bg-neutral-900"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          )}

          {selectedKB ? (
            <div>
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h2 className="text-2xl font-semibold">{selectedKB.name}</h2>
                  <p className="text-sm text-neutral-400">{selectedKB.description}</p>
                </div>
                <button
                  onClick={() => deleteKnowledgeBase(selectedKB.id)}
                  className="text-red-400 hover:text-red-300 text-sm"
                >
                  Delete
                </button>
              </div>

              <div className="flex gap-4 mb-6">
                <button
                  onClick={() => setShowAddDocForm(true)}
                  className="bg-neutral-100 text-neutral-900 py-2 px-4 rounded-md text-sm font-medium"
                >
                  + Add Document
                </button>
              </div>

              {showAddDocForm && (
                <div className="mb-6 p-4 border border-neutral-800 rounded-lg bg-neutral-900/50">
                  <h3 className="text-lg font-medium mb-4">Add Document</h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-neutral-400 mb-1">Source Name</label>
                      <input
                        type="text"
                        value={docSourceName}
                        onChange={(e) => setDocSourceName(e.target.value)}
                        className="w-full bg-neutral-950 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                        placeholder="document.txt"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-neutral-400 mb-1">Content</label>
                      <textarea
                        value={docText}
                        onChange={(e) => setDocText(e.target.value)}
                        className="w-full bg-neutral-950 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                        rows={10}
                        placeholder="Paste your text content here..."
                      />
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={addDocument}
                        disabled={loading || !docText.trim() || !docSourceName.trim()}
                        className="bg-neutral-100 text-neutral-900 py-2 px-4 rounded-md text-sm font-medium disabled:opacity-50"
                      >
                        Add Document
                      </button>
                      <button
                        onClick={() => setShowAddDocForm(false)}
                        className="border border-neutral-800 py-2 px-4 rounded-md text-sm hover:bg-neutral-900"
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                </div>
              )}

              <div>
                <h3 className="text-lg font-medium mb-4">Documents</h3>
                {/* Show server-side documents when logged in */}
                {user && documents.length === 0 ? (
                  <div className="text-neutral-500">No documents yet. Add one to get started.</div>
                ) : user && documents.length > 0 ? (
                  <div className="space-y-2">
                    {documents.map((doc) => (
                      <div
                        key={doc.id}
                        className="p-3 border border-neutral-800 rounded-md bg-neutral-900/30"
                      >
                        <div className="font-medium">{doc.source_name}</div>
                        <div className="text-xs text-neutral-400">
                          {doc.chunk_count} chunks | {doc.file_type}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}

                {/* Show local documents when not logged in */}
                {!user && localDocuments.length === 0 ? (
                  <div className="text-neutral-500">No documents yet. Add one to get started.</div>
                ) : !user && localDocuments.length > 0 ? (
                  <div className="space-y-2">
                    {localDocuments.map((doc) => (
                      <div
                        key={doc.id}
                        className="p-3 border border-neutral-800 rounded-md bg-neutral-900/30"
                      >
                        <div className="font-medium">{doc.source_name}</div>
                        <div className="text-xs text-neutral-400">
                          {doc.chunk_count} chunks | {doc.file_type}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="text-center text-neutral-500 mt-20">
              Select a knowledge base to view details
            </div>
          )}

          {error && (
            <div className="mt-4 p-3 bg-red-900/30 border border-red-800 rounded-md text-red-300 text-sm">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
