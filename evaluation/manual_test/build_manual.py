"""Builds the many-page test PDF and its answer key.

Run from this folder:
    uv run --with reportlab==5.1.0 --with pypdf==6.21.2 python3 build_manual.py

Writes verdane_gh4_manual.pdf and answer_key.json next to this file. The page
of each answer is found by searching the finished PDF's text, so the key always
matches the file. The PDF has no outline, so readers must find sections from
the headings (larger bold text).
"""

import json
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (KeepTogether, PageBreak, Paragraph, Preformatted,
                                SimpleDocTemplate, Spacer, Table, TableStyle)

import manual_content as content

PDF_NAME = "verdane_gh4_manual.pdf"
KEY_NAME = "answer_key.json"
HERE = Path(__file__).parent

# A5 is a common page size for device operator manuals.
PAGE_SIZE = A5
MARGIN = 0.7 * inch
TEXT_WIDTH = PAGE_SIZE[0] - 2 * MARGIN

BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=content.BODY_FONT_SIZE,
                      leading=16, spaceAfter=8)
BULLET = ParagraphStyle("bullet", parent=BODY, leftIndent=18, bulletIndent=6, spaceAfter=4)
CHAPTER = ParagraphStyle("chapter", fontName="Helvetica-Bold", fontSize=18, leading=24,
                         spaceAfter=14)
SECTION = ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=14, leading=18,
                         spaceBefore=12, spaceAfter=8)
CELL = ParagraphStyle("cell", fontName="Helvetica", fontSize=9.5, leading=12)
CELL_HEADER = ParagraphStyle("cellHeader", parent=CELL, fontName="Helvetica-Bold")
CODE = ParagraphStyle("code", fontName="Courier", fontSize=9.5, leading=12,
                      leftIndent=12, spaceBefore=2, spaceAfter=10)
TITLE = ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=26, leading=32,
                       spaceAfter=16)
SUBTITLE = ParagraphStyle("subtitle", fontName="Helvetica", fontSize=14, leading=18)


def _table(rows):
    data = [[Paragraph(escape(cell), CELL_HEADER if r == 0 else CELL) for cell in row]
            for r, row in enumerate(rows)]
    table = Table(data, repeatRows=1, hAlign="LEFT",
                  colWidths=[TEXT_WIDTH / len(rows[0])] * len(rows[0]))
    table.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8E8E8")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return table


def _flowables():
    story = [Spacer(1, 1.5 * inch),
             Paragraph(escape(content.TITLE), TITLE),
             Paragraph(escape(content.SUBTITLE), SUBTITLE)]
    for chapter in content.chapters():
        story.append(PageBreak())
        story.append(Paragraph(escape(f'{chapter["number"]} {chapter["title"]}'), CHAPTER))
        for section in chapter["sections"]:
            heading = Paragraph(escape(f'{section["number"]} {section["title"]}'), SECTION)
            body = []
            for kind, value in section["blocks"]:
                if kind == "p":
                    body.append(Paragraph(escape(value), BODY))
                elif kind == "bullets":
                    body.extend(Paragraph(escape(item), BULLET, bulletText="•")
                                for item in value)
                elif kind == "code":
                    body.append(Preformatted(value, CODE))
                elif kind == "table":
                    body.append(_table(value))
                    body.append(Spacer(1, 8))
            # Keep each heading with the start of its section.
            story.append(KeepTogether([heading, body[0]]))
            story.extend(body[1:])
    return story


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 9)
    canvas.drawString(MARGIN, 0.4 * inch, f"Verdane GH-4 Operator Manual - page {doc.page}")
    canvas.restoreState()


def build_pdf(path):
    """Writes the manual to path. The output is byte-identical on every run."""
    rl_config.invariant = 1
    doc = SimpleDocTemplate(str(path), pagesize=PAGE_SIZE, leftMargin=MARGIN, rightMargin=MARGIN,
                            topMargin=MARGIN, bottomMargin=MARGIN,
                            title=content.TITLE, author="Verdane (fictional)")
    doc.build(_flowables(), onFirstPage=lambda c, d: None, onLaterPages=_footer)


def answer_key(pdf_path):
    """Each question with the 1-based page its fact is on (None if unanswerable)."""
    from pypdf import PdfReader

    pages = [re.sub(r"\s+", " ", page.extract_text())
             for page in PdfReader(str(pdf_path)).pages]
    key = []
    for q in content.QUESTIONS:
        page = None
        if q["fact"] is not None:
            fact = re.sub(r"\s+", " ", q["fact"]).strip()
            found = [i + 1 for i, text in enumerate(pages) if fact in text]
            if len(found) != 1:
                raise ValueError(f'{q["id"]}: fact found on pages {found}')
            page = found[0]
        key.append({"id": q["id"], "question": q["question"],
                    "expected_answer": q["expected_answer"], "section": q["section"],
                    "page": page, "tests": q["tests"]})
    return key, len(pages)


def main():
    pdf = HERE / PDF_NAME
    build_pdf(pdf)
    key, page_count = answer_key(pdf)
    (HERE / KEY_NAME).write_text(json.dumps(key, indent=2) + "\n")
    print(f"{pdf.name}: {page_count} pages")
    for entry in key:
        print(f'{entry["id"]}  p. {entry["page"]}  {entry["section"]}')
    return 0


if __name__ == "__main__":
    sys.exit(main())
