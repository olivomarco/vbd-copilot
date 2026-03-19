"""Token cost estimation for known LLM models.

Prices are per-1M-tokens estimates.  Not intended for billing accuracy -
only for rough usage dashboards.
"""

from __future__ import annotations

# (input_price_per_1M_tokens, output_price_per_1M_tokens)
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # OpenAI
    "gpt-5.4": (2.50, 10.00),
    "gpt-5-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    # Anthropic
    "claude-sonnet-4.6": (3.00, 15.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-opus-4": (15.00, 75.00),
    "claude-opus-4.6": (15.00, 75.00),
    # Fallback
    "default": (2.50, 10.00),
}


def estimate_cost(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> float:
    """Return estimated cost in USD for the given token counts."""
    prices = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    input_cost = (input_tokens / 1_000_000) * prices[0]
    output_cost = (output_tokens / 1_000_000) * prices[1]
    return input_cost + output_cost
