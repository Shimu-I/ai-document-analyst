"""Document type classifier: transparent keyword scoring (no model, no network).

Each document type has weighted cue patterns. The type with the highest score wins; confidence
comes from the absolute score and the margin over the runner-up. The matched cues are returned
so the decision can be inspected ("why did it say research paper?").
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# (regex, weight). Each pattern is counted at most 3 times so one repeated word cannot dominate.
CUES: dict[str, list[tuple[str, float]]] = {
    "Research paper": [
        (r"\babstract\b", 3), (r"\breferences\b", 2), (r"\bet al\b", 2), (r"\bdoi\b|arxiv", 2),
        (r"\bkeywords?\b", 1.5), (r"\bintroduction\b", 1), (r"\brelated work\b", 2.5),
        (r"\bwe (propose|present|evaluate|show|study)\b", 2), (r"\bexperiments?\b", 1),
        (r"\b(figure|fig\.|table) \d", 1), (r"\bconclusions?\b", 1), (r"\bmethodolog", 1),
        (r"\bcase study\b", 1), (r"\bbaseline\b", 1), (r"\bour (method|approach|results)\b", 1.5)],
    "Invoice or receipt": [
        (r"\binvoice\b", 3), (r"\bbill to\b", 3), (r"\btotal due\b|\bamount due\b", 3),
        (r"\bsub-?total\b", 2), (r"\bqty\b|\bquantity\b", 1), (r"\bunit price\b", 2),
        (r"\bvat\b|\bsales tax\b", 1.5), (r"\breceipt\b", 2), (r"\bpayment terms\b", 2)],
    "Resume / CV": [
        (r"\bcurriculum vitae\b|\brésumé\b|\bresume\b", 3), (r"\bwork experience\b|\bexperience\b", 1.5),
        (r"\beducation\b", 1.5), (r"\bskills\b", 1.5), (r"\bobjective\b|\bprofile\b", 1),
        (r"linkedin\.com", 2), (r"\bcertifications?\b", 1), (r"\bprojects\b", 0.5),
        (r"\b\+?\d[\d ()-]{8,}\d\b", 0.5)],
    "Contract / legal agreement": [
        (r"\bagreement\b", 2), (r"\bhereinafter\b", 3), (r"\bparties\b|\bthe party\b", 2),
        (r"\bwhereas\b", 3), (r"\bgoverning law\b", 3), (r"\bterminat", 1.5), (r"\bindemnif", 2.5),
        (r"\bliabilit", 1.5), (r"\bconfidential", 1), (r"\bshall\b", 1), (r"\bclause\b|\bsection \d", 1)],
    "Meeting notes / minutes": [
        (r"\bagenda\b", 2.5), (r"\battendees?\b|\bparticipants\b", 2.5), (r"\bminutes\b", 2),
        (r"\baction items?\b", 3), (r"\bnext meeting\b", 3), (r"\bdiscussed\b", 1), (r"\bdecisions?\b", 1)],
    "Business report / proposal": [
        (r"\bexecutive summary\b", 3), (r"\brecommendations?\b", 2), (r"\bfindings\b", 1.5),
        (r"\bobjectives?\b", 1), (r"\bscope\b", 1), (r"\btimeline\b|\bmilestones?\b", 1.5),
        (r"\bbudget\b", 1), (r"\bstakeholders?\b", 1.5), (r"\bquarter(ly)?\b|\bq[1-4]\b", 1),
        (r"\brevenue\b|\bkpi\b", 1), (r"\breport\b", 2), (r"\bhighlights?\b|\bsummary\b", 1),
        (r"\bresults\b|\bperformance\b", 0.5)],
    "Technical documentation / manual": [
        (r"\binstallation\b|\binstall\b", 2), (r"\bconfigure\b|\bconfiguration file\b", 1.5),
        (r"\bprerequisites?\b", 2.5), (r"\busage\b", 1), (r"\bapi\b", 1), (r"\bparameters?\b", 1),
        (r"\btroubleshooting\b", 3), (r"\bstep \d\b", 1.5), (r"```", 1), (r"\breturns?\b", 0.5)],
    "Letter / email": [
        (r"\bdear\b", 2), (r"\bsincerely\b|\bregards\b|\byours (faithfully|truly)\b", 3),
        (r"^subject:", 3), (r"\bplease find attached\b|\battached\b", 1.5), (r"\bthank you\b", 1)],
    "Study notes / lecture material": [
        (r"\blecture\b", 2.5), (r"\bchapter \d", 2), (r"\bdefinition\b", 2), (r"\btheorem\b|\bproof\b", 2.5),
        (r"\bexercises?\b", 2), (r"\bsyllabus\b|\bcourse\b", 1.5), (r"\bexample \d", 1.5)],
}


@dataclass
class TypeGuess:
    doc_type: str
    confidence: str                    # high | medium | low
    cues: list[str] = field(default_factory=list)
    score: float = 0.0


def _score(text: str, patterns: list[tuple[str, float]]) -> tuple[float, list[str]]:
    total, hits = 0.0, []
    for pat, w in patterns:
        n = len(re.findall(pat, text, flags=re.I | re.M))
        if n:
            total += w * min(n, 3)
            hits.append(re.sub(r"\\b|\\", "", pat.split("|")[0]) + (f" x{n}" if n > 1 else ""))
    return total, hits


KIND_LABELS = {"json": "Structured data (JSON)", "yaml": "Configuration / data (YAML)",
               "toml": "Configuration (TOML)", "xml": "Structured data (XML)", "notebook": "Jupyter notebook",
               "code": "Source code", "html": "Web page"}


def classify(markdown: str, kind: str, headings: list[str] | None = None) -> TypeGuess:
    # Format-driven types first: the file kind is a strong signal.
    low = markdown.lower()
    if kind in KIND_LABELS:
        return TypeGuess(KIND_LABELS[kind], "high", [f"{kind} file"], 0)
    if kind in ("xlsx", "csv"):
        fin = len(re.findall(r"\b(budget|revenue|cost|expense|total|profit|price|salary|forecast)\b", low))
        roster = len(re.findall(r"\b(name|email|role|department|employee|phone)\b", low))
        sub = "Financial / budget spreadsheet" if fin >= 2 and fin >= roster else \
              "Contact / staff list" if roster >= 3 else "Data spreadsheet"
        return TypeGuess(sub, "medium", [f"{kind} file"], 0)
    # Headings weigh more than body text, so repeat them once.
    text = markdown + "\n" + "\n".join(headings or [])
    scored = {}
    for t, pats in CUES.items():
        s, hits = _score(text, pats)
        scored[t] = (s, hits)
    ranked = sorted(scored.items(), key=lambda kv: kv[1][0], reverse=True)
    best, (bs, bh) = ranked[0]
    second = ranked[1][1][0]
    if kind == "pptx":
        label = "Presentation"
        if bs >= 6:
            label = f"Presentation ({best.lower()} style content)"
        return TypeGuess(label, "medium", ["pptx file"] + bh[:3], bs)
    if bs < 4:
        return TypeGuess("Image with text (OCR)" if kind == "image" else "General document", "low", bh[:4], bs)
    conf = "high" if bs >= 10 and bs >= 1.8 * max(second, 1) else "medium" if bs >= 6 else "low"
    if conf == "low":
        return TypeGuess("Image with text (OCR)" if kind == "image" else "General document", "low", bh[:4], bs)
    return TypeGuess(best, conf, bh[:5], bs)
