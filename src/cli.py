"""Command line: convert documents to Markdown without starting any server.

    python -m src.cli report.pdf slides.pptx budget.xlsx          # writes report.md, slides.md, ...
    python -m src.cli docs/ -o markdown/                          # a whole folder (recursive)
    python -m src.cli paper.pdf --summary                         # add a summary block on top
    python -m src.cli paper.pdf --stdout                          # print instead of writing a file
    python -m src.cli screenshot.png                              # image -> text (OCR)
    python -m src.cli data.json --compact                         # fewer tokens: no empty values, tighter tables
    python -m src.cli big.pdf --max-tokens 6000                   # split into parts that fit a chat window
    python -m src.cli bangla.png --lang ben                       # other OCR language (install tesseract-ocr-ben)
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src import service
from src.convert import SUPPORTED


# When a whole folder is given, only real documents are picked up. Plain text, Markdown, source code and data
# files (JSON, YAML, XML...) are skipped there because they are already text; name them explicitly to convert them.
FOLDER_EXTS = {".pdf", ".docx", ".xlsx", ".xlsm", ".pptx", ".csv", ".tsv", ".html", ".htm", ".ipynb",
               ".doc", ".xls", ".ppt", ".odt", ".ods", ".odp", ".rtf",
               ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif"}


def collect(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            out += sorted(f for f in p.rglob("*") if f.is_file() and f.suffix.lower() in FOLDER_EXTS
                          and not f.name.startswith(("~$", ".")))
        else:
            out.append(p)
    return out


def destination(src: Path, md_name: str, out_dir: Path | None, taken: set[Path]) -> Path:
    """Where to write the .md. Never overwrites the source or another file written in this run:
    report.pdf and report.docx become report.md and report_docx.md."""
    base = (out_dir or src.parent) / md_name
    cands = [base, base.with_name(f"{base.stem}_{src.suffix.lower().lstrip('.')}.md")]
    cands += [base.with_name(f"{base.stem}_{src.suffix.lower().lstrip('.')}_{n}.md") for n in range(2, 1000)]
    for c in cands:
        key = c.resolve()
        if key != src.resolve() and key not in taken:
            taken.add(key)
            return c
    raise OSError(f"could not find a free output name for {src}")


def service_tokens(text: str) -> int:
    from src.convert.base import estimate_tokens
    return estimate_tokens(text)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="docmd", description="Convert PDF/DOCX/XLSX/PPTX/images to Markdown.")
    ap.add_argument("paths", nargs="+", help="files or folders")
    ap.add_argument("-o", "--out", help="output folder (default: next to each input file)")
    ap.add_argument("--summary", action="store_true", help="add a short summary block at the top of the .md")
    ap.add_argument("--stdout", action="store_true", help="print Markdown instead of writing files")
    ap.add_argument("--page-markers", action="store_true", help="insert <!-- page N --> comments (PDF)")
    ap.add_argument("--keep-headers", action="store_true", help="do not strip repeated headers/footers (PDF)")
    ap.add_argument("--ocr", action="store_true", help="force OCR for PDFs")
    ap.add_argument("--llm", action="store_true", help="use the configured LLM (LLM_MODEL...) for the summary")
    ap.add_argument("--compact", action="store_true",
                    help="save tokens: drop table padding, comments, empty values in JSON/YAML/XML")
    ap.add_argument("--max-tokens", type=int, metavar="N",
                    help="split the output into parts of about N tokens (breaks before headings)")
    ap.add_argument("--json", choices=["readable", "minified"], default="readable", dest="json_mode",
                    help="JSON/YAML/XML output: readable tables and key: value lines (default) or exact minified JSON")
    ap.add_argument("--lang", help="OCR language(s) for images and scanned PDFs, e.g. eng, ben, eng+ben")
    a = ap.parse_args(argv)

    files = collect(a.paths)
    if not files:
        print("no supported files found", file=sys.stderr)
        return 2
    out_dir = Path(a.out) if a.out else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    failures = 0
    taken: set[Path] = set()
    for f in files:
        try:
            r = service.process(f.read_bytes(), f.name, page_markers=a.page_markers,
                                strip_repeated=not a.keep_headers, force_ocr=a.ocr,
                                use_llm=True if a.llm else False, compact=a.compact, json_mode=a.json_mode,
                                ocr_lang=a.lang, max_tokens=a.max_tokens)
        except (service.ServiceError, OSError) as e:
            print(f"FAILED  {f}: {getattr(e, 'message', e)}", file=sys.stderr)
            failures += 1
            continue
        outputs = service.output_files(r, include_summary=a.summary)
        if a.stdout:
            print("\n\n".join(text for _, text in outputs))
            continue
        st = r["stats"]
        for name, text in outputs:
            dest = destination(f, name, out_dir, taken)
            dest.write_text(text, encoding="utf-8")
            print(f"{f}  ->  {dest}   [{r['analysis']['doc_type']}, {st['words']:,} words, ~{service_tokens(text):,} tokens]")
        for w in r["warnings"]:
            print(f"    note: {w}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
