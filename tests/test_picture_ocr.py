"""Text inside pictures: image-only slides, Word screenshots and PDF figures (need the tesseract program)."""
import io
import shutil
import unittest

from src.convert import convert

HAVE_TESSERACT = shutil.which("tesseract") is not None
LINES = ["Metaphors are good idea", "People should know the business needs", "and how their work fits in the project"]


def _font(size):
    from PIL import ImageFont
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def slide_png() -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1200, 700), "white")
    d = ImageDraw.Draw(img)
    for i, t in enumerate(LINES):
        d.text((60, 80 + i * 110), "• " + t if i == 0 else t, fill="black", font=_font(48))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def icon_png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (40, 40), "red").save(buf, "PNG")
    return buf.getvalue()


def picture_deck() -> bytes:
    from pptx import Presentation
    from pptx.util import Inches
    prs = Presentation()
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.shapes.add_picture(io.BytesIO(slide_png()), Inches(0.5), Inches(0.5), width=Inches(9))
    s.shapes.add_picture(io.BytesIO(icon_png()), Inches(0.1), Inches(0.1), width=Inches(0.3))
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()


@unittest.skipUnless(HAVE_TESSERACT, "tesseract is not installed")
class PictureOcrTests(unittest.TestCase):
    def test_pptx_off_by_default_omits_pictures(self):
        d = convert(picture_deck(), "deck.pptx")
        self.assertNotIn("Metaphors", d.markdown)
        self.assertEqual(d.images_omitted, 2)

    def test_pptx_picture_text_is_read(self):
        d = convert(picture_deck(), "deck.pptx", ocr_pictures=True)
        self.assertIn("Metaphors are good idea", d.markdown)
        self.assertIn("business needs", d.markdown)
        self.assertIn("> ", d.markdown)                              # quoted, apart from real text
        self.assertEqual(d.images_omitted, 1)                        # the 40 px icon has no text and is not read
        self.assertTrue(any("OCR" in w for w in d.warnings))

    def test_pptx_text_and_image_link_together(self):
        d = convert(picture_deck(), "deck.pptx", ocr_pictures=True, assets=True)
        self.assertIn("![Picture 1", d.markdown)
        self.assertIn("Metaphors are good idea", d.markdown)

    def test_docx_screenshot_text(self):
        import docx
        doc = docx.Document()
        doc.add_paragraph("Intro line before the picture.")
        doc.add_picture(io.BytesIO(slide_png()), width=docx.shared.Inches(5.5))
        buf = io.BytesIO()
        doc.save(buf)
        d = convert(buf.getvalue(), "r.docx", ocr_pictures=True)
        self.assertIn("Intro line", d.markdown)
        self.assertIn("business needs", d.markdown)

    def test_pdf_with_raster_slide(self):
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.utils import ImageReader
        from reportlab.pdfgen import canvas
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        c.drawString(40, 560, "Slide deck exported as pictures, page one title line here.")
        c.drawImage(ImageReader(io.BytesIO(slide_png())), 40, 120, width=700, height=408)
        c.save()
        d = convert(buf.getvalue(), "slides.pdf", ocr_pictures=True, assets=True)
        self.assertIn("business needs", d.markdown)

    def test_non_picture_formats_ignore_flag(self):
        d = convert(b"a,b\n1,2\n", "t.csv", ocr_pictures=True)
        self.assertIn("| a | b |", d.markdown)


if __name__ == "__main__":
    unittest.main()


class ProjectStatusTests(unittest.TestCase):
    def test_classify(self):
        from src.project_status import classify
        self.assertEqual(classify(5)[1], "ok")
        self.assertEqual(classify(200)[1], "warn")
        self.assertEqual(classify(900)[1], "bad")
        self.assertEqual(classify(None)[1], "none")

    def test_active_repo(self):
        from datetime import datetime, timezone
        from src.project_status import repo_status
        now = datetime(2026, 11, 22, tzinfo=timezone.utc)
        s = repo_status("a/b", fetch=lambda r: {"pushed_at": "2026-11-10T08:00:00Z"}, now=now)
        self.assertEqual((s["level"], s["days"]), ("ok", 11))
        self.assertIn("Active", s["label"])

    def test_archived_and_offline_and_unset(self):
        from src.project_status import repo_status

        def boom(r):
            raise OSError("offline")
        self.assertEqual(repo_status("a/b", fetch=lambda r: {"pushed_at": "2026-01-01T00:00:00Z", "archived": True})["level"], "bad")
        self.assertEqual(repo_status("a/b", fetch=boom)["level"], "none")
        self.assertEqual(repo_status("Shimu-I/x", fetch=boom)["label"], "Open source")
        self.assertEqual(repo_status("", fetch=boom)["level"], "none")


class FigureLayoutTests(unittest.TestCase):
    def test_bullets_indent_and_heading_kept(self):
        from src.convert.pdf import _rows
        from src.convert.pdf_special import layout_text

        def w(t, x, y, s=28):
            return {"text": t, "x0": x, "x1": x + len(t) * s * .5, "top": y, "bottom": y + s, "size": s}
        words = [w("•", 70, 10), w("Development", 95, 10), w("Methodologies", 300, 10),
                 w("•", 70, 70), w("Agile", 95, 70), w("•", 110, 130), w("How", 135, 130), w("Title", 70, 190, 40)]
        out = layout_text(words, _rows)
        self.assertIn("- Development Methodologies", out)
        self.assertIn("  - How", out)                    # nested item keeps its indentation
        self.assertIn("## Title", out)


@unittest.skipUnless(HAVE_TESSERACT, "tesseract is not installed")
class OcrListLayoutTests(unittest.TestCase):
    def test_bullets_and_nesting_from_a_picture(self):
        from PIL import Image, ImageDraw
        img = Image.new("RGB", (1300, 700), "white")
        d = ImageDraw.Draw(img)
        for text, x, y in [("• Development Methodologies", 60, 60), ("• Agile Development", 60, 170),
                           ("• Extreme Programming", 60, 280), ("• How It Works for Me", 150, 390),
                           ("• Develop Your Own Methodology", 60, 500)]:
            d.text((x, y), text, fill="black", font=_font(52))
        buf = io.BytesIO()
        img.save(buf, "PNG")
        md = convert(buf.getvalue(), "slide.png").markdown
        lines = md.split("\n")
        self.assertTrue(any(l.startswith("- ") and "Agile" in l for l in lines), md)
        self.assertTrue(any(l.startswith("  - ") and "How It Works" in l for l in lines), md)   # nested one level


class PreviewBlocksTests(unittest.TestCase):
    def test_picture_and_its_text_stay_together(self):
        from src.preview import split_blocks
        md = ("Intro\n\n![Figure 1: x](assets/a.png)\n\n> - Agile\n>   - Nested\n\nMiddle\n\n"
              "![Equation 1](assets/b.png)\n\nEnd")
        blocks = split_blocks(md, {"a.png": b"", "b.png": b""})
        self.assertEqual([b[0] for b in blocks], ["md", "img", "md", "img", "md"])
        self.assertEqual(blocks[1][3], "- Agile\n  - Nested")       # quote marks removed, nesting kept
        self.assertEqual(blocks[3][3], "")                          # no text: the picture stays visible

    def test_unknown_image_is_left_as_text(self):
        from src.preview import split_blocks
        self.assertEqual(split_blocks("![a](assets/zz.png)", {})[0][0], "md")


class PrecheckTests(unittest.TestCase):
    ACC = [".pdf", ".docx", ".pptx", ".png"]

    def test_levels(self):
        from src.precheck import advice, check_upload
        self.assertEqual(check_upload("a.pdf", 0, 50, self.ACC)[0], "error")
        self.assertEqual(check_upload("a.pdf", 60 * 1048576, 50, self.ACC)[0], "error")
        self.assertEqual(check_upload("a.exe", 10, 50, self.ACC)[0], "error")
        self.assertEqual(check_upload("a.pdf", 20 * 1048576, 50, self.ACC)[0], "warning")
        self.assertEqual(check_upload("a.pptx", 9 * 1048576, 50, self.ACC, picture_ocr=True)[0], "warning")
        self.assertIsNone(check_upload("a.pdf", 1000, 50, self.ACC))
        self.assertIn("password", advice(422, "this PDF is password-protected").lower())
        self.assertIn("MAX_UPLOAD_MB", advice(413, "file larger than 50 MB"))


class ModelStatusTests(unittest.TestCase):
    def test_states(self):
        from src.model_status import model_status
        self.assertEqual(model_status({})["level"], "none")
        self.assertEqual(model_status({"ANTHROPIC_API_KEY": "x"})["level"], "ok")
        up = lambda url: {"data": [{"id": "llama3.2:3b"}]}
        s = model_status({"LLM_MODEL": "llama3.2"}, get=up)
        self.assertEqual(s["level"], "ok")
        self.assertEqual(s["label"], "Open-source model · Active")
        self.assertIn("llama3.2", s["detail"])
        self.assertEqual(model_status({"LLM_MODEL": "mistral"}, get=up)["level"], "warn")      # server up, model missing

        def down(url):
            raise OSError("refused")
        s = model_status({"LLM_MODEL": "llama3.2"}, get=down)
        self.assertEqual(s["level"], "warn")
        self.assertIn("Not running", s["label"])


class DocViewTests(unittest.TestCase):
    def test_list_and_titles(self):
        from src import docview
        docs = docview.list_docs()
        nums = [d["number"] for d in docs if d["number"]]
        self.assertEqual(nums, [f"{i:02d}" for i in range(1, 16)])           # 01 to 15, in order
        self.assertTrue(all(d["title"] and not d["title"][0].isdigit() for d in docs))
        self.assertTrue(any(d["group"] == "Deep dive" for d in docs))

    def test_toc_ignores_code_and_slugs(self):
        from src import docview
        md = "# T\n\n## First part\n```\n## not a heading\n```\n### Sub `x`\n"
        self.assertEqual(docview.toc(md), [(2, "First part", "first-part"), (3, "Sub x", "sub-x")])

    def test_links_blocks_and_diagrams(self):
        from pathlib import Path
        from src import docview
        self.assertEqual(docview.clean_links("see [08 User Guide](08_user_guide.md) and [web](https://x.y)"),
                         "see **08 User Guide** and [web](https://x.y)")
        d = [d for d in docview.list_docs() if d["number"] == "04"][0]
        blocks = docview.split_blocks(d["path"].read_text(encoding="utf-8"), d["path"])
        kinds = [b[0] for b in blocks]
        self.assertIn("diagram", kinds)
        self.assertNotIn("](0", "".join(b[1] for b in blocks if b[0] == "md"))      # no dead links to other documents
        self.assertTrue(all(b[1] is not None for b in blocks if b[0] == "diagram"))  # pictures were generated

    def test_search(self):
        from src import docview
        hits = docview.search("tesseract install", docview.list_docs())
        self.assertTrue(hits)
        self.assertEqual(docview.search("", docview.list_docs()), [])
        self.assertEqual(docview.search("zzqqxx", docview.list_docs()), [])


def _have_lang(code: str) -> bool:
    from src.convert import image as im
    im._installed_langs.cache_clear()
    return code in im._installed_langs()


@unittest.skipUnless(HAVE_TESSERACT, "tesseract is not installed")
class SlideReadingTests(unittest.TestCase):
    def test_image_slide_text_layout_and_boxes(self):
        from src.slides import read_slides, to_markdown
        s = read_slides(slide_png(), "s.png")
        self.assertEqual(len(s), 1)
        self.assertEqual(s[0].png[:4], b"\x89PNG")                     # the original is kept for viewing
        self.assertIn("business needs", to_markdown(s))
        self.assertTrue(s[0].items)
        for it in s[0].items:                                          # every line is linked to a place on the slide
            x0, y0, x1, y1 = it.bbox
            self.assertTrue(0 <= x0 < x1 <= 1.01 and 0 <= y0 < y1 <= 1.01, it)

    def test_pdf_with_text_layer_uses_it(self):
        from reportlab.lib.pagesizes import landscape, A4
        from reportlab.pdfgen import canvas
        from src.slides import read_slides
        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=landscape(A4))
        c.setFont("Helvetica-Bold", 28)
        for i, t in enumerate(["Development Methodologies", "Agile Development", "Extreme Programming"]):
            c.drawString(80, 450 - i * 70, "- " + t)
        c.showPage()
        c.drawString(80, 450, "Second page has a plain sentence of ordinary body text here.")
        c.save()
        s = read_slides(buf.getvalue(), "d.pdf")
        self.assertEqual([x.number for x in s], [1, 2])
        self.assertEqual(s[0].source, "text layer")
        self.assertIn("Agile Development", s[0].markdown)
        self.assertEqual(s[0].png[:4], b"\x89PNG")

    @unittest.skipUnless(shutil.which("soffice"), "LibreOffice is not installed")
    def test_pptx_picture_slide_is_rendered_and_read(self):
        from src.slides import read_slides
        s = read_slides(picture_deck(), "deck.pptx")
        self.assertEqual(len(s), 1)
        self.assertIn("business needs", s[0].markdown)

    def test_unsupported_and_empty(self):
        from src.convert.base import ConversionError
        from src.slides import read_slides
        with self.assertRaises(ConversionError):
            read_slides(b"", "a.png")
        with self.assertRaises(ConversionError):
            read_slides(b"x", "a.xyz")

    @unittest.skipUnless(shutil.which("tesseract") and _have_lang("ben"), "Bengali language pack is not installed")
    def test_bengali_and_english_together(self):
        from PIL import Image, ImageDraw, ImageFont
        from src.slides import read_slides
        font = None
        for path in ("/usr/share/fonts/truetype/freefont/FreeSans.ttf", "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf"):
            try:
                font = ImageFont.truetype(path, 56)
                break
            except OSError:
                continue
        if font is None:
            self.skipTest("no Bengali font")
        img = Image.new("RGB", (1400, 420), "white")
        d = ImageDraw.Draw(img)
        for t, y in [("• বাংলা ভাষা আমাদের গর্ব", 40), ("• Agile Development", 170), ("• আমি বাংলায় গান গাই", 300)]:
            d.text((60, y), t, fill="black", font=font)
        buf = io.BytesIO()
        img.save(buf, "PNG")
        md = read_slides(buf.getvalue(), "bn.png")[0].markdown
        self.assertIn("Agile Development", md)
        self.assertIn("বাংলা", md)
        self.assertEqual(md.count("\n- ") + md.startswith("- "), 3)


class DeckModelTests(unittest.TestCase):
    def _deck(self):
        from src.desktop_model import Deck
        from src.slides import Item, Slide
        items = [Item("## Title", (0.1, 0.05, 0.9, 0.15), "heading"), Item("- One", (0.1, 0.3, 0.5, 0.4), "bullet"),
                 Item("  - Nested", (0.2, 0.5, 0.6, 0.6), "bullet", 1)]
        s1 = Slide(1, b"", (1000, 500), items, "## Title\n\n- One\n  - Nested")
        s2 = Slide(2, b"", (1000, 500), [], "")
        return Deck([s1, s2], "talk.pptx")

    def test_links_both_ways(self):
        d = self._deck()
        self.assertEqual([(k.line, k.item.kind) for k in d.links(0)], [(0, "heading"), (2, "bullet"), (3, "bullet")])
        self.assertEqual(d.item_for_line(0, 3).level, 1)
        self.assertIsNone(d.item_for_line(0, 1))                      # blank line
        self.assertEqual(d.line_for_point(0, 0.3, 0.35), 2)           # inside the "One" box
        self.assertEqual(d.line_for_point(0, 0.3, 0.62), 3)           # just below "Nested": nearest line
        self.assertIsNone(d.line_for_point(0, 0.95, 0.95))            # far from any text

    def test_edit_keeps_links_when_structure_same_and_falls_back_when_not(self):
        d = self._deck()
        d.set_text(0, "## Title\n\n- Uno\n  - Nested")
        self.assertTrue(d.edited(0))
        self.assertEqual(len(d.links(0)), 3)
        d.set_text(0, "## Title\n\n- Uno\n  - Nested\n- extra line")
        self.assertEqual(len(d.links(0)), 3)                          # falls back to the original text for linking
        d.set_text(0, d.slides[0].markdown)
        self.assertFalse(d.edited(0))

    def test_export_and_numbers(self):
        d = self._deck()
        d.set_text(0, "## Title\n\n- Uno")
        md = d.markdown()
        self.assertIn("## Slide 1", md)
        self.assertIn("- Uno", md)
        self.assertIn("_(no text)_", md)                              # empty slide is still listed
        self.assertGreater(d.tokens(), 0)
        self.assertEqual(d.suggested_name(), "talk.md")

    def test_geometry(self):
        from src.desktop_model import fit, to_canvas
        scale, ox, oy = fit((1000, 500), (800, 800))
        self.assertAlmostEqual(scale, 0.8)
        self.assertEqual((ox, oy), (0, 200))                          # centred vertically
        x0, y0, x1, y1 = to_canvas((0.5, 0.5, 1.0, 1.0), (1000, 500), scale, ox, oy)
        self.assertTrue(400 - 5 < x0 < 400 and 400 - 5 + 200 - 5 < y0 + 200 and x1 > 800 - 1 and y1 > 600 - 1)
