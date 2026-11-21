"""Structured and web formats -> compact Markdown: JSON, YAML, TOML, XML, Jupyter notebooks, HTML, source code.

The main idea for JSON-like data is to stop paying for punctuation. ``{"name": "Ada", "role": "Eng"}``
repeated for every record spends tokens on braces, quotes, commas and the same keys again and again.
A list of similar records becomes one table (keys appear once); other data becomes ``key: value`` lines
with indentation. The result is a readable rendering of the data, not byte-identical JSON; use
``json_mode="minified"`` when the exact JSON text is needed (it only removes whitespace).
"""
from __future__ import annotations

import json
import re
import time
from typing import Any

from .base import ConversionError, ConvertedDocument, clean_chars, md_table, tidy

MAX_DEPTH = 12
MAX_TABLE_COLS = 30
CODE_LANGS = {".py": "python", ".js": "javascript", ".ts": "typescript", ".jsx": "jsx", ".tsx": "tsx",
              ".java": "java", ".c": "c", ".h": "c", ".cpp": "cpp", ".cs": "csharp", ".go": "go",
              ".rs": "rust", ".rb": "ruby", ".php": "php", ".sh": "bash", ".sql": "sql", ".css": "css",
              ".ini": "ini", ".cfg": "ini", ".r": "r", ".kt": "kotlin", ".swift": "swift", ".tex": "latex"}
GOOGLE_POINTERS = {
    ".gsheet": ("Google Sheet", "File > Download > Microsoft Excel (.xlsx) or Comma-separated values (.csv)"),
    ".gdoc": ("Google Doc", "File > Download > Microsoft Word (.docx) or PDF"),
    ".gslides": ("Google Slides file", "File > Download > Microsoft PowerPoint (.pptx) or PDF"),
    ".gdraw": ("Google Drawing", "File > Download > PNG or PDF"),
    ".gform": ("Google Form", "Responses > Link to Sheets, then download that sheet"),
}


def google_pointer_error(ext: str) -> ConversionError:
    kind, how = GOOGLE_POINTERS[ext]
    return ConversionError(
        f"A {ext} file is only a shortcut to a {kind} in Google Drive; it contains no data. "
        f"Open it in Google, use {how}, and upload that file instead.")


# ----------------------------------------------------------------------------- data -> compact text
def _scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return str(int(v))
    return str(v)


def _is_scalar(v: Any) -> bool:
    return not isinstance(v, (dict, list))


def _inline(v: Any) -> str:
    """Compact JSON for values that do not fit a table cell or line."""
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"), default=str)


def _flatten(d: dict, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and v and all(_is_scalar(x) for x in v.values()):
            out.update(_flatten(v, key + "."))
        else:
            out[key] = v
    return out


def _table_rows(items: list[dict]) -> list[list[str]] | None:
    """A list of similar dicts as table rows, or None when it is not table-shaped."""
    if len(items) < 2 or not all(isinstance(i, dict) and i for i in items):
        return None
    flat = [_flatten(i) for i in items]
    keys: list[str] = []
    for f in flat:
        for k in f:
            if k not in keys:
                keys.append(k)
    if len(keys) > MAX_TABLE_COLS:
        return None
    first = set(flat[0])
    overlap = statistics_mean([len(first & set(f)) / max(len(first | set(f)), 1) for f in flat[1:]])
    if overlap < 0.5:
        return None
    rows = [keys]
    for f in flat:
        rows.append([("" if k not in f else _scalar(f[k]) if _is_scalar(f[k]) else _inline(f[k])) for k in keys])
    return rows


def statistics_mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _text_value(s: str, indent: str) -> str:
    """Strings with line breaks become an indented block so the structure stays unambiguous."""
    if "\n" not in s.strip("\n"):
        return s.strip("\n")
    return "|\n" + "\n".join(indent + "  " + ln for ln in s.strip("\n").splitlines())


def render(obj: Any, indent: str = "", depth: int = 0, stats: dict | None = None) -> list[str]:
    stats = stats if stats is not None else {"tables": 0}
    lines: list[str] = []
    if depth > MAX_DEPTH:
        return [indent + _inline(obj)]
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = str(k)
            if _is_scalar(v):
                lines.append(f"{indent}{key}: {_text_value(_scalar(v), indent)}")
            elif v in ({}, []):
                lines.append(f"{indent}{key}: {'{}' if isinstance(v, dict) else '[]'}")
            elif isinstance(v, list) and all(_is_scalar(x) for x in v) and \
                    len(", ".join(map(_scalar, v))) <= 120 and not any("," in _scalar(x) or "\n" in _scalar(x) for x in v):
                lines.append(f"{indent}{key}: {', '.join(_scalar(x) for x in v)}")
            else:
                if depth == 0:
                    sub = render(v, "", depth + 1, stats)
                    lines += ["", f"## {key}"] + ([""] if sub and sub[0].startswith("|") else []) + sub + [""]
                else:
                    lines.append(f"{indent}{key}:")
                    lines += render(v, indent + "  ", depth + 1, stats)
        return lines
    if isinstance(obj, list):
        rows = _table_rows(obj) if obj and all(isinstance(i, dict) for i in obj) else None
        if rows:
            stats["tables"] += 1
            if depth > 1:      # indented tables are not valid Markdown: keep them as plain lines
                return [indent + " | ".join(r) for r in (rows[0:1] + rows[1:])]
            return [md_table(rows)]
        if all(_is_scalar(x) for x in obj):
            joined = ", ".join(_scalar(x) for x in obj)
            if len(joined) <= 120 and not any("," in _scalar(x) or "\n" in _scalar(x) for x in obj):
                return [indent + joined]
        for x in obj:
            if _is_scalar(x):
                lines.append(f"{indent}- {_text_value(_scalar(x), indent)}")
            else:
                sub = render(x, indent + "  ", depth + 1, stats)
                if sub:
                    first = sub[0].lstrip()
                    lines.append(f"{indent}- {first}")
                    lines += sub[1:]
        return lines
    return [indent + _scalar(obj)]


def _drop_empty(o: Any) -> Any:
    """Compact mode for data: remove null / empty-string / empty-container values (reported to the user)."""
    if isinstance(o, dict):
        out = {k: _drop_empty(v) for k, v in o.items()}
        return {k: v for k, v in out.items() if v not in (None, "", [], {})}
    if isinstance(o, list):
        return [_drop_empty(v) for v in o]
    return o


def data_to_markdown(obj: Any, filename: str, kind: str, size: int, source_chars: int, *,
                     json_mode: str = "readable", compact: bool = False, t0: float | None = None,
                     warnings: list[str] | None = None) -> ConvertedDocument:
    warnings = list(warnings or [])
    t0 = t0 or time.perf_counter()
    if compact:
        before = len(_inline(obj))
        obj = _drop_empty(obj)
        after = len(_inline(obj))
        if before != after:
            warnings.append(f"compact mode removed empty values ({before - after} characters of JSON)")
    stats = {"tables": 0}
    if json_mode == "minified":
        md = "```json\n" + _inline(obj) + "\n```\n"
    else:
        md = tidy("\n".join(render(obj, "", 0, stats)))
        if isinstance(obj, (dict, list)) and not md.strip():
            md = _scalar(obj) + "\n" if _is_scalar(obj) else "(empty)\n"
    return ConvertedDocument(filename, kind, md, tables=stats["tables"], warnings=warnings,
                             source_chars=source_chars, seconds=round(time.perf_counter() - t0, 3),
                             size_bytes=size)


# ----------------------------------------------------------------------------- format entry points
def convert_json(data: bytes, filename: str, decode, **kw) -> ConvertedDocument:
    t0 = time.perf_counter()
    text = decode(data)
    try:
        obj = json.loads(text)
    except ValueError:
        # JSON Lines / NDJSON: one object per line
        rows = []
        for i, ln in enumerate(text.splitlines(), 1):
            if ln.strip():
                try:
                    rows.append(json.loads(ln))
                except ValueError as e:
                    raise ConversionError(f"this is not valid JSON (line {i}): {e}") from e
        if not rows:
            raise ConversionError("this JSON file is empty")
        obj = rows
    return data_to_markdown(obj, filename, "json", len(data), len(text), t0=t0, **kw)


def convert_yaml(data: bytes, filename: str, decode, **kw) -> ConvertedDocument:
    try:
        import yaml
    except ImportError as e:
        raise ConversionError("YAML needs the PyYAML package (pip install pyyaml)") from e
    t0 = time.perf_counter()
    text = decode(data)
    try:
        docs = [d for d in yaml.safe_load_all(text) if d is not None]
    except yaml.YAMLError as e:
        raise ConversionError(f"this is not valid YAML: {e}") from e
    obj = docs[0] if len(docs) == 1 else docs
    return data_to_markdown(obj, filename, "yaml", len(data), len(text), t0=t0, **kw)


def convert_toml(data: bytes, filename: str, decode, **kw) -> ConvertedDocument:
    import tomllib
    t0 = time.perf_counter()
    text = decode(data)
    try:
        obj = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ConversionError(f"this is not valid TOML: {e}") from e
    return data_to_markdown(obj, filename, "toml", len(data), len(text), t0=t0, **kw)


def _xml_to_obj(el) -> Any:
    tag_children: dict[str, list] = {}
    for ch in el:
        tag = ch.tag.split("}")[-1] if isinstance(ch.tag, str) else None
        if tag:
            tag_children.setdefault(tag, []).append(_xml_to_obj(ch))
    out: dict[str, Any] = {f"@{k.split('}')[-1]}": v for k, v in el.attrib.items()}
    for tag, vals in tag_children.items():
        out[tag] = vals[0] if len(vals) == 1 else vals
    text = (el.text or "").strip()
    if not out:
        return text
    if text:
        out["#text"] = text
    return out


def convert_xml(data: bytes, filename: str, decode, **kw) -> ConvertedDocument:
    import xml.etree.ElementTree as ET
    t0 = time.perf_counter()
    if b"<!ENTITY" in data[:20000] or b"<!entity" in data[:20000]:
        raise ConversionError("XML with entity declarations is refused for safety")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise ConversionError(f"this is not valid XML: {e}") from e
    obj = {root.tag.split("}")[-1]: _xml_to_obj(root)}
    return data_to_markdown(obj, filename, "xml", len(data), len(decode(data)), t0=t0, **kw)


def convert_ipynb(data: bytes, filename: str, decode, **kw) -> ConvertedDocument:
    t0 = time.perf_counter()
    text = decode(data)
    try:
        nb = json.loads(text)
        cells = nb["cells"]
    except (ValueError, KeyError, TypeError) as e:
        raise ConversionError(f"this is not a Jupyter notebook: {e}") from e
    lang = (nb.get("metadata", {}).get("language_info", {}) or {}).get("name", "python")
    out: list[str] = []
    omitted = 0
    for c in cells:
        src = c.get("source", "")
        src = "".join(src) if isinstance(src, list) else str(src)
        if not src.strip() and not c.get("outputs"):
            continue
        if c.get("cell_type") == "markdown":
            out.append(src.strip())
        elif c.get("cell_type") == "code":
            out.append(f"```{lang}\n{src.rstrip()}\n```")
            for o in c.get("outputs", []):
                t = o.get("text") or (o.get("data", {}) or {}).get("text/plain") or ""
                t = "".join(t) if isinstance(t, list) else str(t)
                if o.get("output_type") == "error":
                    t = f"{o.get('ename', 'Error')}: {o.get('evalue', '')}"
                if set((o.get("data") or {})) & {"image/png", "image/jpeg", "image/svg+xml"}:
                    omitted += 1
                if t.strip():
                    lines = t.rstrip().splitlines()
                    if len(lines) > 40:
                        lines = lines[:40] + [f"... ({len(lines) - 40} more lines)"]
                    out.append("Output:\n```\n" + "\n".join(lines) + "\n```")
        else:
            out.append(src.strip())
    warnings = [f"{omitted} chart/image output(s) omitted"] if omitted else []
    return ConvertedDocument(filename, "notebook", tidy("\n\n".join(out)), warnings=warnings,
                             images_omitted=omitted, source_chars=len(text), size_bytes=len(data),
                             seconds=round(time.perf_counter() - t0, 3))


def convert_code(data: bytes, filename: str, ext: str, decode) -> ConvertedDocument:
    t0 = time.perf_counter()
    text = decode(data)
    fence = "````" if "```" in text else "```"
    md = f"{fence}{CODE_LANGS.get(ext, '')}\n{text.rstrip()}\n{fence}\n"
    return ConvertedDocument(filename, "code", md, source_chars=len(text), size_bytes=len(data),
                             seconds=round(time.perf_counter() - t0, 3))


# ----------------------------------------------------------------------------- HTML
DROP_TAGS = ["script", "style", "noscript", "svg", "iframe", "template", "nav", "footer", "aside", "form",
             "button", "dialog", "canvas", "head"]
HEADING = {f"h{i}": "#" * i for i in range(1, 7)}


def convert_html(data: bytes, filename: str, decode, **kw) -> ConvertedDocument:
    try:
        from bs4 import BeautifulSoup, NavigableString
    except ImportError as e:
        raise ConversionError("HTML needs the beautifulsoup4 package (pip install beautifulsoup4)") from e
    t0 = time.perf_counter()
    raw = decode(data)
    soup = BeautifulSoup(raw, "html.parser")
    title = (soup.title.string or "").strip() if soup.title and soup.title.string else None
    n_img = len(soup.find_all("img"))
    n_links = len(soup.find_all("a", href=True))
    n_boiler = sum(len(soup.find_all(t)) for t in ("nav", "footer", "aside"))
    for t in soup.find_all(DROP_TAGS):
        t.decompose()
    root = soup.find("article") or soup.find("main") or soup.body or soup
    blocks: list[str] = []
    n_tables = 0

    def inline(node) -> str:
        return inline_nodes(node.children)

    def inline_nodes(children) -> str:
        parts = []
        for ch in children:
            if isinstance(ch, NavigableString):
                parts.append(str(ch) if not type(ch).__name__ == "Comment" else "")
            elif ch.name == "br":
                parts.append("\n")
            elif ch.name in ("strong", "b"):
                t = inline(ch).strip()
                parts.append(f" **{t}** " if t else "")
            elif ch.name in ("em", "i"):
                t = inline(ch).strip()
                parts.append(f" *{t}* " if t else "")
            elif ch.name == "code":
                parts.append(f"`{inline(ch).strip()}`")
            elif ch.name == "img":
                alt = (ch.get("alt") or "").strip()
                parts.append(f" [image: {alt}] " if alt else "")
            else:
                parts.append(inline(ch))
        return "".join(parts)

    def squash(s: str) -> str:
        return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"[ \t]*\n[ \t]*", "\n", s)).strip()

    def lst(node, depth=0) -> list[str]:
        out = []
        for n, li in enumerate(node.find_all("li", recursive=False), 1):
            mark = f"{n}." if node.name == "ol" else "-"
            own = [c for c in li.children if getattr(c, "name", None) not in ("ul", "ol")]
            out.append("  " * depth + f"{mark} {squash(inline_nodes(own))}")
            for sub in li.find_all(["ul", "ol"], recursive=False):
                out += lst(sub, depth + 1)
        return out

    def walk(node):
        nonlocal n_tables
        for ch in node.children:
            if isinstance(ch, NavigableString):
                t = squash(str(ch)) if type(ch).__name__ != "Comment" else ""
                if t:
                    blocks.append(t)
                continue
            name = ch.name
            if name in HEADING:
                t = squash(inline(ch))
                if t:
                    blocks.append(f"{HEADING[name]} {t}")
            elif name in ("p", "figcaption", "summary", "dt", "dd", "address"):
                t = squash(inline(ch))
                if t:
                    blocks.append(t)
            elif name in ("ul", "ol"):
                blocks.append("\n".join(lst(ch)))
            elif name == "pre":
                blocks.append("```\n" + ch.get_text().strip("\n") + "\n```")
            elif name == "blockquote":
                t = squash(inline(ch))
                blocks.append("\n".join("> " + ln for ln in t.splitlines()))
            elif name == "table":
                rows = [[squash(inline(c)) for c in tr.find_all(["th", "td"])] for tr in ch.find_all("tr")]
                rows = [r for r in rows if any(r)]
                if rows:
                    blocks.append(md_table(rows))
                    n_tables += 1
            elif name == "hr":
                continue
            else:
                walk(ch)

    walk(root)
    md = tidy("\n\n".join(b for b in blocks if b.strip()))
    if title and not re.match(r"^#\s", md):
        md = f"# {title}\n\n{md}" if md else f"# {title}\n"
    warnings = []
    if n_img:
        warnings.append(f"{n_img} image(s) omitted (alt text kept where present)")
    if n_links:
        warnings.append(f"{n_links} link address(es) dropped; link text kept")
    if n_boiler:
        warnings.append(f"{n_boiler} navigation/footer/sidebar block(s) removed")
    if not md.strip():
        warnings.append("no readable text found in this page (it may be built with JavaScript)")
    return ConvertedDocument(filename, "html", clean_chars(md), title=title, tables=n_tables,
                             images_omitted=n_img, warnings=warnings, source_chars=len(raw),
                             size_bytes=len(data), seconds=round(time.perf_counter() - t0, 3))
