"""Chapter-match judge: does the assigned chapter really fit the question?"""
from __future__ import annotations

import json

from ..adapters import LLMAdapter
from ..models import ChapterMatch, ChapterSpec, JudgeResult, QuestionRecord


def judge_match(
    *,
    question: QuestionRecord,
    match: ChapterMatch,
    chapters: list[ChapterSpec],
    judge_llm: LLMAdapter,
) -> JudgeResult:
    if not match.primary_chapter:
        return JudgeResult(
            **{"pass": False},
            score=0.0,
            issues=["no primary chapter assigned"],
            repair_instructions=["re-run chapter matcher with enlarged candidate set"],
        )
    ch_by_id = {c.chapter_id: c for c in chapters}
    primary = ch_by_id.get(match.primary_chapter)
    system = (
        "You are a chapter match judge. Decide whether the primary chapter fits the question. "
        "Return strict JSON."
    )
    user = (
        f"QUESTION: {question.verbatim_text}\n\n"
        f"PRIMARY CHAPTER: {match.primary_chapter} "
        f"(title: {primary.title if primary else ''}, "
        f"keywords: {', '.join(primary.keywords) if primary else ''})\n"
        f"SECONDARY CHAPTERS: {match.secondary_chapters}\n"
        f"RETRIEVAL_STRENGTH: {match.retrieval_strength:.3f}\n"
        f"CLASSIFIER_CONFIDENCE: {match.classifier_confidence:.3f}\n\n"
        'Return JSON: {"pass": bool, "score": 0-1, "issues": [str], "better_chapter": "ch_... or null"}'
    )
    resp = judge_llm.complete(system=system, user=user, json_mode=True, temperature=0.0)
    try:
        data = json.loads(resp.text.strip().strip("`"))
    except Exception:
        data = {"pass": True, "score": match.classifier_confidence, "issues": ["non-JSON judge"]}
    return JudgeResult(
        **{"pass": bool(data.get("pass", True))},
        score=float(data.get("score", match.classifier_confidence)),
        issues=data.get("issues") or [],
        repair_instructions=(
            [f"reclassify to {data['better_chapter']}"] if data.get("better_chapter") else []
        ),
    )
