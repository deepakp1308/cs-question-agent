"""Discover inputs on disk and build a run manifest."""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

from ..hashing import sha256_file
from ..models import PaperManifestEntry, RunManifest

PDF_SUFFIXES = {".pdf"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}


def _detect_kind(path: Path) -> str:
    s = path.suffix.lower()
    if s in PDF_SUFFIXES:
        # We do not differentiate scanned vs digital here; extractor handles fallback.
        return "pdf"
    if s in IMAGE_SUFFIXES:
        return "image"
    return "unknown"


def _page_count(path: Path) -> int:
    if path.suffix.lower() not in PDF_SUFFIXES:
        return 1
    try:
        import fitz  # PyMuPDF

        with fitz.open(path) as doc:
            return doc.page_count
    except Exception:
        return 0


def _paper_id(path: Path) -> str:
    return path.stem.replace(" ", "_").lower()


def discover_inputs(input_dir: str | Path, run_id: str) -> RunManifest:
    root = Path(input_dir)
    papers_dir = root / "papers"
    entries: list[PaperManifestEntry] = []
    if papers_dir.exists():
        for p in sorted(papers_dir.iterdir()):
            if p.is_file() and _detect_kind(p) != "unknown":
                entries.append(
                    PaperManifestEntry(
                        paper_id=_paper_id(p),
                        source_file=str(p),
                        file_hash=sha256_file(p),
                        kind=_detect_kind(p),
                        page_count=_page_count(p),
                    )
                )
    return RunManifest(
        run_id=run_id,
        input_dir=str(root),
        started_at=_dt.datetime.now(_dt.UTC).isoformat() + "Z",
        papers=entries,
    )
