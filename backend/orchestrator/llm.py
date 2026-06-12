"""LLM answer providers for assembled prompts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from backend.vector.config import GeminiGenerationSettings


class AnswerProvider(Protocol):
    """Generates a natural-language answer from an assembled prompt."""

    def generate_answer(self, prompt: str) -> str:
        """Return the generated answer text."""


@dataclass
class GeminiAnswerProvider:
    """Generate answers with Gemini through the Google GenAI SDK.

    The SDK import and client construction happen lazily at initialization time
    so tests can use fake providers without requiring network access.
    """

    settings: GeminiGenerationSettings
    client: Any = field(init=False)

    def __post_init__(self) -> None:
        if not self.settings.api_key:
            raise ValueError("GEMINI_SECRET_KEY is required for Gemini generation.")

        from google import genai

        self.client = genai.Client(api_key=self.settings.api_key)

    def generate_answer(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.settings.model_name,
            contents=prompt,
        )
        text: str | None = getattr(response, "text", None)
        if text is None:
            return ""
        return text
