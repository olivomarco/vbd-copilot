"""Tests for services/model_router.py -- query classification logic.

Validates that queries are correctly routed to GPT-4o-mini (simple/FAQ)
or GPT-4o (complex/billing) based on message length, keywords,
bill reference presence, and conversation depth.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.models.schemas import ModelClassification
from app.services.model_router import ModelRouter


@pytest.fixture
def router(mock_settings: MagicMock) -> ModelRouter:
    """Create a ModelRouter with test settings."""
    return ModelRouter(mock_settings)


class TestModelRouterSimpleQueries:
    """Verify that simple/FAQ queries route to GPT-4o-mini."""

    def test_simple_faq_routes_to_mini(self, router: ModelRouter) -> None:
        """Short question without bill_ref should route to mini."""
        result = router.classify("Come posso pagare la bolletta?")
        assert result.model == "gpt-4o-mini"
        assert result.needs_billing_data is False

    def test_default_is_mini(self, router: ModelRouter) -> None:
        """Standard short question defaults to cost-effective model."""
        result = router.classify("Cos'e' il bonus sociale?")
        assert result.model == "gpt-4o-mini"
        assert result.needs_billing_data is False

    def test_short_message_no_keywords(self, router: ModelRouter) -> None:
        """A brief generic question stays on mini."""
        result = router.classify("Quando arriva la prossima bolletta?")
        assert result.model == "gpt-4o-mini"


class TestModelRouterComplexQueries:
    """Verify that complex queries route to GPT-4o."""

    def test_bill_ref_routes_to_4o(self, router: ModelRouter) -> None:
        """Message with bill_ref should route to GPT-4o and flag billing data."""
        result = router.classify(
            "Spiega la mia bolletta",
            bill_ref="BILL-2024-001",
        )
        assert result.model == "gpt-4o"
        assert result.needs_billing_data is True

    def test_long_complex_question_routes_to_4o(self, router: ModelRouter) -> None:
        """Message > 200 chars should route to GPT-4o."""
        long_message = (
            "Vorrei capire nel dettaglio la ripartizione delle voci di costo "
            "nella mia bolletta, in particolare la differenza tra gli oneri di "
            "sistema e le accise. Inoltre mi interessa sapere perche' la quota "
            "fissa e' cambiata rispetto al mese precedente."
        )
        assert len(long_message) > 200
        result = router.classify(long_message)
        assert result.model == "gpt-4o"

    def test_high_turn_count_routes_to_4o(self, router: ModelRouter) -> None:
        """Conversation turn > 5 should route to GPT-4o."""
        result = router.classify("Grazie, e il gas?", conversation_turn=6)
        assert result.model == "gpt-4o"

    def test_numerical_comparison_keywords_confronto(self, router: ModelRouter) -> None:
        """Keyword 'confronto' triggers complex routing."""
        result = router.classify("Vorrei un confronto con la bolletta scorsa")
        assert result.model == "gpt-4o"

    def test_numerical_comparison_keywords_differenza(self, router: ModelRouter) -> None:
        """Keyword 'differenza' triggers complex routing."""
        result = router.classify("Qual e' la differenza tra le due tariffe?")
        assert result.model == "gpt-4o"

    def test_numerical_comparison_keywords_calcolo(self, router: ModelRouter) -> None:
        """Keyword 'calcolo' triggers complex routing."""
        result = router.classify("Mi fai il calcolo del consumo annuale?")
        assert result.model == "gpt-4o"

    def test_numerical_comparison_keywords_aumento(self, router: ModelRouter) -> None:
        """Keyword 'aumento' triggers complex routing."""
        result = router.classify("Come si spiega l'aumento della bolletta?")
        assert result.model == "gpt-4o"

    def test_numerical_comparison_keywords_percentuale(self, router: ModelRouter) -> None:
        """Keyword 'percentuale' triggers complex routing."""
        result = router.classify("Che percentuale sono le tasse?")
        assert result.model == "gpt-4o"

    def test_turn_count_at_boundary(self, router: ModelRouter) -> None:
        """Turn count exactly 5 should still be mini (threshold is > 5)."""
        result = router.classify("Come posso pagare?", conversation_turn=5)
        assert result.model == "gpt-4o-mini"


class TestModelRouterClassificationOutput:
    """Verify the structure and content of ModelClassification output."""

    def test_classification_returns_correct_model_name(self, router: ModelRouter) -> None:
        """Exact deployment names from settings are used."""
        simple = router.classify("Ciao")
        assert simple.model == "gpt-4o-mini"

        complex_ = router.classify("Dettaglio", bill_ref="BILL-001-XYZ")
        assert complex_.model == "gpt-4o"

    def test_classification_has_reasoning(self, router: ModelRouter) -> None:
        """Reasoning field is always non-empty."""
        simple = router.classify("Ciao")
        assert isinstance(simple.reasoning, str)
        assert len(simple.reasoning) > 0

        complex_ = router.classify("Confronto bollette", bill_ref="BILL-001-XYZ")
        assert isinstance(complex_.reasoning, str)
        assert len(complex_.reasoning) > 0

    def test_classification_returns_model_classification_type(
        self, router: ModelRouter
    ) -> None:
        """Return type is always a ModelClassification instance."""
        result = router.classify("Test")
        assert isinstance(result, ModelClassification)

    def test_multiple_complex_signals_combined(self, router: ModelRouter) -> None:
        """Multiple complex signals (bill_ref + keywords + long + high turn)."""
        long_msg = "Vorrei sapere la differenza " + "x" * 200
        result = router.classify(
            long_msg,
            bill_ref="BILL-2024-999",
            conversation_turn=10,
        )
        assert result.model == "gpt-4o"
        assert result.needs_billing_data is True
        assert "bill reference" in result.reasoning
        assert "numerical-comparison keywords" in result.reasoning

    def test_needs_billing_data_false_without_bill_ref(self, router: ModelRouter) -> None:
        """Even with complex keywords, needs_billing_data is False without bill_ref."""
        result = router.classify("Confronto tariffe attuali")
        assert result.needs_billing_data is False
