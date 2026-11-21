"""Token-saving post-processing: compact mode and splitting by token budget.

Compact mode only removes characters that carry no information for a reader or an AI model:
HTML comments (page markers), padding and the alignment row of Markdown tables, repeated spaces and
extra blank lines. Code blocks are never touched. Text, numbers and table cell values are unchanged.
"""
from __future__ import annotations

import re

from .base import estimate_tokens

FENCE_RE = re.compile(r"^(```|~~~)")
SEP_RE = re.compile(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")


def _split_cells(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells, cur, esc = [], [], False
    for ch in line:
        if esc:
            cur.append(ch)
            esc = False
        elif ch == "\\":
            cur.append(ch)
            esc = True
        elif ch == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    cells.append("".join(cur).strip())
    return cells


def compact_markdown(md: str) -> tuple[str, int]:
    """Return (compact markdown, characters saved)."""
    out: list[str] = []
    in_code = False
    lines = md.splitlines()
    i = 0
    while i < len(lines):
        ln = lines[i]
        if FENCE_RE.match(ln.strip()):
            in_code = not in_code
            out.append(ln)
            i += 1
            continue
        if in_code:
            out.append(ln)
            i += 1
            continue
        # a Markdown table: header line followed by the alignment row
        if ln.lstrip().startswith("|") and i + 1 < len(lines) and SEP_RE.match(lines[i + 1].strip()):
            out.append(" | ".join(_split_cells(ln)))
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                out.append(" | ".join(_split_cells(lines[i])))
                i += 1
            continue
        ln = re.sub(r"<!--.*?-->", "", ln)
        if not ln.strip():
            out.append("")
        else:
            lead = re.match(r"^\s*", ln).group(0)
            out.append(lead + re.sub(r"[ \t]{2,}", " ", ln.strip()))
        i += 1
    res = re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()
    res = res + "\n" if res else ""
    return res, max(0, len(md) - len(res))


# ----------------------------------------------------------------------------- split by token budget
def _blocks(md: str) -> list[str]:
    """Paragraph-level blocks; fenced code and tables stay in one piece."""
    blocks, cur, in_code = [], [], False
    for ln in md.splitlines():
        if FENCE_RE.match(ln.strip()):
            in_code = not in_code
        cur.append(ln)
        if not in_code and not ln.strip():
            if any(x.strip() for x in cur):
                blocks.append("\n".join(cur).strip("\n"))
            cur = []
    if any(x.strip() for x in cur):
        blocks.append("\n".join(cur).strip("\n"))
    return blocks


def _split_big(block: str, budget: int) -> list[str]:
    """A single block larger than the budget: split on lines (keeping a table header on every part)."""
    lines = block.splitlines()
    header = lines[:2] if len(lines) > 2 and lines[0].lstrip().startswith("|") and SEP_RE.match(lines[1].strip()) else []
    parts, cur = [], list(header)
    for ln in lines[len(header):]:
        if estimate_tokens("\n".join(cur + [ln])) > budget and len(cur) > len(header):
            parts.append("\n".join(cur))
            cur = list(header)
        cur.append(ln)
    if len(cur) > len(header):
        parts.append("\n".join(cur))
    out = []
    for p in parts:                       # one huge line: cut by characters as a last resort
        while estimate_tokens(p) > budget * 1.2 and len(p) > 400:
            cut = max(200, int(len(p) * budget / max(estimate_tokens(p), 1)))
            sp = p.rfind(" ", 0, cut)
            cut = sp if sp > cut * 0.5 else cut
            out.append(p[:cut])
            p = p[cut:].lstrip()
        out.append(p)
    return out


def split_by_tokens(md: str, max_tokens: int) -> list[str]:
    """Split Markdown into parts of roughly <= max_tokens, preferring to break before headings."""
    if max_tokens < 200:
        raise ValueError("max_tokens must be at least 200")
    if estimate_tokens(md) <= max_tokens:
        return [md]
    units: list[str] = []
    for b in _blocks(md):
        units += _split_big(b, max_tokens) if estimate_tokens(b) > max_tokens else [b]
    parts, cur, cur_tok = [], [], 0
    for u in units:
        t = estimate_tokens(u) + 1
        starts_section = u.lstrip().startswith("#")
        overflow = cur_tok + t > max_tokens and (cur_tok >= 0.25 * max_tokens or cur_tok + t > 1.15 * max_tokens)
        if cur and (overflow or (starts_section and cur_tok > 0.6 * max_tokens)):
            parts.append("\n\n".join(cur))
            cur, cur_tok = [], 0
        cur.append(u)
        cur_tok += t
    if cur:
        parts.append("\n\n".join(cur))
    n = len(parts)
    return [f"(part {i} of {n})\n\n{p.strip()}\n" for i, p in enumerate(parts, 1)]
