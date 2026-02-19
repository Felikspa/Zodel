"use client";

import { useEffect, useMemo, useState } from "react";
import { t } from "@/lib/i18n";
import { useI18n } from "@/app/providers";

const API_BASE = process.env.NEXT_PUBLIC_ZODEL_API_BASE ?? "http://127.0.0.1:8000";

type Corpus = { corpus_id: string; name: string; description?: string };

export default function RagPage() {
  const { locale } = useI18n();
  const [corpora, setCorpora] = useState<Corpus[]>([]);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<string>("");
  const [text, setText] = useState("");
  const [embeddingModel, setEmbeddingModel] = useState("Cloud:text-embedding-3-small");
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ score: number; chunk: { text: string; source_name: string } }[]>([]);
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const res = await fetch(`${API_BASE}/api/rag/corpora`);
    const data = await res.json();
    setCorpora(data.corpora ?? []);
    if (!selected && data.corpora?.[0]?.corpus_id) setSelected(data.corpora[0].corpus_id);
  }

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectedCorpus = useMemo(() => corpora.find((c) => c.corpus_id === selected), [corpora, selected]);

  async function createCorpus() {
    setBusy(true);
    try {
      await fetch(`${API_BASE}/api/rag/corpora`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description })
      });
      setName("");
      setDescription("");
      await refresh();
    } finally {
      setBusy(false);
    }
  }

  async function addText() {
    if (!selected) return;
    setBusy(true);
    try {
      await fetch(`${API_BASE}/api/rag/add_text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          corpus_id: selected,
          source_name: "manual",
          text,
          embedding_model: embeddingModel
        })
      });
      setText("");
    } finally {
      setBusy(false);
    }
  }

  async function runQuery() {
    if (!selected) return;
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/rag/query`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          corpus_id: selected,
          query,
          embedding_model: embeddingModel,
          top_k: 5
        })
      });
      const data = await res.json();
      setResults(data.results ?? []);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100">
      <div className="mx-auto max-w-5xl px-6 py-8">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">{t(locale, "rag.title")}</h1>
          <a className="text-sm text-neutral-400 hover:text-neutral-200" href="/chat">
            Back to chat
          </a>
        </div>

        <div className="mt-6 grid gap-6 md:grid-cols-2">
          <div className="rounded-xl border border-neutral-800 bg-neutral-950 p-4">
            <div className="text-sm font-medium">Corpora</div>
            <div className="mt-3 space-y-2">
              <select
                className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-sm"
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
              >
                <option value="" disabled>
                  Select corpus…
                </option>
                {corpora.map((c) => (
                  <option key={c.corpus_id} value={c.corpus_id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <div className="text-xs text-neutral-500">
                {selectedCorpus ? (
                  <>
                    <div>ID: {selectedCorpus.corpus_id}</div>
                    <div>{selectedCorpus.description}</div>
                  </>
                ) : (
                  "No corpus selected."
                )}
              </div>
            </div>

            <div className="mt-4 border-t border-neutral-800 pt-4">
              <div className="text-sm font-medium">Create corpus</div>
              <div className="mt-2 space-y-2">
                <input
                  className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-sm"
                  placeholder="Name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
                <input
                  className="w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-sm"
                  placeholder="Description"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                />
                <button
                  className="rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-900 disabled:opacity-50"
                  onClick={() => void createCorpus()}
                  disabled={busy || !name.trim()}
                >
                  Create
                </button>
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-neutral-800 bg-neutral-950 p-4">
            <div className="text-sm font-medium">Embedding model</div>
            <input
              className="mt-2 w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-sm"
              value={embeddingModel}
              onChange={(e) => setEmbeddingModel(e.target.value)}
              placeholder="Cloud:text-embedding-3-small"
            />

            <div className="mt-4 border-t border-neutral-800 pt-4">
              <div className="text-sm font-medium">Add text</div>
              <textarea
                className="mt-2 w-full resize-none rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-sm"
                rows={6}
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Paste knowledge text here..."
              />
              <button
                className="mt-2 rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-900 disabled:opacity-50"
                onClick={() => void addText()}
                disabled={busy || !selected || !text.trim()}
              >
                Add
              </button>
            </div>

            <div className="mt-4 border-t border-neutral-800 pt-4">
              <div className="text-sm font-medium">Query</div>
              <input
                className="mt-2 w-full rounded-md border border-neutral-800 bg-neutral-950 px-2 py-2 text-sm"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask something..."
              />
              <button
                className="mt-2 rounded-md bg-neutral-100 px-3 py-2 text-sm font-medium text-neutral-900 disabled:opacity-50"
                onClick={() => void runQuery()}
                disabled={busy || !selected || !query.trim()}
              >
                Search
              </button>
              <div className="mt-3 space-y-2">
                {results.map((r, i) => (
                  <div key={i} className="rounded-lg border border-neutral-800 bg-neutral-900 p-3">
                    <div className="text-xs text-neutral-400">
                      score: {r.score.toFixed(4)} • source: {r.chunk.source_name}
                    </div>
                    <div className="mt-2 whitespace-pre-wrap text-sm">{r.chunk.text}</div>
                  </div>
                ))}
                {results.length === 0 ? <div className="text-xs text-neutral-500">No results.</div> : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

