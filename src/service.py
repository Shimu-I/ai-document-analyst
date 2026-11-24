"""Framework-independent request handling, shared by the CLI, the API and the Streamlit UI."""
from __future__ import annotations

import io
import os
import re
import time
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.analyze.summarize import analyze
from src.convert import ACCEPTED, SUPPORTED, ConversionError, convert, split_by_tokens
from src.llm.client import llm_configured

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "50")) * 1024 * 1024


class ServiceError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


def health() -> dict[str, Any]:
    return {"status": "ok", "supported_types": SUPPORTED, "accepted_types": ACCEPTED,
            "llm_configured": llm_configured(),
            "max_upload_mb": MAX_UPLOAD_BYTES // (1024 * 1024)}


def md_filename(filename: str) -> str:
    stem = re.sub(r"[^\w.\-()\[\] ]+", "_", Path(filename or "document").stem).strip(" ._") or "document"
    return f"{stem}.md"


def with_summary(markdown: str, analysis: dict[str, Any], filename: str) -> str:
    """Markdown with a short summary block on top (optional download variant)."""
    head = [f"> **Source:** {filename}",
            f"> **What this is:** {analysis['one_line']}",
            f"> **Summary:** {analysis['summary']}"]
    for p in analysis.get("key_points") or []:
        head.append(f"> - {p}")
    return "\n".join(head) + "\n\n---\n\n" + markdown


def process(data: bytes, filename: str, *, page_markers: bool = False, strip_repeated: bool = True,
            force_ocr: bool = False, use_llm: bool | None = None, compact: bool = False,
            json_mode: str = "readable", ocr_lang: str | None = None,
            max_tokens: int | None = None, assets: bool = False,
            ocr_pictures: bool = False) -> dict[str, Any]:
    """Convert one file and analyse it. Returns a JSON-ready dict.

    ocr_pictures: read the text inside pictures with OCR (image-based slides, screenshots, PDF figures).
    max_tokens: when set, ``output_files(result)`` splits the Markdown into parts of about that many tokens.
    assets: save pictures, diagrams and equations as image files; they are returned under the private key
    ``_assets`` ({name: bytes}) so that the dict stays JSON-ready once that key is removed (see ``public``).
    """
    t_start = time.perf_counter()
    if max_tokens is not None and max_tokens < 200:
        raise ServiceError(422, "max_tokens must be at least 200")
    if not data:
        raise ServiceError(400, "empty file")
    if len(data) > MAX_UPLOAD_BYTES:
        raise ServiceError(413, f"file larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    try:
        doc = convert(data, filename, page_markers=page_markers, strip_repeated=strip_repeated,
                      force_ocr=force_ocr, compact=compact, json_mode=json_mode, ocr_lang=ocr_lang,
                      assets=assets, ocr_pictures=ocr_pictures)
    except ConversionError as e:
        msg = str(e)
        raise ServiceError(415 if msg.startswith("unsupported") else 422, msg) from e
    except Exception as e:  # a parser crashed on a malformed file
        raise ServiceError(422, f"could not convert this file: {type(e).__name__}: {e}") from e
    an = asdict(analyze(doc, use_llm))
    return {
        "filename": filename,
        "markdown_filename": md_filename(filename),
        "markdown": doc.markdown,
        "analysis": an,
        "stats": {"kind": doc.kind, "pages": doc.pages, "sheets": doc.sheets, "words": doc.words,
                  "characters": len(doc.markdown), "estimated_tokens": doc.est_tokens, "tables": doc.tables,
                  "images_omitted": doc.images_omitted, "ocr_pages": doc.ocr_pages,
                  "headers_footers_removed": doc.headers_footers_removed, "seconds": doc.seconds,
                  "size_bytes": doc.size_bytes, "source_tokens": doc.source_tokens,
                  "ocr_confidence": doc.ocr_confidence, "image_tokens_est": doc.image_tokens_est,
                  "compact_saved_chars": doc.compact_saved_chars, "figures": doc.figures,
                  "formulas": doc.formulas, "asset_files": sorted(doc.assets)},
        "max_tokens": max_tokens,
        "elapsed": round(time.perf_counter() - t_start, 3),
        "_assets": dict(doc.assets),
        "warnings": doc.warnings + an["warnings"],
    }


def public(r: dict[str, Any]) -> dict[str, Any]:
    """The result without private keys (image bytes), safe to send as JSON."""
    return {k: v for k, v in r.items() if not k.startswith("_")}


def output_files(r: dict[str, Any], include_summary: bool = False) -> list[tuple[str, str]]:
    """The .md file(s) to hand to the user: one file, or several parts when max_tokens was set."""
    md = with_summary(r["markdown"], r["analysis"], r["filename"]) if include_summary else r["markdown"]
    name = r["markdown_filename"]
    parts = split_by_tokens(md, r["max_tokens"]) if r.get("max_tokens") else [md]
    if len(parts) == 1:
        return [(name, parts[0])]
    stem = Path(name).stem
    return [(f"{stem}_part{i}.md", p) for i, p in enumerate(parts, 1)]


def zip_results(results: list[dict[str, Any]], include_summary: bool = False) -> bytes:
    """All converted files as one .zip (names de-duplicated)."""
    buf, used = io.BytesIO(), set()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for r in results:
            files = output_files(r, include_summary)
            n = 1
            while any(name in used for name, _ in files):     # same name twice: add a number to every part
                n += 1
                files = [(f"{Path(name).stem}_{n}.md", text) for name, text in output_files(r, include_summary)]
            for name, text in files:
                used.add(name)
                z.writestr(name, text)
            for name, blob in (r.get("_assets") or {}).items():     # image files; names are unique per document
                if f"assets/{name}" not in z.namelist():
                    z.writestr(f"assets/{name}", blob)
    return buf.getvalue()
