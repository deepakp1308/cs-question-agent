import pytest

from app.config import ModelRole, ModelsBlock, ProjectConfig


def _build(
    generator_provider: str,
    judge_provider: str,
    *,
    generator_model: str = "g",
    judge_model: str = "j",
) -> ProjectConfig:
    return ProjectConfig(
        models=ModelsBlock(
            classifier=ModelRole(provider="mock", model="m"),
            generator=ModelRole(provider=generator_provider, model=generator_model),
            judge=ModelRole(provider=judge_provider, model=judge_model),
            embeddings=ModelRole(provider="mock", model="e"),
            reranker=ModelRole(provider="mock", model="r"),
        )
    )


def test_independence_ok_for_mock():
    cfg = _build("mock", "mock")
    cfg.validate_model_independence()  # must not raise


def test_independence_ok_different_providers():
    cfg = _build("openai", "anthropic")
    cfg.validate_model_independence()


def test_independence_ok_same_provider_different_models():
    # Allowed (e.g., gemma3:12b vs gemma3:4b) but weaker independence.
    cfg = _build("ollama", "ollama", generator_model="gemma3:12b", judge_model="gemma3:4b")
    cfg.validate_model_independence()


def test_independence_rejects_identical_provider_and_model():
    cfg = _build("openai", "openai", generator_model="gpt-4o", judge_model="gpt-4o")
    with pytest.raises(ValueError):
        cfg.validate_model_independence()
