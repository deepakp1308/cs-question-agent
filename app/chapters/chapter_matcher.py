"""Match a question to one or more chapters using hybrid retrieval + LLM classifier."""
from __future__ import annotations

import json
from typing import Any

from ..adapters import LLMAdapter
from ..models import ChapterMatch, ChapterSpec, QuestionRecord
from ..retrieval import RetrievalStore


def _parse_classifier_json(text: str) -> dict[str, Any]:
    try:
        # Permissive: sometimes models wrap JSON in backticks.
        txt = text.strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            if txt.lower().startswith("json\n"):
                txt = txt[5:]
        return json.loads(txt)
    except Exception:
        return {"primary_chapter": None, "secondary_chapters": [], "confidence": 0.0}


def match_question(
    *,
    question: QuestionRecord,
    chapters: list[ChapterSpec],
    store: RetrievalStore,
    classifier: LLMAdapter,
    top_k: int = 10,
    prompt_version: str = "v1",
) -> ChapterMatch:
    # 1) Retrieval candidates: top-k textbook chunks by fused score.
    hits = store.search(
        question.verbatim_text + " " + question.normalized_text,
        k=top_k,
        source_types=["textbook"],
    )
    retrieval_strength = max((s for _, s in hits), default=0.0)

    # 2) Build candidate chapter list by collapsing hits per chapter.
    scores_by_chapter: dict[str, float] = {}
    for chunk, score in hits:
        scores_by_chapter[chunk.chapter_id] = max(scores_by_chapter.get(chunk.chapter_id, 0.0), score)
    candidate_ids = sorted(scores_by_chapter.keys(), key=lambda c: -scores_by_chapter[c])
    candidates = [
        {"chapter_id": cid, "retrieval_score": scores_by_chapter[cid]} for cid in candidate_ids
    ]

    # 3) LLM classifier confirms assignment.
    ch_lookup = {c.chapter_id: c for c in chapters}
    chapter_descriptions = "\n".join(
        f"- {c.chapter_id}: {c.title} (aliases: {', '.join(c.aliases) or 'none'})"
        for c in chapters
    ) or "(no chapters configured)"

    system = (
        "You are a chapter classifier. Given a question and a fixed list of chapter ids, "
        "select the single most likely primary chapter and up to two secondary chapters. "
        "Return strict JSON only."
    )
    user = (
        f"CHAPTERS:\n{chapter_descriptions}\n\n"
        f"CANDIDATES (retrieval): {json.dumps(candidates)}\n\n"
        f"QUESTION: {question.verbatim_text}\n\n"
        'Return JSON: {"primary_chapter": "ch_...", '
        '"secondary_chapters": ["ch_..."], "confidence": 0.0-1.0, "justification": "..."}'
    )
    resp = classifier.complete(system=system, user=user, json_mode=True, temperature=0.0)
    parsed = _parse_classifier_json(resp.text)

    # Validate against known chapter ids; fall back to top retrieval candidate.
    primary = parsed.get("primary_chapter")
    if primary not in ch_lookup and candidate_ids:
        primary = candidate_ids[0]
    secondary = [c for c in (parsed.get("secondary_chapters") or []) if c in ch_lookup and c != primary]

    classifier_confidence = float(parsed.get("confidence") or 0.0)

    return ChapterMatch(
        question_id=question.question_id,
        primary_chapter=primary,
        secondary_chapters=secondary,
        retrieval_strength=float(retrieval_strength),
        classifier_confidence=classifier_confidence,
        candidates=candidates,
    )
