import io
import unittest

from src.convert import SUPPORTED, ConversionError, convert
from tests.helpers import sample


class DocxTests(unittest.TestCase):
    def test_structure(self):
        d = convert(sample("report.docx"), "report.docx")
        t = d.markdown
        self.assertIn("Quarterly Operations Report", t)
        self.assertIn("- Throughput rose in every region", t)
        self.assertIn("| North | 1200 | 45000 |", t)
        self.assertEqual(d.kind, "docx")
        self.assertEqual(d.tables, 1)
        self.assertTrue(any("headers, footers" in w for w in d.warnings))

    def test_bold_italic_and_hyperlink(self):
        import docx
        doc = docx.Document()
        p = doc.add_paragraph("plain ")
        p.add_run("bold").bold = True
        p.add_run(" and ")
        p.add_run("italic").italic = True
        b = io.BytesIO(); doc.save(b)
        t = convert(b.getvalue(), "f.docx").markdown
        self.assertIn("plain **bold** and *italic*", t)

    def test_corrupt(self):
        with self.assertRaises(ConversionError):
            convert(b"not a zip", "x.docx")


class XlsxTests(unittest.TestCase):
    def test_sheets_and_tables(self):
        d = convert(sample("budget.xlsx"), "budget.xlsx")
        self.assertEqual(d.sheets, ["Budget", "Staff"])
        self.assertIn("## Budget", d.markdown)
        self.assertIn("| Hardware | 1200 | 1350 | 2550 |", d.markdown)     # formula results, not formulas
        self.assertIn("| Ada | Engineer | 2024-02-01 |", d.markdown)

    def test_edge_cases(self):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Calc"
        ws.append(["a", "b", "sum"])
        ws.append([1, 2, "=A2+B2"])                   # never calculated: no stored result
        ws["A4"] = "x | y\nz"
        hidden = wb.create_sheet("Secret"); hidden.sheet_state = "hidden"; hidden["A1"] = "hidden data"
        big = wb.create_sheet("Big")
        for i in range(5100):
            big.append([i, "r"])
        b = io.BytesIO(); wb.save(b)
        d = convert(b.getvalue(), "t.xlsx")
        self.assertIn("=A2+B2", d.markdown)
        self.assertIn("x \\| y<br>z", d.markdown)     # pipe escaped, newline kept inside the cell
        self.assertNotIn("hidden data", d.markdown)
        joined = " ".join(d.warnings)
        self.assertIn("no stored result", joined)
        self.assertIn("truncated to 5000 rows", joined)
        self.assertIn("hidden sheet", joined)


class PptxTests(unittest.TestCase):
    def test_slides_notes_table_chart(self):
        d = convert(sample("deck.pptx"), "deck.pptx")
        t = d.markdown
        self.assertEqual(d.pages, 5)
        self.assertIn("## Slide 1: Product Launch Plan", t)
        self.assertIn("- Reach 10,000 users", t)
        self.assertIn("  - Through referrals", t)                  # nested bullet keeps its level
        self.assertIn("> **Notes:** Mention the pilot results here.", t)
        self.assertIn("| Email | 2000 |", t)
        self.assertIn("| Feb | 340 |", t)                          # chart data is exported as a table
        self.assertEqual(d.images_omitted, 1)


class TextTests(unittest.TestCase):
    def test_csv_txt_json(self):
        self.assertIn("| a | b |", convert(b"a;b\n1;2\n", "d.csv").markdown)
        self.assertEqual(convert("café au lait".encode("cp1252"), "n.txt").markdown.strip(), "café au lait")
        self.assertEqual("k: 1\n", convert(b'{"k":1}', "d.json").markdown)
        self.assertIn('{"k":1}', convert(b'{ "k" : 1 }', "d.json", json_mode="minified").markdown)
        self.assertEqual(convert("a,b\n\u00e9,\u00fc\n".encode("utf-16"), "u.csv").markdown.count("\u00e9"), 1)
        self.assertIn("\u00e9", convert("a;b\n\u00e9;1\n".encode("utf-8-sig"), "bom.csv").markdown)

    def test_unsupported_and_empty(self):
        with self.assertRaises(ConversionError) as cm:
            convert(b"MZ", "program.exe")
        self.assertTrue(str(cm.exception).startswith("unsupported"))
        with self.assertRaises(ConversionError):
            convert(b"", "a.docx")
        self.assertIn(".pdf", SUPPORTED)

    def test_blank_image_warns(self):
        import shutil
        if not shutil.which("tesseract"):
            self.skipTest("tesseract not installed")
        from PIL import Image
        b = io.BytesIO(); Image.new("RGB", (200, 80), "white").save(b, "PNG")
        d = convert(b.getvalue(), "blank.png")
        self.assertEqual(d.markdown, "")
        self.assertTrue(any("no text" in w for w in d.warnings))


if __name__ == "__main__":
    unittest.main()
