"""Two-stage extraction judge.

Stage 1: deterministic text-diff verifier. Uses the source-PDF text of the
question's bounding boxes and compares with `verbatim_text` via rapidfuzz.

Stage 2: LLM judge. Only invoked when Stage 1 does not pass.
"""
from __future__ import annotations

import json
import re

from rapidfuzz import fuzz

from ..adapters import LLMAdapter
from ..extract.pdf_parser import parse_pdf_lines
from ..models import JudgeResult, QuestionRecord

_WS = re.compile(r"\s+")
_LEADING_NUMBERING = re.compile(
    r"^\s*(?:Q)?(?:\d{1,3}[.)]|\(?(?:[a-z]|i|ii|iii|iv|v|vi|vii|viii|ix|x)\)|[a-z][.)])\s+",
    re.IGNORECASE,
)
_TRAILING_MARKS = re.compile(r"\s*[\[(]\s*\d{1,2}\s*(?:marks?)?\s*[\])]\s*$", re.IGNORECASE)


def _canonical(text: str) -> str:
    """Normalize the same way the extractor does so the diff is apples-to-apples.

    We compare prompt bodies: strip any leading numbering/enumerator token,
    strip trailing marks, collapse whitespace, lowercase.
    """
    out_lines: list[str] = []
    for line in text.splitlines():
        stripped = _LEADING_NUMBERING.sub("", line, count=1)
        stripped = _TRAILING_MARKS.sub("", stripped)
        out_lines.append(stripped)
    return _WS.sub(" ", "\n".join(out_lines)).strip().lower()


def _source_text_for(question: QuestionRecord) -> str:
    """Reconstruct the source text for the question's bbox refs."""
    if not question.bbox_refs:
        return ""
    lines = parse_pdf_lines(question.source_file)
    pages = {b.page for b in question.bbox_refs}
    # Collect all lines from those pages whose bbox overlaps any question bbox.
    out: list[str] = []
    for ln in lines:
        if ln.page not in pages:
            continue
        lx0, ly0, lx1, ly1 = ln.bbox
        for b in question.bbox_refs:
            if b.page != ln.page:
                continue
            # Overlap check (loose; y-overlap is sufficient for single-column exam pages).
            if not (ly1 < b.y0 - 2 or ly0 > b.y1 + 2):
                out.append(ln.text)
                break
    return "\n".join(out)


def judge_extraction(
    *,
    question: QuestionRecord,
    judge_llm: LLMAdapter | None,
    stage1_threshold: float = 0.99,
    stage1_escalate_threshold: float = 0.95,
    invoke_llm: bool = True,
) -> JudgeResult:
    src = _source_text_for(question)
    ratio = 0.0
    if src and question.verbatim_text:
        ratio = fuzz.ratio(_canonical(src), _canonical(question.verbatim_text)) / 100.0

    if ratio >= stage1_threshold:
        return JudgeResult(
            **{"pass": True},
            score=ratio,
            sub_scores={"text_fidelity": ratio},
            stage_1_passed=True,
            stage_1_similarity=ratio,
        )

    if ratio < stage1_escalate_threshold or not invoke_llm or judge_llm is None:
        return JudgeResult(
            **{"pass": False},
            score=ratio,
            issues=[f"stage_1_similarity={ratio:.3f} below hard threshold"],
            repair_instructions=["re-extract the question with page-crop context"],
            sub_scores={"text_fidelity": ratio},
            stage_1_passed=False,
            stage_1_similarity=ratio,
        )

    # Stage 2: LLM judge.
    system = (
        "You are a strict extraction judge. Compare the SOURCE text to the EXTRACTED text. "
        "Return strict JSON with pass/score and issues. Fail on missing numbering, marks, or wording."
    )
    user = (
        f"SOURCE:\n{src}\n\n"
        f"EXTRACTED verbatim_text:\n{question.verbatim_text}\n\n"
        f"EXTRACTED numbering_path: {question.numbering_path}\n"
        f"EXTRACTED marks: {question.marks}\n\n"
        f"STAGE_1_SIMILARITY: {ratio:.3f}\n"
        'Return JSON: {"pass": bool, "score": 0-1, "issues": [str], "repair_instructions": [str]}'
    )
    resp = judge_llm.complete(system=system, user=user, json_mode=True, temperature=0.0)
    try:
        data = json.loads(resp.text.strip().strip("`"))
    except Exception:
        data = {"pass": False, "score": ratio, "issues": ["judge returned non-JSON"]}
    return JudgeResult(
        **{"pass": bool(data.get("pass"))},
        score=float(data.get("score", ratio)),
        issues=data.get("issues") or [],
        repair_instructions=data.get("repair_instructions") or [],
        sub_scores={"text_fidelity": ratio},
        stage_1_passed=False,
        stage_1_similarity=ratio,
    )
