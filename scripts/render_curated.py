"""Render a curated YAML (question + hand-written answer) to a clean styled PDF.

Uses ReportLab Platypus directly so the PDF is properly styled even without
system libraries (WeasyPrint optional).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parent.parent


COL_PRIMARY = HexColor("#2c5282")
COL_PRIMARY_DARK = HexColor("#1a365d")
COL_ANSWER_BAR = HexColor("#276749")
COL_ANSWER_DARK = HexColor("#22543d")
COL_TOPIC_BG = HexColor("#edf2f7")
COL_Q_BG = HexColor("#f6f8fb")
COL_A_BG = HexColor("#f0fdf4")
COL_CHECK = HexColor("#276749")
COL_MISTAKE_BG = HexColor("#fff5f5")
COL_MISTAKE_BAR = HexColor("#c53030")
COL_MISTAKE_DARK = HexColor("#742a2a")
COL_BODY = HexColor("#1a202c")
COL_MUTED = HexColor("#4a5568")


def _make_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "h1": ParagraphStyle(
            "h1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            textColor=COL_PRIMARY_DARK,
            spaceAfter=2,
            leading=24,
        ),
        "meta": ParagraphStyle(
            "meta",
            parent=base["BodyText"],
            fontName="Helvetica-Oblique",
            fontSize=9.5,
            textColor=COL_MUTED,
            spaceAfter=16,
        ),
        "q_head": ParagraphStyle(
            "q_head",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            textColor=COL_PRIMARY,
            spaceAfter=2,
        ),
        "question": ParagraphStyle(
            "question",
            parent=base["BodyText"],
            fontName="Times-Roman",
            fontSize=11.5,
            leading=15,
            textColor=COL_BODY,
            spaceAfter=8,
        ),
        "a_head": ParagraphStyle(
            "a_head",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.5,
            textColor=COL_ANSWER_BAR,
            spaceAfter=3,
        ),
        "direct": ParagraphStyle(
            "direct",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=14,
            textColor=COL_ANSWER_DARK,
            spaceAfter=6,
        ),
        "section_label": ParagraphStyle(
            "section_label",
            parent=base["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=8.8,
            textColor=HexColor("#444"),
            spaceBefore=4,
            spaceAfter=3,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=13.5,
            textColor=COL_BODY,
            leftIndent=2,
        ),
        "check": ParagraphStyle(
            "check",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.8,
            textColor=COL_CHECK,
            spaceBefore=6,
        ),
        "mistake": ParagraphStyle(
            "mistake",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.8,
            leading=13,
            textColor=COL_MISTAKE_DARK,
            leftIndent=8,
            rightIndent=8,
            spaceBefore=4,
            spaceAfter=2,
            backColor=COL_MISTAKE_BG,
            borderPadding=(6, 8, 6, 8),
            borderColor=COL_MISTAKE_BAR,
            borderWidth=0,
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            textColor=COL_MUTED,
            alignment=TA_LEFT,
        ),
    }


def _q_block(q: dict, styles: dict[str, ParagraphStyle]) -> Table:
    """Build one question+answer block as a single-cell shaded Table for visual grouping."""
    flowables: list = []
    head_text = f"QUESTION {q['number']}"
    if q.get("marks"):
        plural = "s" if q["marks"] != 1 else ""
        head_text += f"  <font color='#666' size='8'>[{q['marks']} mark{plural}]</font>"
    if q.get("topic"):
        head_text += f"  <font color='#4a5568' backcolor='#edf2f7' size='7.5'>&nbsp;{q['topic']}&nbsp;</font>"
    flowables.append(Paragraph(head_text, styles["q_head"]))
    flowables.append(Paragraph(q["question"], styles["question"]))

    # Answer inner block
    answer_flow: list = []
    answer_flow.append(Paragraph("ANSWER", styles["a_head"]))
    answer_flow.append(Paragraph(q["answer_direct"], styles["direct"]))
    if q.get("working"):
        answer_flow.append(Paragraph("Working / explanation", styles["section_label"]))
        items = [ListItem(Paragraph(step, styles["bullet"]), leftIndent=14) for step in q["working"]]
        answer_flow.append(
            ListFlowable(
                items,
                bulletType="1",
                bulletFormat="%s.",
                bulletFontName="Helvetica-Bold",
                bulletFontSize=10,
                leftIndent=18,
                spaceBefore=0,
                spaceAfter=0,
            )
        )
    if q.get("check"):
        answer_flow.append(Paragraph(q["check"], styles["check"]))
    if q.get("common_mistake"):
        answer_flow.append(
            Paragraph(
                f"<b>Common mistake:</b> {q['common_mistake']}",
                styles["mistake"],
            )
        )

    answer_table = Table(
        [[answer_flow]],
        colWidths=["*"],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COL_A_BG),
                ("LINEBEFORE", (0, 0), (-1, -1), 2, COL_ANSWER_BAR),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        ),
    )
    flowables.append(answer_table)

    outer = Table(
        [[flowables]],
        colWidths=["*"],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), COL_Q_BG),
                ("LINEBEFORE", (0, 0), (-1, -1), 3, COL_PRIMARY),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        ),
    )
    return outer


def render_pdf(yaml_path: Path, out_pdf: Path) -> None:
    data = yaml.safe_load(yaml_path.read_text())
    styles = _make_styles()
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    # Document with page numbers.
    doc = BaseDocTemplate(
        str(out_pdf),
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=data["title"],
    )
    frame = Frame(
        doc.leftMargin,
        doc.bottomMargin,
        doc.width,
        doc.height,
        id="normal",
    )

    def _on_page(canvas, _doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(COL_MUTED)
        canvas.drawCentredString(
            A4[0] / 2, 10 * mm, f"Page {_doc.page}"
        )
        canvas.restoreState()

    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_on_page)])

    story: list = []
    story.append(Paragraph(data["title"], styles["h1"]))
    story.append(
        Paragraph(
            f'{len(data["questions"])} questions &middot; For a Grade {data.get("grade_level",10)} first-time learner &middot; Worked answers in Cambridge IGCSE style',
            styles["meta"],
        )
    )
    for q in data["questions"]:
        story.append(KeepTogether(_q_block(q, styles)))
        story.append(Spacer(1, 8))
    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            "Generated by cs-question-agent &middot; curated Chapter 1 &middot; cambridge_igcse_0478",
            styles["footer"],
        )
    )
    doc.build(story)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("yaml_path", type=Path)
    parser.add_argument("--out", type=Path, required=True, help="Output PDF path")
    args = parser.parse_args()
    render_pdf(args.yaml_path, args.out)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
