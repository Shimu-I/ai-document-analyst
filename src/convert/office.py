"""DOCX / XLSX / PPTX / CSV -> Markdown (python-docx, openpyxl, python-pptx)."""
from __future__ import annotations

import csv
import io
import re
import time
from datetime import date, datetime, time as dtime

from .assets import AssetStore, alt_text
from .picture_ocr import PictureOCR, quote
from .base import ConversionError, ConvertedDocument, clean_chars, md_table, tidy
from .omml import omml_to_latex

MAX_SHEET_ROWS = 5000
MAX_SHEET_COLS = 60


# =========================================================================== DOCX
def _run_md(text: str, bold: bool, italic: bool) -> str:
    if not text.strip():
        return text
    lead = text[: len(text) - len(text.lstrip())]
    trail = text[len(text.rstrip()):]
    core = text.strip()
    if bold and italic:
        core = f"***{core}***"
    elif bold:
        core = f"**{core}**"
    elif italic:
        core = f"*{core}*"
    return lead + core + trail


def _para_md(p, plain: bool = False, math: list | None = None) -> str:
    """Paragraph text with bold/italic/links. ``math``: when a list is given, equations become $..$ /
    $$..$$ LaTeX in the text (and are appended to the list); otherwise they are left out."""
    from docx.text.hyperlink import Hyperlink
    from docx.text.run import Run

    parts: list[str] = []
    for child in p._p.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "r":
            r = Run(child, p)
            txt = clean_chars(r.text)
            parts.append(txt if plain else _run_md(txt, bool(r.bold), bool(r.italic)))
        elif tag == "hyperlink":
            r = Hyperlink(child, p)
            txt = clean_chars(r.text)
            parts.append(f"[{txt}]({r.url})" if r.url and txt.strip() else txt)
        elif tag in ("oMath", "oMathPara") and math is not None:
            tex = omml_to_latex(child)
            if tex:
                math.append(tex)
                parts.append(f" $${tex}$$ " if tag == "oMathPara" else f"${tex}$")
    s = "".join(parts)
    # merge adjacent same-format spans produced run by run:  **a****b** -> **ab**
    s = re.sub(r"\*\*\*\*(?!\*)", "", s) if not plain else s
    return s.strip()


def _num_format(doc, p) -> tuple[str, int]:
    """('bullet'|'number', level) for a list paragraph, else ('', 0)."""
    from docx.oxml.ns import qn

    pPr = p._p.pPr
    numPr = pPr.numPr if pPr is not None else None
    style = (p.style.name or "").lower() if p.style is not None else ""
    level = 0
    if numPr is not None and numPr.ilvl is not None:
        level = int(numPr.ilvl.val)
    kind = ""
    if numPr is not None and numPr.numId is not None:
        kind = "bullet"
        try:
            numbering = doc.part.numbering_part.element
            num_id = str(numPr.numId.val)
            for num in numbering.findall(qn("w:num")):
                if num.get(qn("w:numId")) == num_id:
                    abs_id = num.find(qn("w:abstractNumId")).get(qn("w:val"))
                    for an in numbering.findall(qn("w:abstractNum")):
                        if an.get(qn("w:abstractNumId")) == abs_id:
                            for lvl in an.findall(qn("w:lvl")):
                                if lvl.get(qn("w:ilvl")) == str(level):
                                    fmt = lvl.find(qn("w:numFmt"))
                                    if fmt is not None and fmt.get(qn("w:val")) != "bullet":
                                        kind = "number"
        except Exception:
            pass
    elif "list number" in style:
        kind = "number"
    elif "list bullet" in style or style == "list paragraph":
        kind = "bullet"
    if "list number" in style:
        kind = "number"
        m = re.search(r"(\d)$", style)
        level = int(m.group(1)) - 1 if m else level
    elif "list bullet" in style:
        m = re.search(r"(\d)$", style)
        level = int(m.group(1)) - 1 if m else level
    return kind, level


def _para_pictures(doc, p, store: AssetStore | None, pocr: PictureOCR | None = None) -> list[str]:
    """Markdown image lines for the pictures anchored in a paragraph."""
    blips = [e for e in p._p.iter() if isinstance(e.tag, str) and e.tag.endswith("}blip")]
    lines = []
    for b in blips:
        rid = b.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed")
        if (store is None and pocr is None) or not rid:
            continue
        try:
            part = doc.part.related_parts[rid]
            ext = part.partname.ext.lower().lstrip(".")
            if ext not in ("png", "jpg", "jpeg", "gif"):
                continue                                  # EMF/WMF and similar cannot be shown by Markdown viewers
            if store is None:
                txt = pocr.read(part.blob)
                if txt:
                    lines.append(quote(txt))
                continue
            descr = ""
            for e in p._p.iter():
                if isinstance(e.tag, str) and e.tag.endswith("}docPr") and e.get("descr"):
                    descr = e.get("descr")
            path = store.add("img", part.blob, ext)
            if path:
                lines.append(f"![Picture {store.count('img')}{': ' + alt_text(descr) if descr else ''}]({path})")
            txt = pocr.read(part.blob) if pocr is not None else ""
            if txt:
                lines.append(quote(txt))
        except Exception:
            continue
    return lines


def convert_docx(data: bytes, filename: str = "document.docx", store: AssetStore | None = None,
                 pocr: PictureOCR | None = None) -> ConvertedDocument:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    t0 = time.perf_counter()
    try:
        doc = docx.Document(io.BytesIO(data))
    except Exception as e:
        raise ConversionError(f"could not open DOCX: {e}") from e

    blocks: list[str] = []
    title: str | None = None
    n_tables = n_formulas = 0
    counters: dict[int, int] = {}
    prev_list = False
    # If the file has a Title paragraph, Heading 1 becomes "##" so the title stays the only "#".
    has_title = any((p.style is not None and (p.style.name or "").lower() == "title") and p.text.strip()
                    for p in doc.paragraphs)
    offset = 1 if has_title else 0
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, doc)
            style = (p.style.name or "") if p.style is not None else ""
            eqs: list[str] = []
            text = _para_md(p, math=eqs)
            plain = _para_md(p, plain=True)
            pics = _para_pictures(doc, p, store, pocr)
            n_formulas += len(eqs)
            if not plain and eqs:
                plain = " ".join(eqs)
            if not plain:
                if pics:
                    blocks.extend(pics)
                    prev_list = False
                continue
            m = re.match(r"heading (\d)", style, re.I)
            if style.lower() == "title" or m:
                lvl = 1 if style.lower() == "title" else min(int(m.group(1)) + offset, 6)
                blocks.append("#" * lvl + " " + plain)
                if title is None and (lvl == 1 or style.lower() == "title"):
                    title = plain
                elif title is None:
                    title = plain
                prev_list = False
                continue
            kind, level = _num_format(doc, p)
            if kind:
                indent = "  " * level
                if kind == "number":
                    counters[level] = counters.get(level, 0) + 1
                    for deeper in [k for k in counters if k > level]:
                        counters.pop(deeper)
                    item = f"{indent}{counters[level]}. {text}"
                else:
                    item = f"{indent}- {text}"
                if prev_list and blocks:
                    blocks[-1] += "\n" + item
                else:
                    blocks.append(item)
                prev_list = True
                continue
            counters.clear()
            prev_list = False
            if style.lower() == "subtitle":
                text = f"*{plain}*"
            blocks.append(text.strip())
            blocks.extend(pics)
        elif tag == "tbl":
            tbl = Table(child, doc)
            rows = []
            for r in tbl.rows:
                seen, cells = set(), []
                for c in r.cells:
                    cells.append("" if id(c._tc) in seen else " ".join(
                        _para_md(pp) for pp in c.paragraphs if pp.text.strip()))
                    seen.add(id(c._tc))
                rows.append(cells)
            if rows:
                blocks.append(md_table(rows))
                n_tables += 1
            prev_list = False
    images = len(doc.inline_shapes)
    warnings = []
    if store is not None:
        images = max(0, images - store.count("img"))
        if images:
            warnings.append(f"{images} picture(s) could not be saved (unsupported format such as EMF/WMF, or limit reached)")
    elif pocr is not None:
        images = max(0, images - pocr.read_count)
        if images:
            warnings.append(f"{images} picture(s) had no readable text and were omitted")
    elif images:
        warnings.append(f"{images} image(s) omitted: only text is converted")
    warnings.append("headers, footers, footnotes and text boxes are not included")
    if pocr is not None:
        warnings.extend(pocr.note())
    md = tidy("\n\n".join(blocks))
    if not md.strip():
        warnings.append("no text found in this document")
    if title is None:
        title = (doc.core_properties.title or "").strip() or None
    return ConvertedDocument(filename, "docx", md, title=title, tables=n_tables, images_omitted=images,
                             warnings=warnings, seconds=round(time.perf_counter() - t0, 3),
                             size_bytes=len(data), formulas=n_formulas,
                             assets=dict(store.files) if store is not None else {},
                             figures=store.count("img") if store is not None else 0)


# =========================================================================== XLSX
def _fmt_value(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, datetime):
        return v.date().isoformat() if v.time() == dtime(0, 0) else v.isoformat(sep=" ", timespec="minutes")
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, dtime):
        return v.isoformat(timespec="minutes")
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() and abs(v) < 1e15 else format(v, ".15g")
    return clean_chars(str(v))


def convert_xlsx(data: bytes, filename: str = "workbook.xlsx") -> ConvertedDocument:
    import openpyxl

    t0 = time.perf_counter()
    try:
        wb_vals = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        wb_form = openpyxl.load_workbook(io.BytesIO(data), data_only=False)
    except Exception as e:
        raise ConversionError(f"could not open XLSX: {e}") from e
    blocks: list[str] = []
    warnings: list[str] = []
    sheets: list[str] = []
    n_tables = images = no_cache = 0
    for ws in wb_vals.worksheets:
        if ws.sheet_state != "visible":
            warnings.append(f"hidden sheet '{ws.title}' skipped")
            continue
        wf = wb_form[ws.title]
        sheets.append(ws.title)
        images += len(getattr(ws, "_images", [])) + len(getattr(ws, "_charts", []))
        max_r, max_c = min(ws.max_row or 0, MAX_SHEET_ROWS), min(ws.max_column or 0, MAX_SHEET_COLS)
        if (ws.max_row or 0) > MAX_SHEET_ROWS:
            warnings.append(f"sheet '{ws.title}' truncated to {MAX_SHEET_ROWS} rows")
        if (ws.max_column or 0) > MAX_SHEET_COLS:
            warnings.append(f"sheet '{ws.title}' truncated to {MAX_SHEET_COLS} columns")
        rows: list[list[str]] = []
        for r in range(1, max_r + 1):
            row = []
            for c in range(1, max_c + 1):
                v = ws.cell(r, c).value
                if v is None:
                    f = wf.cell(r, c).value
                    if isinstance(f, str) and f.startswith("="):
                        v, no_cache = f, no_cache + 1
                row.append(_fmt_value(v))
            rows.append(row)
        # trim empty trailing columns, then split into tables at fully empty rows
        while rows and rows[0] and all(not r[-1] for r in rows if r):
            rows = [r[:-1] for r in rows]
            if not rows[0]:
                break
        segments: list[list[list[str]]] = []
        cur: list[list[str]] = []
        for row in rows:
            if any(c.strip() for c in row):
                cur.append(row)
            elif cur:
                segments.append(cur)
                cur = []
        if cur:
            segments.append(cur)
        blocks.append(f"## {ws.title}")
        if not segments:
            blocks.append("*(empty sheet)*")
        for seg in segments:
            blocks.append(md_table(seg))
            n_tables += 1
    if no_cache:
        warnings.append(f"{no_cache} formula cell(s) had no stored result (file never recalculated); "
                        "the formula text is shown instead")
    if images:
        warnings.append(f"{images} chart(s)/image(s) omitted")
    md = tidy("\n\n".join(blocks))
    title = (wb_vals.properties.title or "").strip() or None
    return ConvertedDocument(filename, "xlsx", md, title=title, sheets=sheets, tables=n_tables,
                             images_omitted=images, warnings=warnings,
                             seconds=round(time.perf_counter() - t0, 3), size_bytes=len(data))


def convert_csv(data: bytes, filename: str = "data.csv") -> ConvertedDocument:
    t0 = time.perf_counter()
    text = _decode(data)
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel_tab if filename.lower().endswith(".tsv") else csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect)]
    warnings = []
    if len(rows) > MAX_SHEET_ROWS:
        rows = rows[:MAX_SHEET_ROWS]
        warnings.append(f"truncated to {MAX_SHEET_ROWS} rows")
    md = tidy(md_table(rows)) if rows else ""
    return ConvertedDocument(filename, "csv", md, tables=1 if rows else 0, warnings=warnings,
                             seconds=round(time.perf_counter() - t0, 3), size_bytes=len(data))


# =========================================================================== PPTX
def _decode(data: bytes) -> str:
    """Bytes -> text. UTF-16 is only trusted when the file starts with its byte-order mark: almost any
    byte string decodes as UTF-16, so trying it blindly turns Windows-1252 text into garbage."""
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            pass
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _shape_sort_key(sh):
    return (round((sh.top or 0) / 228600), sh.left or 0)  # rows of ~0.25 inch, then left to right


def _walk(shapes):
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    for sh in sorted(shapes, key=_shape_sort_key):
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk(sh.shapes)
        else:
            yield sh


def _chart_md(chart) -> str:
    try:
        plot = chart.plots[0]
        cats = [str(c) for c in plot.categories]
        rows = [["", *[s.name or "" for s in plot.series]]]
        for i, c in enumerate(cats):
            rows.append([c, *[_fmt_value(list(s.values)[i]) for s in plot.series]])
        head = ""
        if chart.has_title and chart.chart_title.has_text_frame:
            head = f"**Chart: {chart.chart_title.text_frame.text.strip()}**\n\n"
        return head + md_table(rows)
    except Exception:
        return ""


def convert_pptx(data: bytes, filename: str = "slides.pptx", store: AssetStore | None = None,
                 pocr: PictureOCR | None = None) -> ConvertedDocument:
    from pptx import Presentation
    from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER

    t0 = time.perf_counter()
    try:
        prs = Presentation(io.BytesIO(data))
    except Exception as e:
        raise ConversionError(f"could not open PPTX: {e}") from e
    blocks: list[str] = []
    warnings: list[str] = []
    n_tables = images = 0
    deck_title: str | None = None
    for no, slide in enumerate(prs.slides, 1):
        title_shape = slide.shapes.title
        title = clean_chars(title_shape.text_frame.text).strip().replace("\x0b", " ") if \
            title_shape is not None and title_shape.has_text_frame else ""
        if deck_title is None and title:
            deck_title = title
        blocks.append(f"## Slide {no}: {title}" if title else f"## Slide {no}")
        for sh in _walk(slide.shapes):
            if title_shape is not None and sh.shape_id == title_shape.shape_id:
                continue
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
                saved = False
                try:
                    blob, ext = sh.image.blob, (sh.image.ext or "").lower()
                except Exception:
                    blob, ext = None, ""
                if store is not None and blob and ext in ("png", "jpg", "jpeg", "gif"):
                    path = store.add("img", blob, ext, tag=f"s{no}_")
                    if path:
                        descr = sh._element.xpath(".//p:cNvPr/@descr")
                        blocks.append(f"![Picture {store.count('img')}"
                                      f"{': ' + alt_text(descr[0]) if descr and not re.search(r'\.(png|jpe?g|gif)$', descr[0], re.I) else ''}]({path})")
                        saved = True
                read = False
                if pocr is not None and blob and ext in ("png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif"):
                    txt = pocr.read(blob)
                    if txt:
                        blocks.append(quote(txt))
                        read = True
                if not saved and not read:
                    images += 1
                continue
            if getattr(sh, "has_chart", False) and sh.has_chart:
                md = _chart_md(sh.chart)
                if md:
                    blocks.append(md)
                    n_tables += 1
                images += 0
                continue
            if getattr(sh, "has_table", False) and sh.has_table:
                rows = [[clean_chars(c.text) for c in r.cells] for r in sh.table.rows]
                blocks.append(md_table(rows))
                n_tables += 1
                continue
            if sh.has_text_frame and sh.text_frame.text.strip():
                is_body = sh.is_placeholder and sh.placeholder_format.type in (
                    PP_PLACEHOLDER.BODY, PP_PLACEHOLDER.OBJECT)
                lines, any_bullet = [], False
                for p in sh.text_frame.paragraphs:
                    txt = clean_chars("".join(r.text for r in p.runs) or p.text).replace("\x0b", " ").strip()
                    if not txt:
                        continue
                    pPr = p._p.pPr
                    has_bu = pPr is not None and any(
                        ch.tag.rsplit("}", 1)[-1] in ("buChar", "buAutoNum") for ch in pPr)
                    no_bu = pPr is not None and any(ch.tag.rsplit("}", 1)[-1] == "buNone" for ch in pPr)
                    if (is_body and not no_bu) or has_bu:
                        lines.append("  " * p.level + "- " + txt)
                        any_bullet = True
                    else:
                        lines.append(txt)
                if lines:
                    blocks.append("\n".join(lines) if any_bullet else "\n\n".join(lines))
        if slide.has_notes_slide:
            notes = clean_chars(slide.notes_slide.notes_text_frame.text or "").strip()
            if notes:
                blocks.append("> **Notes:** " + notes.replace("\n", "\n> "))
    if images:
        warnings.append(f"{images} picture(s) omitted: " + ("unsupported format or limit reached"
                                                           if store is not None else
                                                           "no readable text" if pocr is not None else
                                                           "only text is converted"))
    if pocr is not None:
        warnings.extend(pocr.note())
    md = tidy("\n\n".join(blocks))
    title = deck_title or (prs.core_properties.title or "").strip() or None
    return ConvertedDocument(filename, "pptx", md, title=title, pages=len(prs.slides), tables=n_tables,
                             images_omitted=images, warnings=warnings,
                             seconds=round(time.perf_counter() - t0, 3), size_bytes=len(data),
                             assets=dict(store.files) if store is not None else {},
                             figures=store.count("img") if store is not None else 0)
