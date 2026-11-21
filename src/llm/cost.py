"""Token and cost accounting.

Prices are USD per million tokens, taken from the Anthropic pricing page on
2026-10-17 (https://platform.claude.com/docs/en/about-claude/pricing). They
change; override with environment variables ``PRICE_INPUT_PER_MTOK`` /
``PRICE_OUTPUT_PER_MTOK``.

Any model that is not in ``PRICES`` (local Ollama models, free-tier providers) is
costed at **$0**, which is what a free/local model costs to run. If a
provider charges for it, set the two environment variables above.
"""
from __future__ import annotations

import os

PRICES = {
    # model id: (input $/MTok, output $/MTok)  - standard (non-batch, no caching), prompts <= 100k tokens
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 characters per token for English). Used only when an
    API usage figure is unavailable, e.g. for a dry-run cost projection."""
    return max(1, round(len(text) / 4))


def price_for(model: str) -> tuple[float, float]:
    env_in, env_out = os.getenv("PRICE_INPUT_PER_MTOK"), os.getenv("PRICE_OUTPUT_PER_MTOK")
    if env_in and env_out:
        return float(env_in), float(env_out)
    return PRICES.get(model, (0.0, 0.0))


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    p_in, p_out = price_for(model)
    return (input_tokens * p_in + output_tokens * p_out) / 1_000_000
