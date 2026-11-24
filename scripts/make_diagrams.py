"""Render every ```mermaid block in docs/*.md and docs/deep_dive/*.md to docs/assets/diagrams/<doc>_<n>.png.

The in-app Documentation page shows these pictures (Streamlit cannot draw Mermaid itself). Needs mermaid-cli:
    npm i -g @mermaid-js/mermaid-cli
    python scripts/make_diagrams.py
"""
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
OUT = DOCS / "assets" / "diagrams"


def main() -> int:
    if not shutil.which("mmdc"):
        print("mmdc not found: npm i -g @mermaid-js/mermaid-cli", file=sys.stderr)
        return 2
    OUT.mkdir(parents=True, exist_ok=True)
    cfg = Path(tempfile.mkdtemp()) / "pp.json"
    cfg.write_text('{"args": ["--no-sandbox"]}')
    failed = n = 0
    for md in sorted(DOCS.glob("*.md")) + sorted((DOCS / "deep_dive").glob("*.md")):
        for i, src in enumerate(re.findall(r"```mermaid\n(.*?)```", md.read_text(encoding="utf-8"), re.S)):
            tmp = cfg.parent / f"{md.stem}_{i}.mmd"
            tmp.write_text(src)
            r = subprocess.run(["mmdc", "-p", str(cfg), "-i", str(tmp), "-o", str(OUT / f"{md.stem}_{i}.png"),
                                "-s", "2", "-b", "white", "-q"], capture_output=True, text=True)
            n += 1
            if r.returncode:
                failed += 1
                print(f"FAILED {md.name} #{i}: {r.stderr.strip()[:200]}", file=sys.stderr)
    print(f"{n - failed} of {n} diagrams written to {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
