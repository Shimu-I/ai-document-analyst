"""Typeset a realistic two-column research paper with pdfLaTeX and record exactly what it contains.

Why: real papers are typeset by LaTeX, with features our office-made samples lack: a full-width title
and abstract over a two-column body, ligatures (fi, ffi), tables drawn with horizontal rules only
(booktabs), footnotes, equations and a numbered reference list.

Outputs:  data/samples/paper_latex.pdf   and   data/samples/expected/paper_latex.json
Deterministic (fixed seed).   Usage: python scripts/make_latex_sample.py     (needs pdflatex)
"""
from __future__ import annotations

import json
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "samples"

SUBJECTS = ["The pruning step", "Our approach", "The workflow", "The baseline", "This study", "The efficient scheduler",
            "The corpus", "Static analysis", "The official benchmark", "The prototype"]
VERBS = ["reduces", "improves", "reveals", "supports", "limits", "explains", "tracks", "measures"]
OBJECTS = ["call graph size", "reachability results", "memory usage", "build times", "false alarms",
           "dependency coverage", "review effort", "scan latency"]
TAILS = ["across all benchmark projects", "when the entry points are known", "in the majority of cases",
         "while remaining fluent for reviewers", "under realistic workloads", "without manual configuration",
         "even for different code styles"]


def sentence(rng: random.Random, n: int) -> str:
    return (f"{rng.choice(SUBJECTS)} {rng.choice(VERBS)} {rng.choice(OBJECTS)} {rng.choice(TAILS)} "
            f"(case {n}, value {rng.randint(10, 99)}.{rng.randint(0, 9)}).")


def paragraph(rng: random.Random, start: int, n: int = 5) -> str:
    return " ".join(sentence(rng, start + i) for i in range(n))


def tex_escape(s: str) -> str:
    return s.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")


def build() -> tuple[str, dict]:
    rng = random.Random(11)
    title = "Call Graph Pruning for Large Codebases: An Empirical Study"
    authors = "Jane Researcher and John Analyst"
    abstract = paragraph(rng, 1, 6)
    sections = [("Introduction", 3), ("Related Work", 2), ("Approach", 3), ("Evaluation", 3), ("Conclusion", 2)]
    n = 100
    body: list[tuple[str, str]] = []            # ("h", text) | ("p", text)
    for name, n_par in sections:
        body.append(("h", name))
        for _ in range(n_par):
            body.append(("p", paragraph(rng, n)))
            n += 5
    bullets = ["Fewer false alarms for reviewers", "Lower memory use on large projects",
               "No manual configuration is required"]
    steps = ["Build the call graph", "Prune unreachable nodes", "Report the remaining findings"]
    table = [["Project", "Nodes", "Pruned", "Time (s)"], ["alpha", "12000", "8400", "31"],
             ["beta", "9500", "7100", "24"], ["gamma", "20100", "15300", "58"]]
    caption = "Pruning results on three benchmark projects."
    footnote = "All numbers in this paper come from the synthetic benchmark."
    refs = ["A. Author and B. Writer. Practical call graphs. Journal of Examples, 12(3):45-67, 2019.",
            "C. Scholar. Reachability in the large. Proceedings of the Example Conference, pages 100-110, 2021."]

    tex = [r"\documentclass[10pt,twocolumn]{article}",
           r"\usepackage[utf8]{inputenc}\usepackage[T1]{fontenc}\usepackage{amsmath,booktabs,graphicx,hyperref}",
           r"\usepackage[margin=0.8in]{geometry}",
           rf"\title{{{tex_escape(title)}}}\author{{{authors}}}\date{{}}",
           r"\begin{document}",
           rf"\twocolumn[\maketitle\begin{{abstract}}{tex_escape(abstract)}\end{{abstract}}\vspace{{1em}}]"]
    step_added = False
    for kind, text in body:
        if kind == "h":
            tex.append(rf"\section{{{tex_escape(text)}}}")
            if text == "Approach" and not step_added:
                pass
        else:
            tex.append(tex_escape(text) + "\n")
        if kind == "h" and text == "Introduction":
            tex.append(r"\begin{itemize}" + "".join(rf"\item {tex_escape(b)}" for b in bullets) + r"\end{itemize}")
        if kind == "h" and text == "Approach":
            tex.append(r"\begin{enumerate}" + "".join(rf"\item {tex_escape(b)}" for b in steps) + r"\end{enumerate}")
            tex.append(r"The pruning ratio is defined as" + r"\begin{equation}r = \frac{p}{n}\end{equation}"
                       + rf"where $p$ is the pruned count and $n$ the node count.\footnote{{{tex_escape(footnote)}}}")
        if kind == "h" and text == "Evaluation":
            tex.append(r"\begin{table}[h]\centering\begin{tabular}{lrrr}\toprule "
                       + " & ".join(table[0]).replace("(s)", "(s)") + r"\\ \midrule "
                       + r" \\ ".join(" & ".join(r) for r in table[1:]) + r"\\ \bottomrule\end{tabular}"
                       + rf"\caption{{{caption}}}\end{{table}}")
    tex.append(r"\begin{thebibliography}{9}" + "".join(rf"\bibitem{{r{i}}} {tex_escape(r)}" for i, r in enumerate(refs))
               + r"\end{thebibliography}\end{document}")

    # ---- ground truth (what the PDF is KNOWN to contain, in reading order)
    sec_titles = [f"{i} {name}" for i, (name, _) in enumerate(sections, 1)]
    headings = [title, "Abstract"] + sec_titles + ["References"]
    anchors = [title, authors, "Abstract", abstract]
    list_items, texts, i_sec = list(bullets) + list(steps), [], 0
    for kind, text in body:
        if kind == "h":
            i_sec += 1
            anchors.append(sec_titles[i_sec - 1])
            if text == "Introduction":
                anchors += bullets
            if text == "Approach":
                anchors += steps
        else:
            anchors.append(text)
    anchors += ["References"] + [f"[{i}] {r}" for i, r in enumerate(refs, 1)]
    words_src = [title, authors, "Abstract", abstract] + sec_titles + [t for k, t in body if k == "p"] + bullets + steps \
        + [c for r in table for c in r] + [caption, "Table 1:", footnote, "References"] + refs
    words = re.findall(r"[a-z0-9]+", " ".join(words_src).lower())
    # the numbers printed in front of references/list items are markers, not words of the source
    expected = {"words": words, "anchors": anchors, "texts": anchors, "headings": headings, "tables": [table],
                "list_items": list_items,
                "notes": "Equation r = p/n, section numbers and reference markers are typeset by LaTeX and "
                         "are not in 'words'; they can only lower precision slightly."}
    return "\n".join(tex), expected


def main() -> None:
    if not shutil.which("pdflatex"):
        sys.exit("pdflatex is required to build this sample")
    tex, expected = build()
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "paper_latex.tex").write_text(tex, encoding="utf-8")
        for _ in range(2):                                    # twice: references and numbering settle
            r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "paper_latex.tex"],
                               cwd=d, capture_output=True, text=True, timeout=180)
            if r.returncode:
                sys.exit(r.stdout[-2000:])
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "expected").mkdir(exist_ok=True)
        shutil.copy(Path(d) / "paper_latex.pdf", OUT / "paper_latex.pdf")
    (OUT / "expected" / "paper_latex.json").write_text(json.dumps(expected, indent=1, ensure_ascii=False) + "\n")
    print("wrote", OUT / "paper_latex.pdf")


if __name__ == "__main__":
    main()
