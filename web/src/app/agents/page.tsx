"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { t } from "@/lib/i18n";
import { useI18n } from "@/app/providers";

const API_BASE = process.env.NEXT_PUBLIC_ZODEL_API_BASE ?? "http://127.0.0.1:8000";

// Local storage types for anonymous users
type LocalAgent = {
  id: string;
  name: string;
  description: string;
  model: string;
  system_prompt: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  presence_penalty: number;
  frequency_penalty: number;
  is_default: boolean;
  created_at: string;
  updated_at: string;
};

type Agent = {
  id: number;
  name: string;
  description: string;
  model: string;
  system_prompt: string;
  temperature: number;
  max_tokens: number;
  top_p: number;
  presence_penalty: number;
  frequency_penalty: number;
  is_default: boolean;
  created_at: string;
  updated_at: string;
};

export default function AgentsPage() {
  const { locale } = useI18n();
  const router = useRouter();

  const [user, setUser] = useState<{ id: number; username: string; locale: string } | null>(null);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [localAgents, setLocalAgents] = useState<LocalAgent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form states
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [editingAgent, setEditingAgent] = useState<Agent | LocalAgent | null>(null);
  const [formData, setFormData] = useState({
    name: "",
    description: "",
    model: "",
    system_prompt: "",
    temperature: 0.7,
    max_tokens: 4096,
    top_p: 1.0,
    presence_penalty: 0.0,
    frequency_penalty: 0.0,
    is_default: false
  });

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

  // Load local agents from localStorage
  useEffect(() => {
    if (user) return; // Use server-side when logged in
    try {
      const raw = localStorage.getItem("zodel_local_agents");
      if (raw) {
        const parsed = JSON.parse(raw) as LocalAgent[];
        setLocalAgents(parsed);
      }
    } catch {
      // ignore
    }
  }, [user]);

  // Save local agents to localStorage
  function saveLocalAgents(agentList: LocalAgent[]) {
    try {
      localStorage.setItem("zodel_local_agents", JSON.stringify(agentList));
    } catch {
      // ignore
    }
  }

  useEffect(() => {
    if (user) {
      loadAgents();
    }
  }, [user]);

  async function loadAgents() {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const token = localStorage.getItem("zodel_token");
      const res = await fetch(`${API_BASE}/api/agents?user_id=${user.id}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : undefined
      });
      if (!res.ok) throw new Error("Failed to load agents");
      const data = await res.json();
      setAgents(data.agents || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  function openCreateForm() {
    setFormData({
      name: "",
      description: "",
      model: "",
      system_prompt: "",
      temperature: 0.7,
      max_tokens: 4096,
      top_p: 1.0,
      presence_penalty: 0.0,
      frequency_penalty: 0.0,
      is_default: false
    });
    setEditingAgent(null);
    setShowCreateForm(true);
  }

  function openEditForm(agent: Agent | LocalAgent) {
    setFormData({
      name: agent.name,
      description: agent.description,
      model: agent.model,
      system_prompt: agent.system_prompt,
      temperature: agent.temperature,
      max_tokens: agent.max_tokens,
      top_p: agent.top_p,
      presence_penalty: agent.presence_penalty,
      frequency_penalty: agent.frequency_penalty,
      is_default: agent.is_default
    });
    setEditingAgent(agent);
    setShowCreateForm(true);
  }

  async function saveAgent() {
    if (!formData.name.trim()) return;

    // If user is logged in, use API
    if (user) {
      setLoading(true);
      try {
        const token = localStorage.getItem("zodel_token");
        const body = {
          user_id: user.id,
          ...formData,
          name: formData.name.trim(),
          description: formData.description.trim()
        };

        let res;
        if (editingAgent && "id" in editingAgent && typeof editingAgent.id === "number") {
          res = await fetch(`${API_BASE}/api/agents/${editingAgent.id}`, {
            method: "PUT",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {})
            },
            body: JSON.stringify(body)
          });
        } else {
          res = await fetch(`${API_BASE}/api/agents`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {})
            },
            body: JSON.stringify(body)
          });
        }

        if (!res.ok) throw new Error(editingAgent ? "Failed to update agent" : "Failed to create agent");
        await loadAgents();
        setShowCreateForm(false);
        setEditingAgent(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    } else {
      // Use localStorage for anonymous users
      const now = new Date().toISOString();

      if (editingAgent && "id" in editingAgent && typeof editingAgent.id === "string") {
        // Update existing local agent
        setLocalAgents((prev) => {
          const updated = prev.map(a =>
            a.id === editingAgent.id
              ? {
                  ...a,
                  name: formData.name.trim(),
                  description: formData.description.trim(),
                  model: formData.model,
                  system_prompt: formData.system_prompt,
                  temperature: formData.temperature,
                  max_tokens: formData.max_tokens,
                  top_p: formData.top_p,
                  presence_penalty: formData.presence_penalty,
                  frequency_penalty: formData.frequency_penalty,
                  is_default: formData.is_default,
                  updated_at: now
                }
              : a
          );
          saveLocalAgents(updated);
          return updated;
        });
      } else {
        // Create new local agent
        const newAgent: LocalAgent = {
          id: `local_${Date.now()}`,
          name: formData.name.trim(),
          description: formData.description.trim(),
          model: formData.model,
          system_prompt: formData.system_prompt,
          temperature: formData.temperature,
          max_tokens: formData.max_tokens,
          top_p: formData.top_p,
          presence_penalty: formData.presence_penalty,
          frequency_penalty: formData.frequency_penalty,
          is_default: formData.is_default,
          created_at: now,
          updated_at: now
        };
        setLocalAgents((prev) => {
          const updated = [...prev, newAgent];
          saveLocalAgents(updated);
          return updated;
        });
      }
      setShowCreateForm(false);
      setEditingAgent(null);
    }
  }

  async function deleteAgent(agentId: number | string) {
    if (!confirm("Are you sure you want to delete this agent?")) return;

    // If user is logged in, use API
    if (user && typeof agentId === "number") {
      setLoading(true);
      try {
        const token = localStorage.getItem("zodel_token");
        const res = await fetch(`${API_BASE}/api/agents/${agentId}`, {
          method: "DELETE",
          headers: token ? { Authorization: `Bearer ${token}` } : undefined
        });
        if (!res.ok) throw new Error("Failed to delete agent");
        await loadAgents();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    } else if (!user && typeof agentId === "string") {
      // Use localStorage for anonymous users
      setLocalAgents((prev) => {
        const updated = prev.filter(a => a.id !== agentId);
        saveLocalAgents(updated);
        return updated;
      });
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <div className="max-w-6xl mx-auto p-6">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold">Agents</h1>
            <p className="text-sm text-neutral-400">Create and manage your custom AI agents</p>
          </div>
          <button
            onClick={() => router.push("/chat")}
            className="text-sm text-neutral-400 hover:text-neutral-200"
          >
            Back to Chat
          </button>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-900/30 border border-red-800 rounded-md text-red-300 text-sm">
            {error}
          </div>
        )}

        <button
          onClick={openCreateForm}
          className="bg-neutral-100 text-neutral-900 py-2 px-4 rounded-md text-sm font-medium mb-6"
        >
          + New Agent
        </button>

        {loading && <div className="text-sm text-neutral-400">Loading...</div>}

        {/* Show server-side agents when logged in */}
        {user && agents.length === 0 && !loading && (
          <div className="text-center text-neutral-500 py-12">
            No agents yet. Create one to get started.
          </div>
        )}

        {/* Show local agents when not logged in */}
        {!user && localAgents.length === 0 && !loading && (
          <div className="text-center text-neutral-500 py-12">
            No agents yet. Create one to get started.
          </div>
        )}

        {/* Server-side agents */}
        {user && agents.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
            {agents.map((agent) => (
              <div
                key={agent.id}
                className="p-4 border border-neutral-800 rounded-lg bg-neutral-900/30"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="font-medium text-lg">{agent.name}</h3>
                    {agent.is_default && (
                      <span className="text-xs bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded">Default</span>
                    )}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => openEditForm(agent)}
                      className="text-sm text-neutral-400 hover:text-neutral-200"
                    >
                      Edit
                    </button>
                    <button
                      onClick={() => deleteAgent(agent.id)}
                      className="text-sm text-red-400 hover:text-red-300"
                    >
                      Delete
                    </button>
                  </div>
                </div>
                <p className="text-sm text-neutral-400 mb-3">{agent.description || "No description"}</p>
                <div className="text-xs text-neutral-500 space-y-1">
                  <div><span className="text-neutral-400">Model:</span> {agent.model || "Not set"}</div>
                  <div><span className="text-neutral-400">Temperature:</span> {agent.temperature}</div>
                  <div><span className="text-neutral-400">Max Tokens:</span> {agent.max_tokens}</div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Local agents */}
        {!user && localAgents.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {localAgents.map((agent) => (
              <div
                key={agent.id}
                className="p-4 border border-neutral-800 rounded-lg bg-neutral-900/30"
              >
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="font-medium text-lg">{agent.name}</h3>
                    {agent.is_default && (
                      <span className="text-xs bg-blue-900/50 text-blue-300 px-2 py-0.5 rounded">Default</span>
                    )}
                  </div>
                  <div className="flex gap-2
                      onClick">
                    <button={() => openEditForm(agent)}
                      className="-400 hover:texttext-sm text-neutral-neutral-200"
                    >
                      Edit
                    </button>
                    <button(agent.id)}
={() => deleteAgent
                      onClick-400 hover:texttext-sm text-red                      className="                    >
                      Delete-red-300"
>
                </div>
                  </div
                    </button>
                <p className="text-sm text-neutral-400 mb-3">{agent.description ||</p>
                "No description"} <div className="text-xs text-y-1">
-neutral-500 space                  <div><span className="">Model:</spantext-neutral-400> {agent.model || "Not set"}</div>
                  <div><span className="text-neutral-400">Temperature:</span> {agent.temperature}</div>
                  <div><span className="text-neutral-400">Max Tokens:</span> {agent.max_tokens}</div>
                </div>
              </div>
            ))}
          </div>
        )}
              <p className="text-sm text-neutral-400 mb-3">{agent.description || "No description"}</p>
              <div className="text-xs text-neutral-500 space-y-1">
                <div><span className="text-neutral-400">Model:</span> {agent.model || "Not set"}</div>
                <div><span className="text-neutral-400">Temperature:</span> {agent.temperature}</div>
                <div><span className="text-neutral-400">Max Tokens:</span> {agent.max_tokens}</div>
              </div>
            </div>
          ))}
        </div>

        {showCreateForm && (
          <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
            <div className="bg-neutral-950 border border-neutral-800 rounded-lg p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
              <h2 className="text-xl font-semibold mb-4">
                {editingAgent ? "Edit Agent" : "Create Agent"}
              </h2>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-neutral-400 mb-1">Name *</label>
                  <input
                    type="text"
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    placeholder="My Custom Agent"
                  />
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-1">Description</label>
                  <textarea
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                    className="w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    rows={2}
                    placeholder="Optional description"
                  />
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-1">Model</label>
                  <input
                    type="text"
                    value={formData.model}
                    onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                    className="w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    placeholder="Ollama:llama3.2"
                  />
                </div>

                <div>
                  <label className="block text-sm text-neutral-400 mb-1">System Prompt</label>
                  <textarea
                    value={formData.system_prompt}
                    onChange={(e) => setFormData({ ...formData, system_prompt: e.target.value })}
                    className="w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    rows={4}
                    placeholder="You are a helpful assistant..."
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-neutral-400 mb-1">Temperature</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="2"
                      value={formData.temperature}
                      onChange={(e) => setFormData({ ...formData, temperature: parseFloat(e.target.value) || 0.7 })}
                      className="w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-neutral-400 mb-1">Max Tokens</label>
                    <input
                      type="number"
                      min="1"
                      value={formData.max_tokens}
                      onChange={(e) => setFormData({ ...formData, max_tokens: parseInt(e.target.value) || 4096 })}
                      className="w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-neutral-400 mb-1">Top P</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="1"
                      value={formData.top_p}
                      onChange={(e) => setFormData({ ...formData, top_p: parseFloat(e.target.value) || 1.0 })}
                      className="w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-neutral-400 mb-1">Presence Penalty</label>
                    <input
                      type="number"
                      step="0.1"
                      min="-2"
                      max="2"
                      value={formData.presence_penalty}
                      onChange={(e) => setFormData({ ...formData, presence_penalty: parseFloat(e.target.value) || 0.0 })}
                      className="w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-neutral-400 mb-1">Frequency Penalty</label>
                    <input
                      type="number"
                      step="0.1"
                      min="-2"
                      max="2"
                      value={formData.frequency_penalty}
                      onChange={(e) => setFormData({ ...formData, frequency_penalty: parseFloat(e.target.value) || 0.0 })}
                      className="w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm"
                    />
                  </div>
                  <div className="flex items-center pt-6">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={formData.is_default}
                        onChange={(e) => setFormData({ ...formData, is_default: e.target.checked })}
                        className="w-4 h-4"
                      />
                      <span className="text-sm">Set as default</span>
                    </label>
                  </div>
                </div>

                <div className="flex gap-2 pt-4">
                  <button
                    onClick={saveAgent}
                    disabled={loading || !formData.name.trim()}
                    className="bg-neutral-100 text-neutral-900 py-2 px-4 rounded-md text-sm font-medium disabled:opacity-50"
                  >
                    {editingAgent ? "Update" : "Create"}
                  </button>
                  <button
                    onClick={() => {
                      setShowCreateForm(false);
                      setEditingAgent(null);
                    }}
                    className="border border-neutral-800 py-2 px-4 rounded-md text-sm hover:bg-neutral-900"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
