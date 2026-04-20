"""Parse chapter selectors from markdown / text. Screenshot input is out of
scope for the pure-text MVP but the LLM adapter receives structured text so it
works against either source.

Input formats supported:
- Markdown with `# Chapter title` headings; each heading becomes a ChapterSpec.
- Simple `ch_id: Title` lines (one per line).
"""
from __future__ import annotations

import re
from pathlib import Path

from ..models import ChapterSpec

_HEAD = re.compile(r"^#\s+(.+?)\s*$")
_ID_LINE = re.compile(r"^\s*(ch_[a-z0-9_]+)\s*:\s*(.+?)\s*$")


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return f"ch_{s}"


def parse_selector_file(path: str | Path) -> list[ChapterSpec]:
    text = Path(path).read_text()
    specs: list[ChapterSpec] = []
    for line in text.splitlines():
        m = _ID_LINE.match(line)
        if m:
            specs.append(ChapterSpec(chapter_id=m.group(1), title=m.group(2)))
            continue
        m = _HEAD.match(line)
        if m:
            title = m.group(1)
            specs.append(ChapterSpec(chapter_id=_slug(title), title=title))
    # Deduplicate by chapter_id keeping first occurrence.
    seen: set[str] = set()
    deduped: list[ChapterSpec] = []
    for s in specs:
        if s.chapter_id in seen:
            continue
        seen.add(s.chapter_id)
        deduped.append(s)
    return deduped


def parse_selector_dir(path: str | Path) -> list[ChapterSpec]:
    root = Path(path)
    if not root.exists():
        return []
    specs: list[ChapterSpec] = []
    for p in sorted(root.iterdir()):
        if p.is_file() and p.suffix.lower() in (".md", ".txt"):
            specs.extend(parse_selector_file(p))
    # Deduplicate across files.
    seen: set[str] = set()
    deduped: list[ChapterSpec] = []
    for s in specs:
        if s.chapter_id in seen:
            continue
        seen.add(s.chapter_id)
        deduped.append(s)
    return deduped
