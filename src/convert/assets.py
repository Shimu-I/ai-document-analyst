"""Pictures, diagrams and equations kept as image files next to the Markdown.

A converter that is given an ``AssetStore`` saves each picture, diagram or equation it finds as a PNG
(or the original JPEG/GIF) and puts a Markdown image link in the text: ``![alt](assets/name.png)``.
The alt text carries the words that were inside the picture, so a text-only AI chat still gets them.
"""
from __future__ import annotations

import io
import re

MAX_ASSETS = 80          # per document; more are counted and reported, not saved
MAX_WIDTH = 1600         # pixels; wider crops are scaled down to keep files small


def safe_stem(filename: str) -> str:
    stem = re.sub(r"\.[^.]*$", "", filename or "document")
    return re.sub(r"[^\w\-]+", "_", stem).strip("_")[:40] or "document"


def alt_text(text: str, limit: int = 160) -> str:
    """Single-line text that is safe inside ![...]."""
    t = re.sub(r"\(cid:\d+\)", "", text or "")
    t = re.sub(r"\s+", " ", t).strip().replace("[", "(").replace("]", ")")
    return t if len(t) <= limit else t[: limit - 1].rstrip() + "…"


def png_bytes(img) -> bytes:
    """PIL image -> PNG bytes, scaled down when very wide."""
    if img.width > MAX_WIDTH:
        img = img.resize((MAX_WIDTH, max(1, round(img.height * MAX_WIDTH / img.width))))
    if img.mode not in ("RGB", "L", "RGBA"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()


class AssetStore:
    """Collects the image files of one document. Names are prefixed with the document name, so the
    files of several documents can share one ``assets/`` folder."""

    def __init__(self, filename: str, limit: int = MAX_ASSETS):
        self.stem = safe_stem(filename)
        self.files: dict[str, bytes] = {}
        self.counts: dict[str, int] = {}
        self.limit = limit
        self.skipped = 0

    def add(self, kind: str, data: bytes, ext: str = "png", tag: str = "") -> str | None:
        """Save one file; returns the Markdown path (``assets/...``) or None when the limit is reached."""
        if len(self.files) >= self.limit:
            self.skipped += 1
            return None
        n = self.counts[kind] = self.counts.get(kind, 0) + 1
        name = f"{self.stem}_{tag}{kind}{n}.{ext}"
        self.files[name] = data
        return f"assets/{name}"

    def count(self, kind: str) -> int:
        return self.counts.get(kind, 0)
