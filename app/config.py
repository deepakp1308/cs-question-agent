"""Project configuration loader (project.yaml)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ModelRole(BaseModel):
    provider: str
    model: str


class ModelsBlock(BaseModel):
    classifier: ModelRole
    generator: ModelRole
    judge: ModelRole
    embeddings: ModelRole
    reranker: ModelRole


class ConfidenceWeights(BaseModel):
    ensemble_agreement: float = 0.40
    grounding_ratio: float = 0.35
    retrieval_strength: float = 0.25


class QualityBlock(BaseModel):
    min_extraction_score: float = 0.98
    min_answer_score: float = 0.90
    max_repair_loops: int = 2
    max_run_cost_usd: float = 25.00
    confidence_weights: ConfidenceWeights = Field(default_factory=ConfidenceWeights)
    grounding_ratio_floor: float = 0.70


class PublishBlock(BaseModel):
    github_pages_repo: str = ""
    custom_domain: str = ""
    visibility: str = "public"


class RuntimeBlock(BaseModel):
    concurrency: int = 4
    enable_ensemble: bool = True


class ProjectConfig(BaseModel):
    subject: str = "computer_science"
    grade_level: int = 10
    student_age: int = 15
    teaching_style: str = "clear, patient, first-time learner"
    exam_board: str = "generic"
    selection_mode: str = "all_questions"
    dedupe_mode: str = "group_exact_duplicates"
    publish: PublishBlock = Field(default_factory=PublishBlock)
    quality: QualityBlock = Field(default_factory=QualityBlock)
    runtime: RuntimeBlock = Field(default_factory=RuntimeBlock)
    models: ModelsBlock

    def validate_model_independence(self) -> None:
        if self.models.judge.provider == "mock" or self.models.generator.provider == "mock":
            return
        same_provider = self.models.judge.provider == self.models.generator.provider
        same_model = (
            same_provider and self.models.judge.model == self.models.generator.model
        )
        if same_model:
            raise ValueError(
                "judge.model must not be identical to generator.model "
                f"(got {self.models.generator.provider}/{self.models.generator.model} for both) — "
                "see spec §Model policy"
            )
        # Same-provider / different-model is allowed (e.g. gemma3:12b vs gemma3:4b) but
        # is weaker independence than different-family. The orchestrator logs a warning.


def load_project(path: str | Path) -> ProjectConfig:
    data: dict[str, Any] = yaml.safe_load(Path(path).read_text())
    cfg = ProjectConfig.model_validate(data)
    cfg.validate_model_independence()
    return cfg
