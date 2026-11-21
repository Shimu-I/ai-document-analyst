"""Images, data files, HTML, Google shortcuts, compact mode, splitting and token estimates."""
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from src import service
from src.cli import main as cli_main
from src.convert import ConversionError, convert, split_by_tokens
from src.convert.base import estimate_tokens
from src.convert.compact import compact_markdown

HAVE_TESSERACT = shutil.which("tesseract") is not None


def records(n=30):
    return [{"id": i, "name": f"User {i}", "email": f"u{i}@example.com", "active": i % 2 == 0,
             "address": {"city": "Dhaka", "zip": str(1000 + i)}, "tags": ["a", "b"],
             "note": None if i % 3 else ""} for i in range(1, n + 1)]


class JsonTests(unittest.TestCase):
    def test_list_of_records_becomes_one_table(self):
        d = convert(json.dumps(records()).encode(), "u.json")
        self.assertEqual(d.tables, 1)
        self.assertIn("| id | name | email | active | address.city | address.zip | tags | note |", d.markdown)
        self.assertEqual(d.markdown.count("User "), 30)          # every record kept
        self.assertEqual(d.markdown.count("address"), 2)         # the key appears once, not 30 times

    def test_readable_uses_fewer_tokens_than_pretty_and_minified_json(self):
        data = {"count": 30, "users": records()}
        pretty, mini = json.dumps(data, indent=2), json.dumps(data, separators=(",", ":"))
        d = convert(pretty.encode(), "u.json")
        self.assertLess(d.est_tokens, estimate_tokens(mini))
        self.assertLess(estimate_tokens(mini), estimate_tokens(pretty))
        self.assertEqual(d.source_tokens, estimate_tokens(pretty))

    def test_null_and_empty_string_stay_different(self):
        md = convert(json.dumps([{"a": None, "b": ""}, {"a": 1, "b": 2}]).encode(), "x.json").markdown
        self.assertIn("| null |  |", md)

    def test_scalar_dict_and_nested(self):
        md = convert(b'{"server":{"host":"h","ports":[80,443]},"on":true,"n":null}', "c.json").markdown
        self.assertIn("## server", md)
        self.assertIn("host: h", md)
        self.assertIn("ports: 80, 443", md)
        self.assertIn("on: true", md)
        self.assertIn("n: null", md)

    def test_compact_drops_empty_values_and_says_so(self):
        d = convert(json.dumps(records()).encode(), "u.json", compact=True)
        self.assertNotIn("| note |", d.markdown)
        self.assertTrue(any("empty values" in w for w in d.warnings))
        self.assertNotIn("| --- |", d.markdown)                    # alignment row removed in compact mode

    def test_minified_mode_is_exact_json(self):
        d = convert(b'{ "k" : [1, 2], "s": "x y" }', "d.json", json_mode="minified")
        self.assertIn('{"k":[1,2],"s":"x y"}', d.markdown)

    def test_jsonl(self):
        d = convert(b'{"a":1}\n{"a":2}\n', "e.jsonl")
        self.assertEqual(d.tables, 1)
        self.assertIn("| 1 |", d.markdown)

    def test_invalid_json_is_a_clear_error(self):
        with self.assertRaises(ConversionError):
            convert(b"{not json", "bad.json")

    def test_multiline_string_keeps_structure(self):
        md = convert(json.dumps({"text": "line one\nline two"}).encode(), "t.json").markdown
        self.assertIn("text: |", md)
        self.assertIn("  line two", md)


class OtherFormatTests(unittest.TestCase):
    def test_yaml_and_toml(self):
        y = convert(b"server:\n  host: h\n  port: 80\nitems: [a, b]\n", "c.yaml").markdown
        self.assertIn("host: h", y)
        self.assertIn("items: a, b", y)
        t = convert(b'[tool]\nname = "demo"\n', "p.toml").markdown
        self.assertIn("name: demo", t)

    def test_xml_attributes_and_repeated_elements(self):
        xml = b'<lib><book id="1"><t>A</t></book><book id="2"><t>B</t></book></lib>'
        md = convert(xml, "l.xml").markdown
        self.assertIn("@id", md)
        self.assertIn("@id | t", md)          # nested tables are plain rows: indented tables are not valid Markdown
        self.assertIn("1 | A", md)
        self.assertIn("2 | B", md)

    def test_xml_with_entities_is_refused(self):
        with self.assertRaises(ConversionError):
            convert(b'<?xml version="1.0"?><!DOCTYPE a [<!ENTITY x "y">]><a>&x;</a>', "bomb.xml")

    def test_notebook_keeps_code_text_output_and_drops_image_data(self):
        nb = {"cells": [{"cell_type": "markdown", "source": ["# Title"]},
                        {"cell_type": "code", "source": ["print(1)"],
                         "outputs": [{"output_type": "stream", "text": ["1\n"]},
                                     {"output_type": "display_data", "data": {"image/png": "AAAA" * 5000, "text/plain": ["<Fig>"]}}]}],
              "metadata": {"language_info": {"name": "python"}}}
        d = convert(json.dumps(nb).encode(), "n.ipynb")
        self.assertIn("```python\nprint(1)\n```", d.markdown)
        self.assertIn("# Title", d.markdown)
        self.assertNotIn("AAAA", d.markdown)
        self.assertEqual(d.images_omitted, 1)
        self.assertLess(d.est_tokens * 20, d.source_tokens)

    def test_html_drops_boilerplate_keeps_content(self):
        html = (b"<html><head><title>T</title><script>var secret=1</script><style>.a{}</style></head><body>"
                b"<nav><a href='/'>Home</a></nav><main><h1>Head</h1><p>Hello <b>bold</b> <a href='http://x.test/very/long/url'>link</a></p>"
                b"<ul><li>one<ul><li>nested</li></ul></li></ul><table><tr><th>A</th></tr><tr><td>1</td></tr></table></main>"
                b"<footer>Copyright</footer></body></html>")
        d = convert(html, "p.html")
        for gone in ("secret", "Home", "Copyright", "x.test"):
            self.assertNotIn(gone, d.markdown)
        for kept in ("# Head", "Hello **bold** link", "- one", "  - nested", "| A |"):
            self.assertIn(kept, d.markdown)
        self.assertLess(d.est_tokens, d.source_tokens)
        self.assertTrue(any("link address" in w for w in d.warnings))

    def test_code_file_is_fenced_with_language(self):
        d = convert(b"def f():\n    return 1\n", "a.py")
        self.assertTrue(d.markdown.startswith("```python"))

    def test_code_containing_backticks_uses_a_longer_fence(self):
        d = convert(b"x = '''```'''\n", "a.py")
        self.assertTrue(d.markdown.startswith("````python"))

    def test_google_shortcut_files_explain_what_to_do(self):
        for ext, hint in ((".gsheet", ".xlsx"), (".gdoc", ".docx"), (".gslides", ".pptx")):
            with self.assertRaises(ConversionError) as cm:
                convert(b'{"url": "https://docs.google.com/x"}', "f" + ext)
            self.assertIn("shortcut", str(cm.exception))
            self.assertIn(hint, str(cm.exception))


class CompactTests(unittest.TestCase):
    TABLE = "| a   | b   |\n| --- | --- |\n| 1   | 2   |\n| 3   | 4   |\n"

    def test_tables_lose_padding_and_alignment_row_but_keep_every_cell(self):
        out, saved = compact_markdown("Intro\n\n" + self.TABLE)
        self.assertEqual(out, "Intro\n\na | b\n1 | 2\n3 | 4\n")
        self.assertGreater(saved, 0)

    def test_code_blocks_are_untouched(self):
        src = "```\n|  a  |  b  |\n| --- | --- |\n<!-- keep -->   x\n```\n"
        self.assertEqual(compact_markdown(src)[0], src)

    def test_comments_and_blank_lines_go(self):
        out, _ = compact_markdown("a\n\n\n\n<!-- page 2 -->\n\nb\n")
        self.assertEqual(out, "a\n\nb\n")

    def test_escaped_pipe_survives(self):
        out, _ = compact_markdown("| x | y |\n| --- | --- |\n| a \\| b | c |\n")
        self.assertIn("a \\| b | c", out)

    def test_idempotent(self):
        once, _ = compact_markdown("# T\n\n" + self.TABLE)
        self.assertEqual(compact_markdown(once)[0], once)


class SplitTests(unittest.TestCase):
    DOC = "\n\n".join(f"## Section {i}\n\n" + " ".join(f"word{i}_{j}" for j in range(300)) for i in range(1, 7))

    def test_small_documents_are_not_split(self):
        self.assertEqual(split_by_tokens("hello\n", 1000), ["hello\n"])

    def test_parts_respect_the_budget_and_lose_nothing(self):
        parts = split_by_tokens(self.DOC, 800)
        self.assertGreater(len(parts), 2)
        for p in parts:
            self.assertLessEqual(estimate_tokens(p), 800 * 1.25)
        joined = " ".join(parts)
        for i in range(1, 7):
            self.assertIn(f"word{i}_0", joined)
            self.assertIn(f"word{i}_299", joined)
        self.assertTrue(parts[0].startswith(f"(part 1 of {len(parts)})"))

    def test_breaks_happen_before_headings(self):
        parts = split_by_tokens(self.DOC, 800)
        for p in parts[1:]:
            body = p.split("\n\n", 1)[1]
            self.assertTrue(body.startswith("## Section") or body.startswith("word"), body[:40])

    def test_table_header_is_repeated_on_every_part(self):
        rows = "\n".join(f"| {i} | name{i} |" for i in range(400))
        parts = split_by_tokens("| id | name |\n| --- | --- |\n" + rows + "\n", 300)
        self.assertGreater(len(parts), 2)
        for p in parts:
            self.assertIn("| id | name |", p)

    def test_budget_too_small(self):
        with self.assertRaises(ValueError):
            split_by_tokens("x", 50)


class TokenEstimateTests(unittest.TestCase):
    def test_empty_and_english(self):
        self.assertEqual(estimate_tokens("   "), 0)
        self.assertEqual(estimate_tokens("a" * 400), 100)

    def test_other_scripts_cost_more_per_character(self):
        self.assertGreater(estimate_tokens("আমি বাংলায় কথা বলি" * 10), estimate_tokens("I speak English " * 10))


class ServiceCliTests(unittest.TestCase):
    def test_split_outputs_and_zip(self):
        text = "\n\n".join(f"## S{i}\n\n" + "lorem ipsum " * 400 for i in range(5))
        r = service.process(text.encode(), "big.txt", max_tokens=1000)
        files = service.output_files(r)
        self.assertGreater(len(files), 2)
        self.assertEqual(files[0][0], "big_part1.md")
        z = zipfile.ZipFile(io.BytesIO(service.zip_results([r])))
        self.assertEqual(sorted(z.namelist()), sorted(n for n, _ in files))

    def test_max_tokens_validated(self):
        with self.assertRaises(service.ServiceError) as cm:
            service.process(b"x", "a.txt", max_tokens=10)
        self.assertEqual(cm.exception.status, 422)

    def test_stats_report_raw_file_comparison_only_for_text_formats(self):
        r = service.process(json.dumps({"users": records()}, indent=2).encode(), "u.json", compact=True)
        self.assertLess(r["stats"]["estimated_tokens"], r["stats"]["source_tokens"])
        r2 = service.process(b"a,b\n1,2\n", "t.csv")
        self.assertIsNotNone(r2["stats"]["source_tokens"])

    def test_google_file_is_a_422_with_instructions(self):
        with self.assertRaises(service.ServiceError) as cm:
            service.process(b"{}", "x.gsheet")
        self.assertEqual(cm.exception.status, 422)
        self.assertIn("Download", cm.exception.message)

    def test_cli_options_and_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "u.json").write_text(json.dumps({"users": records()}, indent=2))
            (d / "s.gsheet").write_text("{}")
            out = d / "out"
            self.assertEqual(cli_main([str(d / "u.json"), "--compact", "-o", str(out)]), 0)
            self.assertTrue((out / "u.md").exists())
            self.assertEqual(cli_main([str(d / "s.gsheet"), "-o", str(out)]), 1)
            (d / "big.txt").write_text("\n\n".join("## S%d\n\n%s" % (i, "lorem ipsum " * 400) for i in range(4)))
            self.assertEqual(cli_main([str(d / "big.txt"), "--max-tokens", "1000", "-o", str(out)]), 0)
            self.assertTrue((out / "big_part1.md").exists())


# ----------------------------------------------------------------------------- images (need the tesseract program)
def _font(size):
    from PIL import ImageFont
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                 "/Library/Fonts/Arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


NOTES = ["Meeting notes - Project Atlas", "Date: 12 March 2026", "1. Budget approved: $12,400",
         "2. Launch moved to April 9", "3. Owner of risks: Grace"]


def make_image(fmt="PNG", bg=(255, 255, 255), fg=(0, 0, 0), mode="RGB", noise=False):
    from PIL import Image, ImageDraw
    img = Image.new("RGBA" if mode == "RGBA" else "RGB", (700, 280), bg if mode != "RGBA" else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = 10
    for line in NOTES:
        d.text((10, y), line, fill=fg if mode != "RGBA" else (0, 0, 0, 255), font=_font(28))
        y += 46
    if noise:
        import random
        from PIL import ImageFilter
        img = img.filter(ImageFilter.GaussianBlur(2.2))
        px, r = img.load(), random.Random(1)
        for _ in range(int(700 * 280 * 0.12)):
            px[r.randrange(700), r.randrange(280)] = (r.randint(60, 220),) * 3
    buf = io.BytesIO()
    img.save(buf, fmt)
    return buf.getvalue()


@unittest.skipUnless(HAVE_TESSERACT, "tesseract is not installed")
class ImageTests(unittest.TestCase):
    def check_notes(self, md):
        for needle in ("Meeting notes", "12 March 2026", "$12,400", "April 9", "Grace"):
            self.assertIn(needle, md)

    def test_png_text_lines_and_numbered_list_are_kept(self):
        d = convert(make_image(), "n.png")
        self.check_notes(d.markdown)
        self.assertIn("1. Budget approved", d.markdown)
        self.assertIn("2. Launch moved", d.markdown)
        self.assertIn("Meeting notes - Project Atlas\n\nDate: 12 March 2026", d.markdown)   # separate paragraphs, not one line
        self.assertEqual(d.kind, "image")
        self.assertGreater(d.ocr_confidence, 85)
        self.assertEqual(d.image_tokens_est, round(700 * 280 / 750))

    def test_jpeg_and_webp(self):
        for fmt, name in (("JPEG", "n.jpg"), ("WEBP", "n.webp")):
            self.check_notes(convert(make_image(fmt), name).markdown)

    def test_dark_mode_screenshot_is_inverted(self):
        self.check_notes(convert(make_image(bg=(25, 25, 30), fg=(235, 235, 235)), "dark.png").markdown)

    def test_transparent_png_is_not_read_as_a_black_square(self):
        self.check_notes(convert(make_image(mode="RGBA"), "t.png").markdown)

    def test_poor_image_produces_a_confidence_warning(self):
        d = convert(make_image(noise=True), "bad.png")
        self.assertTrue(d.ocr_confidence is None or d.ocr_confidence < 95)
        self.assertTrue(any("OCR" in w for w in d.warnings))

    def test_blank_image_says_it_may_not_be_text(self):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (300, 200), "white").save(buf, "PNG")
        d = convert(buf.getvalue(), "blank.png")
        self.assertEqual(d.markdown.strip(), "")
        self.assertTrue(any("no text found" in w for w in d.warnings))

    def test_missing_language_pack_is_explained(self):
        with self.assertRaises(ConversionError) as cm:
            convert(make_image(), "n.png", ocr_lang="zzz")
        self.assertIn("not installed", str(cm.exception))
        self.assertIn("tesseract-ocr-zzz", str(cm.exception))

    def test_corrupt_image(self):
        with self.assertRaises(ConversionError):
            convert(b"not an image", "x.png")

    def test_analysis_labels_an_image_and_shows_its_text(self):
        r = service.process(make_image(), "n.png")
        self.assertEqual(r["analysis"]["doc_type"], "Image with text (OCR)")
        self.assertIn("Meeting notes", r["markdown"])


if __name__ == "__main__":
    unittest.main()
