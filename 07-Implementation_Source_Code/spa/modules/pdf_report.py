"""
modules/pdf_report.py
----------------------
Render the Markdown produced by `report_builder.build_documentation()` into
a proper PDF, with correct Arabic shaping and right-to-left layout.

Why a separate renderer:
  * `report_builder` stays dependency-free and keeps producing Markdown.
  * PDF generation (ReportLab + Arabic reshaping) is isolated here, so if
    the PDF libraries are unavailable the app can still fall back to the
    Markdown download.

Arabic support:
  * ReportLab's built-in fonts have no Arabic glyphs, so we register the
    Windows "Arial" TTF (which ships Arabic) — falling back to any bundled
    DejaVu/other TTF if Arial is not present.
  * Arabic runs are reshaped (`arabic_reshaper`) and reordered to visual
    order (`python-bidi`) before being drawn, and Arabic paragraphs are
    right-aligned. ASCII-only blocks (SQL, tables of numbers) stay LTR.
"""

from __future__ import annotations

import io
import os
import re

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.doughnut import Doughnut
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.charts.piecharts import Pie
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Preformatted, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

_ARABIC_RE = re.compile(r"[؀-ۿ]")

# Candidate (regular, bold) TTF pairs, tried in order.
_FONT_CANDIDATES = [
    (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
    (r"C:\Windows\Fonts\tahoma.ttf", r"C:\Windows\Fonts\tahomabd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]

_FONT_NAME = "AppArabic"
_FONT_BOLD = "AppArabic-Bold"
_fonts_registered = False


class PdfUnavailableError(Exception):
    """Raised when no Arabic-capable TTF font could be registered."""


def _register_fonts() -> None:
    global _fonts_registered
    if _fonts_registered:
        return
    for regular, bold in _FONT_CANDIDATES:
        if os.path.exists(regular):
            pdfmetrics.registerFont(TTFont(_FONT_NAME, regular))
            bold_path = bold if os.path.exists(bold) else regular
            pdfmetrics.registerFont(TTFont(_FONT_BOLD, bold_path))
            _fonts_registered = True
            return
    raise PdfUnavailableError(
        "No Arabic-capable TTF font found; cannot render the PDF report."
    )


def _has_arabic(text: str) -> bool:
    return bool(_ARABIC_RE.search(text))


def _shape(text: str) -> str:
    """Reshape + reorder a string so Arabic renders correctly in the PDF."""
    if not _has_arabic(text):
        return text
    return get_display(arabic_reshaper.reshape(text))


def _strip_md(text: str) -> str:
    """Remove the inline Markdown markers we don't render as rich text."""
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)   # bold
    text = text.replace("`", "")                    # inline code
    return text


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _styles():
    base = getSampleStyleSheet()
    body = ParagraphStyle(
        "ArBody", parent=base["Normal"], fontName=_FONT_NAME, fontSize=10.5,
        leading=17, alignment=TA_RIGHT, wordWrap="RTL",
    )
    body_ltr = ParagraphStyle(
        "LtrBody", parent=body, alignment=TA_LEFT, wordWrap=None,
    )
    h1 = ParagraphStyle("ArH1", parent=body, fontName=_FONT_BOLD, fontSize=17,
                         leading=24, spaceBefore=6, spaceAfter=10,
                         textColor=colors.HexColor("#1f3b57"))
    h2 = ParagraphStyle("ArH2", parent=body, fontName=_FONT_BOLD, fontSize=13.5,
                         leading=20, spaceBefore=12, spaceAfter=6,
                         textColor=colors.HexColor("#22577a"))
    h3 = ParagraphStyle("ArH3", parent=body, fontName=_FONT_BOLD, fontSize=11.5,
                         leading=18, spaceBefore=8, spaceAfter=4,
                         textColor=colors.HexColor("#2c3e50"))
    code = ParagraphStyle("Code", parent=base["Code"], fontName="Courier",
                           fontSize=8.5, leading=11, textColor=colors.HexColor("#0b3d2e"),
                           backColor=colors.HexColor("#f4f6f8"), borderPadding=6,
                           alignment=TA_LEFT)
    h1_ltr = ParagraphStyle("H1Ltr", parent=h1, alignment=TA_LEFT, wordWrap=None)
    h2_ltr = ParagraphStyle("H2Ltr", parent=h2, alignment=TA_LEFT, wordWrap=None)
    h3_ltr = ParagraphStyle("H3Ltr", parent=h3, alignment=TA_LEFT, wordWrap=None)
    cell = ParagraphStyle("Cell", parent=body, fontSize=9, leading=13)
    cell_ltr = ParagraphStyle("CellLtr", parent=cell, alignment=TA_LEFT,
                               wordWrap=None)
    return {"body": body, "body_ltr": body_ltr, "h1": h1, "h2": h2, "h3": h3,
            "h1_ltr": h1_ltr, "h2_ltr": h2_ltr, "h3_ltr": h3_ltr,
            "code": code, "cell": cell, "cell_ltr": cell_ltr}


def _para(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(_escape(_shape(_strip_md(text))), style)


def _build_table(rows: list[list[str]], styles) -> Table:
    def cell_para(text: str, is_header: bool):
        # Header cells follow the table's RTL alignment; body cells that are
        # purely technical/ASCII (e.g. "student_id (PK/FK -> student)") read
        # far better left-aligned LTR.
        style = styles["cell"] if (is_header or _has_arabic(text)) else styles["cell_ltr"]
        return _para(text, style)

    data = [[cell_para(c, r == 0) for c in row] for r, row in enumerate(rows)]
    tbl = Table(data, repeatRows=1, hAlign="RIGHT")
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#22577a")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), _FONT_BOLD),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1),
         [colors.white, colors.HexColor("#f4f6f8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def _split_table_row(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _as_float(text: str):
    try:
        return float(str(text).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


# Palette mirrors the dashboard's pie/doughnut slice colours.
_PALETTE = [colors.HexColor(c) for c in (
    "#5C7F6C", "#C08457", "#4E6E81", "#B0553F", "#8A9B6E",
    "#3F5B4C", "#D6A461", "#6D8299",
)]


def _extract(rows: list[list[str]], col_idx: int):
    """Pull (labels, values) from a table's column `col_idx` (data rows only)."""
    labels, values = [], []
    for r in rows[1:]:
        if col_idx >= len(r):
            return None, None
        v = _as_float(r[col_idx])
        if v is None:
            return None, None
        labels.append(str(r[0]))
        values.append(v)
    return (labels, values) if values else (None, None)


def _title_string(width, height, text):
    return String(width / 2, height - 14, text, fontName=_FONT_BOLD, fontSize=9.5,
                   fillColor=colors.HexColor("#22577a"), textAnchor="middle")


def _bar_or_line(rows, labels, values, chart_type):
    width, height = 430, 200
    d = Drawing(width, height)
    is_grade = "grade" in rows[0][1].lower()
    top = max(values)
    vmax = 20 if (is_grade and top <= 20) else (round(top * 1.15) + 1)

    if chart_type == "line":
        chart = HorizontalLineChart()
        chart.lines[0].strokeColor = colors.HexColor("#3F5B4C")
        chart.lines[0].strokeWidth = 2
    else:
        chart = VerticalBarChart()
        chart.barWidth = 8
        chart.groupSpacing = 12
        chart.bars[0].fillColor = colors.HexColor("#5C7F6C")
        chart.bars[0].strokeColor = colors.HexColor("#3F5B4C")

    chart.x, chart.y = 40, 35
    chart.width, chart.height = width - 70, height - 70
    chart.data = [values]
    chart.valueAxis.valueMin = 0
    chart.valueAxis.valueMax = vmax
    chart.valueAxis.labels.fontName = _FONT_NAME
    chart.valueAxis.labels.fontSize = 8
    chart.categoryAxis.categoryNames = labels
    chart.categoryAxis.labels.fontName = _FONT_NAME
    chart.categoryAxis.labels.fontSize = 8
    chart.categoryAxis.labels.angle = 30 if max(len(l) for l in labels) > 4 else 0
    chart.categoryAxis.labels.dy = -4
    d.add(chart)

    measure = rows[0][1] if not _has_arabic(rows[0][1]) else "Value"
    dimension = rows[0][0] if not _has_arabic(rows[0][0]) else "category"
    d.add(_title_string(width, height, f"{measure} by {dimension}"))
    return d


def _pie_or_doughnut(rows, labels, values, chart_type):
    width, height = 430, 210
    d = Drawing(width, height)
    chart = Doughnut() if chart_type == "doughnut" else Pie()
    chart.x, chart.y = 150, 20
    chart.width, chart.height = 150, 150
    chart.data = values
    chart.labels = [f"{l} ({int(v) if float(v).is_integer() else v})"
                     for l, v in zip(labels, values)]
    chart.slices.strokeColor = colors.white
    chart.slices.strokeWidth = 1
    for i in range(len(values)):
        chart.slices[i].fillColor = _PALETTE[i % len(_PALETTE)]

    legend = Legend()
    legend.x, legend.y = 10, height - 40
    legend.fontName = _FONT_NAME
    legend.fontSize = 8
    legend.dxTextSpace = 5
    legend.deltay = 12
    legend.colorNamePairs = [
        (_PALETTE[i % len(_PALETTE)], f"{labels[i]} ({int(values[i]) if float(values[i]).is_integer() else values[i]})")
        for i in range(len(values))
    ]
    d.add(legend)
    d.add(chart)

    measure = rows[0][-1] if not _has_arabic(rows[0][-1]) else "Count"
    dimension = rows[0][0] if not _has_arabic(rows[0][0]) else "category"
    d.add(_title_string(width, height, f"{measure} share by {dimension}"))
    return d


def _chart_from_rows(rows: list[list[str]], chart_type: str = "bar"):
    """Return a ReportLab chart Drawing for a results table, matching the
    dashboard's chart type (bar / line / pie / doughnut); None if not chartable.

    `rows` includes the header row at index 0.
    """
    try:
        if len(rows) < 3 or len(rows[0]) < 2:
            return None
        header = [h.lower() for h in rows[0]]
        if not any(k in header[1] for k in
                   ("grade", "avg", "average", "value", "mean", "count")):
            return None

        ct = (chart_type or "bar").lower()
        if ct in ("pie", "doughnut"):
            # Composition uses the last (count) column.
            labels, values = _extract(rows, len(rows[0]) - 1)
            if not labels:
                return None
            return _pie_or_doughnut(rows, labels, values, ct)

        labels, values = _extract(rows, 1)
        if not labels:
            return None
        return _bar_or_line(rows, labels, values, "line" if ct == "line" else "bar")
    except Exception:  # noqa: BLE001 - a chart must never break the PDF build
        return None


def markdown_to_pdf(md_text: str) -> bytes:
    """Convert the documentation Markdown into PDF bytes."""
    _register_fonts()
    styles = _styles()
    story: list = []

    lines = md_text.splitlines()
    i = 0
    n = len(lines)
    pending_chart = "bar"  # chart type for the next results table
    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Chart-type directive: [[chart:pie]] — applies to the next table.
        if stripped.startswith("[[chart:") and stripped.endswith("]]"):
            pending_chart = stripped[len("[[chart:"):-2].strip() or "bar"
            i += 1
            continue

        # Fenced code block (```sql ... ```)
        if stripped.startswith("```"):
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing fence
            story.append(Preformatted("\n".join(code_lines) or " ", styles["code"]))
            story.append(Spacer(1, 6))
            continue

        # Markdown table (consecutive lines starting with |)
        if stripped.startswith("|"):
            table_lines = []
            while i < n and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            rows = []
            for tl in table_lines:
                cells = _split_table_row(tl)
                # skip the |---|---| separator row
                if all(set(c) <= set("-: ") for c in cells):
                    continue
                rows.append(cells)
            if rows:
                story.append(_build_table(rows, styles))
                story.append(Spacer(1, 8))
                chart = _chart_from_rows(rows, pending_chart)
                if chart is not None:
                    story.append(chart)
                    story.append(Spacer(1, 10))
            pending_chart = "bar"  # reset after consuming
            continue

        # Headings (right-aligned for Arabic, left-aligned for Latin text)
        if stripped.startswith("### "):
            txt = stripped[4:]
            story.append(_para(txt, styles["h3" if _has_arabic(txt) else "h3_ltr"]))
        elif stripped.startswith("## "):
            txt = stripped[3:]
            story.append(_para(txt, styles["h2" if _has_arabic(txt) else "h2_ltr"]))
        elif stripped.startswith("# "):
            txt = stripped[2:]
            story.append(_para(txt, styles["h1" if _has_arabic(txt) else "h1_ltr"]))
        elif not stripped:
            story.append(Spacer(1, 4))
        else:
            # Bullet lines keep their leading marker; everything else is a paragraph.
            style = styles["body"] if _has_arabic(stripped) else styles["body_ltr"]
            story.append(_para(stripped, style))
        i += 1

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title="Final Documentation Report",
    )
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()
