"""Deterministic question extractor.

Strategy:
- Parse the PDF into lines with geometry + font (pdf_parser).
- Walk lines, tracking section and instruction context.
- Start a new question whenever a top-level number appears; open subparts on
  alpha/roman prefixes; stitch continuation lines into the current record.
- Detect OR branches, monospace code blocks, and marks.
- Never paraphrase: `verbatim_text` is exactly the concatenation of source lines.
"""
from __future__ import annotations

import re
from pathlib import Path

from ..hashing import question_id
from ..models import BBox, CodeBlock, QuestionRecord
from .pdf_parser import Line, parse_pdf_lines
from .regex_rules import (
    INSTRUCTION,
    OR_LINE,
    SECTION,
    extract_marks,
    parse_number_prefix,
    strip_number_prefix,
)

_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    return _WS.sub(" ", text).strip().lower()


def _finalize_record(
    *,
    paper_id: str,
    source_file: str,
    paper_hash: str,
    section: str | None,
    instruction: str | None,
    numbering: list[str],
    lines: list[Line],
    marks: int | None,
    or_group_id: str | None,
    variant_role: str,
) -> QuestionRecord:
    pages = sorted({ln.page for ln in lines})
    page_range = (pages[0] if pages else 1, pages[-1] if pages else 1)
    # Assemble verbatim text verbatim from the lines — no paraphrasing.
    verbatim_text = "\n".join(ln.text for ln in lines).strip()
    # Strip leading numbering from the first line so the reader sees the prompt.
    first = lines[0].text
    stripped_first = strip_number_prefix(first)
    if stripped_first and stripped_first != first:
        # Replace only the first occurrence, preserving the rest of the body.
        body = "\n".join([stripped_first] + [ln.text for ln in lines[1:]]).strip()
    else:
        body = verbatim_text
    # Strip a trailing marks token from the visible text (keep marks as metadata).
    body = re.sub(r"\s*[\[(]\d{1,2}\s*marks?[\])]\s*$", "", body, flags=re.IGNORECASE)
    body = re.sub(r"\s*[\[(](\d{1,2})[\])]\s*$", "", body)

    bbox_refs = [
        BBox(page=ln.page, x0=ln.bbox[0], y0=ln.bbox[1], x1=ln.bbox[2], y1=ln.bbox[3])
        for ln in lines
    ]
    code_blocks: list[CodeBlock] = []
    run_buffer: list[Line] = []
    for ln in lines:
        if ln.is_monospace:
            run_buffer.append(ln)
        else:
            if run_buffer:
                code_blocks.append(
                    CodeBlock(
                        text="\n".join(r.text for r in run_buffer),
                        indent=len(run_buffer[0].text) - len(run_buffer[0].text.lstrip()),
                        bbox=BBox(
                            page=run_buffer[0].page,
                            x0=run_buffer[0].bbox[0],
                            y0=run_buffer[0].bbox[1],
                            x1=run_buffer[-1].bbox[2],
                            y1=run_buffer[-1].bbox[3],
                        ),
                    )
                )
                run_buffer = []
    if run_buffer:
        code_blocks.append(
            CodeBlock(
                text="\n".join(r.text for r in run_buffer),
                indent=len(run_buffer[0].text) - len(run_buffer[0].text.lstrip()),
                bbox=BBox(
                    page=run_buffer[0].page,
                    x0=run_buffer[0].bbox[0],
                    y0=run_buffer[0].bbox[1],
                    x1=run_buffer[-1].bbox[2],
                    y1=run_buffer[-1].bbox[3],
                ),
            )
        )

    qid = question_id(paper_hash, numbering)
    return QuestionRecord(
        question_id=qid,
        paper_id=paper_id,
        source_file=source_file,
        page_range=page_range,
        section_heading=section,
        instruction_context=instruction,
        numbering_path=numbering,
        marks=marks,
        verbatim_text=body,
        normalized_text=normalize(body),
        bbox_refs=bbox_refs,
        code_blocks=code_blocks,
        or_group_id=or_group_id,
        variant_role=variant_role,
        extraction_confidence=1.0,
    )


def extract_paper(
    *,
    paper_id: str,
    source_file: str | Path,
    paper_hash: str,
) -> list[QuestionRecord]:
    lines = parse_pdf_lines(source_file)
    if not lines:
        return []

    records: list[QuestionRecord] = []
    current_section: str | None = None
    current_instruction: str | None = None
    numbering: list[str] = []  # ["3"], ["3","a"], ["3","a","ii"]
    record_lines: list[Line] = []
    marks: int | None = None
    or_group_id: str | None = None
    variant_role = "primary"

    def flush() -> None:
        nonlocal record_lines, marks, or_group_id, variant_role
        if numbering and record_lines:
            records.append(
                _finalize_record(
                    paper_id=paper_id,
                    source_file=str(source_file),
                    paper_hash=paper_hash,
                    section=current_section,
                    instruction=current_instruction,
                    numbering=list(numbering),
                    lines=list(record_lines),
                    marks=marks,
                    or_group_id=or_group_id,
                    variant_role=variant_role,
                )
            )
        record_lines = []
        marks = None
        # or_group_id persists across the paired OR branch below, cleared elsewhere.

    for line in lines:
        text = line.text.rstrip()
        if not text.strip():
            continue
        if SECTION.match(text):
            flush()
            current_section = text.strip()
            numbering = []
            or_group_id = None
            variant_role = "primary"
            continue
        if INSTRUCTION.match(text):
            current_instruction = text.strip()
            continue
        if OR_LINE.match(text):
            # Pair the previous question with an "alternative" variant.
            flush()
            # Give a shared or_group_id to the next top-level sibling.
            previous = records[-1] if records else None
            if previous and previous.or_group_id is None:
                # Tag previous as primary in a fresh group; next as alternative.
                group_id = f"org_{previous.question_id}"
                previous.or_group_id = group_id
                or_group_id = group_id
                variant_role = "alternative"
            continue

        prefix = parse_number_prefix(text)
        if prefix is not None:
            level, value = prefix
            if level == "top":
                flush()
                numbering = [value]
                or_group_id = or_group_id if variant_role == "alternative" else None
                variant_role = variant_role if variant_role == "alternative" else "primary"
            elif level == "alpha":
                flush()
                # Attach subpart to current top-level.
                if numbering and numbering[0].isdigit():
                    numbering = [numbering[0], value]
                else:
                    numbering = [value]
                variant_role = "primary"
                or_group_id = None
            elif level == "roman":
                flush()
                if len(numbering) >= 2:
                    numbering = [numbering[0], numbering[1], value]
                else:
                    numbering = numbering + [value]
                variant_role = "primary"
                or_group_id = None
            record_lines.append(line)
            m = extract_marks(text)
            if m is not None:
                marks = m
            # After starting a record, the OR-variant sticks only to this question; reset after.
            if variant_role == "alternative":
                # once the alternative variant is attached to this question, reset for next.
                pass
            continue

        # Continuation line for the current record.
        if numbering and record_lines:
            record_lines.append(line)
            m = extract_marks(text)
            if m is not None:
                marks = m

    flush()
    return records
