import json
import unittest

from src.analyze.classify import classify
from src.analyze.summarize import _llm_refine, analyze, extractive_summary, headings_of, sentences
from src.convert import ConvertedDocument, convert
from src.llm.client import LLMResponse, LLMUnavailable
from tests.helpers import sample


class Stub:
    model = "stub"

    def __init__(self, reply=None, error=None):
        self.reply, self.error = reply, error

    def complete(self, prompt, system=None):
        if self.error:
            raise self.error
        return LLMResponse(self.reply, 100, 50, 0.1, "stub")


def doc(md, kind="pdf", **kw):
    return ConvertedDocument("x." + kind, kind, md, **kw)


class ClassifyTests(unittest.TestCase):
    def test_samples(self):
        for name, expected in [("paper_latex.pdf", "Research paper"), ("paper_two_column.pdf", "Research paper"),
                               ("report.pdf", "Business report / proposal"), ("budget.xlsx", "Financial")]:
            d = convert(sample(name), name)
            g = classify(d.markdown, d.kind, [h for _, h in headings_of(d.markdown)])
            self.assertIn(expected, g.doc_type, name)

    def test_invoice_resume_contract_and_unknown(self):
        self.assertEqual(classify("INVOICE\nBill to: Acme\nSubtotal 10\nTotal due: 11\nUnit price Qty", "pdf").doc_type,
                         "Invoice or receipt")
        self.assertEqual(classify("Curriculum Vitae\nWork experience\nEducation\nSkills\nlinkedin.com/in/x", "pdf").doc_type,
                         "Resume / CV")
        self.assertEqual(classify("This Agreement is made between the parties hereinafter. Whereas the parties; "
                                  "governing law; indemnify; liability", "docx").doc_type, "Contract / legal agreement")
        g = classify("My shopping list: eggs, milk.", "pdf")
        self.assertEqual((g.doc_type, g.confidence), ("General document", "low"))

    def test_presentation_is_decided_by_format(self):
        self.assertTrue(classify("## Slide 1: Hi", "pptx").doc_type.startswith("Presentation"))


class SummaryTests(unittest.TestCase):
    def test_paper_summary_comes_from_the_abstract(self):
        d = convert(sample("paper_latex.pdf"), "p.pdf")
        a = analyze(d, use_llm=False)
        self.assertEqual(a.method, "extractive")
        self.assertEqual(a.doc_type, "Research paper")
        self.assertIn("case 1,", a.summary)                    # abstract sentences
        self.assertNotIn("case 100,", a.summary)
        self.assertTrue(a.title.startswith("Call Graph Pruning"))
        self.assertIn("1 Introduction", [o.strip() for o in a.outline])

    def test_spreadsheet_and_deck_summaries_are_structural(self):
        x = analyze(convert(sample("budget.xlsx"), "b.xlsx"), use_llm=False)
        self.assertIn("'Budget': 3 data rows, columns Item, Q1, Q2, Total", x.summary)
        p = analyze(convert(sample("deck.pptx"), "d.pptx"), use_llm=False)
        self.assertTrue(p.summary.startswith("5 slides: Product Launch Plan"))

    def test_extractive_summary_is_deterministic_and_in_order(self):
        text = " ".join(f"Sentence number {i} talks about alpha beta gamma topic {i % 3} in some detail." for i in range(20))
        s1, s2 = extractive_summary(text, 3), extractive_summary(text, 3)
        self.assertEqual(s1, s2)
        self.assertEqual(len(sentences(s1)), 3)
        nums = [int(n) for n in __import__("re").findall(r"number (\d+)", s1)]
        self.assertEqual(nums, sorted(nums))

    def test_abbreviations_do_not_split_sentences(self):
        self.assertEqual(len(sentences("Smith et al. showed this works. It is fast, e.g. on small files.")), 2)

    def test_tiny_document(self):
        a = analyze(doc("Hi.\n"), use_llm=False)
        self.assertIn("Not enough", a.summary)


class LlmSummaryTests(unittest.TestCase):
    MD = "# Report\n\nRevenue grew to 4500 dollars in 2025. The team shipped three releases. " * 3

    def setUp(self):
        self.d = doc(self.MD)
        self.a = analyze(self.d, use_llm=False)

    def reply(self, **kw):
        base = {"doc_type": "Sales report", "summary": "The report says revenue grew to 4500 dollars and the team "
                "shipped three releases during the year.", "key_points": ["Revenue 4500 dollars"]}
        return json.dumps({**base, **kw})

    def test_good_reply_replaces_summary(self):
        _llm_refine(self.a, self.d, Stub(self.reply()))
        self.assertEqual(self.a.method, "llm")
        self.assertEqual(self.a.doc_type, "Sales report")
        self.assertEqual(self.a.key_points, ["Revenue 4500 dollars"])

    def test_invented_number_is_rejected(self):
        before = self.a.summary
        _llm_refine(self.a, self.d, Stub(self.reply(summary="Revenue grew to 9999 dollars and the team shipped releases.")))
        self.assertEqual((self.a.method, self.a.summary), ("extractive", before))
        self.assertTrue(any("9999" in w for w in self.a.warnings))

    def test_fenced_json_and_bad_json(self):
        _llm_refine(self.a, self.d, Stub("```json\n" + self.reply() + "\n```"))
        self.assertEqual(self.a.method, "llm")
        a2 = analyze(self.d, use_llm=False)
        _llm_refine(a2, self.d, Stub("I cannot do that"))
        self.assertEqual(a2.method, "extractive")
        self.assertTrue(any("not valid JSON" in w for w in a2.warnings))

    def test_unavailable_llm_falls_back_with_a_warning(self):
        import src.analyze.summarize as sm
        orig = sm.make_client
        sm.make_client = lambda: Stub(error=LLMUnavailable("no server"))
        try:
            a = analyze(self.d, use_llm=True)
        finally:
            sm.make_client = orig
        self.assertEqual(a.method, "extractive")
        self.assertTrue(any("unavailable" in w for w in a.warnings))


if __name__ == "__main__":
    unittest.main()
