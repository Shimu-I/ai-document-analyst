"""Images (PNG, JPG, WEBP, TIFF, BMP, GIF) -> text/Markdown with Tesseract OCR.

What is done beyond a bare ``image_to_string``:

* transparent PNGs are put on white (otherwise the background turns black and OCR sees nothing),
  dark-mode screenshots are inverted, contrast is stretched, small images are enlarged;
* two page-segmentation modes are tried and the one that reads more text with more confidence wins;
* the layout is rebuilt from word positions: lines that were not wrapped stay separate lines,
  wrapped paragraph lines are re-joined, ``1.`` / ``-`` lines become list items and clearly larger
  lines become headings;
* the OCR confidence is reported, and the doubtful words are named so they can be checked;
* the language is configurable (``OCR_LANG=eng+ben``; the matching tesseract language pack is needed).
"""
from __future__ import annotations

import functools
import io
import os
import re
import statistics
import time

from .base import ConversionError, ConvertedDocument, clean_chars, tidy

LIST_NUM_RE = re.compile(r"^(\d{1,3})[.)]\s+(.*)$")
LIST_BUL_RE = re.compile(r"^[•●▪◦‣*·-]\s+(.*)$")
LABEL_RE = re.compile(r"^\S+( \S+){0,3}:(\s|$)")
MAX_FRAMES = 20
MAX_SIDE = 5000          # larger images are shrunk before OCR
MIN_SIDE = 1400          # smaller images are enlarged
LOW_CONF = 60            # words below this are named in the warning
WARN_MEAN_CONF = 85      # mean confidence below this produces a warning


@functools.lru_cache(maxsize=1)
def _installed_langs() -> frozenset:
    try:
        import pytesseract
        return frozenset(pytesseract.get_languages(config=""))
    except Exception:
        return frozenset()


def ocr_lang(explicit: str | None = None) -> str:
    """Language codes for Tesseract. ``auto`` (the default) reads English and, when its language pack is
    installed, Bengali too (``eng+ben``): Tesseract then picks the right script word by word."""
    lang = (explicit or os.getenv("OCR_LANG") or "auto").strip()
    if lang.lower() == "auto":
        return "eng+ben" if "ben" in _installed_langs() else "eng"
    return lang


def _imports():
    try:
        import pytesseract
        from PIL import Image, ImageOps
    except ImportError as e:
        raise ConversionError("OCR needs pytesseract, Pillow and the tesseract program") from e
    return pytesseract, Image, ImageOps


def check_language(lang: str) -> None:
    """Fail early with a helpful message if a requested language pack is not installed."""
    pytesseract, _, _ = _imports()
    try:
        have = set(pytesseract.get_languages(config=""))
    except Exception:  # tesseract missing or old: let the real call report the problem
        return
    missing = [code for code in lang.split("+") if code and code not in have]
    if missing:
        raise ConversionError(
            f"OCR language '{', '.join(missing)}' is not installed. Install it, e.g. "
            f"'sudo apt install tesseract-ocr-{missing[0]}' (installed: {', '.join(sorted(have - {'osd'}))})")


def prepare(img):
    """Return a grey image that is easier to read: flattened, upright, light background, enlarged."""
    _, Image, ImageOps = _imports()
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        img = Image.alpha_composite(base, rgba).convert("RGB")
    g = img.convert("L")
    if statistics.fmean(g.resize((64, 64)).tobytes()) < 110:       # light text on a dark background
        g = ImageOps.invert(g)
    g = ImageOps.autocontrast(g, cutoff=1)
    w, h = g.size
    side = max(w, h)
    if side < MIN_SIDE:
        f = min(3.0, MIN_SIDE / side)
        g = g.resize((round(w * f), round(h * f)), Image.LANCZOS)
    elif side > MAX_SIDE:
        f = MAX_SIDE / side
        g = g.resize((round(w * f), round(h * f)), Image.LANCZOS)
    return g


def _read_words(img, lang: str, psm: int):
    pytesseract, _, _ = _imports()
    try:
        d = pytesseract.image_to_data(img, lang=lang, config=f"--psm {psm}",
                                      output_type=pytesseract.Output.DICT, timeout=120)
    except pytesseract.TesseractNotFoundError as e:
        raise ConversionError("the tesseract program is not installed (sudo apt install tesseract-ocr)") from e
    except RuntimeError as e:
        raise ConversionError(f"OCR timed out or failed: {e}") from e
    words = []
    for i, t in enumerate(d["text"]):
        t = (t or "").strip()
        try:
            conf = float(d["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if t and conf >= 0:
            words.append({"text": t, "conf": conf, "key": (d["block_num"][i], d["par_num"][i], d["line_num"][i]),
                          "left": d["left"][i], "top": d["top"][i], "w": d["width"][i], "h": d["height"][i]})
    return words


def read_best(img, lang: str):
    """Try a few segmentation modes; keep the one with the most total confidence."""
    best, best_score = [], -1.0
    for psm in (3, 6, 4):
        words = _read_words(img, lang, psm)
        score = sum(w["conf"] for w in words if w["conf"] > 30)
        if score > best_score:
            best, best_score = words, score
        mean = statistics.fmean(w["conf"] for w in words) if words else 0
        if psm == 3 and mean >= 90 and len(words) >= 3:
            break                                                    # good enough, skip the other modes
    return best


def _lines(words):
    by: dict[tuple, list] = {}
    for w in words:
        by.setdefault(w["key"], []).append(w)
    out = []
    for key, ws in by.items():
        ws.sort(key=lambda w: w["left"])
        out.append({"key": key, "text": " ".join(w["text"] for w in ws),
                    "left": min(w["left"] for w in ws), "right": max(w["left"] + w["w"] for w in ws),
                    "top": min(w["top"] for w in ws), "h": statistics.median(w["h"] for w in ws),
                    "bottom": max(w["top"] + w["h"] for w in ws), "words": ws})
    out.sort(key=lambda l: l["key"])
    return out


BULLET_MISREADS = {"e", "o", "¢", "€", "«", "®", "©", "»", "°", "+", "~", "•", "●", "▪", "*", "-", "—", "–"}


def _bullet_start(ln) -> str | None:
    """Text after a bullet mark, when the line starts with one. OCR often reads a round bullet as 'e', 'o',
    '¢' or '«', so a lone mark before a capitalised word counts as a bullet."""
    ws = ln["words"]
    nxt = ws[1]["text"][:1] if len(ws) >= 2 else ""
    # "capitalised word" for Latin text; scripts without capitals (Bengali and others) count when the next word is a letter
    if nxt and ws[0]["text"] in BULLET_MISREADS and (nxt.isupper() or (nxt.isalpha() and nxt.upper() == nxt.lower())):
        return " ".join(w["text"] for w in ws[1:])
    return None


def _layout(words) -> list[list[dict]]:
    lines = _lines(words)
    if not lines:
        return []
    body_h = statistics.median(l["h"] for l in lines)
    right_max = max(l["right"] for l in lines)
    bullets = {id(l): _bullet_start(l) for l in lines}
    # Slides: OCR often drops the round bullet completely. When some lines clearly are bullets and nearly every
    # line is short and of the same height, the lines without a mark are bullets too.
    marked = [l for l in lines if bullets[id(l)] is not None or LIST_BUL_RE.match(l["text"])]

    def _short(l):
        return len(l["words"]) <= 10 and not re.search(r"[.:;!?]$", l["text"])
    if marked and sum(_short(l) for l in lines) >= 0.8 * len(lines):
        for l in lines:
            if (bullets[id(l)] is None and not LIST_BUL_RE.match(l["text"]) and not LIST_NUM_RE.match(l["text"])
                    and _short(l) and 0.75 * body_h <= l["h"] < 1.45 * body_h):
                bullets[id(l)] = l["text"]
                l["nomark"] = True          # the bullet itself was not read: its text starts one bullet-width further right
    # width of "bullet + space", measured on lines where the bullet was read; otherwise about one line height
    mw = [l["words"][1]["left"] - l["words"][0]["left"] for l in lines
          if len(l["words"]) >= 2 and l["words"][0]["text"] in BULLET_MISREADS and bullets[id(l)] is not None
          and not l.get("nomark")]
    marker_w = statistics.median(mw) if mw else 0.9 * body_h

    def eff(l):
        return l["left"] - (marker_w if l.get("nomark") else 0)
    lefts = [eff(l) for l in lines if bullets[id(l)] is not None or LIST_BUL_RE.match(l["text"])
             or LIST_NUM_RE.match(l["text"])]
    list_base = min(lefts) if lefts else 0
    blocks: list[list[dict]] = []    # each block: list of entries {md, bbox, kind}
    kind: str | None = None          # "para" | "list": the block being built
    cur: list[dict] = []
    prev = None

    def flush():
        nonlocal kind
        if cur:
            blocks.append(list(cur))
        cur.clear()
        kind = None

    def box(ln):
        return (ln["left"], ln["top"], ln["right"], ln["bottom"])

    def merge(entry, ln):
        l, t_, r, b = entry["bbox"]
        entry["bbox"] = (min(l, ln["left"]), min(t_, ln["top"]), max(r, ln["right"]), max(b, ln["bottom"]))

    for ln in lines:
        text = clean_chars(ln["text"])
        new_block = prev is None or prev["key"][:2] != ln["key"][:2]
        gap = (ln["top"] - prev["bottom"]) if prev else 0
        brk = new_block or gap > 0.9 * body_h
        # a wrapped line continues the previous one: that line ran to the right margin and did not end a sentence
        continues = (prev is not None and not brk and prev["right"] >= 0.88 * right_max
                     and not re.search(r"[.:;!?]$", prev["text"])
                     and not LABEL_RE.match(text))          # "Date: ..." starts a new line, it does not wrap
        m_num, m_bul = LIST_NUM_RE.match(text), LIST_BUL_RE.match(text)
        mis = bullets[id(ln)] if not (m_num or m_bul) else None
        if m_num or m_bul or mis is not None:
            if kind != "list":
                flush()
                kind = "list"
            level = max(0, round((eff(ln) - list_base) / (2.0 * body_h)))      # indentation = nesting
            cur.append({"md": "  " * level + (f"{m_num.group(1)}. {m_num.group(2)}" if m_num else
                                              f"- {m_bul.group(1)}" if m_bul else f"- {clean_chars(mis)}"),
                        "bbox": box(ln), "kind": "bullet", "level": level})
        elif ln["h"] >= 1.45 * body_h and len(text.split()) <= 12:
            flush()
            blocks.append([{"md": f"## {text}", "bbox": box(ln), "kind": "heading", "level": 0}])
        elif kind in ("para", "list") and cur and continues:
            cur[-1]["md"] += " " + text
            merge(cur[-1], ln)
        elif kind == "para" and not brk:
            cur.append({"md": text, "bbox": box(ln), "kind": "text", "level": 0})
        else:
            flush()
            kind = "para"
            cur.append({"md": text, "bbox": box(ln), "kind": "text", "level": 0})
        prev = ln
    flush()
    return blocks


def layout_to_markdown(words) -> str:
    """Rebuild paragraphs, lists and headings from word positions."""
    return "\n\n".join("\n".join(e["md"] for e in blk) for blk in _layout(words))


def layout_entries(words) -> list[dict]:
    """The same layout as a flat list of {md, bbox (pixels), kind, level}, for linking text to the picture."""
    return [e for blk in _layout(words) for e in blk]


def convert_image(data: bytes, filename: str, lang: str | None = None) -> ConvertedDocument:
    t0 = time.perf_counter()
    pytesseract, Image, _ = _imports()
    lang = ocr_lang(lang)
    check_language(lang)
    try:
        src = Image.open(io.BytesIO(data))
        src.load()
    except Exception as e:
        raise ConversionError(f"could not read this image: {e}") from e
    width, height = src.size
    frames = [src]
    n_frames = getattr(src, "n_frames", 1)
    if n_frames > 1:
        from PIL import ImageSequence
        frames = [f.copy() for _, f in zip(range(MAX_FRAMES), ImageSequence.Iterator(src))]
    warnings: list[str] = []
    if n_frames > MAX_FRAMES:
        warnings.append(f"only the first {MAX_FRAMES} of {n_frames} pages were read")
    parts, all_words = [], []
    for fr in frames:
        words = read_best(prepare(fr), lang)
        all_words += words
        md = layout_to_markdown(words)
        if md:
            parts.append(md)
    text = tidy("\n\n".join(parts))
    conf = round(statistics.fmean(w["conf"] for w in all_words), 1) if all_words else None
    if not text:
        warnings.append("no text found in this image. It may be a photo, chart or diagram: text conversion "
                        "cannot capture that, so send the image itself instead")
    else:
        doubtful = [w["text"] for w in all_words if w["conf"] < LOW_CONF and len(w["text"]) > 1]
        if conf is not None and conf < WARN_MEAN_CONF:
            warnings.append(f"OCR confidence is low ({conf:.0f}%): check names and numbers against the image"
                            + (f". Doubtful words: {', '.join(dict.fromkeys(doubtful[:8]))}" if doubtful else ""))
        else:
            warnings.append("text was read with OCR: double-check important numbers and names")
            if doubtful:
                warnings.append(f"doubtful words: {', '.join(dict.fromkeys(doubtful[:8]))}")
    return ConvertedDocument(filename, "image", text, pages=n_frames if n_frames > 1 else None,
                             ocr_pages=len(frames), warnings=warnings, ocr_confidence=conf,
                             image_tokens_est=round(width * height / 750) * len(frames),
                             seconds=round(time.perf_counter() - t0, 3), size_bytes=len(data))
