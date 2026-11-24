"""Reading the project documents for the in-app Documentation page: list, split into blocks, contents, search.

Pure functions (no Streamlit), so they can be tested. Documents are the Markdown files in ``docs/`` and
``docs/deep_dive/``. Mermaid diagrams are shown from PNG files made ahead of time by ``scripts/make_diagrams.py``.
"""
from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
DIAGRAMS = DOCS / "assets" / "diagrams"

GROUPS = [("Understand", ["01", "02", "03"]), ("How it works", ["04", "05", "06"]), ("Use it", ["07", "08", "09"]),
          ("Trust it", ["10", "11", "12"]), ("Help", ["13", "14"]), ("Project", ["15"])]


def title_of(path: Path) -> str:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# "):
            return re.sub(r"^\d+\s*[-–]\s*", "", line[2:]).strip()
    return path.stem.replace("_", " ")


def list_docs(root: Path = DOCS) -> list[dict]:
    """[{key, number, title, path, group}] numbered documents first (in order), then the deep-dive chapters."""
    out = []
    for p in sorted(root.glob("[0-9][0-9]_*.md")):
        n = p.name[:2]
        group = next((g for g, nums in GROUPS if n in nums), "Other")
        out.append({"key": p.stem, "number": n, "title": title_of(p), "path": p, "group": group})
    for p in sorted((root / "deep_dive").glob("*.md")):
        out.append({"key": "dd_" + p.stem, "number": "", "title": title_of(p), "path": p, "group": "Deep dive"})
    return out


def slug(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s]+", "-", s)


def toc(md: str) -> list[tuple[int, str, str]]:
    """[(level, text, anchor)] for ## and ### headings, ignoring code blocks."""
    out, fence = [], False
    for line in md.splitlines():
        if line.startswith("```"):
            fence = not fence
        m = None if fence else re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if m:
            text = re.sub(r"[`*_]", "", m.group(2))
            out.append((len(m.group(1)), text, slug(text)))
    return out


LINK_MD = re.compile(r"\[([^\]]+)\]\((?!https?://)([^)#\s]+\.md)(#[^)]*)?\)")


def clean_links(md: str) -> str:
    """Links to other documents cannot work inside one page: keep the link text, in bold."""
    return LINK_MD.sub(lambda m: f"**{m.group(1)}**", md)


IMG = re.compile(r"^!\[(.*?)\]\(([^)\s]+)\)\s*$")


def split_blocks(md: str, doc_path: Path, diagram_dir: Path = DIAGRAMS) -> list[tuple]:
    """("md", text) | ("img", file, alt) | ("diagram", png_or_None, source). Mermaid blocks are numbered per document."""
    out: list[tuple] = []
    buf: list[str] = []
    lines = md.split("\n")
    n_mm = 0
    i = 0

    def flush():
        if "".join(buf).strip():
            out.append(("md", clean_links("\n".join(buf))))
        buf.clear()

    while i < len(lines):
        ln = lines[i]
        if ln.strip() == "```mermaid":
            flush()
            j = i + 1
            while j < len(lines) and lines[j].strip() != "```":
                j += 1
            png = diagram_dir / f"{doc_path.stem}_{n_mm}.png"
            out.append(("diagram", png if png.exists() else None, "\n".join(lines[i + 1:j])))
            n_mm += 1
            i = j + 1
            continue
        m = IMG.match(ln.strip())
        if m and not m.group(2).startswith("http"):
            f = (doc_path.parent / m.group(2)).resolve()
            if f.exists():
                flush()
                out.append(("img", f, m.group(1)))
                i += 1
                continue
        buf.append(ln)
        i += 1
    flush()
    return out


def search(query: str, docs: list[dict], limit: int = 12) -> list[dict]:
    """Documents ranked by how many search words they contain; each hit has the best matching line as a snippet."""
    words = [w for w in re.findall(r"\w+", query.lower()) if len(w) > 1]
    if not words:
        return []
    hits = []
    for d in docs:
        text = d["path"].read_text(encoding="utf-8")
        low = text.lower()
        if not all(w in low for w in words):
            continue
        score = sum(low.count(w) for w in words) + 5 * sum(w in d["title"].lower() for w in words)
        best, best_n = "", -1
        for line in text.splitlines():
            if line.startswith("```") or not line.strip():
                continue
            n = sum(w in line.lower() for w in words)
            if n > best_n:
                best, best_n = line.strip(), n
        snippet = re.sub(r"[#|*`>]", " ", best)
        snippet = re.sub(r"\s+", " ", snippet).strip()
        hits.append({**d, "score": score, "snippet": snippet[:160]})
    hits.sort(key=lambda h: -h["score"])
    return hits[:limit]
