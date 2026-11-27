"""Editable document export. No network calls; optional libraries load lazily."""
from __future__ import annotations

import io
import os
import re
from html import escape
from pathlib import Path


def plain_text(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1（\2）", text)
    text = re.sub(r"(?m)^#{1,6}\s+", "", text)
    text = text.replace("**", "").replace("`", "").replace("~~", "")
    for symbol, label in {"✅": "[已具备]", "⚠️": "[注意]", "❌": "[未通过]"}.items():
        text = text.replace(symbol, label)
    return text


def missing_fields(text: str) -> list[str]:
    return list(dict.fromkeys(plain_text(line).strip().lstrip("- ")[:160]
                             for line in text.splitlines() if re.search(r"_{3,}", line)))


def _blocks(text: str):
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if line.startswith("|"):
            rows = []
            while True:
                if not re.fullmatch(r"[|\s:\-]+", line):
                    rows.append([plain_text(cell.strip()) for cell in line.strip("|").split("|")])
                if i >= len(lines) or not lines[i].strip().startswith("|"):
                    break
                line = lines[i].strip()
                i += 1
            if rows:
                yield "table", rows
        elif re.match(r"^#{1,6}\s", line):
            level = len(line.split(" ", 1)[0])
            yield f"h{min(level, 3)}", plain_text(line)
        else:
            yield "text", plain_text(line.removeprefix("> "))


def export_docx(text: str) -> bytes:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    doc = Document()
    section = doc.sections[0]
    section.page_width, section.page_height = Inches(8.5), Inches(11)
    section.top_margin = section.bottom_margin = Inches(0.75)
    section.left_margin = section.right_margin = Inches(0.8)
    for name in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3"):
        style = doc.styles[name]
        style.font.name = "Calibri"
        style.font.color.rgb = RGBColor(0, 0, 0)
        style.element.get_or_add_rPr().get_or_add_rFonts().set(qn("w:eastAsia"), "宋体")
    normal = doc.styles["Normal"]
    normal.font.size = Pt(11)
    normal.paragraph_format.line_spacing = 1.3
    normal.paragraph_format.space_after = Pt(4)
    doc.styles["Title"].font.size = Pt(19)
    for kind, value in _blocks(text):
        if kind == "table":
            width = max(len(row) for row in value)
            table = doc.add_table(rows=0, cols=width)
            table.style = "Table Grid"
            for idx, row in enumerate(value):
                cells = table.add_row().cells
                for j, cell in enumerate(row):
                    cells[j].text = cell
                    if idx == 0:
                        for run in cells[j].paragraphs[0].runs:
                            run.bold = True
                if idx == 0:
                    repeat = OxmlElement("w:tblHeader")
                    table.rows[0]._tr.get_or_add_trPr().append(repeat)
            doc.add_paragraph()
        elif kind == "h1":
            doc.add_paragraph(value, style="Title")
        elif kind.startswith("h"):
            doc.add_heading(value, level=int(kind[1]) - 1)
        else:
            doc.add_paragraph(value)
    footer = section.footer.paragraphs[0]
    footer.alignment = 1
    footer.add_run("第 ")
    field = OxmlElement("w:fldSimple")
    field.set(qn("w:instr"), "PAGE")
    footer._p.append(field)
    footer.add_run(" 页")
    result = io.BytesIO()
    doc.save(result)
    return result.getvalue()


def _pdf_font() -> str:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    name = "LexFlowCJK"
    if name in pdfmetrics.getRegisteredFontNames():
        return name
    candidates = [os.getenv("LEXFLOW_CJK_FONT", ""), "C:/Windows/Fonts/simsun.ttc",
                  "/usr/share/fonts/truetype/arphic/uming.ttc"]
    for path in candidates:
        if path and Path(path).is_file():
            try:
                pdfmetrics.registerFont(TTFont(name, path, subfontIndex=0))
                return name
            except Exception:
                continue
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    return "STSong-Light"


def export_pdf(text: str) -> bytes:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors

    font = _pdf_font()
    styles = {
        "text": ParagraphStyle("body", fontName=font, fontSize=11, leading=16,
                               wordWrap="CJK", spaceAfter=4),
        "h1": ParagraphStyle("title", fontName=font, fontSize=19, leading=26,
                             wordWrap="CJK", spaceAfter=16, keepWithNext=True),
        "h2": ParagraphStyle("heading", fontName=font, fontSize=14, leading=20,
                             wordWrap="CJK", spaceBefore=12, spaceAfter=8, keepWithNext=True),
        "h3": ParagraphStyle("subheading", fontName=font, fontSize=12, leading=18,
                             wordWrap="CJK", spaceBefore=8, spaceAfter=6, keepWithNext=True),
    }
    blocks = []
    for kind, value in _blocks(text):
        if kind == "table":
            width = max(len(row) for row in value)
            rows = [[Paragraph(escape(cell), styles["text"]) for cell in
                     (row + [""] * (width - len(row)))] for row in value]
            table = Table(rows, colWidths=[496.8 / width] * width, repeatRows=1)
            table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#aaaaaa")),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            blocks += [table, Spacer(1, 10)]
        else:
            blocks.append(Paragraph(escape(value), styles[kind]))
    result = io.BytesIO()
    def page_number(canvas, doc):
        canvas.setFont(font, 9)
        canvas.drawCentredString(letter[0] / 2, 27, f"第 {doc.page} 页")
    SimpleDocTemplate(result, pagesize=letter, leftMargin=57.6, rightMargin=57.6,
                      topMargin=54, bottomMargin=48).build(
                          blocks or [Paragraph("空白草稿", styles["text"])],
                          onFirstPage=page_number, onLaterPages=page_number)
    return result.getvalue()
