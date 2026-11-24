"""Shared types and Markdown helpers for all converters."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

LIGATURES = {"\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl",
             "\u00ad": "", "\u00a0": " ", "\u200b": ""}


@dataclass
class ConvertedDocument:
    filename: str
    kind: str                      # pdf | docx | xlsx | pptx | image | text | csv
    markdown: str
    title: str | None = None
    pages: int | None = None       # pdf pages / pptx slides
    sheets: list[str] = field(default_factory=list)
    tables: int = 0
    images_omitted: int = 0
    ocr_pages: int = 0
    headers_footers_removed: int = 0
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0
    size_bytes: int = 0
    ocr_confidence: float | None = None     # mean word confidence (0-100) when OCR was used on an image
    image_tokens_est: int | None = None     # rough cost of sending the image itself (width x height / 750)
    source_chars: int | None = None         # characters of the original text, for text-like formats only
    compact_saved_chars: int = 0            # characters removed by compact mode
    assets: dict[str, bytes] = field(default_factory=dict)   # image files referenced from the Markdown
    figures: int = 0                        # pictures / diagrams saved as images
    formulas: int = 0                       # equations kept (as LaTeX text or as images)

    @property
    def words(self) -> int:
        return len(re.findall(r"\w+", self.markdown))

    @property
    def est_tokens(self) -> int:
        return estimate_tokens(self.markdown)

    @property
    def source_tokens(self) -> int | None:
        return None if self.source_chars is None else max(1, round(self.source_chars / 4))


def estimate_tokens(text: str) -> int:
    """Rough token estimate: about 4 characters per token for English / Latin text, and about 1.5
    characters per token for other scripts (Bangla, Arabic, CJK...), which real tokenizers split into
    many more tokens. This is a planning figure, not what any particular AI tool will count."""
    if not text.strip():
        return 0
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    other = len(text) - ascii_chars
    return max(1, round(ascii_chars / 4 + other / 1.5))


class ConversionError(ValueError):
    """The file cannot be converted (unsupported, corrupt, encrypted...)."""


# pdfminer prints glyphs that have no Unicode mapping as "(cid:N)", where N is the character code. LaTeX
# documents without \\usepackage{cmap} do this for the ligatures. The codes are fixed by the two standard TeX
# font encodings (T1 and OT1), so inside a word they can be restored safely.
_TEX_LIGATURES = {27: "ff", 28: "fi", 29: "fl", 30: "ffi", 31: "ffl",      # T1 (Cork) encoding
                  11: "ff", 12: "fi", 13: "fl", 14: "ffi", 15: "ffl"}      # OT1 (original TeX) encoding
CID_RE = re.compile(r"\(cid:(\d+)\)")


def fix_cids(s: str) -> str:
    def repl(m: re.Match) -> str:
        lig = _TEX_LIGATURES.get(int(m.group(1)))
        before, after = s[max(0, m.start() - 1):m.start()], s[m.end():m.end() + 1]
        return lig if lig and (before.isalpha() or after.isalpha()) else m.group(0)
    return CID_RE.sub(repl, s) if "(cid:" in s else s


def clean_chars(s: str) -> str:
    for k, v in LIGATURES.items():
        s = s.replace(k, v)
    return fix_cids(s)


def md_cell(v) -> str:
    """Make a value safe inside a Markdown table cell."""
    if v is None:
        return ""
    s = clean_chars(str(v)).replace("\r\n", "\n").replace("\r", "\n").strip()
    return s.replace("|", "\\|").replace("\n", "<br>")


def md_table(rows: list[list]) -> str:
    """Rows -> GitHub-flavoured Markdown table; the first row is the header."""
    rows = [list(r) for r in rows if r is not None]
    if not rows:
        return ""
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    # drop fully empty trailing columns
    while width > 1 and all(not str(r[width - 1] or "").strip() for r in rows):
        rows = [r[:-1] for r in rows]
        width -= 1
    header, body = rows[0], rows[1:]
    out = ["| " + " | ".join(md_cell(c) for c in header) + " |",
           "| " + " | ".join("---" for _ in header) + " |"]
    out += ["| " + " | ".join(md_cell(c) for c in r) + " |" for r in body]
    return "\n".join(out)


def tidy(md: str) -> str:
    """Collapse 3+ blank lines, strip trailing spaces, end with one newline."""
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    return md.strip() + "\n" if md.strip() else ""
