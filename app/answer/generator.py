"""Retrieval-grounded answer generator with optional ensemble for confidence."""
from __future__ import annotations

import json
import re
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
    # Some models wrap output in a leading language tag.
    try:
        data = json.loads(txt)
    except Exception:
        # Try extracting the first {...} block.
        import re

        m = re.search(r"\{[\s\S]*\}", txt)
        if not m:
            return {}
        try:
            data = json.loads(m.group(0))
        except Exception:
            return {}
    return _normalize_answer_shape(data)


def _normalize_answer_shape(data: dict[str, Any]) -> dict[str, Any]:
    """Coerce flexible model output into the shape the orchestrator expects."""
    if not isinstance(data, dict):
        return {}
    out = dict(data)

    def _as_str(v: Any) -> str:
        if v is None:
            return ""
        if isinstance(v, str):
            return v
        if isinstance(v, list):
            return "\n".join(_as_str(x) for x in v if x is not None)
        return str(v)

    def _as_list_of_str(v: Any) -> list[str]:
        if v is None:
            return []
        if isinstance(v, list):
            return [_as_str(x) for x in v if x]
        if isinstance(v, str):
            # Split numbered or bulleted strings into a list.
            import re

            parts = re.split(r"(?:\n+|\s*\d+\.\s+|\s*-\s+|\s*\*\s+)", v)
            return [p.strip() for p in parts if p and p.strip()]
        return [str(v)]

    out["direct_answer"] = _as_str(out.get("direct_answer"))
    out["exam_style_answer"] = _as_str(out.get("exam_style_answer"))
    out["step_by_step_explanation"] = _as_list_of_str(out.get("step_by_step_explanation"))
    if "simple_example" in out:
        out["simple_example"] = _as_str(out.get("simple_example")) or None
    if "common_mistake" in out:
        out["common_mistake"] = _as_str(out.get("common_mistake")) or None
    # evidence_chunk_ids must be a flat list of strings.
    ec = out.get("evidence_chunk_ids") or []
    if isinstance(ec, str):
        ec = [ec]
    out["evidence_chunk_ids"] = [str(x) for x in ec if x]
    try:
        out["answer_confidence"] = float(out.get("answer_confidence") or 0.0)
    except (TypeError, ValueError):
        out["answer_confidence"] = 0.0
    return out


_DOT_LEADER = re.compile(r"\.{6,}")
_BLANK_UNDERSCORE = re.compile(r"_{4,}")


def _clean_question(text: str) -> str:
    """Strip answer-space artefacts that Cambridge papers use (dot leaders, blank lines)."""
    t = _DOT_LEADER.sub(" ", text)
    t = _BLANK_UNDERSCORE.sub(" ", t)
    # Collapse repeated whitespace.
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def _build_prompt(question: QuestionRecord, context: str, teaching_style: str) -> tuple[str, str]:
    system = (
        "You are an expert 10th-grade computer science teacher preparing Cambridge IGCSE students. "
        f"Teaching style: {teaching_style}. "
        "Your student is 15 and seeing this topic for the first time. "
        "You MUST ground every statement in the provided CHAPTER CONTEXT chunks. "
        "You MUST return a single JSON object and nothing else — no prose, no markdown fences.\n\n"
        "JSON schema (every key is required):\n"
        "{\n"
        '  "direct_answer": string,              // one sentence or short phrase\n'
        '  "exam_style_answer": string,          // 1-3 sentences in exam-appropriate language\n'
        '  "step_by_step_explanation": [string], // 2-4 steps, plain English first\n'
        '  "simple_example": string,             // concrete everyday example or short number example\n'
        '  "common_mistake": string,             // one mistake students typically make\n'
        '  "evidence_chunk_ids": [string],       // ids from the [chunk:...] tags you used, e.g. "ch_hardware_0001"\n'
        '  "answer_confidence": number           // 0 to 1\n'
        "}"
    )
    cleaned_q = _clean_question(question.verbatim_text)
    user = (
        f"QUESTION: {cleaned_q}\n"
        f"MARKS: {question.marks or 'unspecified'}\n\n"
        f"CHAPTER CONTEXT (cite the [chunk:...] ids you use in evidence_chunk_ids):\n{context}\n\n"
        "Return the JSON object now."
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
