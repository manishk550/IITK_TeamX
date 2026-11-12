"""Turn the technical report into a formatted document of about 12 pages.

12pt body, 1.5 line spacing, and 1 inch margins. A title page is included.
Run: PYTHONPATH=.vendor python3 scripts/build_report_docx.py
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.text import WD_LINE_SPACING
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "final_technical_report.md"
OUT = ROOT / "docs" / "FinSight_Technical_Report.docx"


def add_runs(paragraph, text: str, size: int = 12, bold: bool = False):
    paragraph.paragraph_format.line_spacing_rule = WD_LINE_SPACING.ONE_POINT_FIVE
    paragraph.paragraph_format.space_after = Pt(8)
    buffer = ""
    mode = None
    def flush():
        nonlocal buffer
        if buffer:
            run = paragraph.add_run(buffer)
            run.font.name = "Times New Roman"
            run.font.size = Pt(size)
            run.bold = bold or mode == "code"
            run.font.color.rgb = RGBColor(0x14, 0x20, 0x33)
            if mode == "code":
                run.font.name = "Courier New"
                run.font.size = Pt(10)
            buffer = ""
    for char in text:
        if char == "`":
            flush()
            mode = None if mode == "code" else "code"
            continue
        buffer += char
    flush()


def build() -> Path:
    document = Document()
    for section in document.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)

    title = document.add_paragraph()
    title.alignment = 1
    run = title.add_run("FinSight")
    run.bold = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(28)
    subtitle = document.add_paragraph()
    subtitle.alignment = 1
    add_runs(subtitle, "Technical report\nTrack B — API-side capstone\nA cited financial-report copilot on the course model Qwen/Qwen3-8B", size=14)
    meta = document.add_paragraph()
    meta.alignment = 1
    add_runs(meta, "Team: add the team name\nMembers: add the six names\n12 November 2026", size=12)
    document.add_page_break()

    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip():
            index += 1
            continue
        if line.startswith("# "):
            heading = document.add_heading(line[2:].strip(), level=0)
            for run in heading.runs:
                run.font.name = "Times New Roman"
            index += 1
            continue
        if line.startswith("## "):
            heading = document.add_heading(line[3:].strip(), level=1)
            for run in heading.runs:
                run.font.name = "Times New Roman"
            index += 1
            continue
        if line.startswith("### "):
            heading = document.add_heading(line[4:].strip(), level=2)
            for run in heading.runs:
                run.font.name = "Times New Roman"
            index += 1
            continue
        if line.startswith("|"):
            rows = []
            while index < len(lines) and lines[index].startswith("|"):
                cells = [cell.strip() for cell in lines[index].strip().strip("|").split("|")]
                if not all(set(cell) <= set("-: ") for cell in cells):
                    rows.append(cells)
                index += 1
            if rows:
                width = max(len(row) for row in rows)
                table = document.add_table(rows=len(rows), cols=width)
                table.style = "Table Grid"
                for r, row in enumerate(rows):
                    for c in range(width):
                        table.rows[r].cells[c].text = row[c] if c < len(row) else ""
                document.add_paragraph()
            continue
        if line.startswith("```"):
            index += 1
            code = []
            while index < len(lines) and not lines[index].startswith("```"):
                code.append(lines[index])
                index += 1
            index += 1
            paragraph = document.add_paragraph()
            add_runs(paragraph, "\n".join(code), size=10)
            continue
        paragraph = document.add_paragraph()
        text = line
        if text.startswith("- "):
            text = "• " + text[2:]
        add_runs(paragraph, text)
        index += 1

    document.save(OUT)
    words = len(SOURCE.read_text(encoding="utf-8").split())
    print(OUT)
    print(f"source words: {words}; at 12pt and 1.5 spacing this is about {round(words / 320) + 1} pages including the title page")
    return OUT


if __name__ == "__main__":
    build()
