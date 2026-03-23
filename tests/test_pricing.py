"""Tests for pricing.py - token cost estimation."""

import pytest

from pricing import MODEL_PRICING, estimate_cost


class TestEstimateCost:
    """Tests for the estimate_cost function."""

    def test_zero_tokens(self):
        assert estimate_cost("gpt-4o", 0, 0) == 0.0

    def test_known_model_input_only(self):
        # gpt-4o: input=$2.50/1M
        cost = estimate_cost("gpt-4o", input_tokens=1_000_000)
        assert cost == pytest.approx(2.50)

    def test_known_model_output_only(self):
        # gpt-4o: output=$10.00/1M
        cost = estimate_cost("gpt-4o", output_tokens=1_000_000)
        assert cost == pytest.approx(10.00)

    def test_known_model_both(self):
        # gpt-4o: $2.50 in + $10.00 out per 1M
        cost = estimate_cost("gpt-4o", input_tokens=1_000_000, output_tokens=1_000_000)
        assert cost == pytest.approx(12.50)

    def test_small_token_count(self):
        # 1000 tokens of gpt-4o input = $0.0025
        cost = estimate_cost("gpt-4o", input_tokens=1000)
        assert cost == pytest.approx(0.0025)

    def test_unknown_model_uses_default(self):
        cost = estimate_cost("unknown-model", input_tokens=1_000_000)
        default_input_price = MODEL_PRICING["default"][0]
        assert cost == pytest.approx(default_input_price)

    def test_claude_sonnet(self):
        # claude-sonnet-4.6: $3.00 in, $15.00 out per 1M
        cost = estimate_cost("claude-sonnet-4.6", input_tokens=500_000, output_tokens=200_000)
        expected = (500_000 / 1_000_000) * 3.00 + (200_000 / 1_000_000) * 15.00
        assert cost == pytest.approx(expected)

    def test_claude_opus(self):
        # claude-opus-4: $15.00 in, $75.00 out per 1M
        cost = estimate_cost("claude-opus-4", input_tokens=100_000, output_tokens=50_000)
        expected = (100_000 / 1_000_000) * 15.00 + (50_000 / 1_000_000) * 75.00
        assert cost == pytest.approx(expected)

    def test_gpt4_1_mini(self):
        cost = estimate_cost("gpt-4.1-mini", input_tokens=1_000_000, output_tokens=1_000_000)
        assert cost == pytest.approx(0.40 + 1.60)

    def test_all_known_models_in_pricing_table(self):
        """Every model in the pricing table should produce a non-default result."""
        for model_name in MODEL_PRICING:
            if model_name == "default":
                continue
            cost = estimate_cost(model_name, input_tokens=1_000_000, output_tokens=1_000_000)
            in_price, out_price = MODEL_PRICING[model_name]
            assert cost == pytest.approx(in_price + out_price)
