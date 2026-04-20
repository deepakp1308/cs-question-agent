"""Google Gemini adapter — activated when GOOGLE_API_KEY is set."""
from __future__ import annotations

import os
from dataclasses import dataclass

from .llm_base import EmbeddingResponse, LLMResponse

_PRICES = {
    "gemini-1.5-flash": (0.000075, 0.0003),
    "gemini-1.5-pro": (0.00125, 0.005),
    "gemini-2.0-flash": (0.000075, 0.0003),
    "gemini-2.5-flash": (0.000075, 0.0003),
    "gemini-2.5-pro": (0.00125, 0.005),
}


def _price(model: str, i: int, o: int) -> float:
    pin, pout = _PRICES.get(model, (0.000075, 0.0003))
    return (i / 1000.0) * pin + (o / 1000.0) * pout


@dataclass
class GoogleAdapter:
    model: str = "gemini-1.5-flash"
    provider: str = "google"

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        import google.generativeai as genai  # lazy

        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
        model = genai.GenerativeModel(self.model, system_instruction=system)
        generation_config: dict = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        if json_mode:
            generation_config["response_mime_type"] = "application/json"
        resp = model.generate_content(user, generation_config=generation_config)
        text = resp.text or ""
        in_tok = getattr(resp.usage_metadata, "prompt_token_count", 0) if resp.usage_metadata else 0
        out_tok = getattr(resp.usage_metadata, "candidates_token_count", 0) if resp.usage_metadata else 0
        return LLMResponse(
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=_price(self.model, in_tok, out_tok),
            raw=resp,
            meta={"provider": "google", "model": self.model},
        )


@dataclass
class GoogleEmbeddingAdapter:
    model: str = "text-embedding-004"
    provider: str = "google"
    dimensions: int = 768

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        import google.generativeai as genai

        genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
        vectors: list[list[float]] = []
        for t in texts:
            r = genai.embed_content(model=f"models/{self.model}", content=t)
            vectors.append(r["embedding"])
        return EmbeddingResponse(
            vectors=vectors,
            input_tokens=sum(len(t.split()) for t in texts),
            cost_usd=0.0,
        )
