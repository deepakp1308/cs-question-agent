"""Cohere adapter — activated when COHERE_API_KEY is set. Primarily used for embeddings and rerank."""
from __future__ import annotations

import os
from dataclasses import dataclass

from .llm_base import EmbeddingResponse, LLMResponse


@dataclass
class CohereAdapter:
    model: str = "command-r-plus"
    provider: str = "cohere"

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        import cohere  # lazy

        client = cohere.Client(os.environ.get("COHERE_API_KEY"))
        resp = client.chat(
            model=self.model,
            message=user,
            preamble=system,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"} if json_mode else None,
        )
        text = getattr(resp, "text", "") or ""
        usage = getattr(resp, "meta", None)
        in_tok = 0
        out_tok = 0
        if usage is not None:
            tokens = getattr(usage, "tokens", None)
            if tokens is not None:
                in_tok = getattr(tokens, "input_tokens", 0) or 0
                out_tok = getattr(tokens, "output_tokens", 0) or 0
        return LLMResponse(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=(in_tok / 1000.0) * 0.0025 + (out_tok / 1000.0) * 0.01,
            raw=resp,
            meta={"provider": "cohere", "model": self.model},
        )


@dataclass
class CohereEmbeddingAdapter:
    model: str = "embed-english-v3.0"
    provider: str = "cohere"
    dimensions: int = 1024

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        import cohere

        client = cohere.Client(os.environ.get("COHERE_API_KEY"))
        resp = client.embed(texts=texts, model=self.model, input_type="search_document")
        vectors = list(resp.embeddings)
        return EmbeddingResponse(
            vectors=vectors,
            input_tokens=sum(len(t.split()) for t in texts),
            cost_usd=0.0001 * len(texts),
        )
