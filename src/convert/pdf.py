"""PDF -> Markdown.

Pipeline (all offline, pdfplumber + Tesseract):

1. Per page, read words with font size / font name.
2. Pages without a text layer are OCR'd (scanned PDFs, hybrid PDFs).
3. Ruled tables are found with pdfplumber and emitted as Markdown tables.
4. Two-column layouts are detected from an empty vertical gutter and read
   left column first, then right column (full-width lines stay in place).
5. Repeated headers/footers and bare page numbers are removed (counted in the result).
6. Lines are classified: heading (larger font, or short all-bold line), list item,
   monospace code line, or paragraph text; wrapped lines are re-joined and
   end-of-line hyphenation is repaired.

Known limits are listed in docs/deep_dive/conversion_notes.md (tables without ruling lines
come out as text, images are omitted, maths is plain text).
"""
from __future__ import annotations

import io
import re
import statistics
import time
from collections import Counter
from dataclasses import dataclass

from .pdf_special import extract_special
from .base import CID_RE, ConversionError, ConvertedDocument, clean_chars, md_table, tidy

BULLET_RE = re.compile(r"^([•●▪◦‣•●▪◦\-–—*])\s+(.+)$")
NUMBER_RE = re.compile(r"^(\d{1,3}[.)])\s+(.+)$")
REF_RE = re.compile(r"^\[\d{1,3}\]\s")
PAGE_NUM_RE = re.compile(r"^\s*(page\s*)?\d{1,4}(\s*(/|of)\s*\d{1,4})?\s*$", re.I)
MONO_HINT = ("mono", "courier", "consolas", "menlo", "code", "typewriter")
# A gap wider than this fraction of the font size is a space. Justified text can squeeze word gaps to
# about 0.15 em while kerning inside a word stays below 0.05 em. The same value is used to split words
# and to put spaces back, so they cannot disagree.
WORD_GAP = 0.12
BOLD_HINT = ("bold", "black", "heavy", "semibold", "demi")


@dataclass
class Item:
    kind: str            # "line" | "table" | "ocr" | "block" (stand-alone text block)
    page: int
    top: float
    bottom: float
    x0: float
    x1: float
    text: str = ""
    size: float = 0.0
    bold: bool = False
    mono: bool = False
    col: int | None = None   # None = full width, 0 = left, 1 = right
    page_height: float = 0.0


# ------------------------------------------------------------------ layout helpers
def _rows(words: list[dict]) -> list[list[dict]]:
    """Cluster words into visual rows by vertical centre."""
    ws = sorted(words, key=lambda w: ((w["top"] + w["bottom"]) / 2, w["x0"]))
    rows: list[list[dict]] = []
    for w in ws:
        cy = (w["top"] + w["bottom"]) / 2
        if rows:
            r = rows[-1]
            rcy = sum((x["top"] + x["bottom"]) / 2 for x in r) / len(r)
            rsize = max(x["size"] for x in r)
            if abs(cy - rcy) <= 0.55 * max(rsize, w["size"]):
                r.append(w)
                continue
        rows.append([w])
    return [sorted(r, key=lambda w: w["x0"]) for r in rows]


def _detect_gutter(rows: list[list[dict]], width: float) -> tuple[float, float] | None:
    """Find the empty vertical strip between two text columns, or None for a one-column page.

    A page can start with a full-width title and abstract above a two-column body, so up to 30% of the
    rows may cross the middle. What proves two columns is that many rows have a clear gap there and that
    clearly more rows are split than full-width."""
    if len(rows) < 12:
        return None
    n = int(width) + 1
    cover = [0] * n
    for r in rows:
        seen = set()
        for w in r:
            for x in range(max(0, int(w["x0"])), min(n, int(w["x1"]) + 1)):
                seen.add(x)
        for x in seen:
            cover[x] += 1
    lo, hi = int(0.35 * width), int(0.65 * width)
    thr = 0.30 * len(rows)
    best, cur_start = (0, 0), None
    for x in range(lo, hi + 1):
        if cover[x] <= thr:
            cur_start = x if cur_start is None else cur_start
            if x - cur_start + 1 > best[1] - best[0]:
                best = (cur_start, x + 1)
        else:
            cur_start = None
    gx0, gx1 = best
    if gx1 - gx0 < 8:
        return None
    words = [w for r in rows for w in r]
    left = sum(1 for w in words if w["x1"] <= gx0 + 1)
    right = sum(1 for w in words if w["x0"] >= gx1 - 1)
    if left < 0.25 * len(words) or right < 0.25 * len(words):
        return None
    gw = gx1 - gx0
    split = full = 0
    for r in rows:
        L = [w for w in r if w["x1"] <= gx0 + 1]
        R = [w for w in r if w["x0"] >= gx1 - 1]
        if L and R and min(w["x0"] for w in R) - max(w["x1"] for w in L) >= max(6.0, 0.6 * gw):
            split += 1
        elif not (L and not R) and not (R and not L):
            full += 1
    if split < 6 or split < 2 * full:
        return None
    return float(gx0), float(gx1)


def _is_bold(fontname: str) -> bool:
    f = (fontname or "").lower()
    return any(h in f for h in BOLD_HINT)


def _is_mono(fontname: str) -> bool:
    f = (fontname or "").lower()
    return any(h in f for h in MONO_HINT)


def _fix_symbol_bullet(ws: list[dict]) -> list[dict]:
    """Bullets are often a single glyph from a symbol font (private-use code point). Make it '•'."""
    first = ws[0]
    t = first["text"]
    f = (first.get("fontname") or "").lower()
    if len(ws) > 1 and re.fullmatch(r"\(cid:\d+\)", t):
        return [dict(first, text="•")] + ws[1:]
    if len(t) == 1 and (0xF000 <= ord(t) <= 0xF0FF or any(h in f for h in ("symbol", "wingding", "dingbat"))):
        ws = [dict(first, text="•", fontname=ws[1]["fontname"] if len(ws) > 1 else first["fontname"])] + ws[1:]
    return ws


def _line_from_words(ws: list[dict], page: int, col: int | None, page_h: float) -> Item:
    ws = _fix_symbol_bullet(ws)
    parts, prev = [], None
    for w in ws:
        if prev is not None and w["x0"] - prev["x1"] > WORD_GAP * max(w["size"], 1):
            parts.append(" ")
        parts.append(w["text"])
        prev = w
    sizes = [w["size"] for w in ws]
    return Item(
        kind="line", page=page, top=min(w["top"] for w in ws), bottom=max(w["bottom"] for w in ws),
        x0=min(w["x0"] for w in ws), x1=max(w["x1"] for w in ws),
        text=clean_chars("".join(parts)).strip(), size=statistics.median(sizes),
        bold=all(_is_bold(w["fontname"]) for w in ws), mono=all(_is_mono(w["fontname"]) for w in ws),
        col=col, page_height=page_h)


def _order(items: list[Item]) -> list[Item]:
    """Reading order: top-to-bottom; between full-width items, left column then right column."""
    out: list[Item] = []
    buf: list[Item] = []

    def flush():
        out.extend(sorted([i for i in buf if i.col == 0], key=lambda i: i.top))
        out.extend(sorted([i for i in buf if i.col == 1], key=lambda i: i.top))
        buf.clear()

    for it in sorted(items, key=lambda i: (i.top, i.x0)):
        if it.col is None:
            flush()
            out.append(it)
        else:
            buf.append(it)
    flush()
    return out


# ------------------------------------------------------------------ rotated text
def _orient(c: dict) -> str:
    """normal | up | down | flipped | diagonal, from the glyph's transform matrix (a, b, c, d, e, f).

    pdfminer's own 'upright' flag calls 45 degree and 180 degree text upright, so it cannot be used."""
    m = c.get("matrix")
    if not m or not str(c.get("text", "")).strip():
        return "normal"
    a, b = m[0], m[1]
    if abs(b) > 5 * abs(a):
        return "up" if b > 0 else "down"
    if a < 0 and abs(b) <= 0.17 * abs(a):
        return "flipped"
    if abs(b) > 0.17 * abs(a):
        return "diagonal"
    return "normal"


def _rotated_blocks(page, pno: int, H: float, W: float) -> tuple[list[Item], int]:
    """Read vertical and upside-down text (arXiv margin stamps, rotated labels) in its real reading
    direction. Diagonal text (watermarks) is dropped and counted. Returns (blocks, dropped_chars)."""
    groups: dict[tuple[str, int], list[dict]] = {}
    dropped = 0
    for c in page.chars:
        o = _orient(c)
        if o == "normal":
            continue
        if o == "diagonal":
            dropped += 1
            continue
        m = c["matrix"]
        # The baseline is the same for every glyph of a line. pdfplumber's `size` is NOT usable here: for
        # rotated glyphs it is the glyph's own advance, so it differs from letter to letter.
        line_coord = m[4] if o in ("up", "down") else (H - m[5])
        groups.setdefault((o, round(line_coord / 4.0)), []).append(c)
    blocks: list[Item] = []
    for (o, _), chars in sorted(groups.items(), key=lambda kv: (min(c["top"] for c in kv[1]), kv[0][1])):
        key = {"up": lambda c: -c["top"], "down": lambda c: c["top"], "flipped": lambda c: -c["x0"]}[o]
        chars.sort(key=key)
        out, prev = [], None
        for c in chars:
            if prev is not None:
                gap = {"up": prev["top"] - c["bottom"], "down": c["top"] - prev["bottom"],
                       "flipped": prev["x0"] - c["x1"]}[o]
                font_size = (c["x1"] - c["x0"]) if o in ("up", "down") else (c["bottom"] - c["top"])
                if gap > WORD_GAP * max(font_size, 1):
                    out.append(" ")
            out.append(c["text"])
            prev = c
        text = clean_chars("".join(out)).strip()
        if len(text) >= 3:
            blocks.append(Item("block", pno, min(c["top"] for c in chars), max(c["bottom"] for c in chars),
                               min(c["x0"] for c in chars), max(c["x1"] for c in chars), text,
                               page_height=H))
    return blocks, dropped


# ------------------------------------------------------------------ tables with horizontal rules only
def _rule_tables(page, words: list[dict], pno: int, H: float, existing: list[Item]) -> list[Item]:
    """Tables typeset with horizontal rules only (LaTeX booktabs, many reports). pdfplumber needs a full
    grid, so these are found here: two or more long, equally wide rules enclose rows of words, and the
    columns are the empty vertical strips between the words."""
    W = float(page.width)
    rules: list[tuple[float, float, float]] = []
    for ln in page.lines:
        if abs(ln["bottom"] - ln["top"]) < 1.5 and ln["x1"] - ln["x0"] > 0.2 * W:
            rules.append((ln["top"], ln["x0"], ln["x1"]))
    for rc in page.rects:
        if rc["height"] < 2.0 and rc["width"] > 0.2 * W:
            rules.append(((rc["top"] + rc["bottom"]) / 2, rc["x0"], rc["x1"]))
    rules.sort()
    groups: list[list[tuple[float, float, float]]] = []
    for r in rules:
        for g in groups:
            if abs(g[0][1] - r[1]) < 8 and abs(g[0][2] - r[2]) < 8 and 0 <= r[0] - g[-1][0] <= 300:
                if r[0] - g[-1][0] > 1:           # same rule drawn twice
                    g.append(r)
                break
        else:
            groups.append([r])
    out: list[Item] = []
    for g in groups:
        if len(g) < 2:
            continue
        top, bottom, gx0, gx1 = g[0][0], g[-1][0], g[0][1], g[0][2]
        if any(t.top < bottom and t.bottom > top and t.x0 < gx1 and t.x1 > gx0 for t in existing + out):
            continue
        ws = [w for w in words if top + 0.5 < (w["top"] + w["bottom"]) / 2 < bottom - 0.5
              and gx0 - 4 <= (w["x0"] + w["x1"]) / 2 <= gx1 + 4]
        rows = _rows(ws)
        if len(rows) < 2 or len(rows) > 60:
            continue
        gap = max(6.0, 0.9 * statistics.median(w["size"] for w in ws))
        cols: list[list[float]] = []
        for w in sorted(ws, key=lambda w: w["x0"]):
            if cols and w["x0"] - cols[-1][1] < gap:
                cols[-1][1] = max(cols[-1][1], w["x1"])
            else:
                cols.append([w["x0"], w["x1"]])
        if len(cols) < 2:
            continue
        grid = []
        for r in rows:
            cells = [[] for _ in cols]
            for w in r:
                cx = (w["x0"] + w["x1"]) / 2
                k = next((i for i, c in enumerate(cols) if c[0] - 1 <= cx <= c[1] + 1), None)
                if k is not None:
                    cells[k].append(w["text"])
            grid.append([clean_chars(" ".join(c)) for c in cells])
        multi = sum(1 for row in grid if sum(1 for c in row if c) >= 2)
        if multi < 0.6 * len(grid):
            continue                              # not tabular: probably a ruled title or note
        out.append(Item("table", pno, top, bottom, gx0, gx1, md_table(grid), page_height=H))
    return out


# ------------------------------------------------------------------ OCR
def _ocr_page(page) -> str:
    try:
        import pytesseract
    except ImportError as e:
        raise ConversionError("OCR needs pytesseract and the tesseract program installed") from e
    img = page.to_image(resolution=250).original.convert("L")
    from .image import check_language, ocr_lang
    lang = ocr_lang()
    check_language(lang)
    return pytesseract.image_to_string(img, lang=lang)


OCR_LIST_RE = re.compile(r"^(\d{1,3}[.)]\s|[•●▪◦‣*\-–—eo¢«»]\s)")


def _ocr_blocks(text: str) -> list[str]:
    """Split OCR output into paragraphs. Blocks that look like lists keep one item per line."""
    out = []
    for b in re.split(r"\n\s*\n", clean_chars(text)):
        lines = [l.strip() for l in b.splitlines() if l.strip()]
        if not lines:
            continue
        marked = [l for l in lines if OCR_LIST_RE.match(l)]
        if len(lines) > 1 and len(marked) >= 2:
            fixed = []
            for l in lines:
                m = re.match(r"^([•●▪◦‣*\-–—eo¢«»])\s+(.*)$", l)
                fixed.append(f"- {m.group(2)}" if m else l)   # OCR often reads a bullet as 'e', 'o' or '¢'
            out.append("\n".join(fixed))
        else:
            out.append(" ".join(lines))
    return out


# ------------------------------------------------------------------ main
def convert_pdf(data: bytes, filename: str = "document.pdf", *, page_markers: bool = False,
                strip_repeated: bool = True, force_ocr: bool = False, store=None, pocr=None) -> ConvertedDocument:
    """store: an AssetStore; when given, figures, diagrams and display equations are saved as images."""
    import pdfplumber

    t0 = time.perf_counter()
    warnings: list[str] = []
    try:
        pdf = pdfplumber.open(io.BytesIO(data))
    except Exception as e:
        # pdfplumber wraps pdfminer errors, and the wrapper's own text is empty: look at the whole chain.
        chain, cur = [], e
        while cur is not None and len(chain) < 6:
            chain.append(f"{cur.__class__.__name__} {cur}".lower())
            cur = cur.__cause__ or cur.__context__
        if any("password" in c or "encrypt" in c for c in chain):
            raise ConversionError("this PDF is password-protected; remove the password and try again") from e
        msg = str(e) or e.__class__.__name__
        raise ConversionError(f"could not open PDF: {msg}") from e

    items: list[Item] = []
    n_tables = n_images = n_ocr = n_rotated = n_diagonal = 0
    with pdf:
        n_pages = len(pdf.pages)
        for pno, page in enumerate(pdf.pages, 1):
            H, W = float(page.height), float(page.width)
            try:
                has_odd = any(_orient(c) != "normal" for c in page.chars)
                src = page.filter(lambda o: o.get("object_type") != "char" or _orient(o) == "normal") \
                    if has_odd else page
                words = src.extract_words(x_tolerance=3, x_tolerance_ratio=WORD_GAP, y_tolerance=2,
                                          keep_blank_chars=False, extra_attrs=["size", "fontname"])
            except Exception as e:  # damaged page
                warnings.append(f"page {pno}: could not read text ({e})")
                words = []
            n_images += len(page.images)
            rotated_blocks, dropped = _rotated_blocks(page, pno, H, W)
            n_rotated += len(rotated_blocks)
            n_diagonal += dropped
            chars = sum(len(w["text"]) for w in words)
            if force_ocr or chars < 20:
                try:
                    blocks = _ocr_blocks(_ocr_page(page))
                except ConversionError as e:
                    warnings.append(f"page {pno}: no text layer and OCR unavailable ({e})")
                    blocks = []
                if blocks:
                    n_ocr += 1
                    top = 0.0
                    for b in blocks:
                        items.append(Item("ocr", pno, top, top + 1, 0, W, b, page_height=H))
                        top += 1
                continue

            table_items: list[Item] = []
            try:
                for tb in page.find_tables():
                    rows = [[(c or "").replace("\n", " ").strip() for c in r] for r in tb.extract()]
                    cells = [c for r in rows for c in r]
                    if len(rows) >= 2 and max(len(r) for r in rows) >= 2 and \
                            sum(1 for c in cells if c) >= 0.4 * len(cells):
                        x0, top, x1, bottom = tb.bbox
                        table_items.append(Item("table", pno, top, bottom, x0, x1,
                                                md_table(rows), page_height=H))
            except Exception as e:
                warnings.append(f"page {pno}: table detection failed ({e})")
            table_items += _rule_tables(page, words, pno, H, table_items)
            n_tables += len(table_items)

            def in_table(w):
                cx, cy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
                return any(t.x0 - 1 <= cx <= t.x1 + 1 and t.top - 1 <= cy <= t.bottom + 1 for t in table_items)

            words = [w for w in words if not in_table(w)]
            special: list[Item] = []
            if store is not None:
                try:
                    found, words = extract_special(page, words, [(t.x0, t.top, t.x1, t.bottom) for t in table_items],
                                                   store, _rows, pno, pocr)
                    for kind, b, md_text in found:
                        special.append(Item("block", pno, b[1], b[3], b[0], b[2], md_text, page_height=H))
                except Exception as e:      # a damaged drawing must not stop the text from converting
                    warnings.append(f"page {pno}: figures and equations could not be extracted ({e})")
            rows = _rows(words)
            gutter = _detect_gutter(rows, W)
            page_items: list[Item] = []
            for r in rows:
                if not gutter:
                    page_items.append(_line_from_words(r, pno, None, H))
                    continue
                gw = gutter[1] - gutter[0]
                mid = (gutter[0] + gutter[1]) / 2
                crosses = any(w["x0"] < gutter[0] and w["x1"] > gutter[1] for w in r)
                left = [w for w in r if (w["x0"] + w["x1"]) / 2 < mid]
                right = [w for w in r if (w["x0"] + w["x1"]) / 2 >= mid]
                if crosses:
                    page_items.append(_line_from_words(r, pno, None, H))
                elif left and right:
                    gap = min(w["x0"] for w in right) - max(w["x1"] for w in left)
                    if gap >= max(6.0, 0.6 * gw):          # a real column gap, not a word space
                        page_items.append(_line_from_words(left, pno, 0, H))
                        page_items.append(_line_from_words(right, pno, 1, H))
                    else:                                  # full-width text that happens to be near the gutter
                        page_items.append(_line_from_words(r, pno, None, H))
                elif left:
                    page_items.append(_line_from_words(left, pno, 0, H))
                else:
                    page_items.append(_line_from_words(right, pno, 1, H))
            for t in table_items + special:
                if gutter and (t.x1 <= gutter[0] + 2 or t.x0 >= gutter[1] - 2):
                    t.col = 0 if t.x1 <= gutter[0] + 2 else 1
                page_items.append(t)
            items.extend(_order(page_items))
            items.extend(rotated_blocks)     # margin stamps etc.: after the page's normal text

    if pocr is not None:
        warnings.extend(pocr.note())
    if store is not None:
        if store.skipped:
            warnings.append(f"{store.skipped} more figure(s) or equation(s) were found but not saved "
                            f"(limit of {store.limit} per document)")
        if n_images and not store.count("fig"):
            warnings.append(f"{n_images} image(s) could not be saved as pictures (too small or page backgrounds)")
    elif n_images:
        warnings.append(f"{n_images} image(s) omitted: only text is converted")
    if n_rotated:
        warnings.append(f"{n_rotated} line(s) of vertical text (margin stamps, rotated labels) were moved to "
                        "the end of their page")
    if n_diagonal:
        warnings.append(f"{n_diagonal} character(s) of diagonal text (watermarks) were skipped")
    if n_ocr:
        warnings.append(f"{n_ocr} page(s) had no text layer and were read with OCR (expect character errors)")

    removed = 0
    if strip_repeated and n_pages >= 2:
        items, removed = _strip_margins(items, n_pages)

    md, title_from_md = _assemble(items, page_markers)
    md = tidy(md)
    n_cid = len(CID_RE.findall(md))
    if n_cid:
        warnings.append(f"{n_cid} character(s) could not be decoded (the PDF's font has no Unicode table) "
                        "and appear as (cid:N); running OCR on this file may read them correctly")
    if not md.strip():
        warnings.append("no text could be extracted from this PDF")
    meta_title = None
    try:
        with pdfplumber.open(io.BytesIO(data)) as p2:
            meta_title = (p2.metadata or {}).get("Title") or None
    except Exception:
        pass
    return ConvertedDocument(filename=filename, kind="pdf", markdown=md,
                             title=title_from_md or (clean_chars(str(meta_title)).strip() if meta_title else None),
                             pages=n_pages, tables=n_tables, images_omitted=n_images, ocr_pages=n_ocr,
                             headers_footers_removed=removed, warnings=warnings,
                             seconds=round(time.perf_counter() - t0, 3), size_bytes=len(data),
                             assets=dict(store.files) if store is not None else {},
                             figures=store.count("fig") if store is not None else 0,
                             formulas=store.count("eq") if store is not None else 0)


def _norm(t: str) -> str:
    return re.sub(r"\d+", "#", t.lower()).strip()


def _strip_margins(items: list[Item], n_pages: int) -> tuple[list[Item], int]:
    margin = [i for i in items if i.kind == "line" and i.page_height and
              (i.top < 0.08 * i.page_height or i.bottom > 0.92 * i.page_height)]
    pages_by_text: dict[str, set[int]] = {}
    for i in margin:
        pages_by_text.setdefault(_norm(i.text), set()).add(i.page)
    drop = set()
    for i in margin:
        if PAGE_NUM_RE.match(i.text):
            drop.add(id(i))
        elif n_pages >= 3 and len(pages_by_text[_norm(i.text)]) >= max(3, 0.5 * n_pages):
            drop.add(id(i))
    return [i for i in items if id(i) not in drop], len(drop)


# ------------------------------------------------------------------ assembly
def _assemble(items: list[Item], page_markers: bool) -> tuple[str, str | None]:
    lines = [i for i in items if i.kind == "line"]
    sizes = Counter()
    for i in lines:
        sizes[round(i.size * 2) / 2] += len(i.text)
    body = sizes.most_common(1)[0][0] if sizes else 10.0
    heading_sizes = sorted({round(i.size) for i in lines
                            if i.size >= body * 1.15 + 0.3 and len(i.text) <= 200}, reverse=True)

    def level_for(i: Item) -> int | None:
        if i.mono or len(i.text) > 200 or not i.text:
            return None
        if i.size >= body * 1.15 + 0.3:
            return min(heading_sizes.index(round(i.size)) + 1, 4)
        if i.bold and len(i.text) <= 100 and not i.text.endswith((",", ";", ".", "?", "!")) and \
                not BULLET_RE.match(i.text) and len(i.text.split()) <= 14:
            return min(len(heading_sizes) + 1, 4) if heading_sizes else 2
        return None

    blocks: list[str] = []
    title: str | None = None
    para: list[Item] = []        # current paragraph / list item lines
    para_kind = "p"              # p | li
    li_marker = "-"
    code: list[Item] = []
    heading: tuple[int, list[str], Item] | None = None
    last_page = 0

    def end_sentence(t: str) -> bool:
        return bool(re.search(r"[.!?:;”\")\]]\s*$", t))

    def join(parts: list[str]) -> str:
        out = ""
        for p in parts:
            p = p.strip()
            if not out:
                out = p
            elif out.endswith("-") and p[:1].islower() and len(out) > 1 and out[-2].isalpha():
                out = out[:-1] + p
            else:
                out += " " + p
        return out

    def flush_para():
        nonlocal para, para_kind
        if para:
            text = join([i.text for i in para])
            blocks.append(f"{li_marker} {text}" if para_kind == "li" else text)
        para = []
        para_kind = "p"

    def flush_code():
        nonlocal code
        if code:
            left = min(i.x0 for i in code)
            unit = max(code[0].size * 0.6, 1.0)
            body_lines = [" " * int(round((i.x0 - left) / unit)) + i.text for i in code]
            blocks.append("```\n" + "\n".join(body_lines) + "\n```")
        code = []

    def flush_heading():
        nonlocal heading, title
        if heading:
            lvl, parts, _ = heading
            text = " ".join(parts)
            blocks.append("#" * lvl + " " + text)
            if title is None and lvl == 1:
                title = text
        heading = None

    def flush_all():
        flush_heading()
        flush_para()
        flush_code()

    prev: Item | None = None
    for it in items:
        if page_markers and it.page != last_page:
            flush_all()
            blocks.append(f"<!-- page {it.page} -->")
        last_page = it.page
        if it.kind in ("table", "ocr", "block"):
            flush_all()
            blocks.append(it.text)
            prev = None
            continue

        lvl = level_for(it)
        if lvl:
            flush_para()
            flush_code()
            if heading and heading[0] == lvl and prev is not None and prev.page == it.page \
                    and it.top - prev.bottom < 0.8 * it.size:
                heading[1].append(it.text)
            else:
                flush_heading()
                heading = (lvl, [it.text], it)
            prev = it
            continue
        flush_heading()

        if it.mono:
            flush_para()
            code.append(it)
            prev = it
            continue
        flush_code()

        m_b, m_n = BULLET_RE.match(it.text), NUMBER_RE.match(it.text)
        new_block = False
        if m_b or m_n or REF_RE.match(it.text):
            new_block = True
        elif not para:
            new_block = True
        else:
            same_col = prev is not None and prev.page == it.page and prev.col == it.col
            if same_col:
                gap = it.top - prev.bottom
                if gap > 0.45 * it.size:
                    new_block = True
                elif prev.x0 < it.x0 - 0.8 * it.size and end_sentence(prev.text) and para_kind == "p":
                    new_block = True   # first-line indent after a finished sentence
            else:  # column or page change: continue only if the sentence is unfinished
                if end_sentence(para[-1].text) or it.text[:1].isupper():
                    new_block = True
        if new_block:
            flush_para()
            if m_b:
                para_kind, li_marker = "li", "-"
                it = _with_text(it, m_b.group(2))
            elif m_n:
                para_kind, li_marker = "li", m_n.group(1)
                it = _with_text(it, m_n.group(2))
        para.append(it)
        prev = it
    flush_all()
    return "\n\n".join(_merge_lists(blocks)), title


def _with_text(it: Item, text: str) -> Item:
    return Item(it.kind, it.page, it.top, it.bottom, it.x0, it.x1, text, it.size, it.bold, it.mono,
                it.col, it.page_height)


def _merge_lists(blocks: list[str]) -> list[str]:
    """Join consecutive list items with a single newline so they render as one list."""
    out: list[str] = []
    li = re.compile(r"^(- |\d{1,3}[.)] )")
    for b in blocks:
        if out and li.match(b) and li.match(out[-1].split("\n")[0]) and "\n\n" not in out[-1]:
            out[-1] += "\n" + b
        else:
            out.append(b)
    return out
