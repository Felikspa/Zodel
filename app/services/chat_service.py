from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Generator, List, Optional, Tuple

from app.config import DEFAULT_SYSTEM_PROMPT
from app.helper import extract_model_name, infer_provider_from_model, stream_chat


@dataclass(frozen=True)
class RoutingConfig:
    classifier_model: str
    labels: List[str]
    output_models: List[str]
    custom_classifier_prompt: str = ""


def _strip_display_prefix(assistant_text: str) -> str:
    # Strip legacy UI prefix like **[Ollama:xxx]**:
    return re.sub(r"\*\*\[.*?\]\*\*:\s*", "", assistant_text)


class ChatService:
    """
    Framework-agnostic chat service.

    It exposes streaming text output suitable for SSE/WebSocket.
    """

    def _classify_and_route(self, msg: str, routing: RoutingConfig) -> Tuple[str, str]:
        if not routing.classifier_model:
            raise ValueError("classifier_model is required for Auto mode.")
        if not routing.labels or not routing.output_models or len(routing.labels) != len(routing.output_models):
            raise ValueError("labels/output_models must be non-empty and 1:1 mapped.")

        default_fallback_model = routing.output_models[0]
        model_map = dict(zip([l.strip().lower() for l in routing.labels], routing.output_models))

        labels_str = ", ".join(model_map.keys())
        if routing.custom_classifier_prompt.strip():
            classifier_prompt = routing.custom_classifier_prompt.strip()
            if "respond only" not in classifier_prompt.lower():
                classifier_prompt += f" Respond ONLY with one of the following words: {labels_str}."
        else:
            classifier_prompt = (
                "You are a routing agent. Classify the user's prompt. "
                f"Respond ONLY with one of the following single words: {labels_str}."
            )

        classifier_messages = [
            {"role": "system", "content": classifier_prompt},
            {"role": "user", "content": msg},
        ]
        classifier_provider = infer_provider_from_model(routing.classifier_model)
        classifier_name = extract_model_name(routing.classifier_model)

        try:
            classification = "".join(stream_chat(classifier_provider, classifier_name, classifier_messages)).strip().lower()
        except Exception as e:
            note = f"[route_fallback] classifier_failed: {e}"
            return default_fallback_model, note

        if classification in model_map:
            return model_map[classification], ""

        note = f"[route_fallback] unexpected_label:{classification} expected:{labels_str}"
        return default_fallback_model, note

    def stream_chat_completion(
        self,
        *,
        user_message: str,
        history: List[Tuple[str, str]],
        mode: str,
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        routing: Optional[RoutingConfig] = None,
    ) -> Generator[str, None, None]:
        """
        Args:
            user_message: current user message (plain text).
            history: list of (user, assistant) plain-text turns, oldest->newest.
            mode: "chat" | "auto"
            model: required when mode == "chat"
            routing: required when mode == "auto"
        """
        system_prompt = (system_prompt or DEFAULT_SYSTEM_PROMPT).strip() or DEFAULT_SYSTEM_PROMPT

        if mode not in {"chat", "auto"}:
            raise ValueError("mode must be 'chat' or 'auto'")

        if mode == "chat":
            if not model:
                raise ValueError("model is required for chat mode.")
            final_model = model
            route_note = ""
        else:
            if not routing:
                raise ValueError("routing config is required for auto mode.")
            final_model, route_note = self._classify_and_route(user_message, routing)

        provider = infer_provider_from_model(final_model)
        pure_model = extract_model_name(final_model)

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for u, a in history:
            if u:
                messages.append({"role": "user", "content": u})
            if a:
                messages.append({"role": "assistant", "content": _strip_display_prefix(a)})
        messages.append({"role": "user", "content": user_message})

        if route_note:
            yield f"\n\n[system] {route_note}\n\n"

        yield from stream_chat(provider, pure_model, messages)

    def generate_title(self, messages: List[Dict[str, str]]) -> str:
        """
        Generate a short title for a conversation based on the first few messages.

        Args:
            messages: List of message dicts with 'role' and 'content' keys.

        Returns:
            A short, descriptive title for the conversation.
        """
        if not messages:
            return "New Chat"

        # Get the first user message and maybe assistant response
        title_messages = [{"role": "system", "content": "You are a title generator. Generate a short, descriptive title (max 50 characters) for this conversation. Only respond with the title, no quotes or punctuation."}]

        # Find the first user message
        first_user_msg = ""
        for msg in messages:
            if msg.get("role") == "user":
                first_user_msg = msg.get("content", "")[:500]
                break

        if not first_user_msg:
            return "New Chat"

        title_messages.append({"role": "user", "content": f"Conversation start: {first_user_msg}"})

        # Use a simple approach - use Ollama as default for title generation
        # This can be made configurable later
        try:
            provider = "ollama"
            model = "llama3.2"
            title = "".join(stream_chat(provider, model, title_messages)).strip()
            # Clean up the title
            title = title.strip('"\'')
            if len(title) > 50:
                title = title[:47] + "..."
            return title if title else "New Chat"
        except Exception:
            # Fallback: extract first few words from user message
            words = first_user_msg.split()[:5]
            return " ".join(words) if words else "New Chat"
