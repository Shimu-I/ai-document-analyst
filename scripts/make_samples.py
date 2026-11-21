"""Generate sample documents + the content each one is KNOWN to contain.

Outputs (data/samples/):
  report.docx / report.pdf         headings, bold/italic, bullets, numbered list, table, code, footer
  paper_two_column.docx / .pdf     one-column title+abstract, then 2-column body over several pages
  budget.xlsx                      two sheets, formulas with cached results, two tables on one sheet
  deck.pptx                        title, bullets with levels, table, chart, notes, picture
  scanned.pdf                      image-only PDF (needs OCR)
  expected/<name>.json             ground truth: words, ordered anchors, headings, tables, list items

LibreOffice (soffice) is used to render DOCX -> PDF and to recalculate the workbook, so the PDFs
and the XLSX are realistic files produced by a real office suite, not by our own code.
Deterministic (fixed seed). Usage: python scripts/make_samples.py
"""
from __future__ import annotations

import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "samples"
EXP = OUT / "expected"

SUBJECTS = ["The analysis", "Our method", "The pipeline", "The baseline", "This study", "The proposed system",
            "The dataset", "Static analysis", "The evaluation", "The prototype"]
VERBS = ["reduces", "improves", "reveals", "supports", "limits", "explains", "tracks", "measures"]
OBJECTS = ["call graph precision", "reachability results", "memory usage", "build times", "false positives",
           "dependency coverage", "review effort", "scan latency"]
TAILS = ["across all benchmark projects", "when the entry points are known", "in the majority of cases",
         "while keeping the report readable", "under realistic workloads", "without manual configuration"]


def sentence(rng: random.Random, n: int) -> str:
    return (f"{rng.choice(SUBJECTS)} {rng.choice(VERBS)} {rng.choice(OBJECTS)} {rng.choice(TAILS)}"
            f" (case {n}, value {rng.randint(10, 99)}.{rng.randint(0, 9)}).")


def paragraph(rng: random.Random, start: int, n_sent: int = 5) -> str:
    return " ".join(sentence(rng, start + i) for i in range(n_sent))


def soffice(*args: str) -> None:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe:
        sys.exit("LibreOffice (soffice) is required to build the PDF samples")
    with tempfile.TemporaryDirectory() as home:
        subprocess.run([exe, "--headless", *args], check=True, capture_output=True, timeout=240,
                       env={"HOME": home, "PATH": "/usr/bin:/bin:/usr/local/bin"})


def add_page_field(paragraph_obj) -> None:
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    run = paragraph_obj.add_run()
    for kind, text in (("begin", None), (None, "PAGE"), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar")
            el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText")
            el.set(qn("xml:space"), "preserve")
            el.text = text
        run._r.append(el)


def words_of(*texts: str) -> list[str]:
    import re
    return re.findall(r"[a-z0-9]+", " ".join(texts).lower())


# ------------------------------------------------------------------------------------ report
def make_report() -> dict:
    import docx
    from docx.shared import Pt

    rng = random.Random(1)
    d = docx.Document()
    exp = {"anchors": [], "headings": [], "tables": [], "list_items": [], "texts": []}

    def para(text, bold=False, italic=False, style=None):
        p = d.add_paragraph(style=style)
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        exp["anchors"].append(text)
        exp["texts"].append(text)
        return p

    def head(text, lvl):
        d.add_heading(text, lvl)
        exp["headings"].append(text)
        exp["anchors"].append(text)
        exp["texts"].append(text)

    head("Quarterly Operations Report", 0)
    para("Prepared for the operations board. All figures are illustrative.", italic=True)
    head("1. Summary", 1)
    para(paragraph(rng, 1))
    head("2. Highlights", 1)
    for t in ["Throughput rose in every region", "Support backlog fell by a third", "Two vendors were replaced"]:
        d.add_paragraph(t, style="List Bullet")
        exp["list_items"].append(t)
        exp["anchors"].append(t)
        exp["texts"].append(t)
    head("2.1 Next steps", 2)
    for t in ["Approve the revised budget", "Hire two analysts", "Review vendor contracts"]:
        d.add_paragraph(t, style="List Number")
        exp["list_items"].append(t)
        exp["anchors"].append(t)
        exp["texts"].append(t)
    head("3. Regional results", 1)
    rows = [["Region", "Orders", "Revenue"], ["North", "1200", "45000"], ["South", "950", "38250"],
            ["East", "1430", "51200"]]
    t = d.add_table(rows=len(rows), cols=3)
    t.style = "Table Grid"
    for i, r in enumerate(rows):
        for j, c in enumerate(r):
            t.cell(i, j).text = c
    exp["tables"].append(rows)
    exp["anchors"] += [c for r in rows for c in r]
    exp["texts"] += [c for r in rows for c in r]
    head("4. Notes", 1)
    para(paragraph(rng, 10))
    code = d.add_paragraph()
    run = code.add_run("def total(orders):\n    return sum(orders)")
    run.font.name = "Courier New"
    run.font.size = Pt(10)
    exp["texts"].append("def total(orders): return sum(orders)")
    para("Contact the operations desk for the underlying data.", bold=True)
    sec = d.sections[0]
    fp = sec.footer.paragraphs[0]
    fp.text = "Acme Corp - Confidential - page "
    add_page_field(fp)
    path = OUT / "report.docx"
    d.save(path)
    soffice("--convert-to", "pdf", "--outdir", str(OUT), str(path))
    return exp


# ------------------------------------------------------------------------------------ paper
def make_paper() -> dict:
    import docx
    from docx.enum.section import WD_SECTION
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt

    rng = random.Random(2)
    d = docx.Document()
    d.styles["Normal"].font.size = Pt(10)
    exp = {"anchors": [], "headings": [], "tables": [], "list_items": [], "texts": []}

    def head(text, lvl):
        d.add_heading(text, lvl)
        exp["headings"].append(text)
        exp["anchors"].append(text)
        exp["texts"].append(text)

    def para(text):
        d.add_paragraph(text)
        exp["anchors"].append(text)
        exp["texts"].append(text)

    head("Reachability Matters: A Static-Analysis Case Study", 0)
    para("Jane Researcher and John Analyst, Example University")
    head("Abstract", 1)
    para(paragraph(rng, 1, 4))
    sec = d.add_section(WD_SECTION.CONTINUOUS)
    cols = OxmlElement("w:cols")
    cols.set(qn("w:num"), "2")
    cols.set(qn("w:space"), "425")
    sec._sectPr.append(cols)
    n = 20
    for h in ["1. Introduction", "2. Background", "3. Approach", "4. Evaluation", "5. Discussion", "6. Conclusion"]:
        head(h, 1)
        for _ in range(3):
            para(paragraph(rng, n, 6))
            n += 6
    for s in d.sections:
        s.header.paragraphs[0].text = "Reachability Matters - Technical Report"
        fp = s.footer.paragraphs[0]
        fp.text = "Page "
        add_page_field(fp)
    path = OUT / "paper_two_column.docx"
    d.save(path)
    soffice("--convert-to", "pdf", "--outdir", str(OUT), str(path))
    return exp


# ------------------------------------------------------------------------------------ xlsx
def make_xlsx() -> dict:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Budget"
    rows = [["Item", "Q1", "Q2", "Total"], ["Hardware", 1200, 1350, "=B2+C2"], ["Software", 800, 760, "=B3+C3"],
            ["Travel", 300.5, 410.25, "=B4+C4"]]
    for r in rows:
        ws.append(r)
    ws.append([])
    ws.append(["Notes", "Figures in USD"])
    ws2 = wb.create_sheet("Staff")
    staff = [["Name", "Role", "Start"], ["Ada", "Engineer", "2024-02-01"], ["Grace", "Analyst", "2023-11-15"]]
    for r in staff:
        ws2.append(r)
    tmp = OUT / "_budget_raw.xlsx"
    wb.save(tmp)
    soffice("--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", str(OUT / "_recalc"), str(tmp))
    shutil.move(str(OUT / "_recalc" / "_budget_raw.xlsx"), OUT / "budget.xlsx")
    shutil.rmtree(OUT / "_recalc")
    tmp.unlink()
    # Ground truth uses the VALUES a spreadsheet user sees (formulas shown as their results).
    budget = [["Item", "Q1", "Q2", "Total"], ["Hardware", "1200", "1350", "2550"],
              ["Software", "800", "760", "1560"], ["Travel", "300.5", "410.25", "710.75"]]
    notes = [["Notes", "Figures in USD"]]
    flat = ["Budget"] + [c for r in budget for c in r] + [c for r in notes for c in r] + \
           ["Staff"] + [c for r in staff for c in r]
    return {"anchors": flat, "headings": ["Budget", "Staff"], "tables": [budget, notes, staff],
            "list_items": [], "texts": flat}


# ------------------------------------------------------------------------------------ pptx
def make_pptx() -> dict:
    from pptx import Presentation
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.util import Inches
    from PIL import Image

    prs = Presentation()
    exp = {"anchors": [], "headings": [], "tables": [], "list_items": [], "texts": []}
    s = prs.slides.add_slide(prs.slide_layouts[0])
    s.shapes.title.text = "Product Launch Plan"
    s.placeholders[1].text = "Marketing team, autumn"
    exp["anchors"] += ["Product Launch Plan", "Marketing team, autumn"]
    exp["texts"] += ["Product Launch Plan", "Marketing team, autumn"]
    s = prs.slides.add_slide(prs.slide_layouts[1])
    s.shapes.title.text = "Goals"
    tf = s.placeholders[1].text_frame
    tf.text = "Reach 10,000 users"
    p = tf.add_paragraph()
    p.text = "Through referrals"
    p.level = 1
    p = tf.add_paragraph()
    p.text = "Keep churn under 3%"
    s.notes_slide.notes_text_frame.text = "Mention the pilot results here."
    items = ["Reach 10,000 users", "Through referrals", "Keep churn under 3%"]
    exp["list_items"] += items
    exp["anchors"] += ["Goals"] + items + ["Mention the pilot results here."]
    exp["texts"] += ["Goals"] + items + ["Mention the pilot results here."]
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Budget"
    rows = [["Channel", "Cost"], ["Email", "2000"], ["Events", "7500"]]
    tbl = s.shapes.add_table(3, 2, Inches(1), Inches(2), Inches(6), Inches(1.5)).table
    for i, r in enumerate(rows):
        for j, c in enumerate(r):
            tbl.cell(i, j).text = c
    exp["tables"].append(rows)
    exp["anchors"] += ["Budget"] + [c for r in rows for c in r]
    exp["texts"] += ["Budget"] + [c for r in rows for c in r]
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Signups by month"
    cd = CategoryChartData()
    cd.categories = ["Jan", "Feb", "Mar"]
    cd.add_series("Signups", (120, 340, 560))
    s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(2), Inches(6), Inches(4), cd)
    chart = ["Signups by month", "Signups", "Jan", "120", "Feb", "340", "Mar", "560"]  # row-major, as a table
    exp["anchors"] += chart
    exp["texts"] += chart
    img = OUT / "_pic.png"
    Image.new("RGB", (80, 40), (200, 30, 30)).save(img)
    s = prs.slides.add_slide(prs.slide_layouts[5])
    s.shapes.title.text = "Mockup"
    s.shapes.add_picture(str(img), Inches(1), Inches(2))
    img.unlink()
    exp["anchors"].append("Mockup")
    exp["texts"].append("Mockup")
    exp["headings"] = []  # slide headings are "## Slide N: title"; checked through texts
    prs.save(OUT / "deck.pptx")
    return exp


# ------------------------------------------------------------------------------------ scanned
def make_scanned(report_exp: dict) -> dict:
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(str(OUT / "report.pdf"))
    imgs = [pdf[i].render(scale=2.5).to_pil().convert("L") for i in range(len(pdf))]
    imgs[0].save(OUT / "scanned.pdf", save_all=True, append_images=imgs[1:], resolution=180)
    keep = ["texts", "anchors"]
    return {k: (report_exp[k] if k in keep else []) for k in report_exp}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    EXP.mkdir(exist_ok=True)
    rep = make_report()
    exps = {"report": rep, "paper_two_column": make_paper(), "budget": make_xlsx(), "deck": make_pptx(),
            "scanned": make_scanned(rep)}
    for name, e in exps.items():
        e["words"] = words_of(*e["texts"])
        (EXP / f"{name}.json").write_text(json.dumps(e, indent=1) + "\n")
    print("wrote", sorted(p.name for p in OUT.iterdir() if p.is_file()))


if __name__ == "__main__":
    main()
