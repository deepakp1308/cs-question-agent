from __future__ import annotations

from .llm_base import EmbeddingAdapter, LLMAdapter, LLMResponse


def build_adapter(provider: str, model: str) -> LLMAdapter:
    """Factory that returns the requested adapter. Real adapters are lazy-imported."""
    provider = provider.lower()
    if provider == "mock":
        from .mock_adapter import MockAdapter

        return MockAdapter(model=model)
    if provider == "replay":
        from .replay_adapter import ReplayAdapter

        return ReplayAdapter(model=model)
    if provider == "ollama":
        from .ollama_adapter import OllamaAdapter

        return OllamaAdapter(model=model)
    if provider == "openai":
        from .openai_adapter import OpenAIAdapter

        return OpenAIAdapter(model=model)
    if provider == "anthropic":
        from .anthropic_adapter import AnthropicAdapter

        return AnthropicAdapter(model=model)
    if provider == "google":
        from .google_adapter import GoogleAdapter

        return GoogleAdapter(model=model)
    if provider == "cohere":
        from .cohere_adapter import CohereAdapter

        return CohereAdapter(model=model)
    raise ValueError(f"Unknown LLM provider: {provider!r}")


def build_embedding_adapter(provider: str, model: str) -> EmbeddingAdapter:
    provider = provider.lower()
    if provider == "mock":
        from .mock_adapter import MockEmbeddingAdapter

        return MockEmbeddingAdapter(model=model)
    if provider == "ollama":
        from .ollama_adapter import OllamaEmbeddingAdapter

        return OllamaEmbeddingAdapter(model=model)
    if provider == "openai":
        from .openai_adapter import OpenAIEmbeddingAdapter

        return OpenAIEmbeddingAdapter(model=model)
    if provider == "google":
        from .google_adapter import GoogleEmbeddingAdapter

        return GoogleEmbeddingAdapter(model=model)
    if provider == "cohere":
        from .cohere_adapter import CohereEmbeddingAdapter

        return CohereEmbeddingAdapter(model=model)
    raise ValueError(f"Provider {provider!r} does not expose embeddings in this build")


__all__ = [
    "LLMAdapter",
    "LLMResponse",
    "EmbeddingAdapter",
    "build_adapter",
    "build_embedding_adapter",
]
