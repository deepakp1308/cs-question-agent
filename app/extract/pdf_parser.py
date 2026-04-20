"""Layout-aware PDF parsing using PyMuPDF.

Returns a simple, easily-testable per-line structure with geometry + font info
so downstream extraction can detect monospace code blocks.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Span:
    text: str
    page: int
    x0: float
    y0: float
    x1: float
    y1: float
    font: str
    size: float

    @property
    def is_monospace(self) -> bool:
        f = self.font.lower()
        return any(k in f for k in ("mono", "courier", "consolas", "menlo"))


@dataclass
class Line:
    page: int
    text: str
    spans: list[Span]
    bbox: tuple[float, float, float, float]

    @property
    def is_monospace(self) -> bool:
        return bool(self.spans) and all(s.is_monospace for s in self.spans if s.text.strip())


def parse_pdf_lines(path: str | Path) -> list[Line]:
    """Return an ordered list of Line objects with geometry from every page."""
    import fitz  # PyMuPDF

    out: list[Line] = []
    with fitz.open(path) as doc:
        for page_idx, page in enumerate(doc, start=1):
            blocks = page.get_text("dict").get("blocks", [])
            for block in blocks:
                for line in block.get("lines", []):
                    spans_out: list[Span] = []
                    texts: list[str] = []
                    xs0: list[float] = []
                    ys0: list[float] = []
                    xs1: list[float] = []
                    ys1: list[float] = []
                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        if not text:
                            continue
                        x0, y0, x1, y1 = span.get("bbox", (0, 0, 0, 0))
                        s = Span(
                            text=text,
                            page=page_idx,
                            x0=x0,
                            y0=y0,
                            x1=x1,
                            y1=y1,
                            font=span.get("font", ""),
                            size=span.get("size", 0.0),
                        )
                        spans_out.append(s)
                        texts.append(text)
                        xs0.append(x0)
                        ys0.append(y0)
                        xs1.append(x1)
                        ys1.append(y1)
                    if not spans_out:
                        continue
                    out.append(
                        Line(
                            page=page_idx,
                            text="".join(texts).rstrip(),
                            spans=spans_out,
                            bbox=(min(xs0), min(ys0), max(xs1), max(ys1)),
                        )
                    )
    return out
