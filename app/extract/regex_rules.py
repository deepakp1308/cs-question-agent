"""Deterministic regex patterns used by the question extractor and judges."""
from __future__ import annotations

import re

# Matches top-level numbering like "1." "12)" "Q3."
NUMBER_TOP = re.compile(r"^\s*(?:Q)?(\d{1,3})\s*[.)]\s+", re.IGNORECASE)

# Matches subparts like "(a)" "a)" "(i)" "i."
NUMBER_ALPHA = re.compile(r"^\s*\(?([a-z])\)\s+", re.IGNORECASE)
NUMBER_ROMAN = re.compile(r"^\s*\(?((?:i|ii|iii|iv|v|vi|vii|viii|ix|x))\)\s+", re.IGNORECASE)

# Marks in brackets: [2], [2 marks], (2 marks), (2)
MARKS = re.compile(r"[\[(](\d{1,2})\s*(?:marks?)?[\])]", re.IGNORECASE)

# Section headings
SECTION = re.compile(r"^\s*(Section\s+[A-Z]|PART\s+[A-Z0-9]+)\b.*$", re.IGNORECASE)

# Instruction lines ("Answer all questions.", "Attempt any three.")
INSTRUCTION = re.compile(r"^\s*(Answer\s+.+\.|Attempt\s+.+\.)\s*$", re.IGNORECASE)

# OR-branch between subparts
OR_LINE = re.compile(r"^\s*OR\s*$", re.IGNORECASE)


def parse_number_prefix(line: str) -> tuple[str, str] | None:
    """Return (level, value) if the line starts with a numbering token, else None.
    level ∈ {"top","alpha","roman"}."""
    m = NUMBER_TOP.match(line)
    if m:
        return "top", m.group(1)
    m = NUMBER_ROMAN.match(line)
    if m:
        return "roman", m.group(1).lower()
    m = NUMBER_ALPHA.match(line)
    if m:
        return "alpha", m.group(1).lower()
    return None


def strip_number_prefix(line: str) -> str:
    for pat in (NUMBER_TOP, NUMBER_ROMAN, NUMBER_ALPHA):
        m = pat.match(line)
        if m:
            return line[m.end() :]
    return line


def extract_marks(line: str) -> int | None:
    m = MARKS.search(line)
    if m:
        try:
            return int(m.group(1))
        except ValueError:
            return None
    return None
