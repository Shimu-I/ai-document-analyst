"""Splits Markdown into blocks for the preview page, so a picture and the text read from it stay together.

Each block is ``("md", text)`` or ``("img", alt, name, text)``. ``text`` is the quoted text that follows the
picture (without the ``> `` marks), or ``""`` when the picture has no text of its own.
"""
from __future__ import annotations

import re

IMG_LINE = re.compile(r"^!\[(.*?)\]\(assets/([^)\s]+)\)\s*$")


def _unquote(lines: list[str]) -> str:
    return "\n".join(l[2:] if l.startswith("> ") else l.lstrip(">") for l in lines)


def split_blocks(md: str, assets: set[str] | dict) -> list[tuple]:
    lines = md.split("\n")
    out: list[tuple] = []
    chunk: list[str] = []

    def flush():
        if "".join(chunk).strip():
            out.append(("md", "\n".join(chunk)))
        chunk.clear()

    i = 0
    while i < len(lines):
        m = IMG_LINE.match(lines[i].strip())
        if m and m.group(2) in assets:
            flush()
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            q: list[str] = []
            while j < len(lines) and lines[j].startswith(">"):
                q.append(lines[j])
                j += 1
            if q:
                out.append(("img", m.group(1), m.group(2), _unquote(q)))
                i = j
            else:
                out.append(("img", m.group(1), m.group(2), ""))
                i += 1
            continue
        chunk.append(lines[i])
        i += 1
    flush()
    return out
