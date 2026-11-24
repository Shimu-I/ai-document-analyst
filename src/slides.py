"""Slide-by-slide reading: for each slide or page, the original picture and the text read from it, with the position
of every text line on the picture.

This is the core of the desktop app's "filmstrip" view: the original slide on the left, the text in the same layout
on the right, and a line of text can be linked to the place it came from. English and Bengali are both read
(language ``auto``: English, plus Bengali when its Tesseract language pack is installed).

Sources: images (each frame is one slide), PDF pages (text layer when there is one, OCR otherwise) and PowerPoint /
Word files (rendered through LibreOffice to PDF first).
"""
from __future__ import annotations

import io
import shutil
import statistics
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .convert.base import ConversionError
from .convert import IMAGE_EXTS
from .convert import image as img_mod

MAX_SLIDES = 80
RENDER_SCALE = 2.0           # PDF points to pixels (144 dpi)
MIN_TEXT_CHARS = 20          # below this a PDF page counts as a picture and is read with OCR


@dataclass
class Item:
    md: str                                   # the line as Markdown ("- text", "## text", "text")
    bbox: tuple[float, float, float, float]   # x0, y0, x1, y1 as fractions of the slide (0 to 1)
    kind: str                                 # bullet | heading | text
    level: int = 0                            # nesting level of a bullet


@dataclass
class Slide:
    number: int
    png: bytes                                # the original slide as a PNG
    size: tuple[int, int]
    items: list[Item] = field(default_factory=list)
    markdown: str = ""
    source: str = "ocr"                       # ocr | text layer
    confidence: float | None = None
    lang: str = ""
    note: str = ""


def _png(img) -> bytes:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def _items(entries, w: float, h: float) -> list[Item]:
    return [Item(e["md"], (e["bbox"][0] / w, e["bbox"][1] / h, e["bbox"][2] / w, e["bbox"][3] / h), e["kind"], e.get("level", 0))
            for e in entries]


def _from_ocr(img, number: int, lang: str) -> Slide:
    _, Image, ImageOps = img_mod._imports()
    img = ImageOps.exif_transpose(img)
    prepared = img_mod.prepare(img)
    words = img_mod.read_best(prepared, lang)
    good = [w for w in words if w["conf"] > 0]
    conf = round(statistics.fmean(w["conf"] for w in good), 1) if good else None
    entries = img_mod.layout_entries(words)
    s = Slide(number, _png(img), img.size, _items(entries, *prepared.size), img_mod.layout_to_markdown(words), "ocr", conf, lang)
    if not entries:
        s.note = "no text found on this slide (a photo or a drawing)"
    return s


def _words_from_pdf(page, scale: float) -> list[dict]:
    """Words of a PDF page in the shape the OCR layout code expects (pixel boxes, one row key per text row)."""
    raw = page.extract_words(extra_attrs=["size"], keep_blank_chars=False, use_text_flow=False)
    raw.sort(key=lambda w: ((w["top"] + w["bottom"]) / 2, w["x0"]))
    rows: list[list[dict]] = []
    for w in raw:
        cy = (w["top"] + w["bottom"]) / 2
        if rows and abs(cy - statistics.fmean((r["top"] + r["bottom"]) / 2 for r in rows[-1])) <= 0.55 * max(w["size"], 1):
            rows[-1].append(w)
        else:
            rows.append([w])
    out = []
    for i, row in enumerate(rows):
        for w in row:
            out.append({"text": w["text"], "left": w["x0"] * scale, "top": w["top"] * scale, "w": (w["x1"] - w["x0"]) * scale,
                        "h": (w["bottom"] - w["top"]) * scale, "conf": 95.0, "key": (0, 0, i)})
    return out


def _from_pdf(data: bytes, lang: str, limit: int) -> list[Slide]:
    try:
        import pdfplumber
        import pypdfium2 as pdfium
    except ImportError as e:
        raise ConversionError("PDF slides need pdfplumber and pypdfium2") from e
    slides: list[Slide] = []
    doc = pdfium.PdfDocument(data)
    try:
        with pdfplumber.open(io.BytesIO(data)) as pl:
            for i, page in enumerate(pl.pages[:limit]):
                pil = doc[i].render(scale=RENDER_SCALE).to_pil()
                words = _words_from_pdf(page, RENDER_SCALE)
                if sum(len(w["text"]) for w in words) >= MIN_TEXT_CHARS:
                    entries = img_mod.layout_entries(words)
                    slides.append(Slide(i + 1, _png(pil), pil.size, _items(entries, *pil.size),
                                        img_mod.layout_to_markdown(words), "text layer", None, ""))
                else:
                    slides.append(_from_ocr(pil, i + 1, lang))
            if len(pl.pages) > limit:
                slides[-1].note = f"only the first {limit} of {len(pl.pages)} pages were read"
    except ConversionError:
        raise
    except Exception as e:
        raise ConversionError(f"could not read this PDF: {e}") from e
    finally:
        doc.close()
    return slides


def _to_pdf(data: bytes, filename: str) -> bytes:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise ConversionError("slides and Word files need LibreOffice to be shown as pictures "
                              "(sudo apt install libreoffice-impress libreoffice-writer), or export the file as PDF first")
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / ("in" + Path(filename).suffix.lower())
        src.write_bytes(data)
        r = subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", d, str(src)],
                           capture_output=True, text=True, timeout=180)
        out = Path(d) / "in.pdf"
        if r.returncode or not out.exists():
            raise ConversionError(f"LibreOffice could not open this file: {r.stderr.strip()[:200]}")
        return out.read_bytes()


def read_slides(data: bytes, filename: str, lang: str | None = None, limit: int = MAX_SLIDES) -> list[Slide]:
    """One Slide per slide, page or image frame."""
    if not data:
        raise ConversionError("the file is empty")
    lang = img_mod.ocr_lang(lang)
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        pdf = data
    elif ext in (".pptx", ".ppt", ".odp", ".docx", ".doc", ".odt", ".rtf"):
        pdf = _to_pdf(data, filename)
    elif ext in IMAGE_EXTS:
        img_mod.check_language(lang)
        _, Image, _ = img_mod._imports()
        try:
            src = Image.open(io.BytesIO(data))
            src.load()
        except Exception as e:
            raise ConversionError(f"could not read this image: {e}") from e
        from PIL import ImageSequence
        frames = [f.copy() for _, f in zip(range(limit), ImageSequence.Iterator(src))] if getattr(src, "n_frames", 1) > 1 else [src]
        return [_from_ocr(f, i + 1, lang) for i, f in enumerate(frames)]
    else:
        raise ConversionError(f"slide view does not support '{ext}' files (use PDF, PowerPoint, Word or an image)")
    img_mod.check_language(lang)
    return _from_pdf(pdf, lang, limit)


def to_markdown(slides: list[Slide], headings: bool = True) -> str:
    """All slides as one Markdown text, each under a '## Slide N' heading when ``headings``."""
    parts = []
    for s in slides:
        body = s.markdown.strip() or "_(no text)_"
        parts.append((f"## Slide {s.number}\n\n" if headings else "") + body)
    return "\n\n".join(parts) + "\n"
