"""Figures, diagrams and display equations of one PDF page, saved as images.

Text extraction cannot represent a diagram or a typeset formula, so these regions are cropped from the
rendered page and stored through an ``AssetStore``. The words inside each region become the alt text.

How regions are found:
  figures   raster images, and clusters of many vector drawing objects (lines, curves, rectangles) that are
            not part of a table
  formulas  "segments" of a text row (words separated by small gaps) that are mostly set in a maths font or
            contain several maths symbols, with no running prose; neighbouring short segments (numerator,
            denominator, limits) are added to the box
"""
from __future__ import annotations

import re

from .assets import AssetStore, alt_text, png_bytes
from .picture_ocr import quote

MATH_FONT_HINTS = ("cmmi", "cmsy", "cmex", "cmmib", "msam", "msbm", "mtmi", "mtsy", "mtex", "mtextra",
                   "math", "stix", "euclid", "eufm", "rsfs", "txmi", "txsy", "mnsymbol")
MATH_CHARS = set("∑∏∫∮√∂∇∞≈≠≡≤≥≪≫±∓∈∉⊂⊃⊆⊇∪∩∀∃∄→←↔⇒⇔⇐↦∝∠⊥∥∧∨¬∅ℝℕℤℚℂ"
                 "αβγδεζηθικλμνξπρστυφχψω"
                 "ΓΔΘΛΞΠΣΦΨΩ")
EQ_NUMBER_RE = re.compile(r"^\(\s*[\w.\-]{1,8}\s*\)$")
MIN_FIG_W, MIN_FIG_H = 40.0, 30.0          # points
MIN_VECTOR_OBJECTS = 6
FIGURE_QUOTE_WORDS = 6        # figures with at least this many words also get their text as a quote
MAX_WORDS_IN_FIGURE = 60                   # a "figure" holding a page of text is a background, not a figure
RESOLUTION = 170                           # dpi of the crops


def is_math_font(fontname: str) -> bool:
    f = (fontname or "").lower()
    return any(h in f for h in MATH_FONT_HINTS)


def _segments(row: list[dict]) -> list[list[dict]]:
    """Split one text row where the gap between words is large (columns, equation numbers)."""
    segs: list[list[dict]] = []
    for w in row:
        if segs and w["x0"] - segs[-1][-1]["x1"] <= 1.6 * max(w["size"], 1):
            segs[-1].append(w)
        else:
            segs.append([w])
    return segs


def _seg_text(seg: list[dict]) -> str:
    return " ".join(w["text"] for w in seg)


def is_formula_segment(seg: list[dict]) -> bool:
    chars = sum(len(w["text"]) for w in seg)
    if not chars or chars > 200:
        return False
    text = _seg_text(seg)
    mf = sum(len(w["text"]) for w in seg if is_math_font(w.get("fontname", "")))
    sym = sum(1 for w in seg for c in w["text"] if c in MATH_CHARS)
    prose = len(re.findall(r"[A-Za-z]{4,}", text))
    if mf / chars >= 0.25 and prose < 4:
        return True
    if sym >= 2 and prose < 3:
        return True
    if sym >= 1 and prose == 0 and len(seg) <= 12 and re.search(r"[=<>≈≠≤≥]", text):
        return True
    return False


def _box(words: list[dict]) -> list[float]:
    return [min(w["x0"] for w in words), min(w["top"] for w in words),
            max(w["x1"] for w in words), max(w["bottom"] for w in words)]


def _union(a: list[float], b: list[float]) -> list[float]:
    return [min(a[0], b[0]), min(a[1], b[1]), max(a[2], b[2]), max(a[3], b[3])]


def _overlaps(a, b, pad: float = 0.0) -> bool:
    return a[0] - pad <= b[2] and b[0] - pad <= a[2] and a[1] - pad <= b[3] and b[1] - pad <= a[3]


def _inside(w: dict, box) -> bool:
    cx, cy = (w["x0"] + w["x1"]) / 2, (w["top"] + w["bottom"]) / 2
    return box[0] - 1 <= cx <= box[2] + 1 and box[1] - 1 <= cy <= box[3] + 1


def _crop(page, box, pad: float = 3.0):
    x0, top, x1, bottom = box
    bbox = (max(0.0, x0 - pad), max(0.0, top - pad),
            min(float(page.width), x1 + pad), min(float(page.height), bottom + pad))
    if bbox[2] - bbox[0] < 2 or bbox[3] - bbox[1] < 2:
        return None
    return png_bytes(page.crop(bbox).to_image(resolution=RESOLUTION).original)


# ------------------------------------------------------------------ figures
def _merge_boxes(boxes: list[list[float]], pad: float) -> list[list[float]]:
    merged: list[list[float]] = []
    for b in sorted(boxes):
        b = list(b)
        hit = [m for m in merged if _overlaps(m, b, pad)]
        for m in hit:
            merged.remove(m)
            b = _union(m, b)
        merged.append(b)
    return merged


def _vector_boxes(page, avoid: list, W: float, H: float) -> list[list[float]]:
    clusters: list[list] = []          # [x0, top, x1, bottom, count]
    for o in list(page.curves) + list(page.lines) + list(page.rects):
        w, h = o["x1"] - o["x0"], o["bottom"] - o["top"]
        if w > 0.9 * W and h > 0.9 * H:
            continue                                  # page background
        cx, cy = (o["x0"] + o["x1"]) / 2, (o["top"] + o["bottom"]) / 2
        if any(a[0] - 1 <= cx <= a[2] + 1 and a[1] - 1 <= cy <= a[3] + 1 for a in avoid):
            continue                                  # inside a table
        b = [o["x0"], o["top"], o["x1"], o["bottom"], 1]
        hit = [c for c in clusters if _overlaps(c, b, 12.0)]
        for c in hit:
            clusters.remove(c)
            b = _union(c, b) + [c[4] + b[4]]
        clusters.append(b)
    out = []
    for c in clusters:
        w, h = c[2] - c[0], c[3] - c[1]
        if c[4] >= MIN_VECTOR_OBJECTS and w >= MIN_FIG_W and h >= MIN_FIG_H and w * h < 0.7 * W * H:
            out.append(c[:4])
    return out


def _figure_boxes(page, avoid: list, W: float, H: float) -> list[list[float]]:
    boxes = []
    for im in page.images:
        w, h = im["x1"] - im["x0"], im["bottom"] - im["top"]
        if w >= MIN_FIG_W and h >= MIN_FIG_H and not (w * h > 0.85 * W * H):
            boxes.append([im["x0"], im["top"], im["x1"], im["bottom"]])
    boxes += _vector_boxes(page, avoid, W, H)
    return _merge_boxes(boxes, 4.0)


CAPTION_RE = re.compile(r"^(fig(ure)?\.?|table|tab\.)\s*\d", re.I)


def _absorb_labels(box: list[float], words: list[dict], rows_fn) -> list[float]:
    """Axis titles and tick labels just outside the drawing belong to it; captions do not."""
    box = list(box)
    for _ in range(2):
        for r in rows_fn(words):
            for seg in _segments(r):
                text = _seg_text(seg)
                if len(seg) > 3 or len(text) > 24 or CAPTION_RE.match(text):
                    continue
                sb = _box(seg)
                if not _inside_box(sb, box) and _overlaps(box, sb, 12.0):
                    box = _union(box, sb)
    return box


def _inside_box(a, b) -> bool:
    return a[0] >= b[0] - 1 and a[1] >= b[1] - 1 and a[2] <= b[2] + 1 and a[3] <= b[3] + 1


# ------------------------------------------------------------------ formulas
def _formula_boxes(rows: list[list[dict]]) -> list[tuple[list[float], list[dict]]]:
    """(box, words) for every display equation among the rows."""
    segs = [(i, s) for i, r in enumerate(rows) for s in _segments(r)]
    marked = [(i, s) for i, s in segs if is_formula_segment(s)]
    if not marked:
        return []
    groups: list[list] = []                       # [box, words]
    for _, s in marked:
        b = _box(s)
        hit = [g for g in groups if _overlaps(g[0], b, 0.8 * max(w["size"] for w in s))]
        words = list(s)
        for g in hit:
            groups.remove(g)
            b = _union(g[0], b)
            words += g[1]
        groups.append([b, words])
    taken = {id(w) for g in groups for w in g[1]}
    rest = [(i, s) for i, s in segs if not any(id(w) in taken for w in s)]
    for _ in range(3):                            # absorb fraction parts, limits, equation numbers
        changed = False
        for i, s in list(rest):
            sb, size = _box(s), max(w["size"] for w in s)
            text = _seg_text(s)
            small = len(text) <= 30 and not re.search(r"[A-Za-z]{5,}", text)
            for g in groups:
                gap_v = max(sb[1] - g[0][3], g[0][1] - sb[3], 0.0)
                h_overlap = sb[0] <= g[0][2] and sb[2] >= g[0][0]
                near_right = EQ_NUMBER_RE.match(text) and gap_v == 0 and sb[0] >= g[0][2]
                if (small and h_overlap and gap_v <= 0.7 * size) or near_right:
                    g[0] = _union(g[0], sb)
                    g[1].extend(s)
                    rest.remove((i, s))
                    changed = True
                    break
        if not changed:
            break
    return [(g[0], g[1]) for g in groups]


def formula_text(words: list[dict]) -> str:
    ws = sorted(words, key=lambda w: (round((w["top"] + w["bottom"]) / 2 / 4), w["x0"]))
    return " ".join(w["text"] for w in ws)


BULLET = re.compile(r"^[•●▪◦‣·*\-–—]\s*(.+)$")


def layout_text(words: list[dict], rows_fn) -> str:
    """Text of a figure in the shape it has on the page: one line per row, bullets as list items,
    indentation as nested items, clearly larger rows as headings."""
    rows = [r for r in rows_fn(words) if r]
    if not rows:
        return ""
    sizes = sorted(max(w.get("size", 10) for w in r) for r in rows)
    body = sizes[len(sizes) // 2] or 10
    base = min(r[0]["x0"] for r in rows)
    out: list[str] = []
    for r in rows:
        text = " ".join(w["text"] for w in r).strip()
        size = max(w.get("size", body) for w in r)
        m = BULLET.match(text)
        level = max(0, int(round((r[0]["x0"] - base) / (1.6 * body))))
        if m:
            out.append("  " * level + "- " + m.group(1))
        elif size >= 1.3 * body and len(text.split()) <= 12:
            out.append("## " + text)
        else:
            out.append(text)
    # blank line between a list and a following plain line (and the reverse) so Markdown keeps them apart
    res: list[str] = []
    for i, ln in enumerate(out):
        if i and (ln.lstrip().startswith("- ") != out[i - 1].lstrip().startswith("- ") or ln.startswith("## ")):
            res.append("")
        res.append(ln)
    return "\n".join(res)


# ------------------------------------------------------------------ entry point
def extract_special(page, words: list[dict], table_boxes: list, store: AssetStore, rows_fn, pno: int, pocr=None,
                    ) -> tuple[list[tuple[str, list[float], str]], list[dict]]:
    """Returns ([(kind, box, markdown)], remaining_words). ``kind`` is "figure" or "equation"."""
    W, H = float(page.width), float(page.height)
    found: list[tuple[str, list[float], str]] = []
    consumed: set[int] = set()

    for box in _figure_boxes(page, table_boxes, W, H):
        box = _absorb_labels(box, words, rows_fn)
        inside = [w for w in words if _inside(w, box)]
        if len(inside) > MAX_WORDS_IN_FIGURE:
            continue
        png = _crop(page, box)
        if png is None:
            continue
        n = store.count("fig") + 1
        path = store.add("fig", png, tag=f"p{pno}_")
        if path is None:
            continue
        label = alt_text(formula_text(inside)) if inside else ""
        md = f"![Figure {n}{': ' + label if label else ''}]({path})"
        # Words inside a figure (slide pages, labelled diagrams) are kept in full as a quote, because the
        # alt text is cut short. A picture without a text layer is read with OCR when that is switched on.
        full = layout_text(inside, rows_fn) if len(inside) >= FIGURE_QUOTE_WORDS else ""
        if not full and pocr is not None and len(inside) < FIGURE_QUOTE_WORDS:
            full = pocr.read(png)
        if full:
            md += "\n\n" + quote(full)
        found.append(("figure", box, md))
        consumed.update(id(w) for w in inside)

    left = [w for w in words if id(w) not in consumed]
    for box, ws in _formula_boxes(rows_fn(left)):
        png = _crop(page, box)
        if png is None:
            continue
        n = store.count("eq") + 1
        path = store.add("eq", png, tag=f"p{pno}_")
        if path is None:
            continue
        found.append(("equation", box, f"![Equation {n}: {alt_text(formula_text(ws), 120)}]({path})"))
        consumed.update(id(w) for w in ws)
    return found, [w for w in words if id(w) not in consumed]
