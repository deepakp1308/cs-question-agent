"""Generate example_input/papers/sample_paper.pdf using ReportLab.

Run once after cloning:   python scripts/make_sample_paper.py
"""
from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "example_input" / "papers" / "sample_paper.pdf"
OUT.parent.mkdir(parents=True, exist_ok=True)


def main() -> None:
    styles = getSampleStyleSheet()
    body = ParagraphStyle("body", parent=styles["BodyText"], fontName="Helvetica", fontSize=11, leading=14)
    section = ParagraphStyle("section", parent=styles["Heading2"], spaceBefore=16)
    code = ParagraphStyle("code", parent=styles["Code"], fontName="Courier", fontSize=10, leading=12)

    doc = SimpleDocTemplate(str(OUT), pagesize=A4, title="Sample CS Paper")
    story = []
    story.append(Paragraph("Computer Science — Sample Paper", styles["Title"]))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Section A", section))
    story.append(Paragraph("Answer all questions.", body))
    story.append(Spacer(1, 6))
    story.append(Paragraph("1. State two advantages of using a star topology. [2]", body))
    story.append(Spacer(1, 6))
    story.append(Paragraph("2. Explain the difference between a switch and a router. [2]", body))
    story.append(Spacer(1, 6))
    story.append(Paragraph("3. Consider the following SQL statement:", body))
    story.append(Paragraph("SELECT name FROM students WHERE grade = 10;", code))
    story.append(Paragraph("(a) What does the WHERE clause do? [1]", body))
    story.append(Paragraph("(b) Name the clause used to sort the results. [1]", body))
    story.append(Spacer(1, 12))
    story.append(Paragraph("Section B", section))
    story.append(Paragraph("Attempt any two questions.", body))
    story.append(Spacer(1, 6))
    story.append(Paragraph("4. Define a primary key and give one example. [2]", body))
    story.append(Paragraph("OR", body))
    story.append(Paragraph("5. Define a foreign key and give one example. [2]", body))
    doc.build(story)
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
