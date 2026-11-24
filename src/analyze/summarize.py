"""Summaries: free extractive summary by default, optional LLM summary with number checking."""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from src.convert.base import ConvertedDocument
from src.llm.client import LLMUnavailable, llm_configured, make_client

from .classify import classify

ROOT = Path(__file__).resolve().parents[2]
STOP = set("""a about above after again all also am an and any are as at be because been before being below between both
but by can could did do does doing down during each few for from further had has have having he her here hers him his how
i if in into is it its itself just me more most my no nor not now of off on once only or other our out over own same she
should so some such than that the their them then there these they this those through to too under until up very was we
were what when where which while who whom why will with would you your et al fig table""".split())
ABBREV = ("al.", "e.g.", "i.e.", "fig.", "eq.", "vs.", "dr.", "mr.", "mrs.", "no.", "etc.", "approx.", "cf.", "inc.")
SUMMARY_HEADINGS = re.compile(r"^(abstract|summary|executive summary|overview|introduction|about)\b", re.I)
LLM_MAX_CHARS = int(os.getenv("LLM_SUMMARY_CHARS", "12000"))


@dataclass
class Analysis:
    doc_type: str
    confidence: str
    cues: list[str]
    title: str | None
    one_line: str
    summary: str
    outline: list[str]
    key_points: list[str] = field(default_factory=list)
    method: str = "extractive"                     # extractive | llm
    warnings: list[str] = field(default_factory=list)


# ----------------------------------------------------------------------------- text helpers
def headings_of(md: str) -> list[tuple[int, str]]:
    out, in_code = [], False
    for line in md.splitlines():
        if line.startswith("```"):
            in_code = not in_code
        m = None if in_code else re.match(r"^(#{1,6})\s+(.*\S)\s*$", line)
        if m:
            out.append((len(m.group(1)), m.group(2).strip()))
    return out


def prose(md: str) -> str:
    """Markdown -> plain prose paragraphs (drops tables, code, headings, short list fragments)."""
    keep, in_code = [], False
    for line in md.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or line.lstrip().startswith(("|", "#", "<!--", ">", "![")):   # "![" = saved figure/equation
            continue
        t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", line)
        t = re.sub(r"[*_`]+", "", t).strip()
        t = re.sub(r"^(?:[-*]|\d+[.)])\s+", "", t)
        keep.append(t if len(t.split()) >= 6 or line.strip() == "" else "")
    return re.sub(r"\n{2,}", "\n\n", "\n".join(keep)).strip()


def sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"“(\[])", re.sub(r"\s+", " ", text))
    out: list[str] = []
    for p in parts:
        if out and out[-1].lower().endswith(ABBREV):
            out[-1] += " " + p
        else:
            out.append(p)
    return [s.strip() for s in out if s.strip()]


def section_text(md: str, pattern: re.Pattern) -> str:
    """Text under the first heading that matches `pattern`, up to the next heading."""
    lines, buf, on = md.splitlines(), [], False
    for line in lines:
        m = re.match(r"^#{1,6}\s+(.*\S)", line)
        if m:
            if on:
                break
            head = re.sub(r"^[\d.\s]+", "", m.group(1))
            on = bool(pattern.match(head))
            continue
        if on:
            buf.append(line)
    return "\n".join(buf)


def extractive_summary(text: str, n: int = 4) -> str:
    sents = [s for s in sentences(text) if 6 <= len(s.split()) <= 70]
    if not sents:
        return ""
    if len(sents) <= n:
        return " ".join(sents)
    words = [[w for w in re.findall(r"[a-z][a-z'-]+", s.lower()) if w not in STOP] for s in sents]
    tf = Counter(w for ws in words for w in ws)
    scores = []
    for i, ws in enumerate(words):
        if not ws:
            scores.append(0.0)
            continue
        s = sum(tf[w] for w in ws) / (len(ws) ** 0.6)
        s *= 1.35 if i < 3 else 1.15 if i < 8 else 1.0
        scores.append(s)
    top = sorted(sorted(range(len(sents)), key=lambda i: scores[i], reverse=True)[:n])
    return " ".join(sents[i] for i in top)


# ----------------------------------------------------------------------------- structured summaries
def table_summary(md: str) -> str:
    """Describe spreadsheet-like documents from their tables: 'Sheet X: 4 rows, columns A, B, C'."""
    out, sheet = [], None
    blocks = re.split(r"\n\n+", md)
    for b in blocks:
        if b.startswith("## "):
            sheet = b[3:].strip()
            continue
        if b.lstrip().startswith("|"):
            rows = [r for r in b.splitlines() if r.startswith("|")]
            head = [c.strip() for c in rows[0].strip("|").split("|")]
            n = max(0, len(rows) - 2)
            if n == 0:
                continue          # a lone header/note row is not worth a line in the summary
            label = f"'{sheet}'" if sheet else "table"
            out.append(f"{label}: {n} data row{'s' if n != 1 else ''}, columns {', '.join(h or '(blank)' for h in head[:8])}"
                       + ("..." if len(head) > 8 else ""))
            sheet = None
    return "; ".join(out[:8])


def slides_summary(md: str) -> str:
    titles = re.findall(r"^## Slide \d+:\s*(.+)$", md, flags=re.M)
    n = len(re.findall(r"^## Slide \d+", md, flags=re.M))
    first = " → ".join(titles[:8]) + (" …" if len(titles) > 8 else "")
    return f"{n} slides" + (f": {first}." if first else ".")


def data_summary(md: str, kind: str) -> str:
    """Describe JSON / YAML / XML / TOML data from its rendering: sections, tables, top-level fields."""
    heads = [h for lvl, h in headings_of(md) if lvl == 2]
    tables = table_summary(md)
    scalars = re.findall(r"^([A-Za-z_@#][\w.@#-]*): ", md, flags=re.M)[:6]
    parts = []
    if tables:
        parts.append(tables)
    if heads:
        parts.append("sections: " + ", ".join(heads[:8]))
    if scalars:
        parts.append("fields: " + ", ".join(dict.fromkeys(scalars)))
    return "; ".join(parts) or "Small data file."


def code_summary(md: str) -> str:
    defs = re.findall(r"^\s*(?:async\s+)?(?:def|class|function|fn|func|public\s+\w+)\s+(\w+)", md, flags=re.M)
    lines = max(0, len(md.splitlines()) - 2)
    return f"{lines} lines of code" + (f"; defines {', '.join(dict.fromkeys(defs[:10]))}" if defs else "") + "."


def notebook_summary(md: str) -> str:
    cells = md.count("\n```") // 2 + (1 if md.startswith("```") else 0)
    first = next((h for _, h in headings_of(md)), None)
    return f"Notebook with about {cells} code/output block(s)" + (f"; starts with '{first}'." if first else ".")


# ----------------------------------------------------------------------------- main entry
def one_line(doc: ConvertedDocument, doc_type: str) -> str:
    bits = [doc_type, doc.kind.upper()]
    if doc.kind == "pdf" and doc.pages:
        bits.append(f"{doc.pages} page{'s' if doc.pages != 1 else ''}")
    if doc.kind == "pptx" and doc.pages:
        bits.append(f"{doc.pages} slides")
    if doc.sheets:
        bits.append(f"{len(doc.sheets)} sheet{'s' if len(doc.sheets) != 1 else ''}")
    bits.append(f"{doc.words:,} words")
    return " · ".join(bits)


def analyze(doc: ConvertedDocument, use_llm: bool | None = None) -> Analysis:
    """Classify and summarise a converted document. use_llm=None means 'if an LLM is configured'."""
    heads = headings_of(doc.markdown)
    guess = classify(doc.markdown, doc.kind, [h for _, h in heads])
    outline = [("  " * (lvl - 1)) + h for lvl, h in heads if lvl <= 3][:15]
    title = doc.title or (heads[0][1] if heads else None)
    warnings: list[str] = []

    if doc.kind in ("xlsx", "csv"):
        summary = table_summary(doc.markdown) or "No tables found."
        outline = [h for _, h in heads]
    elif doc.kind in ("json", "yaml", "toml", "xml"):
        summary = data_summary(doc.markdown, doc.kind)
        outline = [h for _, h in heads]
    elif doc.kind == "code":
        summary = code_summary(doc.markdown)
    elif doc.kind == "notebook":
        summary = notebook_summary(doc.markdown)
    elif doc.kind == "pptx":
        summary = slides_summary(doc.markdown)
        body = extractive_summary(prose(doc.markdown), 2)
        summary = (summary + " " + body).strip()
        outline = [h for _, h in heads if True][:20]
    else:
        text = prose(doc.markdown)
        lead = section_text(doc.markdown, SUMMARY_HEADINGS)
        lead_prose = prose(lead)
        summary = extractive_summary(lead_prose, 4) if len(sentences(lead_prose)) >= 2 else ""
        summary = summary or extractive_summary(text, 4)
        if not summary and doc.kind == "image" and 0 < len(text) <= 600:
            summary = "Text in the image: " + " ".join(text.split())
        if not summary:
            summary = "Not enough running text to summarise."

    a = Analysis(guess.doc_type, guess.confidence, guess.cues, title, one_line(doc, guess.doc_type),
                 summary, outline, [], "extractive", warnings)
    want_llm = llm_configured() if use_llm is None else use_llm
    if want_llm and doc.kind not in ("xlsx", "csv", "json", "yaml", "toml", "xml", "code"):
        try:
            _llm_refine(a, doc)
        except LLMUnavailable as e:
            a.warnings.append(f"LLM summary unavailable, used the free extractive summary ({e})")
    return a


# ----------------------------------------------------------------------------- optional LLM
def _llm_input(md: str) -> str:
    if len(md) <= LLM_MAX_CHARS:
        return md
    head, tail = int(LLM_MAX_CHARS * 0.8), int(LLM_MAX_CHARS * 0.2)
    return md[:head] + "\n\n[... middle of the document omitted ...]\n\n" + md[-tail:]


def _numbers_supported(texts: list[str], source: str) -> list[str]:
    """Numbers in model output that do not occur in the document (possible invention)."""
    flat = re.sub(r"[,\s]", "", source)
    bad = []
    for t in texts:
        for n in re.findall(r"\d[\d,]*\.?\d*", t):
            n2 = n.replace(",", "").rstrip(".")
            if len(n2) >= 3 and n2 not in flat:
                bad.append(n)
    return bad


def _parse_json(text: str) -> dict:
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.I)
    try:
        obj = json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.S)
        if not m:
            raise ValueError("no JSON object in reply")
        obj = json.loads(m.group(0))
    if not isinstance(obj, dict):
        raise ValueError("reply is not a JSON object")
    return obj


def _llm_refine(a: Analysis, doc: ConvertedDocument, client=None) -> None:
    prompt = (ROOT / "prompts" / "summary_v1.txt").read_text().replace("{document}", _llm_input(doc.markdown))
    client = client or make_client()
    resp = client.complete(prompt)
    try:
        obj = _parse_json(resp.text)
    except ValueError as e:
        a.warnings.append(f"LLM reply was not valid JSON, kept the extractive summary ({e})")
        return
    summary = str(obj.get("summary") or "").strip()
    points = [str(p).strip() for p in (obj.get("key_points") or []) if str(p).strip()][:6]
    dtype = str(obj.get("doc_type") or "").strip()
    bad = _numbers_supported([summary] + points, doc.markdown)
    if bad:
        a.warnings.append("LLM summary mentioned numbers not found in the document "
                          f"({', '.join(bad[:4])}); kept the extractive summary")
        return
    if len(summary.split()) >= 8:
        a.summary, a.method = summary, "llm"
        a.key_points = points
        if 2 <= len(dtype) <= 40:
            a.doc_type = dtype
            a.one_line = one_line(doc, dtype)
