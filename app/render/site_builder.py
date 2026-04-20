"""Build per-chapter PDFs, a master index, and the audit HTML.

WeasyPrint is preferred for PDF rendering. If it is not installed (or its
system libraries are missing), the renderer falls back to ReportLab so that
the full pipeline still completes end-to-end.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ..models import AnswerRecord, ChapterSpec, JudgeResult, QuestionRecord

_TEMPLATES_DIR = Path(__file__).parent / "html_templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _render_pdf_from_html(html: str, out_path: Path) -> str:
    """Try WeasyPrint; fall back to ReportLab if unavailable."""
    try:
        from weasyprint import HTML  # type: ignore

        HTML(string=html).write_pdf(str(out_path))
        return "weasyprint"
    except Exception:
        return _render_pdf_from_html_reportlab(html, out_path)


def _render_pdf_from_html_reportlab(html: str, out_path: Path) -> str:
    """Very simple fallback — strips tags and lays out text.

    This is NOT pixel-perfect, but it guarantees a usable PDF without
    native system libraries. For production rendering install WeasyPrint.
    """
    import re

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    text = re.sub(r"<style[\s\S]*?</style>", "", html, flags=re.IGNORECASE)
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
    # Keep paragraph/heading breaks, strip remaining tags.
    text = re.sub(r"<(h[1-6]|p|div|li)[^>]*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(h[1-6]|p|div|li)>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()

    doc = SimpleDocTemplate(str(out_path), pagesize=A4, title="Worked answers")
    styles = getSampleStyleSheet()
    story: list[Any] = []
    for para in text.split("\n\n"):
        if not para.strip():
            continue
        story.append(Paragraph(para.replace("\n", "<br/>"), styles["BodyText"]))
        story.append(Spacer(1, 6))
    doc.build(story)
    return "reportlab"


def render_chapter_pdf(
    *,
    chapter: ChapterSpec,
    items: list[dict[str, Any]],
    run_id: str,
    subject: str,
    grade_level: int,
    out_dir: Path,
) -> tuple[Path, str]:
    html = _env().get_template("chapter.html").render(
        chapter=chapter,
        items=items,
        run_id=run_id,
        subject=subject,
        grade_level=grade_level,
    )
    html_path = out_dir / f"chapter_{chapter.chapter_id}.html"
    html_path.write_text(html)
    pdf_path = out_dir / f"chapter_{chapter.chapter_id}.pdf"
    backend = _render_pdf_from_html(html, pdf_path)
    return pdf_path, backend


def render_audit_html(
    *,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    run_id: str,
    out_dir: Path,
) -> Path:
    html = _env().get_template("audit.html").render(
        rows=rows,
        summary=summary,
        run_id=run_id,
        generated_at=_dt.datetime.now(_dt.UTC).isoformat() + "Z",
    )
    path = out_dir / "audit.html"
    path.write_text(html)
    return path


def render_index_html(
    *,
    chapters: list[dict[str, Any]],
    run_id: str,
    subject: str,
    out_dir: Path,
) -> Path:
    html = _env().get_template("index.html").render(
        chapters=chapters,
        run_id=run_id,
        subject=subject,
        generated_at=_dt.datetime.now(_dt.UTC).isoformat() + "Z",
    )
    path = out_dir / "index.html"
    path.write_text(html)
    return path


def build_site(
    *,
    run_id: str,
    subject: str,
    grade_level: int,
    chapters: list[ChapterSpec],
    questions: list[QuestionRecord],
    answers: dict[str, AnswerRecord],
    assignments: dict[str, str | None],
    tiers: dict[str, str],
    extraction_judges: dict[str, JudgeResult],
    answer_judges: dict[str, JudgeResult],
    site_root: Path,
) -> dict[str, Any]:
    run_dir = site_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    # Group per-chapter.
    per_chapter: dict[str, list[dict[str, Any]]] = {c.chapter_id: [] for c in chapters}
    for q in questions:
        ch = assignments.get(q.question_id)
        if ch is None:
            continue
        tier = tiers.get(q.question_id, "quarantine")
        if tier == "quarantine":
            continue  # do not include quarantined items in the student PDF
        per_chapter.setdefault(ch, []).append(
            {"question": q, "answer": answers.get(q.question_id)}
        )

    # Render per-chapter PDFs.
    chapter_entries: list[dict[str, Any]] = []
    for ch in chapters:
        items = per_chapter.get(ch.chapter_id, [])
        if not items:
            continue
        _path, _backend = render_chapter_pdf(
            chapter=ch,
            items=items,
            run_id=run_id,
            subject=subject,
            grade_level=grade_level,
            out_dir=run_dir,
        )
        chapter_entries.append(
            {"chapter_id": ch.chapter_id, "title": ch.title, "question_count": len(items)}
        )

    # Audit rows for every question (including quarantined).
    rows: list[dict[str, Any]] = []
    summary = {"total": len(questions), "auto_publish": 0, "gated_publish": 0, "quarantine": 0, "cost_usd": 0.0}
    for q in questions:
        tier = tiers.get(q.question_id, "quarantine")
        summary[tier] = summary.get(tier, 0) + 1
        rows.append(
            {
                "question": q,
                "answer": answers.get(q.question_id),
                "chapter": assignments.get(q.question_id),
                "extraction": extraction_judges.get(q.question_id),
                "answer_judge": answer_judges.get(q.question_id),
                "tier": tier,
                "models": (q.models_used.model_dump() if q.models_used else {}),
            }
        )

    render_audit_html(rows=rows, summary=summary, run_id=run_id, out_dir=run_dir)
    render_index_html(chapters=chapter_entries, run_id=run_id, subject=subject, out_dir=run_dir)
    # Top-level index.html links to the most recent run.
    top_index = site_root / "index.html"
    top_index.write_text(
        f'<!doctype html><meta http-equiv="refresh" content="0; url=./runs/{run_id}/index.html">'
    )
    return {"run_dir": str(run_dir), "chapters": chapter_entries, "summary": summary}
