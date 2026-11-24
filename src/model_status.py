"""Is the open-source AI model (used only for the optional AI summary) running? Shown as a chip in the top bar.

The model is chosen by the same environment variables as the summary client: ``LLM_MODEL`` and ``LLM_BASE_URL``
(default: Ollama on this computer). The check asks the server for its model list; it never sends a document.
"""
from __future__ import annotations

import json
import os
import urllib.request

from src.llm.client import DEFAULT_OPENAI_BASE_URL


def _get(url: str, timeout: float = 1.5) -> dict:
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "document-analyst"}), timeout=timeout) as r:  # nosec
        return json.load(r)


def model_status(env=None, get=_get) -> dict:
    """{label, level, detail}. level: ok (running), warn (set but not reachable), none (no model set)."""
    env = os.environ if env is None else env
    model = (env.get("LLM_MODEL") or "").strip()
    if not model:
        if env.get("ANTHROPIC_API_KEY"):
            return {"label": "AI model · Claude API", "level": "ok", "detail": "a hosted model is configured for summaries"}
        return {"label": "AI model · off", "level": "none",
                "detail": "No model is set, so summaries use the free built-in method. Set LLM_MODEL to use an open-source model."}
    base = (env.get("LLM_BASE_URL") or DEFAULT_OPENAI_BASE_URL).rstrip("/")
    try:
        data = get(base + "/models")
        names = [m.get("id") or m.get("name") for m in (data.get("data") or data.get("models") or [])]
        ok = not names or any(n and (n == model or n.split(":")[0] == model.split(":")[0]) for n in names)
        if ok:
            return {"label": "Open-source model · Active", "level": "ok", "detail": f"{model} answers at {base}"}
        return {"label": "Open-source model · Not installed", "level": "warn",
                "detail": f"the server at {base} is running but does not list {model}"}
    except Exception as e:
        return {"label": "Open-source model · Not running", "level": "warn",
                "detail": f"no answer from {base} ({type(e).__name__}); start the model server"}
