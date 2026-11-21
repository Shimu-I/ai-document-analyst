"""Run awkward inputs through the same code path as the web page, API and CLI, and print what happens.

    python scripts/corner_cases.py            # prints a Markdown table; exit code 1 if any case deviates
    python scripts/corner_cases.py --verbose  # also prints the first lines of each output

Every case states the behaviour that docs/10_corner_cases_and_troubleshooting.md promises. A case is
SKIPPED when a program it needs (tesseract, LibreOffice) is not installed; it is never silently passed.
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import cli, service  # noqa: E402
from src.convert import convert, split_by_tokens  # noqa: E402
from src.convert.base import estimate_tokens  # noqa: E402

SAMPLES = ROOT / "data" / "samples"
HAVE_TESSERACT = shutil.which("tesseract") is not None
HAVE_SOFFICE = bool(shutil.which("soffice") or shutil.which("libreoffice"))

CASES: list[dict] = []


def case(group: str, name: str, needs: str | None = None):
    """Register a function that returns (ok, observed_text)."""
    def deco(fn):
        CASES.append({"group": group, "name": name, "fn": fn, "needs": needs})
        return fn
    return deco


def run(data: bytes, filename: str, **kw):
    """Returns ('ok', result) or ('error', status, message)."""
    try:
        return ("ok", service.process(data, filename, use_llm=False, **kw))
    except service.ServiceError as e:
        return ("error", e.status, e.message)


def expect_error(res, status: int, *needles: str):
    if res[0] != "error":
        return False, "no error was raised"
    ok = res[1] == status and all(n.lower() in res[2].lower() for n in needles)
    return ok, f"{res[1]}: {res[2][:110]}"


def sample(name: str) -> bytes:
    return (SAMPLES / name).read_bytes()


# ------------------------------------------------------------------ input handling
@case("Input", "empty file")
def _():
    return expect_error(run(b"", "a.pdf"), 400, "empty")


@case("Input", "unknown extension (.exe)")
def _():
    return expect_error(run(b"MZ", "a.exe"), 415, "unsupported")


@case("Input", "no extension at all")
def _():
    return expect_error(run(b"hello", "README"), 415, "unsupported")


@case("Input", "upper-case extension (.PDF) is accepted")
def _():
    r = run(sample("report.pdf"), "REPORT.PDF")
    return r[0] == "ok" and r[1]["stats"]["kind"] == "pdf", r[0]


@case("Input", "PNG bytes saved with a .pdf name")
def _():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buf, "PNG")
    return expect_error(run(buf.getvalue(), "fake.pdf"), 422, "could not open pdf")


@case("Input", "corrupt PDF")
def _():
    return expect_error(run(b"%PDF-1.4 not really a pdf", "x.pdf"), 422)


@case("Input", "password-protected PDF")
def _():
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(200, 200)
    w.encrypt("secret")
    buf = io.BytesIO()
    w.write(buf)
    return expect_error(run(buf.getvalue(), "locked.pdf"), 422, "password")


@case("Input", "DOCX that is not a zip archive")
def _():
    return expect_error(run(b"plain text pretending to be docx", "x.docx"), 422)


@case("Input", "file larger than the upload limit")
def _():
    with mock.patch.object(service, "MAX_UPLOAD_BYTES", 1024 * 1024):       # the default limit is 50 MB
        return expect_error(run(b"x" * (2 * 1024 * 1024), "big.txt"), 413, "larger than 1 MB")


@case("Input", "max_tokens below the minimum (100)")
def _():
    return expect_error(run(b"hello world", "a.txt", max_tokens=100), 422, "at least 200")


# ------------------------------------------------------------------ text and encodings
@case("Text", "CSV saved as Windows-1252 keeps accents")
def _():
    r = run("name,city\nRené,Zürich\n".encode("cp1252"), "a.csv")
    return r[0] == "ok" and "René" in r[1]["markdown"] and "Zürich" in r[1]["markdown"], r[0]


@case("Text", "UTF-16 CSV with byte-order mark")
def _():
    r = run("a,b\n1,2\n".encode("utf-16"), "u16.csv")
    return r[0] == "ok" and "| a | b |" in r[1]["markdown"], r[0]


@case("Text", "semicolon-separated CSV is split into columns")
def _():
    r = run(b"a;b;c\n1;2;3\n", "semi.csv")
    return r[0] == "ok" and "| a | b | c |" in r[1]["markdown"], r[0]


@case("Text", "CSV with 6,000 rows is truncated and says so")
def _():
    text = "id,v\n" + "\n".join(f"{i},x" for i in range(6000))
    r = run(text.encode(), "big.csv")
    return r[0] == "ok" and any("truncated to 5000" in w for w in r[1]["warnings"]), r[0]


@case("Text", "ligatures and soft hyphens are cleaned")
def _():
    r = run("ﬁnal o­k ﬂow".encode(), "t.txt")
    return r[0] == "ok" and r[1]["markdown"].strip() == "final ok flow", r[1]["markdown"].strip() if r[0] == "ok" else r[2]


@case("Text", "pipe character inside a table cell is escaped")
def _():
    r = run(b"a,b\nx|y,2\n", "p.csv")
    return r[0] == "ok" and "x\\|y" in r[1]["markdown"], r[0]


# ------------------------------------------------------------------ Office files
@case("Office", "Excel formula with no stored result")
def _():
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active["A1"], wb.active["A2"] = 5, "=A1*2"
    buf = io.BytesIO()
    wb.save(buf)
    r = run(buf.getvalue(), "f.xlsx")
    return r[0] == "ok" and any("formula cell" in w for w in r[1]["warnings"]), r[0]


@case("Office", "Excel hidden sheet is skipped and reported")
def _():
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active["A1"] = "visible"
    wb.create_sheet("Secret")["A1"] = "hidden data"
    wb["Secret"].sheet_state = "hidden"
    buf = io.BytesIO()
    wb.save(buf)
    r = run(buf.getvalue(), "h.xlsx")
    return (r[0] == "ok" and "hidden data" not in r[1]["markdown"]
            and any("hidden sheet" in w for w in r[1]["warnings"])), r[0]


@case("Office", "Excel workbook with an empty sheet")
def _():
    import openpyxl
    buf = io.BytesIO()
    openpyxl.Workbook().save(buf)
    r = run(buf.getvalue(), "e.xlsx")
    return r[0] == "ok" and "(empty sheet)" in r[1]["markdown"], r[0]


@case("Office", "Word header/footer/footnotes are not included (warning)")
def _():
    import docx
    d = docx.Document()
    d.sections[0].header.paragraphs[0].text = "SECRET HEADER"
    d.add_paragraph("Body text")
    buf = io.BytesIO()
    d.save(buf)
    r = run(buf.getvalue(), "w.docx")
    return (r[0] == "ok" and "SECRET HEADER" not in r[1]["markdown"]
            and any("headers, footers" in w for w in r[1]["warnings"])), r[0]


@case("Office", "PowerPoint slide without a title")
def _():
    from pptx import Presentation
    p = Presentation()
    s = p.slides.add_slide(p.slide_layouts[6])
    s.shapes.add_textbox(0, 0, 3000000, 500000).text_frame.text = "just a text box"
    buf = io.BytesIO()
    p.save(buf)
    r = run(buf.getvalue(), "n.pptx")
    return r[0] == "ok" and "## Slide 1\n" in r[1]["markdown"] and "just a text box" in r[1]["markdown"], r[0]


@case("Office", "old .doc file is converted through LibreOffice", needs="soffice")
def _():
    import subprocess
    import docx
    with tempfile.TemporaryDirectory() as d:
        src = Path(d) / "in.docx"
        doc = docx.Document()
        doc.add_heading("Legacy title", 1)
        doc.add_paragraph("legacy body text")
        doc.save(src)
        exe = shutil.which("soffice") or shutil.which("libreoffice")
        subprocess.run([exe, "--headless", "--convert-to", "doc", "--outdir", d, str(src)],
                       check=True, capture_output=True, timeout=180, env={"HOME": d, "PATH": "/usr/bin:/bin"})
        r = run((Path(d) / "in.doc").read_bytes(), "old.doc")
    return (r[0] == "ok" and "legacy body text" in r[1]["markdown"]
            and any("LibreOffice" in w for w in r[1]["warnings"])), r[0] if r[0] == "ok" else r[2]


# ------------------------------------------------------------------ PDF
@case("PDF", "scanned PDF (no text layer) is read with OCR", needs="tesseract")
def _():
    r = run(sample("scanned.pdf"), "scanned.pdf")
    return (r[0] == "ok" and r[1]["stats"]["ocr_pages"] >= 1
            and any("OCR" in w for w in r[1]["warnings"])), r[0] if r[0] == "ok" else r[2]


def _four_page_pdf() -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for n in range(1, 5):
        c.setFont("Helvetica", 9)
        c.drawString(72, 810, "ACME CONFIDENTIAL REPORT")           # same running header on every page
        c.drawString(290, 30, f"Page {n}")                           # page number
        c.setFont("Helvetica", 11)
        for i in range(6):
            c.drawString(72, 700 - 18 * i, f"Body sentence {i} on page {n} with enough words to be text.")
        c.showPage()
    c.save()
    return buf.getvalue()


@case("PDF", "running header and page numbers are removed from a 4-page PDF")
def _():
    r = run(_four_page_pdf(), "four.pdf")
    if r[0] != "ok":
        return False, r[2]
    md, removed = r[1]["markdown"], r[1]["stats"]["headers_footers_removed"]
    return "ACME CONFIDENTIAL" not in md and "Page 3" not in md and removed == 8 and "Body sentence 0 on page 4" in md, \
        f"removed {removed} lines, body kept"


@case("PDF", "the same PDF with keep_headers=True keeps them")
def _():
    from src.convert import convert
    d = convert(_four_page_pdf(), "four.pdf", strip_repeated=False)
    return "ACME CONFIDENTIAL" in d.markdown and d.headers_footers_removed == 0, f"removed {d.headers_footers_removed}"


# ------------------------------------------------------------------ data files
@case("Data", "invalid JSON")
def _():
    return expect_error(run(b"{not json", "bad.json"), 422, "not valid json")


@case("Data", "JSON Lines becomes one table")
def _():
    r = run(b'{"a":1}\n{"a":2}\n', "e.jsonl")
    return r[0] == "ok" and r[1]["stats"]["tables"] == 1, r[0]


@case("Data", "records with different keys are not forced into one table")
def _():
    data = json.dumps([{"a": 1, "b": 2}, {"x": 1, "y": 2}, {"p": 1, "q": 2}]).encode()
    r = run(data, "mixed.json")
    return r[0] == "ok" and r[1]["stats"]["tables"] == 0, f"tables={r[1]['stats']['tables']}" if r[0] == "ok" else r[2]


@case("Data", "records with more than 30 distinct keys stay as lines")
def _():
    rows = [{f"k{i}": j for i in range(35)} for j in range(3)]
    r = run(json.dumps(rows).encode(), "wide.json")
    return r[0] == "ok" and r[1]["stats"]["tables"] == 0, r[0]


@case("Data", "JSON nested 20 levels deep does not crash")
def _():
    o = cur = {}
    for _ in range(20):
        cur["n"] = {}
        cur = cur["n"]
    cur["leaf"] = 1
    r = run(json.dumps(o).encode(), "deep.json")
    return r[0] == "ok" and "leaf" in r[1]["markdown"], r[0] if r[0] == "ok" else r[2]


@case("Data", "empty JSON object")
def _():
    r = run(b"{}", "e.json")
    return r[0] == "ok" and r[1]["markdown"].strip() == "(empty)", r[1]["markdown"].strip() if r[0] == "ok" else r[2]


@case("Data", "top-level scalar JSON")
def _():
    r = run(b"42", "n.json")
    return r[0] == "ok" and r[1]["markdown"].strip() == "42", r[1]["markdown"].strip() if r[0] == "ok" else r[2]


@case("Data", "non-English text is kept and costs more tokens per character")
def _():
    bn = "আমি বাংলায় কথা বলি"
    r = run(json.dumps({"msg": bn}, ensure_ascii=False).encode(), "bn.json")
    en = "I speak English"
    return (r[0] == "ok" and bn in r[1]["markdown"] and estimate_tokens(bn) > estimate_tokens(en)), r[0]


@case("Data", "XML with an entity declaration is refused")
def _():
    xml = b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "y">]><a>&x;</a>'
    return expect_error(run(xml, "bomb.xml"), 422, "entity")


@case("Data", "invalid XML")
def _():
    return expect_error(run(b"<a><b></a>", "bad.xml"), 422, "not valid xml")


@case("Data", "YAML with several similar documents becomes one table")
def _():
    r = run(b"a: 1\n---\na: 2\n", "m.yaml")
    return r[0] == "ok" and r[1]["stats"]["tables"] == 1 and "| 1 |" in r[1]["markdown"] and "| 2 |" in r[1]["markdown"], (
        r[1]["markdown"].replace("\n", " / ") if r[0] == "ok" else r[2])


@case("Data", "notebook output longer than 40 lines is cut")
def _():
    nb = {"cells": [{"cell_type": "code", "source": ["print(1)"],
                     "outputs": [{"output_type": "stream", "text": [f"line {i}\n" for i in range(100)]}]}],
          "metadata": {}}
    r = run(json.dumps(nb).encode(), "n.ipynb")
    return r[0] == "ok" and "(60 more lines)" in r[1]["markdown"], r[0]


@case("Data", "HTML page that is only JavaScript")
def _():
    r = run(b"<html><body><div id='app'></div><script>render()</script></body></html>", "spa.html")
    return r[0] == "ok" and any("no readable text" in w for w in r[1]["warnings"]), r[0]


@case("Data", "Google Sheets shortcut file")
def _():
    return expect_error(run(b'{"url": "https://docs.google.com/x"}', "s.gsheet"), 422, "shortcut", ".xlsx")


@case("Data", "code containing a ``` fence")
def _():
    r = run(b"x = '''```'''\n", "a.py")
    return r[0] == "ok" and r[1]["markdown"].startswith("````python"), r[0]


# ------------------------------------------------------------------ images
@case("Image", "blank image has no text", needs="tesseract")
def _():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), "white").save(buf, "PNG")
    r = run(buf.getvalue(), "blank.png")
    return r[0] == "ok" and any("no text found" in w for w in r[1]["warnings"]), r[0]


@case("Image", "corrupt image bytes", needs="tesseract")
def _():
    return expect_error(run(b"not an image", "x.png"), 422, "could not read this image")


@case("Image", "OCR language that is not installed", needs="tesseract")
def _():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), "white").save(buf, "PNG")
    return expect_error(run(buf.getvalue(), "x.png", ocr_lang="zzz"), 422, "not installed", "tesseract-ocr-zzz")


@case("Image", "animated GIF with 25 frames reads only the first 20", needs="tesseract")
def _():
    from PIL import Image
    frames = [Image.new("RGB", (120, 80), (i * 9 % 255,) * 3) for i in range(25)]
    buf = io.BytesIO()
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=50)
    r = run(buf.getvalue(), "anim.gif")
    return r[0] == "ok" and any("first 20 of 25" in w for w in r[1]["warnings"]), r[0] if r[0] == "ok" else r[2]


# ------------------------------------------------------------------ token tools
@case("Tokens", "one huge line without spaces is still split under the budget")
def _():
    parts = split_by_tokens("x" * 20000, 500)
    biggest = max(estimate_tokens(p) for p in parts)
    return len(parts) > 3 and biggest <= 500 * 1.3, f"{len(parts)} parts, largest ~{biggest} tokens"


@case("Tokens", "zip of split parts contains every part once")
def _():
    text = "\n\n".join(f"## S{i}\n\n" + "lorem ipsum " * 400 for i in range(5))
    res = run(text.encode(), "big.txt", max_tokens=1000)
    if res[0] != "ok":
        return False, res[2]
    names = [n for n, _ in service.output_files(res[1])]
    z = zipfile.ZipFile(io.BytesIO(service.zip_results([res[1]])))
    return sorted(z.namelist()) == sorted(names) and len(names) > 2, f"{len(names)} parts"


# ------------------------------------------------------------------ command line
@case("CLI", "folder scan skips .json/.py/.txt but converts documents")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "a.json").write_text("{}")
        (d / "b.csv").write_text("a,b\n1,2\n")
        (d / "c.py").write_text("x=1\n")
        found = [p.name for p in cli.collect([str(d)])]
    return found == ["b.csv"], str(found)


@case("CLI", "same name, different extension in one run: nothing is overwritten")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "report.csv").write_text("a,b\n1,2\n")
        (d / "report.txt").write_text("hello there\n")
        out = d / "out"
        with contextlib.redirect_stdout(io.StringIO()):
            code = cli.main([str(d / "report.csv"), str(d / "report.txt"), "-o", str(out)])
        names = sorted(p.name for p in out.iterdir())
    return code == 0 and len(names) == 2 and "report.md" in names, str(names)


@case("CLI", "exit codes: 0 success, 1 a file failed, 2 nothing to do")
def _():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "ok.csv").write_text("a\n1\n")
        (d / "bad.gsheet").write_text("{}")
        empty = d / "empty"
        empty.mkdir()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            got = (cli.main([str(d / "ok.csv"), "--stdout"]), cli.main([str(d / "bad.gsheet")]),
                   cli.main([str(empty)]))
    return got == (0, 1, 2), str(got)


# ------------------------------------------------------------------ driver
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    rows, failed = [], 0
    for c in CASES:
        if (c["needs"] == "tesseract" and not HAVE_TESSERACT) or (c["needs"] == "soffice" and not HAVE_SOFFICE):
            rows.append((c["group"], c["name"], "SKIP", f"{c['needs']} is not installed"))
            continue
        try:
            ok, seen = c["fn"]()
        except Exception as e:  # a crash is a failure, with the reason shown
            ok, seen = False, f"crashed: {type(e).__name__}: {e}"
        failed += 0 if ok else 1
        rows.append((c["group"], c["name"], "PASS" if ok else "FAIL", str(seen).replace("|", "/").replace("\n", " ")[:120]))
    print("| Group | Case | Result | Observed |\n|---|---|---|---|")
    for r in rows:
        print("| " + " | ".join(r) + " |")
    n_skip = sum(1 for r in rows if r[2] == "SKIP")
    print(f"\n{len(rows) - failed - n_skip} passed, {failed} failed, {n_skip} skipped, {len(rows)} cases")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
