"""Grounding-ratio and ensemble-agreement helpers (composite confidence inputs)."""
from __future__ import annotations

import re
from collections.abc import Iterable

from rapidfuzz import fuzz

_CLAIM_SPLIT = re.compile(r"(?<=[.!?])\s+")


def split_claims(text: str) -> list[str]:
    parts = [p.strip() for p in _CLAIM_SPLIT.split(text.strip()) if p.strip()]
    # Filter out very short fragments (less than 3 words) — those are usually not claims.
    return [p for p in parts if len(p.split()) >= 3]


def grounding_ratio(
    *,
    answer_text: str,
    evidence_texts: Iterable[str],
    threshold: float = 55.0,
) -> float:
    """Fraction of the answer's claims that have at least one evidence chunk with
    a partial-ratio fuzzy match above `threshold` (rapidfuzz 0–100 scale)."""
    claims = split_claims(answer_text)
    if not claims:
        return 0.0
    evidence_texts = list(evidence_texts)
    if not evidence_texts:
        return 0.0
    supported = 0
    for c in claims:
        for e in evidence_texts:
            if fuzz.partial_ratio(c, e) >= threshold:
                supported += 1
                break
    return supported / len(claims)


def semantic_agreement(a: str, b: str) -> float:
    """Cheap 0–1 semantic-similarity proxy using token-set ratio."""
    if not a or not b:
        return 0.0
    return fuzz.token_set_ratio(a, b) / 100.0
