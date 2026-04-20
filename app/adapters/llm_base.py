"""Base LLM adapter contract + cost accounting."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    raw: Any = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmbeddingResponse:
    vectors: list[list[float]]
    input_tokens: int = 0
    cost_usd: float = 0.0


class LLMAdapter(Protocol):
    provider: str
    model: str

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse: ...


class EmbeddingAdapter(Protocol):
    provider: str
    model: str
    dimensions: int

    def embed(self, texts: list[str]) -> EmbeddingResponse: ...
