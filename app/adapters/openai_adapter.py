"""OpenAI adapter — activated when OPENAI_API_KEY is set."""
from __future__ import annotations

import os
from dataclasses import dataclass

from .llm_base import EmbeddingResponse, LLMResponse

# Rough default pricing (USD per 1K tokens) — override via env if your pricing differs.
_PRICES = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-5": (0.01, 0.03),
    "gpt-5.4": (0.01, 0.03),
    "gpt-5-mini": (0.0003, 0.0012),
}


def _price(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = _PRICES.get(model, (0.005, 0.015))
    return (input_tokens / 1000.0) * pin + (output_tokens / 1000.0) * pout


@dataclass
class OpenAIAdapter:
    model: str = "gpt-4o-mini"
    provider: str = "openai"

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        from openai import OpenAI  # lazy import

        client = OpenAI()  # reads OPENAI_API_KEY
        kwargs: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        in_tok = getattr(usage, "prompt_tokens", 0) if usage else 0
        out_tok = getattr(usage, "completion_tokens", 0) if usage else 0
        return LLMResponse(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=_price(self.model, in_tok, out_tok),
            raw=resp,
            meta={"provider": "openai", "model": self.model},
        )


@dataclass
class OpenAIEmbeddingAdapter:
    model: str = "text-embedding-3-small"
    provider: str = "openai"
    dimensions: int = 1536

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        from openai import OpenAI

        client = OpenAI()
        resp = client.embeddings.create(model=self.model, input=texts)
        vectors = [item.embedding for item in resp.data]
        usage = getattr(resp, "usage", None)
        tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
        # Pricing for embedding-3-small ~ $0.00002 / 1K tokens
        per_1k = 0.00002 if "small" in self.model else 0.00013
        return EmbeddingResponse(vectors=vectors, input_tokens=tokens, cost_usd=(tokens / 1000.0) * per_1k)


os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
