"""Tests for prompts/system_prompt.py -- system prompt generation.

Verifies Italian-language content, grounding instructions, scope
restrictions, and bill-data injection formatting.
"""

from __future__ import annotations

import pytest

from app.models.schemas import BillData, LineItem
from app.prompts.system_prompt import get_bill_context_prompt, get_system_prompt


class TestGetSystemPrompt:
    """Test the main system prompt generation."""

    def test_get_system_prompt_contains_italian(self) -> None:
        """Prompt is in Italian -- contains key Italian phrases."""
        prompt = get_system_prompt()
        assert "CUSTOMER_NAME" in prompt
        assert "bollette" in prompt.lower() or "bolletta" in prompt.lower()
        assert "cliente" in prompt.lower()

    def test_get_system_prompt_contains_grounding(self) -> None:
        """Grounding instructions are present (respond only from context)."""
        prompt = get_system_prompt()
        assert "contesto" in prompt.lower()
        assert "knowledge base" in prompt.lower()

    def test_get_system_prompt_contains_scope(self) -> None:
        """Scope restriction is present (energy bills only)."""
        prompt = get_system_prompt()
        assert "esclusivamente" in prompt.lower()
        assert "energetiche" in prompt.lower() or "energia" in prompt.lower()

    def test_get_system_prompt_with_context(self) -> None:
        """Knowledge context is injected into the prompt."""
        context = "Le tariffe monorarie applicano un prezzo unico."
        prompt = get_system_prompt(knowledge_context=context)
        assert context in prompt

    def test_get_system_prompt_empty_context_placeholder(self) -> None:
        """Empty context results in a placeholder message."""
        prompt = get_system_prompt(knowledge_context="")
        assert "Nessun contesto disponibile" in prompt

    def test_get_system_prompt_no_context_placeholder(self) -> None:
        """No context argument results in a placeholder message."""
        prompt = get_system_prompt()
        assert "Nessun contesto disponibile" in prompt

    def test_get_system_prompt_numerical_accuracy(self) -> None:
        """Prompt contains numerical accuracy instructions."""
        prompt = get_system_prompt()
        assert "kWh" in prompt
        assert "EUR" in prompt

    def test_get_system_prompt_safety_guardrails(self) -> None:
        """Prompt contains topic restriction / out-of-scope handling."""
        prompt = get_system_prompt()
        # Must mention what to do for out-of-scope questions
        assert "servizio clienti" in prompt.lower()


class TestGetBillContextPrompt:
    """Test bill data injection into prompt context."""

    @pytest.fixture
    def basic_bill(self) -> BillData:
        """Minimal bill data without line items."""
        return BillData(
            bill_ref="BILL-2024-001",
            total_amount=125.60,
            currency="EUR",
            billing_period_start="2024-01-01",
            billing_period_end="2024-01-31",
            payment_status="pagata",
            due_date="2024-02-15",
        )

    @pytest.fixture
    def bill_with_line_items(self, basic_bill: BillData) -> BillData:
        """Bill data with line items and consumption data."""
        return BillData(
            bill_ref="BILL-2024-002",
            total_amount=200.50,
            currency="EUR",
            billing_period_start="2024-02-01",
            billing_period_end="2024-02-28",
            consumption_kwh=220.0,
            consumption_smc=55.0,
            tariff_code="TD-MONO",
            tariff_name="Tariffa Monoraria",
            line_items=[
                LineItem(
                    description="Quota fissa",
                    amount=25.00,
                    unit="EUR/mese",
                    quantity=1.0,
                ),
                LineItem(
                    description="Energia",
                    amount=50.00,
                    unit="kWh",
                    quantity=220.0,
                ),
            ],
            payment_status="da pagare",
            due_date="2024-03-15",
        )

    def test_get_bill_context_prompt(self, basic_bill: BillData) -> None:
        """Bill data is formatted correctly in the prompt section."""
        prompt = get_bill_context_prompt(basic_bill)
        assert "BILL-2024-001" in prompt
        assert "125.60" in prompt
        assert "EUR" in prompt
        assert "2024-01-01" in prompt
        assert "2024-01-31" in prompt
        assert "pagata" in prompt
        assert "2024-02-15" in prompt

    def test_get_bill_context_prompt_with_line_items(
        self, bill_with_line_items: BillData
    ) -> None:
        """Line items are included in the bill context prompt."""
        prompt = get_bill_context_prompt(bill_with_line_items)
        assert "Quota fissa" in prompt
        assert "25.00" in prompt
        assert "Energia" in prompt
        assert "50.00" in prompt
        assert "Dettaglio voci di costo" in prompt

    def test_get_bill_context_prompt_consumption(
        self, bill_with_line_items: BillData
    ) -> None:
        """Consumption data (kWh and Smc) appear when present."""
        prompt = get_bill_context_prompt(bill_with_line_items)
        assert "220.0 kWh" in prompt
        assert "55.0 Smc" in prompt

    def test_get_bill_context_prompt_tariff(
        self, bill_with_line_items: BillData
    ) -> None:
        """Tariff information is formatted correctly."""
        prompt = get_bill_context_prompt(bill_with_line_items)
        assert "Tariffa Monoraria" in prompt
        assert "TD-MONO" in prompt

    def test_get_bill_context_prompt_no_consumption(self, basic_bill: BillData) -> None:
        """No consumption section when data is absent."""
        prompt = get_bill_context_prompt(basic_bill)
        # Should not contain consumption lines since basic_bill has None for both
        assert "Consumo energia elettrica" not in prompt
        assert "Consumo gas naturale" not in prompt

    def test_get_bill_context_prompt_no_payment_status(self) -> None:
        """Missing payment_status shows 'Non disponibile'."""
        bill = BillData(
            bill_ref="BILL-000",
            total_amount=10.0,
            billing_period_start="2024-01-01",
            billing_period_end="2024-01-31",
            payment_status=None,
            due_date=None,
        )
        prompt = get_bill_context_prompt(bill)
        assert "Non disponibile" in prompt

    def test_get_bill_context_prompt_line_item_with_quantity(self) -> None:
        """Line item with quantity and unit shows parenthetical detail."""
        bill = BillData(
            bill_ref="BILL-003",
            total_amount=80.0,
            billing_period_start="2024-01-01",
            billing_period_end="2024-01-31",
            line_items=[
                LineItem(
                    description="Gas",
                    amount=30.00,
                    unit="Smc",
                    quantity=45.0,
                ),
            ],
        )
        prompt = get_bill_context_prompt(bill)
        assert "45.0 Smc" in prompt
        assert "30.00 EUR" in prompt
