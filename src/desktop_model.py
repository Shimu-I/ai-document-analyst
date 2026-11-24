"""State and geometry behind the desktop window (no GUI code, so it can be tested).

A ``Deck`` holds the slides read by ``src.slides``, the user's corrections to the text, and the links between a
line of text and the place it came from on the slide, in both directions.
"""
from __future__ import annotations

from dataclasses import dataclass

from .convert.base import estimate_tokens
from .slides import Item, Slide, to_markdown


def fit(size: tuple[int, int], box: tuple[int, int]) -> tuple[float, int, int]:
    """Scale and offset that centre a picture of ``size`` inside a box of ``box`` pixels without cropping."""
    w, h = size
    bw, bh = box
    scale = min(bw / w, bh / h) if w and h and bw > 0 and bh > 0 else 1.0
    return scale, int((bw - w * scale) / 2), int((bh - h * scale) / 2)


def to_canvas(bbox: tuple[float, float, float, float], size: tuple[int, int], scale: float, ox: int, oy: int) -> tuple[int, int, int, int]:
    """A fractional box on the slide as canvas pixels (x0, y0, x1, y1), padded a little so it frames the text."""
    w, h = size
    pad = 4
    return (int(bbox[0] * w * scale) + ox - pad, int(bbox[1] * h * scale) + oy - pad,
            int(bbox[2] * w * scale) + ox + pad, int(bbox[3] * h * scale) + oy + pad)


@dataclass
class Link:
    line: int            # 0-based line number in the text of the slide
    item: Item


class Deck:
    def __init__(self, slides: list[Slide], filename: str = ""):
        self.slides = slides
        self.filename = filename
        self.edits: dict[int, str] = {}

    # ------------------------------------------------------------------ text
    def text(self, i: int) -> str:
        s = self.slides[i]
        return self.edits.get(s.number, s.markdown)

    def set_text(self, i: int, text: str) -> None:
        s = self.slides[i]
        text = text.rstrip("\n")
        if text == s.markdown:
            self.edits.pop(s.number, None)
        else:
            self.edits[s.number] = text

    def edited(self, i: int) -> bool:
        return self.slides[i].number in self.edits

    # ------------------------------------------------------------------ links
    def links(self, i: int) -> list[Link]:
        """Text line to slide position. The k-th non-blank line is the k-th item; if the number of non-blank lines
        no longer matches (the text was edited), the unedited text is used for linking instead."""
        s = self.slides[i]
        for text in (self.text(i), s.markdown):
            lines = [n for n, ln in enumerate(text.split("\n")) if ln.strip()]
            if len(lines) == len(s.items):
                return [Link(n, it) for n, it in zip(lines, s.items)]
        return []

    def item_for_line(self, i: int, line: int) -> Item | None:
        for lk in self.links(i):
            if lk.line == line:
                return lk.item
        return None

    def line_for_point(self, i: int, x: float, y: float) -> int | None:
        """Text line whose box contains the point (fractions of the slide), else the nearest one within a small margin."""
        best, best_d = None, 0.04
        for lk in self.links(i):
            x0, y0, x1, y1 = lk.item.bbox
            if x0 <= x <= x1 and y0 <= y <= y1:
                return lk.line
            dx = max(x0 - x, 0, x - x1)
            dy = max(y0 - y, 0, y - y1)
            d = (dx * dx + dy * dy) ** 0.5
            if d < best_d:
                best, best_d = lk.line, d
        return best

    # ------------------------------------------------------------------ numbers and export
    def tokens(self, i: int | None = None) -> int:
        if i is not None:
            return estimate_tokens(self.text(i))
        return estimate_tokens(self.markdown())

    def words(self, i: int) -> int:
        return len(self.text(i).split())

    def markdown(self, headings: bool = True) -> str:
        """All slides, with the user's corrections applied."""
        return to_markdown([Slide(s.number, b"", s.size, markdown=self.text(k)) for k, s in enumerate(self.slides)], headings)

    def suggested_name(self) -> str:
        stem = self.filename.rsplit(".", 1)[0] if self.filename else "slides"
        return stem + ".md"
