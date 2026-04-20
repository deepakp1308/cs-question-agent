"""Pydantic schemas for every stage output."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BBox(BaseModel):
    page: int
    x0: float
    y0: float
    x1: float
    y1: float


class CodeBlock(BaseModel):
    text: str
    indent: int = 0
    language: str | None = None
    bbox: BBox | None = None


class DiagramRef(BaseModel):
    caption: str | None = None
    bbox: BBox | None = None


class ChapterSpec(BaseModel):
    chapter_id: str
    title: str
    aliases: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    subtopics: list[str] = Field(default_factory=list)
    source_docs: list[str] = Field(default_factory=list)


class ModelsUsed(BaseModel):
    classifier: str | None = None
    generator: str | None = None
    judge: str | None = None
    embeddings: str | None = None
    reranker: str | None = None


class PromptVersions(BaseModel):
    extract_question: str | None = None
    parse_chapter_selector: str | None = None
    classify_question_to_chapter: str | None = None
    generate_answer_teacher: str | None = None
    judge_extraction: str | None = None
    judge_match: str | None = None
    judge_answer: str | None = None
    repair_answer: str | None = None


class QuestionRecord(BaseModel):
    question_id: str
    paper_id: str
    source_file: str
    page_range: tuple[int, int]
    section_heading: str | None = None
    instruction_context: str | None = None
    numbering_path: list[str]
    marks: int | None = None
    verbatim_text: str
    normalized_text: str
    bbox_refs: list[BBox] = Field(default_factory=list)
    diagram_refs: list[DiagramRef] = Field(default_factory=list)
    diagram_crops: list[str] = Field(default_factory=list)
    code_blocks: list[CodeBlock] = Field(default_factory=list)

    # Structural fields for OR-branches, duplicates, continuations
    or_group_id: str | None = None
    variant_role: str = "primary"  # primary | alternative
    duplicate_group_id: str | None = None
    canonical_question_id: str | None = None
    continuation_of: str | None = None

    # Mark scheme
    acceptable_alternatives: list[dict[str, str]] = Field(default_factory=list)

    extraction_confidence: float = 1.0
    models_used: ModelsUsed = Field(default_factory=ModelsUsed)
    prompt_versions: PromptVersions = Field(default_factory=PromptVersions)


class ChapterMatch(BaseModel):
    question_id: str
    primary_chapter: str | None
    secondary_chapters: list[str] = Field(default_factory=list)
    retrieval_strength: float
    classifier_confidence: float
    candidates: list[dict[str, Any]] = Field(default_factory=list)
    models_used: ModelsUsed = Field(default_factory=ModelsUsed)
    prompt_versions: PromptVersions = Field(default_factory=PromptVersions)


class CompositeConfidence(BaseModel):
    composite: float
    ensemble_agreement: float
    grounding_ratio: float
    retrieval_strength: float
    model_self_reported: float


class AnswerRecord(BaseModel):
    question_id: str
    direct_answer: str
    exam_style_answer: str
    step_by_step_explanation: list[str]
    simple_example: str | None = None
    common_mistake: str | None = None
    evidence_chunk_ids: list[str]
    confidence: CompositeConfidence
    models_used: ModelsUsed = Field(default_factory=ModelsUsed)
    prompt_versions: PromptVersions = Field(default_factory=PromptVersions)


class JudgeResult(BaseModel):
    pass_: bool = Field(alias="pass")
    score: float
    issues: list[str] = Field(default_factory=list)
    repair_instructions: list[str] = Field(default_factory=list)
    sub_scores: dict[str, float] = Field(default_factory=dict)
    stage_1_passed: bool | None = None
    stage_1_similarity: float | None = None

    model_config = {"populate_by_name": True}


class PaperManifestEntry(BaseModel):
    paper_id: str
    source_file: str
    file_hash: str
    kind: str  # pdf | scanned_pdf | image
    page_count: int


class RunManifest(BaseModel):
    run_id: str
    input_dir: str
    started_at: str
    papers: list[PaperManifestEntry] = Field(default_factory=list)
    chapter_specs: list[ChapterSpec] = Field(default_factory=list)
