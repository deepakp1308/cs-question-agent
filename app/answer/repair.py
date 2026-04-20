"""Answer repair loop — re-prompts the generator with judge feedback."""
from __future__ import annotations

import json

from ..adapters import LLMAdapter
from ..config import QualityBlock
from ..models import AnswerRecord, ChapterMatch, CompositeConfidence, JudgeResult, QuestionRecord
from ..retrieval import RetrievalStore
from .generator import _build_context, _parse_answer_json
from .grounding import grounding_ratio, semantic_agreement


def repair_answer(
    *,
    question: QuestionRecord,
    match: ChapterMatch,
    store: RetrievalStore,
    generator: LLMAdapter,
    previous: AnswerRecord,
    judge: JudgeResult,
    quality: QualityBlock,
    teaching_style: str,
) -> AnswerRecord:
    context, chunk_ids, chunk_texts = _build_context(question=question, match=match, store=store)
    system = (
        "You are revising a teaching answer that a strict judge rejected. "
        f"Teaching style: {teaching_style}. "
        "Fix ONLY the issues listed; keep what worked. Ground every claim in the provided chapter context. "
        "Return strict JSON."
    )
    user = (
        f"QUESTION: {question.verbatim_text}\n"
        f"MARKS: {question.marks or 'unspecified'}\n\n"
        f"PREVIOUS ANSWER (JSON): {previous.model_dump_json()}\n\n"
        f"JUDGE ISSUES: {json.dumps(judge.issues)}\n"
        f"REPAIR INSTRUCTIONS: {json.dumps(judge.repair_instructions)}\n\n"
        f"CHAPTER CONTEXT:\n{context}\n\n"
        "Return the same JSON schema as the original answer."
    )
    resp = generator.complete(system=system, user=user, json_mode=True, temperature=0.3)
    data = _parse_answer_json(resp.text)
    text = data.get("exam_style_answer", "") or data.get("direct_answer", "")
    g_ratio = grounding_ratio(
        answer_text=(text + " " + " ".join(data.get("step_by_step_explanation") or [])),
        evidence_texts=chunk_texts,
    )
    agreement = semantic_agreement(previous.exam_style_answer, text)
    w = quality.confidence_weights
    composite = (
        w.ensemble_agreement * agreement
        + w.grounding_ratio * g_ratio
        + w.retrieval_strength * match.retrieval_strength
    )
    composite = max(0.0, min(1.0, composite))
    confidence = CompositeConfidence(
        composite=composite,
        ensemble_agreement=agreement,
        grounding_ratio=g_ratio,
        retrieval_strength=match.retrieval_strength,
        model_self_reported=float(data.get("answer_confidence") or previous.confidence.model_self_reported),
    )
    returned_ids = [c for c in (data.get("evidence_chunk_ids") or []) if c in chunk_ids]
    if not returned_ids:
        returned_ids = previous.evidence_chunk_ids

    return AnswerRecord(
        question_id=question.question_id,
        direct_answer=data.get("direct_answer") or previous.direct_answer,
        exam_style_answer=data.get("exam_style_answer") or previous.exam_style_answer,
        step_by_step_explanation=data.get("step_by_step_explanation") or previous.step_by_step_explanation,
        simple_example=data.get("simple_example") or previous.simple_example,
        common_mistake=data.get("common_mistake") or previous.common_mistake,
        evidence_chunk_ids=returned_ids,
        confidence=confidence,
    )
