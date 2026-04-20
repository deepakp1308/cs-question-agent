import pytest

from app.config import ModelRole, ModelsBlock, ProjectConfig


def _build(generator_provider: str, judge_provider: str) -> ProjectConfig:
    return ProjectConfig(
        models=ModelsBlock(
            classifier=ModelRole(provider="mock", model="m"),
            generator=ModelRole(provider=generator_provider, model="g"),
            judge=ModelRole(provider=judge_provider, model="j"),
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


def test_independence_rejects_same_provider():
    cfg = _build("openai", "openai")
    with pytest.raises(ValueError):
        cfg.validate_model_independence()
