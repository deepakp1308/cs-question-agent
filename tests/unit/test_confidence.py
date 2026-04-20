from app.config import QualityBlock
from app.judge.score_aggregator import confidence_tier
from app.models import AnswerRecord, CompositeConfidence, JudgeResult


def _answer(composite: float, grounding: float) -> AnswerRecord:
    return AnswerRecord(
        question_id="q1",
        direct_answer="x",
        exam_style_answer="x",
        step_by_step_explanation=[],
        evidence_chunk_ids=["e1"],
        confidence=CompositeConfidence(
            composite=composite,
            ensemble_agreement=0.9,
            grounding_ratio=grounding,
            retrieval_strength=0.9,
            model_self_reported=0.9,
        ),
    )


def _jr(passed: bool, score: float = 0.9) -> JudgeResult:
    return JudgeResult(**{"pass": passed}, score=score)


def test_auto_publish_when_all_green():
    q = QualityBlock()
    tier, reasons = confidence_tier(
        answer=_answer(0.96, 0.95),
        extraction=_jr(True),
        match=_jr(True),
        answer_judge_result=_jr(True),
        quality=q,
    )
    assert tier == "auto_publish"
    assert reasons == []


def test_gated_publish_in_middle_band():
    q = QualityBlock()
    tier, _ = confidence_tier(
        answer=_answer(0.88, 0.95),
        extraction=_jr(True),
        match=_jr(True),
        answer_judge_result=_jr(True),
        quality=q,
    )
    assert tier == "gated_publish"


def test_grounding_floor_forces_quarantine_even_with_high_composite():
    q = QualityBlock()
    tier, reasons = confidence_tier(
        answer=_answer(0.99, 0.50),
        extraction=_jr(True),
        match=_jr(True),
        answer_judge_result=_jr(True),
        quality=q,
    )
    assert tier == "quarantine"
    assert any("grounding_ratio_floor" in r for r in reasons)


def test_judge_failure_forces_quarantine():
    q = QualityBlock()
    tier, reasons = confidence_tier(
        answer=_answer(0.99, 0.95),
        extraction=_jr(False),
        match=_jr(True),
        answer_judge_result=_jr(True),
        quality=q,
    )
    assert tier == "quarantine"
    assert any("extraction_judge_failed" in r for r in reasons)
