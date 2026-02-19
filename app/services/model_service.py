from __future__ import annotations

from dataclasses import dataclass
from typing import List

from app.helper import get_all_models


@dataclass(frozen=True)
class ModelInfo:
    id: str  # prefixed model name, e.g. "Ollama:llama3"
    provider: str  # "ollama" | "openai" | "genstudio"
    name: str  # pure model name


def _infer_provider(prefixed_model_name: str) -> str:
    lower = prefixed_model_name.lower()
    if lower.startswith("ollama:"):
        return "ollama"
    if lower.startswith("cloud:"):
        return "openai"
    if lower.startswith("genstudio:"):
        return "genstudio"
    return "unknown"


def _extract_name(prefixed_model_name: str) -> str:
    return prefixed_model_name.split(":", 1)[1] if ":" in prefixed_model_name else prefixed_model_name


class ModelService:
    def list_models(self) -> List[ModelInfo]:
        models = get_all_models()
        return [
            ModelInfo(id=m, provider=_infer_provider(m), name=_extract_name(m))
            for m in models
        ]

