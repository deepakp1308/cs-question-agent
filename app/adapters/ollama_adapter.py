"""Free, local LLM via Ollama (no API key required).

Point OLLAMA_HOST at your Ollama server (default http://localhost:11434).
Pull a model first:  ollama pull llama3.1
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from .llm_base import EmbeddingResponse, LLMResponse


def _host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


@dataclass
class OllamaAdapter:
    model: str = "llama3.1"
    provider: str = "ollama"
    timeout: float = 120.0

    def complete(
        self,
        *,
        system: str,
        user: str,
        json_mode: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        payload: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {"temperature": temperature, "num_predict": max_tokens},
            "stream": False,
        }
        if json_mode:
            payload["format"] = "json"
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(f"{_host()}/api/chat", json=payload)
            r.raise_for_status()
            data = r.json()
        content = data.get("message", {}).get("content", "")
        return LLMResponse(
            text=content,
            input_tokens=data.get("prompt_eval_count", 0),
            output_tokens=data.get("eval_count", 0),
            cost_usd=0.0,
            raw=data,
            meta={"provider": "ollama", "model": self.model},
        )


@dataclass
class OllamaEmbeddingAdapter:
    model: str = "nomic-embed-text"
    provider: str = "ollama"
    dimensions: int = 768
    timeout: float = 120.0

    def embed(self, texts: list[str]) -> EmbeddingResponse:
        vectors: list[list[float]] = []
        tokens = 0
        with httpx.Client(timeout=self.timeout) as client:
            for t in texts:
                r = client.post(f"{_host()}/api/embeddings", json={"model": self.model, "prompt": t})
                r.raise_for_status()
                data = r.json()
                vectors.append(data["embedding"])
                tokens += len(t.split())
        return EmbeddingResponse(vectors=vectors, input_tokens=tokens, cost_usd=0.0)
