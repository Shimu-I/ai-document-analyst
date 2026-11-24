"""Document -> Markdown conversion.

    from src.convert import convert
    doc = convert(open("report.pdf", "rb").read(), "report.pdf")
    open("report.md", "w").write(doc.markdown)
"""
from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .base import ConversionError, ConvertedDocument, clean_chars, tidy
from .office import _decode, convert_csv, convert_docx, convert_pptx, convert_xlsx
from .assets import AssetStore
from .compact import compact_markdown, split_by_tokens
from .image import convert_image
from .picture_ocr import PictureOCR
from .pdf import convert_pdf
from . import structured

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}
TEXT_EXTS = {".txt", ".md", ".markdown", ".log"}
# legacy binary Office formats are converted with LibreOffice when it is installed
LEGACY = {".doc": ("docx", convert_docx), ".xls": ("xlsx", convert_xlsx), ".ppt": ("pptx", convert_pptx),
          ".odt": ("docx", convert_docx), ".ods": ("xlsx", convert_xlsx), ".odp": ("pptx", convert_pptx),
          ".rtf": ("docx", convert_docx)}
HTML_EXTS = {".html", ".htm", ".xhtml"}
DATA_EXTS = {".json", ".jsonl", ".ndjson", ".yaml", ".yml", ".toml", ".xml", ".ipynb"}
CODE_EXTS = set(structured.CODE_LANGS)
GOOGLE_EXTS = set(structured.GOOGLE_POINTERS)
SUPPORTED = sorted({".pdf", ".docx", ".xlsx", ".xlsm", ".pptx", ".csv", ".tsv"}
                   | TEXT_EXTS | IMAGE_EXTS | set(LEGACY) | HTML_EXTS | DATA_EXTS | CODE_EXTS)
# accepted by the upload box: Google shortcut files too, so they get a clear explanation instead of a silent block
ACCEPTED = sorted(set(SUPPORTED) | GOOGLE_EXTS)


def _soffice() -> str | None:
    return shutil.which("soffice") or shutil.which("libreoffice")


def _via_libreoffice(data: bytes, ext: str, target: str) -> bytes:
    exe = _soffice()
    if not exe:
        raise ConversionError(
            f"{ext} is an old format. Save it as .{target} and upload again "
            "(or install LibreOffice so it can be converted automatically).")
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / f"in{ext}"
        src.write_bytes(data)
        try:
            subprocess.run([exe, "--headless", "--convert-to", target, "--outdir", d, str(src)],
                           check=True, capture_output=True, timeout=180,
                           env={**os.environ, "HOME": d})
        except (subprocess.SubprocessError, OSError) as e:
            raise ConversionError(f"LibreOffice could not convert this {ext} file: {e}") from e
        out = Path(d) / f"in.{target}"
        if not out.exists():
            raise ConversionError(f"LibreOffice produced no output for this {ext} file")
        return out.read_bytes()


def convert(data: bytes, filename: str, *, page_markers: bool = False, strip_repeated: bool = True,
            force_ocr: bool = False, compact: bool = False, json_mode: str = "readable",
            ocr_lang: str | None = None, assets: bool = False,
            ocr_pictures: bool = False) -> ConvertedDocument:
    """Convert file bytes to Markdown. Raises ConversionError for unsupported/corrupt files.

    compact    remove padding/alignment rows in tables, comments, repeated spaces, and empty JSON values
    json_mode  "readable" (tables and key: value lines, fewer tokens) or "minified" (exact JSON, no whitespace)
    ocr_lang   Tesseract language(s), e.g. "eng+ben" (default: OCR_LANG environment variable, else English)
    ocr_pictures  read the text inside pictures (slides saved as images, screenshots in Word, PDF figures)
    assets     save pictures, diagrams and equations as image files (``doc.assets``), linked from the Markdown
    """
    if not data:
        raise ConversionError("empty file")
    if json_mode not in ("readable", "minified"):
        raise ConversionError("json_mode must be 'readable' or 'minified'")
    ext = Path(filename or "").suffix.lower()
    dkw = {"json_mode": json_mode, "compact": compact}
    store = AssetStore(filename) if assets else None
    pocr = PictureOCR(ocr_lang) if ocr_pictures and ext in (".pdf", ".docx", ".pptx", ".doc", ".ppt", ".odt", ".odp", ".rtf") else None
    if ext == ".pdf":
        doc = convert_pdf(data, filename, page_markers=page_markers, strip_repeated=strip_repeated,
                          force_ocr=force_ocr, store=store, pocr=pocr)
    elif ext == ".docx":
        doc = convert_docx(data, filename, store=store, pocr=pocr)
    elif ext in (".xlsx", ".xlsm"):
        doc = convert_xlsx(data, filename)
    elif ext == ".pptx":
        doc = convert_pptx(data, filename, store=store, pocr=pocr)
    elif ext in (".csv", ".tsv"):
        doc = convert_csv(data, filename)
        doc.source_chars = len(_decode(data))
    elif ext in IMAGE_EXTS:
        doc = convert_image(data, filename, ocr_lang)
    elif ext in TEXT_EXTS:
        t0 = time.perf_counter()
        text = _decode(data)
        doc = ConvertedDocument(filename, "text", tidy(clean_chars(text)), source_chars=len(text),
                                seconds=round(time.perf_counter() - t0, 3), size_bytes=len(data))
    elif ext in (".json", ".jsonl", ".ndjson"):
        doc = structured.convert_json(data, filename, _decode, **dkw)
    elif ext in (".yaml", ".yml"):
        doc = structured.convert_yaml(data, filename, _decode, **dkw)
    elif ext == ".toml":
        doc = structured.convert_toml(data, filename, _decode, **dkw)
    elif ext == ".xml":
        doc = structured.convert_xml(data, filename, _decode, **dkw)
    elif ext == ".ipynb":
        doc = structured.convert_ipynb(data, filename, _decode)
    elif ext in HTML_EXTS:
        doc = structured.convert_html(data, filename, _decode)
    elif ext in CODE_EXTS:
        doc = structured.convert_code(data, filename, ext, _decode)
    elif ext in GOOGLE_EXTS:
        raise structured.google_pointer_error(ext)
    elif ext in LEGACY:
        target, fn = LEGACY[ext]
        doc = fn(_via_libreoffice(data, ext, target), filename, **({"store": store, "pocr": pocr} if target != "xlsx" else {}))
        doc.warnings.append(f"converted from {ext} through LibreOffice first")
    else:
        raise ConversionError(f"unsupported file type {ext or '(none)'}; supported: {', '.join(SUPPORTED)}")
    if compact and doc.markdown:
        doc.markdown, doc.compact_saved_chars = compact_markdown(doc.markdown)
    return doc


__all__ = ["convert", "ConvertedDocument", "ConversionError", "SUPPORTED", "ACCEPTED", "split_by_tokens"]
