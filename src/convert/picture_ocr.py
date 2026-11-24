"""Text inside pictures (slides saved as images, screenshots pasted into Word, scanned figures).

``PictureOCR`` reads one picture at a time with the same preparation and OCR modes as image files.
Tiny pictures (icons, bullets) and results with very low confidence are ignored, and the number of
pictures read per document is limited so a large deck cannot run for minutes.
"""
from __future__ import annotations

import io
import statistics

MIN_SIDE = 90            # pixels; smaller pictures are icons or bullets
MIN_WORDS = 2
MIN_MEAN_CONF = 45.0
MAX_PICTURES = 60


def quote(text: str) -> str:
    """Markdown block for text read from a picture: a quote, so it stays apart from real text."""
    return "\n".join("> " + ln if ln.strip() else ">" for ln in text.split("\n"))


class PictureOCR:
    def __init__(self, lang: str | None = None, limit: int = MAX_PICTURES):
        from .image import check_language, ocr_lang
        self.lang = ocr_lang(lang)
        check_language(self.lang)
        self.limit = limit
        self.read_count = 0          # pictures that produced text
        self.tried = 0
        self.skipped = 0             # pictures not read because the limit was reached
        self.confs: list[float] = []

    def read(self, data: bytes) -> str:
        """Text found in the picture, or an empty string."""
        from .image import _imports, layout_to_markdown, prepare, read_best
        _, Image, _ = _imports()
        if self.tried >= self.limit:
            self.skipped += 1
            return ""
        try:
            img = Image.open(io.BytesIO(data))
            img.load()
        except Exception:
            return ""
        if min(img.size) < MIN_SIDE:
            return ""
        self.tried += 1
        words = read_best(prepare(img), self.lang)
        good = [w for w in words if w["conf"] > 30 and any(c.isalnum() for c in w["text"])]
        if len(good) < MIN_WORDS or statistics.fmean(w["conf"] for w in good) < MIN_MEAN_CONF:
            return ""
        text = layout_to_markdown(good).strip()
        if text:
            self.read_count += 1
            self.confs.append(statistics.fmean(w["conf"] for w in good))
        return text

    def note(self) -> list[str]:
        out = []
        if self.read_count:
            out.append(f"text from {self.read_count} picture(s) was read with OCR (quoted lines starting with '>'): "
                       "double-check numbers and names")
        if self.skipped:
            out.append(f"{self.skipped} more picture(s) were not read (limit of {self.limit} per document)")
        return out
