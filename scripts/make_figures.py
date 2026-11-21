"""Draw the two result charts used in the README and the portfolio page, from live measurements.

    python scripts/make_figures.py          # needs matplotlib (pip install matplotlib)

Writes docs/assets/tokens_json.png and docs/assets/fidelity.png.

* tokens_json.png  - the sample JSON file in four forms; token counts come from the project's own estimator
                     (about 4 characters per token for English text, an estimate and not a real tokenizer).
* fidelity.png     - read from reports/fidelity.json, which scripts/evaluate_fidelity.py writes.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.convert import convert  # noqa: E402
from src.convert.base import estimate_tokens  # noqa: E402

OUT = ROOT / "docs" / "assets"
BLUE, GREY, INK, MUTED = "#2f5fd0", "#aab4c3", "#1b2430", "#5b6b80"
plt.rcParams.update({"font.family": "DejaVu Sans", "axes.edgecolor": "#c9d3e3", "axes.labelcolor": INK,
                     "xtick.color": INK, "ytick.color": MUTED, "text.color": INK})


def clean_axes(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def tokens_chart() -> None:
    with tempfile.TemporaryDirectory() as d:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "make_data_samples.py"), d], check=True,
                       capture_output=True)
        raw_bytes = (Path(d) / "users.json").read_bytes()
    raw = raw_bytes.decode()
    obj = json.loads(raw)
    rows = [("Indented JSON\n(as saved)", estimate_tokens(raw), GREY),
            ("Minified JSON\n(whitespace removed)", estimate_tokens(json.dumps(obj, separators=(",", ":"))), GREY),
            ("This tool\nreadable", convert(raw_bytes, "users.json").est_tokens, BLUE),
            ("This tool\nreadable + compact", convert(raw_bytes, "users.json", compact=True).est_tokens, BLUE)]
    base = rows[0][1]
    fig, ax = plt.subplots(figsize=(8.6, 4.6), dpi=200)
    bars = ax.bar([r[0] for r in rows], [r[1] for r in rows], color=[r[2] for r in rows], width=0.62)
    for b, (_, v, _) in zip(bars, rows):
        pct = "" if v == base else f"\n{(v - base) / base:+.0%}"
        ax.text(b.get_x() + b.get_width() / 2, v + base * 0.02, f"{v:,}{pct}", ha="center", va="bottom",
                fontsize=11, fontweight="bold", color=INK)
    ax.set_ylim(0, base * 1.22)
    ax.set_ylabel("Estimated tokens")
    ax.set_title(f"Same data, fewer tokens: a {len(obj['users'])}-record JSON file", loc="left", fontsize=13,
                 fontweight="bold")
    clean_axes(ax)
    ax.yaxis.grid(True, color="#e6ebf2")
    ax.set_axisbelow(True)
    fig.text(0.01, 0.01, "Token counts are estimates (characters / 4), not a real tokenizer. Generated sample "
             "data; savings on other files will differ.", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(OUT / "tokens_json.png")
    plt.close(fig)


def _ratio(s: str) -> float | None:
    a, b = s.split("/")
    return None if int(b) == 0 else int(a) / int(b)


def fidelity_chart() -> None:
    rep = json.loads((ROOT / "reports" / "fidelity.json").read_text())
    files = list(rep)
    ours, theirs = [], []
    for f in files:
        ours.append(rep[f]["ours"]["order"])
        theirs.append(rep[f]["markitdown"].get("order", 0.0))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 5.0), dpi=200, gridspec_kw={"width_ratios": [1.5, 1]})
    y = range(len(files))
    h = 0.38
    a1.barh([i + h / 2 for i in y], ours, h, color=BLUE, label="This tool")
    a1.barh([i - h / 2 for i in y], theirs, h, color=GREY, label="markitdown")
    a1.set_yticks(list(y), files, fontsize=9)
    a1.invert_yaxis()
    a1.set_xlim(0, 1.12)
    a1.set_xticks([0, .25, .5, .75, 1], ["0%", "25%", "50%", "75%", "100%"])
    a1.set_title("Reading order kept (higher is better)", loc="left", fontsize=11.5, fontweight="bold")
    for i, (o, t) in enumerate(zip(ours, theirs)):
        a1.text(o + 0.01, i + h / 2, f"{o:.0%}", va="center", fontsize=8, color=INK)
        a1.text(t + 0.01, i - h / 2, f"{t:.0%}", va="center", fontsize=8, color=MUTED)
    a1.legend(frameon=False, fontsize=9, loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=2)
    clean_axes(a1)

    hf = [f for f in files if _ratio(rep[f]["ours"]["headings"]) is not None]
    ho = [_ratio(rep[f]["ours"]["headings"]) for f in hf]
    ht = [_ratio(rep[f]["markitdown"].get("headings", "0/1")) or 0 for f in hf]
    y2 = range(len(hf))
    a2.barh([i + h / 2 for i in y2], ho, h, color=BLUE)
    a2.barh([i - h / 2 for i in y2], ht, h, color=GREY)
    a2.set_yticks(list(y2), hf, fontsize=9)
    a2.invert_yaxis()
    a2.set_xlim(0, 1.12)
    a2.set_xticks([0, .5, 1], ["0%", "50%", "100%"])
    a2.set_title("Headings kept as # lines", loc="left", fontsize=11.5, fontweight="bold")
    for i, (o, t) in enumerate(zip(ho, ht)):
        a2.text(o + 0.01, i + h / 2, f"{o:.0%}", va="center", fontsize=8, color=INK)
        a2.text(t + 0.01, i - h / 2, f"{t:.0%}", va="center", fontsize=8, color=MUTED)
    clean_axes(a2)
    fig.suptitle("Fidelity on 8 sample documents with known content", x=0.01, ha="left", fontsize=13,
                 fontweight="bold")
    fig.text(0.01, 0.01, "Small synthetic samples, and the converter was tuned on them: evidence that the method works, "
             "not a benchmark. scanned.pdf: markitdown has no OCR.", fontsize=7.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.04, 1, 0.94))
    fig.savefig(OUT / "fidelity.png")
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    tokens_chart()
    fidelity_chart()
    print("wrote", OUT / "tokens_json.png", "and", OUT / "fidelity.png")
