"""LLM clients (plain HTTPS via ``requests``, no SDK dependency).

Two providers behind one interface (``complete(prompt) -> LLMResponse``):

* ``AnthropicClient``        - Anthropic Messages API (paid; needs ANTHROPIC_API_KEY).
* ``OpenAICompatibleClient`` - any server that speaks the OpenAI ``/chat/completions``
  protocol. This includes **Ollama** (free, runs on the local computer) and the free
  tiers of several hosted providers. Configure with LLM_BASE_URL / LLM_MODEL /
  LLM_API_KEY.

``make_client()`` picks one from the environment (see its docstring).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass

import requests

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-sonnet-5-5"
DEFAULT_OPENAI_BASE_URL = "http://localhost:11434/v1"  # Ollama's OpenAI-compatible endpoint


class LLMUnavailable(RuntimeError):
    """Raised when no LLM is configured or it cannot be reached."""


@dataclass
class LLMResponse:
    text: str
    input_tokens: int
    output_tokens: int
    seconds: float
    model: str


class AnthropicClient:
    def __init__(self, model: str | None = None, api_key: str | None = None,
                 max_tokens: int = 1024, timeout: float = 60.0):
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_MODEL)
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        self.max_tokens = max_tokens
        self.timeout = timeout

    def complete(self, prompt: str, system: str | None = None) -> LLMResponse:
        if not self.api_key:
            raise LLMUnavailable("ANTHROPIC_API_KEY is not set")
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            body["system"] = system
        t0 = time.perf_counter()
        try:
            r = requests.post(
                API_URL, json=body, timeout=self.timeout,
                headers={"x-api-key": self.api_key, "anthropic-version": API_VERSION,
                         "content-type": "application/json"},
            )
        except requests.RequestException as e:
            raise LLMUnavailable(f"could not reach the Anthropic API: {e}") from e
        dt = time.perf_counter() - t0
        if r.status_code != 200:
            raise LLMUnavailable(f"Anthropic API error {r.status_code}: {r.text[:300]}")
        data = r.json()
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        return LLMResponse(text, usage.get("input_tokens", 0), usage.get("output_tokens", 0), dt, self.model)


class OpenAICompatibleClient:
    """Client for OpenAI-style ``/chat/completions`` servers (Ollama, LM Studio, vLLM, and
    hosted providers that offer this protocol).

    Environment: LLM_BASE_URL (default Ollama), LLM_MODEL (required), LLM_API_KEY (optional;
    local Ollama needs none).
    """

    def __init__(self, model: str | None = None, base_url: str | None = None,
                 api_key: str | None = None, max_tokens: int = 1024, timeout: float | None = None):
        self.model = model or os.getenv("LLM_MODEL")
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or DEFAULT_OPENAI_BASE_URL).rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY")
        self.max_tokens = max_tokens
        # local models on CPU can be slow: generous default timeout
        self.timeout = timeout or float(os.getenv("LLM_TIMEOUT", "300"))

    def complete(self, prompt: str, system: str | None = None) -> LLMResponse:
        if not self.model:
            raise LLMUnavailable("LLM_MODEL is not set (e.g. the name shown by `ollama list`)")
        messages = ([{"role": "system", "content": system}] if system else []) + \
                   [{"role": "user", "content": prompt}]
        body = {"model": self.model, "messages": messages, "temperature": 0, "max_tokens": self.max_tokens}
        headers = {"content-type": "application/json"}
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        t0 = time.perf_counter()
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=body, headers=headers,
                              timeout=self.timeout)
        except requests.RequestException as e:
            raise LLMUnavailable(f"could not reach the LLM server at {self.base_url}: {e}") from e
        dt = time.perf_counter() - t0
        if r.status_code != 200:
            raise LLMUnavailable(f"LLM server error {r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            text = data["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError) as e:
            raise LLMUnavailable(f"unexpected response format from LLM server: {str(data)[:300]}") from e
        usage = data.get("usage") or {}
        return LLMResponse(text, usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0), dt,
                           self.model)


def llm_configured() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY") or os.getenv("LLM_MODEL"))


def make_client():
    """Choose a client from the environment.

    LLM_PROVIDER=anthropic | openai forces a choice. Otherwise: if LLM_MODEL is set use the
    OpenAI-compatible client (free/local options); elif ANTHROPIC_API_KEY is set use Anthropic.
    """
    provider = (os.getenv("LLM_PROVIDER") or "").lower()
    if provider == "anthropic":
        return AnthropicClient()
    if provider in ("openai", "ollama"):
        return OpenAICompatibleClient()
    if os.getenv("LLM_MODEL"):
        return OpenAICompatibleClient()
    if os.getenv("ANTHROPIC_API_KEY"):
        return AnthropicClient()
    raise LLMUnavailable(
        "no LLM configured: set LLM_MODEL (free: Ollama or a free-tier provider) "
        "or ANTHROPIC_API_KEY. The rules-v2 extractor needs neither.")
