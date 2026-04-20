"""Heading-aware chunker for chapter sources and mark schemes."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Chunk:
    chunk_id: str
    chapter_id: str
    source_file: str
    source_type: str  # textbook | markscheme | notes | syllabus
    page: int
    heading_path: list[str]
    text: str
    token_count: int = 0
    metadata: dict = field(default_factory=dict)


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


def _word_count(text: str) -> int:
    return len(text.split())


def chunk_text_file(
    *,
    path: str | Path,
    chapter_id: str,
    source_type: str = "textbook",
    target_words: int = 350,
    overlap_words: int = 50,
) -> list[Chunk]:
    """Chunk a markdown or plain-text file. Chunks never cross a top-level heading."""
    path = Path(path)
    text = path.read_text()
    lines = text.splitlines()
    sections: list[tuple[list[str], list[str]]] = []
    current_heading_path: list[str] = []
    current_lines: list[str] = []

    for line in lines:
        m = _HEADING.match(line)
        if m:
            # Flush current section.
            if current_lines:
                sections.append((list(current_heading_path), current_lines))
                current_lines = []
            level = len(m.group(1))
            title = m.group(2).strip()
            current_heading_path = current_heading_path[: level - 1] + [title]
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((list(current_heading_path), current_lines))

    chunks: list[Chunk] = []
    chunk_counter = 0
    for heading_path, body_lines in sections:
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        words = body.split()
        if not words:
            continue
        step = max(1, target_words - overlap_words)
        for start in range(0, len(words), step):
            piece = " ".join(words[start : start + target_words])
            if not piece.strip():
                continue
            chunk_counter += 1
            cid = f"{chapter_id}_{chunk_counter:04d}"
            chunks.append(
                Chunk(
                    chunk_id=cid,
                    chapter_id=chapter_id,
                    source_file=str(path),
                    source_type=source_type,
                    page=1,
                    heading_path=list(heading_path),
                    text=piece,
                    token_count=_word_count(piece),
                )
            )
            if start + target_words >= len(words):
                break
    return chunks
