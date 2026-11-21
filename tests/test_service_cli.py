import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from src import cli, service
from tests.helpers import SAMPLES, sample


class ServiceTests(unittest.TestCase):
    def test_process_result_shape(self):
        r = service.process(sample("report.pdf"), "report.pdf", use_llm=False)
        json.dumps(r)
        self.assertEqual(r["markdown_filename"], "report.md")
        self.assertIn("# Quarterly Operations Report", r["markdown"])
        self.assertEqual(r["stats"]["kind"], "pdf")
        self.assertGreater(r["stats"]["estimated_tokens"], 100)
        self.assertEqual(r["analysis"]["method"], "extractive")

    def test_error_statuses(self):
        for args, status in [((b"", "a.pdf"), 400), ((b"MZ", "a.exe"), 415), ((b"x", "a.docx"), 422),
                             ((b"%PDF-1.4 junk", "a.pdf"), 422)]:
            with self.assertRaises(service.ServiceError) as cm:
                service.process(*args)
            self.assertEqual(cm.exception.status, status, args)
        with mock.patch.object(service, "MAX_UPLOAD_BYTES", 10):
            with self.assertRaises(service.ServiceError) as cm:
                service.process(sample("report.pdf"), "r.pdf")
        self.assertEqual(cm.exception.status, 413)

    def test_md_filename_is_safe(self):
        self.assertEqual(service.md_filename("My Report (final).pdf"), "My Report (final).md")
        self.assertEqual(service.md_filename("../../etc/passwd"), "passwd.md")
        self.assertEqual(service.md_filename(""), "document.md")
        self.assertEqual(service.md_filename("a/b\\c:d*e?.pdf"), "b_c_d_e.md")

    def test_with_summary_block(self):
        r = service.process(sample("report.pdf"), "report.pdf", use_llm=False)
        out = service.with_summary(r["markdown"], r["analysis"], "report.pdf")
        self.assertTrue(out.startswith("> **Source:** report.pdf"))
        self.assertIn("> **Summary:**", out)
        self.assertTrue(out.endswith(r["markdown"]))

    def test_zip_deduplicates_names(self):
        a = service.process(sample("report.pdf"), "report.pdf", use_llm=False)
        b = service.process(sample("report.docx"), "report.docx", use_llm=False)
        z = zipfile.ZipFile(io.BytesIO(service.zip_results([a, b])))
        self.assertEqual(sorted(z.namelist()), ["report.md", "report_2.md"])

    def test_health(self):
        h = service.health()
        self.assertEqual(h["status"], "ok")
        self.assertIn(".pptx", h["supported_types"])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as out:
            code = cli.main(list(args))
        return code, out.getvalue()

    def test_same_name_different_type_does_not_overwrite(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as dst:
            for n in ("report.pdf", "report.docx"):
                (Path(src) / n).write_bytes(sample(n))
            (Path(src) / "notes.txt").write_text("plain text is skipped when scanning a folder")
            (Path(src) / "data.json").write_text("{}")
            code, _ = self.run_cli(src, "-o", dst)
            self.assertEqual(code, 0)
            self.assertEqual(sorted(p.name for p in Path(dst).iterdir()), ["report.md", "report_pdf.md"])

    def test_summary_flag_and_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "paper.pdf"
            f.write_bytes(sample("paper_latex.pdf"))
            code, _ = self.run_cli(str(f), "--summary")
            self.assertEqual(code, 0)
            md = (Path(d) / "paper.md").read_text()
            self.assertIn("> **What this is:** Research paper", md)
            code, out = self.run_cli(str(f), "--stdout")
            self.assertIn("## Abstract", out)

    def test_bad_file_gives_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "broken.pdf"
            f.write_bytes(b"nope")
            with mock.patch("sys.stderr", new_callable=io.StringIO):
                code, _ = self.run_cli(str(f))
            self.assertEqual(code, 1)

    def test_never_overwrites_a_markdown_source(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "readme.md"
            f.write_text("# Hello\n\nSome text here.")
            self.run_cli(str(f))
            self.assertEqual(f.read_text(), "# Hello\n\nSome text here.")
            self.assertTrue((Path(d) / "readme_md.md").exists())


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            from fastapi.testclient import TestClient
            from api.main import app
        except ImportError:
            raise unittest.SkipTest("fastapi / httpx not installed")
        cls.client = TestClient(app)

    def test_endpoints(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        files = {"file": ("report.pdf", sample("report.pdf"), "application/pdf")}
        r = self.client.post("/convert", files=files, data={"use_llm": "false"})
        self.assertEqual(r.status_code, 200)
        self.assertIn("markdown", r.json())
        r = self.client.post("/analyze", files=files, data={"use_llm": "false"})
        self.assertNotIn("markdown", r.json())
        r = self.client.post("/convert/download", files=files, data={"include_summary": "true", "use_llm": "false"})
        self.assertIn("attachment", r.headers["content-disposition"])
        self.assertTrue(r.text.startswith("> **Source:**"))
        bad = self.client.post("/convert", files={"file": ("a.exe", b"MZ")})
        self.assertEqual(bad.status_code, 415)


if __name__ == "__main__":
    unittest.main()
