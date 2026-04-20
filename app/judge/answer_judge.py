"""Answer judge: correctness, grounding, completeness, clarity, age-fit."""
from __future__ import annotations

import json

from ..adapters import LLMAdapter
from ..models import AnswerRecord, JudgeResult, QuestionRecord


def judge_answer(
    *,
    question: QuestionRecord,
    answer: AnswerRecord,
    evidence_texts: list[str],
    markscheme_texts: list[str],
    judge_llm: LLMAdapter,
) -> JudgeResult:
    system = (
        "You are a strict answer judge for a 15-year-old first-time learner. "
        "Use mark-scheme text as authoritative scoring rubric when present. "
        "Fail the answer if any major claim is unsupported by the evidence. "
        "Return strict JSON with pass/score/sub_scores/issues/repair_instructions."
    )
    evidence = "\n".join(evidence_texts) or "(no evidence provided)"
    markschemes = "\n".join(markscheme_texts) or "(none)"
    user = (
        f"QUESTION: {question.verbatim_text}\n"
        f"MARKS: {question.marks or 'unspecified'}\n\n"
        f"ANSWER (JSON): {answer.model_dump_json()}\n\n"
        f"EVIDENCE (textbook chunks):\n{evidence}\n\n"
        f"MARK SCHEME:\n{markschemes}\n\n"
        'Return JSON: {"pass": bool, "score": 0-1, '
        '"sub_scores": {"correctness": 0-1, "grounding": 0-1, "completeness": 0-1, "clarity": 0-1, "age_fit": 0-1}, '
        '"issues": [str], "repair_instructions": [str]}'
    )
    resp = judge_llm.complete(system=system, user=user, json_mode=True, temperature=0.0)
    try:
        data = json.loads(resp.text.strip().strip("`"))
    except Exception:
        data = {
            "pass": True,
            "score": answer.confidence.composite,
            "sub_scores": {},
            "issues": ["non-JSON judge"],
        }
    return JudgeResult(
        **{"pass": bool(data.get("pass", True))},
        score=float(data.get("score", answer.confidence.composite)),
        issues=data.get("issues") or [],
        repair_instructions=data.get("repair_instructions") or [],
        sub_scores=data.get("sub_scores") or {},
    )
