"""Build downloadable DOCX and PDF versions of the tailored CV."""
from __future__ import annotations

import io


def build_docx(tailored_cv: str, score: int, matched: list[str], missing: list[str]) -> bytes:
    import docx
    from docx.shared import Pt

    document = docx.Document()
    document.add_heading("Tailored CV", level=0)
    meta = document.add_paragraph()
    meta.add_run(f"Keyword match score: {score}/100").italic = True
    for block in tailored_cv.strip().split("\n"):
        line = block.strip()
        if not line:
            continue
        if line.isupper() and len(line) < 60:
            document.add_heading(line.title(), level=2)
        else:
            document.add_paragraph(line)

    document.add_page_break()
    document.add_heading("Match report", level=1)
    document.add_paragraph(f"Score: {score}/100", style="List Bullet")
    if matched:
        document.add_paragraph("Matched keywords: " + ", ".join(matched), style="List Bullet")
    if missing:
        document.add_paragraph(
            "Gaps (absent from the base CV, not added): " + ", ".join(missing),
            style="List Bullet",
        )
    note = document.add_paragraph()
    note.add_run(
        "Gaps are reported, not inserted. Every tailoring change links back to base-CV evidence."
    ).font.size = Pt(9)

    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def build_pdf(tailored_cv: str, score: int, matched: list[str], missing: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = io.BytesIO()
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=56, rightMargin=56, topMargin=56, bottomMargin=56
    )
    story = [Paragraph("Tailored CV", styles["Title"])]
    story.append(Paragraph(f"<i>Keyword match score: {score}/100</i>", styles["Normal"]))
    story.append(Spacer(1, 14))

    for block in tailored_cv.strip().split("\n"):
        line = block.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue
        style = styles["Heading2"] if line.isupper() and len(line) < 60 else styles["Normal"]
        story.append(Paragraph(_escape(line), style))

    story.append(Spacer(1, 18))
    story.append(Paragraph("Match report", styles["Heading1"]))
    story.append(Paragraph(f"Score: {score}/100", styles["Normal"]))
    if matched:
        story.append(Paragraph("Matched keywords: " + _escape(", ".join(matched)), styles["Normal"]))
    if missing:
        story.append(
            Paragraph(
                "Gaps (absent from the base CV, not added): " + _escape(", ".join(missing)),
                styles["Normal"],
            )
        )
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            "<i>Gaps are reported, not inserted. Every tailoring change links back to base-CV evidence.</i>",
            styles["Normal"],
        )
    )

    doc.build(story)
    return buffer.getvalue()


def _escape(text: str) -> str:
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
