import os
import unittest
from unittest import mock

from src.llm import client as c
from src.llm.cost import cost_usd


class FakeResp:
    def __init__(self, status=200, body=None, text=""):
        self.status_code, self._body, self.text = status, body, text

    def json(self):
        return self._body


OPENAI_OK = {"choices": [{"message": {"content": "hello"}}], "usage": {"prompt_tokens": 7, "completion_tokens": 3}}


class OpenAICompatibleTests(unittest.TestCase):
    def test_success_hits_chat_completions_with_bearer_key(self):
        with mock.patch("requests.post", return_value=FakeResp(body=OPENAI_OK)) as post:
            r = c.OpenAICompatibleClient(model="m", base_url="http://x:1/v1/", api_key="k").complete("hi")
        self.assertEqual((r.text, r.input_tokens, r.output_tokens), ("hello", 7, 3))
        url = post.call_args.args[0]
        self.assertEqual(url, "http://x:1/v1/chat/completions")
        self.assertEqual(post.call_args.kwargs["headers"]["authorization"], "Bearer k")
        self.assertEqual(post.call_args.kwargs["json"]["temperature"], 0)

    def test_missing_usage_and_errors(self):
        with mock.patch("requests.post", return_value=FakeResp(body={"choices": [{"message": {"content": "x"}}]})):
            self.assertEqual(c.OpenAICompatibleClient(model="m").complete("q").input_tokens, 0)
        with mock.patch("requests.post", return_value=FakeResp(status=500, text="boom")):
            with self.assertRaises(c.LLMUnavailable):
                c.OpenAICompatibleClient(model="m").complete("q")
        with mock.patch("requests.post", return_value=FakeResp(body={"nope": 1})):
            with self.assertRaises(c.LLMUnavailable):
                c.OpenAICompatibleClient(model="m").complete("q")
        with self.assertRaises(c.LLMUnavailable):
            c.OpenAICompatibleClient(model=None).complete("q")


class SelectionTests(unittest.TestCase):
    def env(self, **kw):
        keys = ("ANTHROPIC_API_KEY", "LLM_MODEL", "LLM_PROVIDER")
        return mock.patch.dict(os.environ, {k: kw.get(k, "") for k in keys})

    def test_nothing_configured(self):
        with self.env():
            self.assertFalse(c.llm_configured())
            with self.assertRaises(c.LLMUnavailable):
                c.make_client()

    def test_llm_model_selects_openai_compatible(self):
        with self.env(LLM_MODEL="llama"):
            self.assertTrue(c.llm_configured())
            self.assertIsInstance(c.make_client(), c.OpenAICompatibleClient)

    def test_anthropic_key_and_override(self):
        with self.env(ANTHROPIC_API_KEY="k"):
            self.assertIsInstance(c.make_client(), c.AnthropicClient)
        with self.env(ANTHROPIC_API_KEY="k", LLM_MODEL="m", LLM_PROVIDER="anthropic"):
            self.assertIsInstance(c.make_client(), c.AnthropicClient)


class CostTests(unittest.TestCase):
    def test_unlisted_models_are_free(self):
        self.assertEqual(cost_usd("llama3", 1000, 1000), 0.0)
        self.assertGreater(cost_usd("claude-sonnet-5-5", 1_000_000, 0), 0)


if __name__ == "__main__":
    unittest.main()
