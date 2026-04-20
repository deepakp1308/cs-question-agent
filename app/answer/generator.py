"""Retrieval-grounded answer generator with optional ensemble for confidence."""
from __future__ import annotations

import json
from typing import Any

from ..adapters import LLMAdapter
from ..config import QualityBlock
from ..models import AnswerRecord, ChapterMatch, CompositeConfidence, QuestionRecord
from ..retrieval import RetrievalStore
from .grounding import grounding_ratio, semantic_agreement


def _build_context(
    *,
    question: QuestionRecord,
    match: ChapterMatch,
    store: RetrievalStore,
    k: int = 6,
) -> tuple[str, list[str], list[str]]:
    chapter_ids = [c for c in [match.primary_chapter, *match.secondary_chapters] if c]
    hits = store.search(
        question.verbatim_text,
        k=k,
        chapter_ids=chapter_ids,
    )
    lines: list[str] = []
    chunk_ids: list[str] = []
    chunk_texts: list[str] = []
    for chunk, _score in hits:
        tag = f"[chunk:{chunk.chunk_id}]"
        lines.append(f"{tag} {chunk.text}")
        chunk_ids.append(chunk.chunk_id)
        chunk_texts.append(chunk.text)
    return "\n\n".join(lines), chunk_ids, chunk_texts


def _parse_answer_json(text: str) -> dict[str, Any]:
    txt = text.strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt.lower().startswith("json\n"):
            txt = txt[5:]
    try:
        return json.loads(txt)
    except Exception:
        return {}


def _build_prompt(question: QuestionRecord, context: str, teaching_style: str) -> tuple[str, str]:
    system = (
        "You are an expert 10th-grade computer science teacher. "
        f"Teaching style: {teaching_style}. "
        "Your student is 15 and seeing this topic for the first time. "
        "Answer grounded ONLY in the provided chapter context. "
        "Return strict JSON with the required fields."
    )
    user = (
        f"QUESTION: {question.verbatim_text}\n"
        f"MARKS: {question.marks or 'unspecified'}\n\n"
        f"CHAPTER CONTEXT:\n{context}\n\n"
        "Return JSON with keys: direct_answer, exam_style_answer, "
        "step_by_step_explanation (array of strings), simple_example, common_mistake, "
        "evidence_chunk_ids (array of the [chunk:...] ids used), answer_confidence (0-1)."
    )
    return system, user


def generate_answer(
    *,
    question: QuestionRecord,
    match: ChapterMatch,
    store: RetrievalStore,
    generator: LLMAdapter,
    quality: QualityBlock,
    teaching_style: str,
    ensemble: bool = True,
    prompt_version: str = "v1",
) -> AnswerRecord:
    context, chunk_ids, chunk_texts = _build_context(question=question, match=match, store=store)
    system, user = _build_prompt(question, context, teaching_style)

    primary_resp = generator.complete(system=system, user=user, json_mode=True, temperature=0.2)
    primary = _parse_answer_json(primary_resp.text)
    primary_text = primary.get("exam_style_answer", "") or primary.get("direct_answer", "")

    # Ensemble for confidence: one extra generation with different temperature.
    agreement = 1.0
    if ensemble:
        alt_resp = generator.complete(system=system, user=user, json_mode=True, temperature=0.6)
        alt = _parse_answer_json(alt_resp.text)
        alt_text = alt.get("exam_style_answer", "") or alt.get("direct_answer", "")
        agreement = semantic_agreement(primary_text, alt_text)

    g_ratio = grounding_ratio(
        answer_text=(primary_text + " " + " ".join(primary.get("step_by_step_explanation") or [])),
        evidence_texts=chunk_texts,
    )

    # Retrieval strength from match; fall back if missing.
    retrieval_strength = float(match.retrieval_strength or 0.0)
    self_reported = float(primary.get("answer_confidence") or 0.0)

    w = quality.confidence_weights
    composite = (
        w.ensemble_agreement * agreement
        + w.grounding_ratio * g_ratio
        + w.retrieval_strength * retrieval_strength
    )
    composite = max(0.0, min(1.0, composite))

    confidence = CompositeConfidence(
        composite=composite,
        ensemble_agreement=agreement,
        grounding_ratio=g_ratio,
        retrieval_strength=retrieval_strength,
        model_self_reported=self_reported,
    )

    # Clamp returned evidence chunk ids to the ones that actually exist in this prompt.
    returned_ids = [c for c in (primary.get("evidence_chunk_ids") or []) if c in chunk_ids]
    if not returned_ids:
        returned_ids = chunk_ids[:2] or ["src_fallback_000"]

    return AnswerRecord(
        question_id=question.question_id,
        direct_answer=primary.get("direct_answer") or primary_text[:200] or "See retrieved source.",
        exam_style_answer=primary.get("exam_style_answer") or primary_text or "",
        step_by_step_explanation=primary.get("step_by_step_explanation") or [],
        simple_example=primary.get("simple_example"),
        common_mistake=primary.get("common_mistake"),
        evidence_chunk_ids=returned_ids,
        confidence=confidence,
    )
