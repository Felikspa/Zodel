from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from app.helper import get_embeddings, infer_provider_from_model, extract_model_name


@dataclass(frozen=True)
class RagChunk:
    chunk_id: str
    corpus_id: str
    source_name: str
    text: str
    embedding: List[float]


@dataclass(frozen=True)
class RagCorpus:
    corpus_id: str
    name: str
    description: str = ""


def _cosine(a: List[float], b: List[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return -1.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


def _chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> List[str]:
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []
    out: List[str] = []
    i = 0
    while i < len(text):
        j = min(len(text), i + chunk_size)
        out.append(text[i:j].strip())
        if j >= len(text):
            break
        i = max(0, j - overlap)
    return [c for c in out if c]


class RagService:
    def __init__(self, data_dir: str | os.PathLike = "data/rag"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._corpora_path = self.data_dir / "corpora.json"

    def list_corpora(self) -> List[RagCorpus]:
        if not self._corpora_path.exists():
            return []
        data = json.loads(self._corpora_path.read_text(encoding="utf-8"))
        return [RagCorpus(**c) for c in data.get("corpora", [])]

    def create_corpus(self, name: str, description: str = "") -> RagCorpus:
        corpus = RagCorpus(corpus_id=str(uuid.uuid4()), name=name.strip(), description=description.strip())
        corpora = self.list_corpora()
        corpora.append(corpus)
        self._corpora_path.write_text(
            json.dumps({"corpora": [c.__dict__ for c in corpora]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return corpus

    def _chunks_path(self, corpus_id: str) -> Path:
        return self.data_dir / f"{corpus_id}.chunks.jsonl"

    def add_document_text(
        self,
        *,
        corpus_id: str,
        source_name: str,
        text: str,
        embedding_model: str,
    ) -> int:
        provider = infer_provider_from_model(embedding_model)
        model_name = extract_model_name(embedding_model)

        chunks = _chunk_text(text)
        if not chunks:
            return 0

        path = self._chunks_path(corpus_id)
        appended = 0
        with path.open("a", encoding="utf-8") as f:
            for chunk_text in chunks:
                emb = get_embeddings(provider, model_name, chunk_text)
                item = RagChunk(
                    chunk_id=str(uuid.uuid4()),
                    corpus_id=corpus_id,
                    source_name=source_name,
                    text=chunk_text,
                    embedding=list(emb),
                )
                f.write(json.dumps(item.__dict__, ensure_ascii=False) + "\n")
                appended += 1
        return appended

    def _iter_chunks(self, corpus_id: str) -> Iterable[RagChunk]:
        path = self._chunks_path(corpus_id)
        if not path.exists():
            return []
        def gen():
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                        yield RagChunk(**obj)
                    except Exception:
                        continue
        return gen()

    def query(
        self,
        *,
        corpus_id: str,
        query_text: str,
        embedding_model: str,
        top_k: int = 5,
    ) -> List[Tuple[float, RagChunk]]:
        provider = infer_provider_from_model(embedding_model)
        model_name = extract_model_name(embedding_model)
        q_emb = list(get_embeddings(provider, model_name, query_text))

        scored: List[Tuple[float, RagChunk]] = []
        for ch in self._iter_chunks(corpus_id):
            score = _cosine(q_emb, ch.embedding)
            scored.append((score, ch))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[: max(1, top_k)]

