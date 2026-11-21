"""Measure how faithfully each converter reproduces a document's known content.

For every sample in data/samples/ (ground truth in data/samples/expected/*.json) this reports:

  word recall      share of the source's words that appear in the Markdown (missing text)
  word precision   share of Markdown words that belong to the source (junk, duplicates, garbling)
  order            longest-in-order share of paragraph anchors (reading order, e.g. two columns)
  headings         expected headings that appear as '#' lines
  tables           expected tables whose cells appear, in order, inside one Markdown table
  list items       expected list items that appear as '-' / '1.' lines
  tokens           estimated tokens of the Markdown (chars / 4)

Our converter is compared with Microsoft's `markitdown` when it is installed (pip install markitdown).
Usage: python scripts/evaluate_fidelity.py          -> prints a table, writes reports/fidelity.json
"""
from __future__ import annotations

import bisect
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.convert import convert  # noqa: E402

SAMPLES = ROOT / "data" / "samples"
FILES = {"report.pdf": "report", "report.docx": "report", "paper_two_column.pdf": "paper_two_column",
         "paper_two_column.docx": "paper_two_column", "paper_latex.pdf": "paper_latex",
         "budget.xlsx": "budget", "deck.pptx": "deck", "scanned.pdf": "scanned"}


def toks(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def strip_structure(md: str) -> str:
    """Remove words that our converter adds on purpose so they are not counted as junk."""
    md = re.sub(r"^## Slide \d+:?", "", md, flags=re.M)
    md = md.replace("**Notes:**", "")
    md = re.sub(r"<!--.*?-->", "", md)
    md = re.sub(r"^\s*\d{1,3}[.)]\s", "", md, flags=re.M)        # numbered-list markers are syntax
    return md


def lis(seq: list[int]) -> int:
    tails: list[int] = []
    for x in seq:
        i = bisect.bisect_left(tails, x)
        if i == len(tails):
            tails.append(x)
        else:
            tails[i] = x
    return len(tails)


def md_tables(md: str) -> list[str]:
    blocks, cur = [], []
    for line in md.splitlines():
        if line.lstrip().startswith("|"):
            cur.append(line)
        elif cur:
            blocks.append("\n".join(cur))
            cur = []
    if cur:
        blocks.append("\n".join(cur))
    return [" ".join(toks(b)) for b in blocks]


def subseq(needle: list[str], hay: list[str]) -> bool:
    it = iter(hay)
    return all(any(n == h for h in it) for n in needle)


def score(md: str, exp: dict) -> dict:
    src = Counter(exp["words"])
    out = Counter(toks(strip_structure(md)))
    overlap = sum((src & out).values())
    recall = overlap / max(1, sum(src.values()))
    precision = overlap / max(1, sum(out.values()))
    # Reading order: walk the anchors in source order and look for each one at/after the previous
    # match (whole-token match). An anchor that only exists earlier in the output is out of order.
    words = toks(md)
    cursor, in_order = 0, 0
    for a in exp["anchors"]:
        t = toks(a)[:8]
        if not t:
            continue
        found = next((i for i in range(cursor, len(words) - len(t) + 1) if words[i:i + len(t)] == t), None)
        if found is not None:
            in_order += 1
            cursor = found + len(t)
    order = in_order / max(1, len(exp["anchors"]))
    heads = {" ".join(toks(re.sub(r"^#+\s*", "", l))) for l in md.splitlines() if l.startswith("#")}
    h_ok = sum(1 for h in exp["headings"] if " ".join(toks(h)) in heads)
    blocks = md_tables(md)
    t_ok = sum(1 for t in exp["tables"]
               if any(subseq(toks(" ".join(c for r in t for c in r)), b.split()) for b in blocks))
    lines = [" ".join(toks(re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", l)))
             for l in md.splitlines() if re.match(r"^\s*(?:[-*]|\d+[.)])\s+", l)]
    l_ok = sum(1 for li in exp["list_items"] if " ".join(toks(li)) in lines)
    return {"word_recall": round(recall, 3), "word_precision": round(precision, 3), "order": round(order, 3),
            "headings": f"{h_ok}/{len(exp['headings'])}", "tables": f"{t_ok}/{len(exp['tables'])}",
            "list_items": f"{l_ok}/{len(exp['list_items'])}", "tokens": max(1, round(len(md) / 4))}


def run_ours(path: Path) -> str:
    return convert(path.read_bytes(), path.name).markdown


def make_markitdown():
    try:
        from markitdown import MarkItDown
    except ImportError:
        return None
    mid = MarkItDown()
    return lambda p: mid.convert(str(p)).text_content


def main() -> None:
    mk = make_markitdown()
    results = {}
    print(f"{'file':26} {'tool':10} {'recall':>7} {'prec':>6} {'order':>6} {'headings':>9} {'tables':>7} {'lists':>6} {'tokens':>7}")
    for fname, exp_name in FILES.items():
        path = SAMPLES / fname
        exp = json.loads((SAMPLES / "expected" / f"{exp_name}.json").read_text())
        for tool, fn in (("ours", run_ours), ("markitdown", mk)):
            if fn is None:
                continue
            try:
                md = fn(path)
                s = score(md, exp)
            except Exception as e:  # a tool failing is a result too
                s = {"error": f"{type(e).__name__}: {str(e)[:80]}"}
            results.setdefault(fname, {})[tool] = s
            if "error" in s:
                print(f"{fname:26} {tool:10} ERROR {s['error']}")
            else:
                print(f"{fname:26} {tool:10} {s['word_recall']:7.3f} {s['word_precision']:6.3f} {s['order']:6.3f} "
                      f"{s['headings']:>9} {s['tables']:>7} {s['list_items']:>6} {s['tokens']:7d}")
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports" / "fidelity.json").write_text(json.dumps(results, indent=2) + "\n")
    if mk is None:
        print("\n(markitdown not installed: only our converter was measured)")


if __name__ == "__main__":
    main()
