"""Publish-decision tiers using composite confidence + hard gates."""
from __future__ import annotations

from ..config import QualityBlock
from ..models import AnswerRecord, JudgeResult


def confidence_tier(
    *,
    answer: AnswerRecord,
    extraction: JudgeResult,
    match: JudgeResult,
    answer_judge_result: JudgeResult,
    quality: QualityBlock,
) -> tuple[str, list[str]]:
    """Return (tier, reasons). tier ∈ {auto_publish, gated_publish, quarantine}."""
    reasons: list[str] = []
    # Hard gates
    if not extraction.pass_:
        reasons.append(f"extraction_judge_failed: {extraction.issues}")
    if not match.pass_:
        reasons.append(f"match_judge_failed: {match.issues}")
    if not answer_judge_result.pass_:
        reasons.append(f"answer_judge_failed: {answer_judge_result.issues}")
    if answer.confidence.grounding_ratio < quality.grounding_ratio_floor:
        reasons.append(
            f"grounding_ratio_floor: {answer.confidence.grounding_ratio:.2f} < {quality.grounding_ratio_floor}"
        )

    if reasons:
        return "quarantine", reasons

    c = answer.confidence.composite
    if c >= 0.95:
        return "auto_publish", []
    if c >= 0.85:
        return "gated_publish", [f"composite={c:.2f} in gated tier"]
    return "quarantine", [f"composite={c:.2f} < 0.85"]
