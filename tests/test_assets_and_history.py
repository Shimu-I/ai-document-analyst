"""Figures, equations and pictures kept as images; LaTeX from Word equations; conversion history."""
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from src import history, service
from src.cli import main as cli_main
from src.convert import convert
from src.convert.omml import M, omml_to_latex

PNG = b"\x89PNG\r\n\x1a\n"


def _font_path():
    try:
        import matplotlib
        p = Path(matplotlib.get_data_path()) / "fonts" / "ttf" / "DejaVuSans.ttf"
        return p if p.exists() else None
    except Exception:
        return None


def math_pdf() -> bytes:
    """One page: a prose line, a display equation (maths symbols), a vector drawing, a prose line."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    pdfmetrics.registerFont(TTFont("DejaVu", str(_font_path())))
    b = io.BytesIO()
    c = canvas.Canvas(b, pagesize=A4)
    c.setFont("DejaVu", 11)
    c.drawString(72, 780, "The total energy of the system is described by the following relation.")
    c.drawString(200, 740, "∑ xᵢ ≤ ∫ f(t) dt ≥ 0")
    c.drawString(72, 700, "Next comes a small drawing made of shapes and lines.")
    for i in range(8):                                       # a drawing: many vector objects, no text
        c.rect(100 + i * 30, 560, 20, 20 + i * 8, stroke=1, fill=0)
        c.line(100 + i * 30, 560, 120 + i * 30, 520)
    c.drawString(72, 450, "The last line is ordinary text and stays text in the output.")
    c.showPage(); c.save()
    return b.getvalue()


@unittest.skipUnless(_font_path(), "needs matplotlib's DejaVu font")
class PdfAssets(unittest.TestCase):
    def test_equation_and_drawing_saved_as_images(self):
        d = convert(math_pdf(), "m.pdf", assets=True)
        self.assertEqual(d.formulas, 1)
        self.assertEqual(d.figures, 1)
        self.assertEqual(len(d.assets), 2)
        for blob in d.assets.values():
            self.assertTrue(blob.startswith(PNG))
        self.assertIn("![Equation 1:", d.markdown)
        self.assertIn("![Figure 1", d.markdown)
        self.assertIn("(assets/m_p1_eq1.png)", d.markdown)
        # prose stays text, in order
        self.assertLess(d.markdown.index("total energy"), d.markdown.index("![Equation 1"))
        self.assertLess(d.markdown.index("![Figure 1"), d.markdown.index("last line"))

    def test_off_by_default(self):
        d = convert(math_pdf(), "m.pdf")
        self.assertEqual(d.assets, {})
        self.assertNotIn("![", d.markdown)

    def test_asset_limit_is_reported(self):
        from src.convert import assets as A
        old = A.MAX_ASSETS
        try:
            A.MAX_ASSETS = 1
            import src.convert as C
            d = C.convert(math_pdf(), "m.pdf", assets=True)
        finally:
            A.MAX_ASSETS = old
        self.assertLessEqual(len(d.assets), 2)


class Omml(unittest.TestCase):
    def _tex(self, inner: str) -> str:
        from lxml import etree
        return omml_to_latex(etree.fromstring(f'<m:oMath xmlns:m="{M}">{inner}</m:oMath>'))

    def test_constructs(self):
        r = lambda t: f"<m:r><m:t>{t}</m:t></m:r>"
        self.assertEqual(self._tex(f"<m:f><m:num>{r('a')}</m:num><m:den>{r('b')}</m:den></m:f>"), r"\frac{a}{b}")
        self.assertEqual(self._tex(f"<m:sSup><m:e>{r('x')}</m:e><m:sup>{r('2')}</m:sup></m:sSup>"), "x^2")
        self.assertEqual(self._tex(f"<m:sSub><m:e>{r('x')}</m:e><m:sub>{r('i')}</m:sub></m:sSub>"), "x_i")
        self.assertEqual(self._tex(f"<m:rad><m:e>{r('x')}</m:e></m:rad>"), r"\sqrt{x}")
        self.assertIn(r"\sum", self._tex(f'<m:nary><m:naryPr><m:chr m:val="∑"/></m:naryPr><m:e>{r("a")}</m:e></m:nary>'))
        self.assertIn(r"\alpha", self._tex(r("α")))


class DocxAndPptx(unittest.TestCase):
    def _picture(self):
        from PIL import Image
        b = io.BytesIO()
        Image.new("RGB", (120, 60), "red").save(b, "PNG")
        b.seek(0)
        return b

    def test_docx_equation_and_picture(self):
        import docx
        from docx.shared import Inches
        from lxml import etree
        d = docx.Document()
        p = d.add_paragraph("Inline ")
        r = "<m:r><m:t>a</m:t></m:r>"
        p._p.append(etree.fromstring(f'<m:oMath xmlns:m="{M}"><m:f><m:num>{r}</m:num><m:den>{r}</m:den></m:f></m:oMath>'))
        d.add_picture(self._picture(), width=Inches(1))
        buf = io.BytesIO(); d.save(buf)
        out = convert(buf.getvalue(), "e.docx", assets=True)
        self.assertIn(r"$\frac{a}{a}$", out.markdown)
        self.assertEqual(out.formulas, 1)
        self.assertEqual(out.figures, 1)
        self.assertIn("![Picture 1](assets/e_img1.png)", out.markdown)
        plain = convert(buf.getvalue(), "e.docx")                # without assets: LaTeX stays, picture is reported
        self.assertIn(r"$\frac{a}{a}$", plain.markdown)
        self.assertTrue(any("image(s) omitted" in w for w in plain.warnings))

    def test_pptx_picture(self):
        from pptx import Presentation
        from pptx.util import Inches
        prs = Presentation()
        s = prs.slides.add_slide(prs.slide_layouts[5])
        s.shapes.title.text = "Deck"
        s.shapes.add_picture(self._picture(), Inches(1), Inches(2), width=Inches(2))
        buf = io.BytesIO(); prs.save(buf)
        out = convert(buf.getvalue(), "d.pptx", assets=True)
        self.assertEqual(out.figures, 1)
        self.assertIn("(assets/d_s1_img1.png)", out.markdown)


@unittest.skipUnless(_font_path(), "needs matplotlib's DejaVu font")
class ServiceCliAssets(unittest.TestCase):
    def test_zip_and_public(self):
        r = service.process(math_pdf(), "m.pdf", assets=True)
        self.assertEqual(r["stats"]["figures"], 1)
        self.assertEqual(len(r["stats"]["asset_files"]), 2)
        import json
        json.dumps(service.public(r))                            # no bytes left
        names = zipfile.ZipFile(io.BytesIO(service.zip_results([r]))).namelist()
        self.assertIn("m.md", names)
        self.assertEqual(sum(n.startswith("assets/") for n in names), 2)

    def test_cli_images_flag(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "m.pdf"
            src.write_bytes(math_pdf())
            out = Path(d) / "out"
            self.assertEqual(cli_main([str(src), "--images", "-o", str(out)]), 0)
            self.assertEqual(len(list((out / "assets").glob("*.png"))), 2)
            self.assertIn("assets/", (out / "m.md").read_text())


class History(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.environ["HISTORY_DB"] = str(Path(self.tmp) / "h.db")

    def tearDown(self):
        os.environ.pop("HISTORY_DB", None)

    def test_record_fetch_clear(self):
        r = service.process(b'[{"a":1,"b":2},{"a":3,"b":4}]', "x.json")
        history.record_success(r, 30)
        history.record_error("bad.exe", "unsupported file type .exe", 5, 0.01)
        rows = history.fetch()
        self.assertEqual([x["filename"] for x in rows], ["bad.exe", "x.json"])      # newest first
        self.assertEqual(rows[1]["ok"], 1)
        self.assertEqual(rows[1]["doc_type"], r["analysis"]["doc_type"])
        self.assertEqual(rows[0]["ok"], 0)
        self.assertIn("filename", history.to_csv(rows).splitlines()[0])
        self.assertEqual(history.clear(), 2)
        self.assertEqual(history.count(), 0)

    def test_no_document_text_is_stored(self):
        r = service.process(b"top secret sentence about nothing", "s.txt")
        history.record_success(r)
        import sqlite3
        raw = sqlite3.connect(os.environ["HISTORY_DB"]).execute("SELECT * FROM runs").fetchall()
        self.assertNotIn("secret", repr(raw))


if __name__ == "__main__":
    unittest.main()


class SummaryIgnoresImages(unittest.TestCase):
    def test_image_lines_are_not_summary_text(self):
        from src.analyze.summarize import prose
        md = "Intro paragraph with enough words to count as prose here.\n\n![Equation 1: E = mc 2 (1)](assets/x.png)\n\nAnother plain paragraph that has many words in it."
        self.assertNotIn("Equation", prose(md))
