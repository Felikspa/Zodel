"use client";

import { fetchSse } from "@/lib/sse";
import { useEffect, useState } from "react";
import { t } from "@/lib/i18n";
import { useI18n } from "@/app/providers";

const API_BASE = process.env.NEXT_PUBLIC_ZODEL_API_BASE ?? "http://127.0.0.1:8000";

type Flow = { id: number; name: string; description?: string; code?: string };

export default function FlowsPage() {
  const { locale } = useI18n();
  const [userId, setUserId] = useState<number>(1);
  const [flows, setFlows] = useState<Flow[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [name, setName] = useState("My Flow");
  const [description, setDescription] = useState("");
  const [code, setCode] = useState("A=GenStudio:deepseek-v3\np1='You are helpful.'\ni='Hello'\ni->A_p1");
  const [output, setOutput] = useState("");
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const res = await fetch(`${API_BASE}/api/flows?user_id=${userId}`);
    const data = await res.json();
    setFlows(data.flows ?? []);
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  async function create() {
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/flows`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userId, name, description, code })
      });
      const data = await res.json();
      await refresh();
      setSelectedId(data.flow?.id ?? null);
    } finally {
      setBusy(false);
    }
  }

  async function load(id: number) {
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/flows/${id}`);
      const data = await res.json();
      const f = data.flow as Flow;
      setSelectedId(f.id);
      setName(f.name);
      setDescription(f.description ?? "");
      setCode(f.code ?? "");
    } finally {
      setBusy(false);
    }
  }

  async function run() {
    setBusy(true);
    setOutput("");
    try {
      for await (const evt of fetchSse(`${API_BASE}/api/zflow/execute`, {
        method: "POST",
        body: JSON.stringify({ script: code })
      })) {
        if (evt.type === "delta") setOutput((p) => p + evt.text);
        if (evt.type === "error") setOutput((p) => p + `\nError: ${evt.message}\n`);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <div className="mx-auto max-w-6xl px-6 py-8">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">{t(locale, "flows.title")}</h1>
          <div className="flex items-center gap-3">
            <a className="text-sm text-neutral-400 hover:text-neutral-200" href="/chat">{t(locale, "nav.chat")}</a>
            <a className="text-sm text-neutral-400 hover:text-neutral-200" href="/rag">{t(locale, "nav.rag")}</a>
          </div>
        </div>

        <div className="mt-6 grid gap-6 lg:grid-cols-3">
          <div className="rounded-xl border border-neutral-800 bg-neutral-950 p-4">
            <div className="flex items-center justify-between">
              <div className="text-sm font-medium">Saved flows</div>
              <button
                className="rounded-md border border-neutral-800 px-2 py-1 text-xs hover:bg-neutral-900"
                onClick={() => void refresh()}
              >
                Refresh
              </button>
            </div>
            <div className="mt-3 space-y-2">
              <label className="text-xs text-neutral-400">User ID</label>
              <input
                className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-sm"
                value={userId}
                onChange={(e) => setUserId(Number(e.target.value) || 1)}
              />
            </div>
            <div className="mt-4 space-y-2">
              {flows.map((f) => (
                <button
                  key={f.id}
                  className={[
                    "w-full rounded-lg border px-3 py-2 text-left text-sm",
                    selectedId === f.id ? "border-neutral-600 bg-neutral-900" : "border-neutral-800 hover:bg-neutral-900"
                  ].join(" ")}
                  onClick={() => void load(f.id)}
                  disabled={busy}
                >
                  <div className="font-medium">{f.name}</div>
                  <div className="mt-1 text-xs text-neutral-500">{f.description}</div>
                </button>
              ))}
              {flows.length === 0 ? <div className="text-xs text-neutral-500">No flows.</div> : null}
            </div>
          </div>

          <div className="rounded-xl border border-neutral-800 bg-neutral-950 p-4 lg:col-span-2">
            <div className="grid gap-3 md:grid-cols-2">
              <div>
                <label className="text-xs text-neutral-400">Name</label>
                <input
                  className="mt-1 w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-sm"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </div>
              <div>
                <label className="text-xs text-neutral-400">Description</label>
                <input
                  className="mt-1 w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-sm"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
              </div>
            </div>

            <div className="mt-4">
              <label className="text-xs text-neutral-400">Zflow code</label>
              <textarea
                className="mt-1 h-64 w-full resize-none rounded-md border border-neutral-800 bg-neutral-950 px-3 py-3 font-mono text-xs outline-none focus:border-neutral-600"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </div>

            <div className="mt-3 flex items-center gap-2">
              <button
                className="rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-900 disabled:opacity-50"
                onClick={() => void create()}
                disabled={busy || !name.trim() || !code.trim()}
              >
                Save
              </button>
              <button
                className="rounded-md border border-neutral-800 px-3 py-2 text-sm hover:bg-neutral-900 disabled:opacity-50"
                onClick={() => void run()}
                disabled={busy || !code.trim()}
              >
                Run
              </button>
            </div>

            <div className="mt-4">
              <label className="text-xs text-neutral-400">Output</label>
              <pre className="mt-1 max-h-64 overflow-auto rounded-md border border-neutral-800 bg-neutral-900 p-3 text-xs whitespace-pre-wrap">
                {output || "—"}
              </pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

