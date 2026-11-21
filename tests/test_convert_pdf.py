import io
import shutil
import unittest

from src.convert import ConversionError, convert
from tests.helpers import rotated_pdf, sample


def md(name, **kw):
    return convert(sample(name), name, **kw)


class PdfTests(unittest.TestCase):
    def test_headings_lists_table_code(self):
        d = md("report.pdf")
        t = d.markdown
        self.assertIn("# Quarterly Operations Report", t)
        self.assertIn("## 3. Regional results", t)
        self.assertIn("### 2.1 Next steps", t)
        self.assertIn("- Throughput rose in every region", t)
        self.assertIn("1. Approve the revised budget", t)
        self.assertIn("| Region | Orders | Revenue |", t)
        self.assertIn("| North | 1200 | 45000 |", t)
        self.assertIn("def total(orders):", t)
        self.assertEqual(d.kind, "pdf")
        self.assertEqual(d.pages, 1)
        self.assertEqual(d.tables, 1)

    def test_two_column_reads_left_column_before_right(self):
        t = md("paper_two_column.pdf").markdown
        order = [t.index(h) for h in ("## Abstract", "## 1. Introduction", "## 2. Background", "## 3. Approach",
                                      "## 4. Evaluation")]
        self.assertEqual(order, sorted(order))
        # the sentence numbering in the sample is continuous, so any column interleaving would break it
        import re
        cases = [int(n) for n in re.findall(r"\(case (\d+),", t)]
        self.assertEqual(cases, sorted(cases))

    def test_latex_paper_ligatures_columns_bullets_and_unruled_table(self):
        d = md("paper_latex.pdf")
        t = d.markdown
        self.assertNotIn("(cid:", t)                       # fi / ff / fl / ffi restored
        self.assertIn("workflow", t)
        self.assertIn("efficient scheduler", t)
        self.assertIn("- Fewer false alarms for reviewers", t)       # bullets from an unmapped glyph
        self.assertIn("| Project | Nodes | Pruned | Time (s) |", t)   # booktabs table without vertical rules
        self.assertIn("| gamma | 20100 | 15300 | 58 |", t)
        self.assertLess(t.index("## Abstract"), t.index("## 1 Introduction"))
        import re
        cases = [int(n) for n in re.findall(r"\(case (\d+),", t)]
        self.assertEqual(cases, sorted(cases))             # full-width abstract above two columns on page 1
        self.assertEqual(d.warnings, [w for w in d.warnings if "(cid" not in w])

    def test_sentence_continues_across_columns(self):
        t = md("paper_latex.pdf").markdown
        self.assertIn("even for different code styles (case 116,", t)    # not split by a paragraph break

    def test_rotated_upside_down_and_diagonal_text(self):
        d = convert(rotated_pdf(), "rot.pdf")
        t = d.markdown
        self.assertIn("arXiv:2406.01234v1 [cs.SE] 19 Jun 2024", t)
        self.assertIn("Upside down sentence here", t)
        self.assertNotIn("DRAFT", t)                       # watermark skipped...
        self.assertNotIn("FT", t.replace("DRAFT", ""))     # ...without leaving fragments behind
        self.assertTrue(any("diagonal" in w for w in d.warnings))
        self.assertLess(t.index("Second normal line"), t.index("arXiv:2406"))   # stamp goes after the body

    @unittest.skipUnless(shutil.which("tesseract"), "tesseract not installed")
    def test_scanned_pdf_uses_ocr(self):
        d = md("scanned.pdf")
        self.assertEqual(d.ocr_pages, 1)
        self.assertGreater(d.words, 150)
        self.assertTrue(any("OCR" in w for w in d.warnings))

    def test_page_markers_and_repeated_footer_removal(self):
        from pypdf import PdfReader, PdfWriter
        w = PdfWriter()
        for _ in range(4):
            for p in PdfReader(io.BytesIO(sample("report.pdf"))).pages:
                w.add_page(p)
        b = io.BytesIO(); w.write(b)
        kept = convert(b.getvalue(), "x.pdf", strip_repeated=False).markdown
        cut = convert(b.getvalue(), "x.pdf")
        self.assertEqual(kept.count("Acme Corp - Confidential"), 4)
        self.assertEqual(cut.markdown.count("Acme Corp - Confidential"), 0)
        self.assertGreaterEqual(cut.headers_footers_removed, 4)
        self.assertIn("<!-- page 3 -->", convert(b.getvalue(), "x.pdf", page_markers=True).markdown)

    def test_password_protected_pdf_has_clear_message(self):
        from pypdf import PdfReader, PdfWriter
        w = PdfWriter()
        for p in PdfReader(io.BytesIO(sample("report.pdf"))).pages:
            w.add_page(p)
        w.encrypt("secret")
        b = io.BytesIO(); w.write(b)
        with self.assertRaises(ConversionError) as cm:
            convert(b.getvalue(), "locked.pdf")
        self.assertIn("password", str(cm.exception))

    def test_corrupt_and_empty_pdf(self):
        with self.assertRaises(ConversionError):
            convert(b"%PDF-1.4 definitely not a pdf", "bad.pdf")
        with self.assertRaises(ConversionError):
            convert(b"", "empty.pdf")


if __name__ == "__main__":
    unittest.main()
