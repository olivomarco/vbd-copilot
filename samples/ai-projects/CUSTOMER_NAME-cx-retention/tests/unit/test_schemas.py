"""Tests for models/schemas.py -- Pydantic model validation.

Verifies correct parsing, validation errors, optional fields, and
literal constraints for all request/response models.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.schemas import (
    BillData,
    ChatRequest,
    ChatStreamEvent,
    FeedbackRequest,
    HealthResponse,
    LineItem,
    MessageResponse,
    ModelClassification,
    SearchResult,
    SessionResponse,
)


class TestChatRequest:
    """Validate ChatRequest parsing and constraints."""

    def test_chat_request_valid(self) -> None:
        """Valid request with message only parses correctly."""
        req = ChatRequest(message="Come pago la bolletta?")
        assert req.message == "Come pago la bolletta?"
        assert req.session_id is None
        assert req.bill_ref is None

    def test_chat_request_all_fields(self) -> None:
        """Valid request with all optional fields set."""
        req = ChatRequest(
            message="Spiega la mia bolletta",
            session_id="abc-123",
            bill_ref="BILL-2024-001",
        )
        assert req.session_id == "abc-123"
        assert req.bill_ref == "BILL-2024-001"

    def test_chat_request_missing_message(self) -> None:
        """Omitting message raises ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            ChatRequest()  # type: ignore[call-arg]
        errors = exc_info.value.errors()
        assert any(e["loc"] == ("message",) for e in errors)

    def test_chat_request_empty_message(self) -> None:
        """Empty string message violates min_length=1."""
        with pytest.raises(ValidationError):
            ChatRequest(message="")

    def test_chat_request_too_long_message(self) -> None:
        """Message exceeding max_length=2000 is rejected."""
        with pytest.raises(ValidationError):
            ChatRequest(message="x" * 2001)

    def test_chat_request_optional_fields(self) -> None:
        """session_id and bill_ref default to None."""
        req = ChatRequest(message="test")
        assert req.session_id is None
        assert req.bill_ref is None


class TestFeedbackRequest:
    """Validate FeedbackRequest literal rating constraints."""

    def test_feedback_request_valid_up(self) -> None:
        """Rating 'up' is accepted."""
        req = FeedbackRequest(
            session_id="s1",
            message_id="m1",
            rating="up",
        )
        assert req.rating == "up"

    def test_feedback_request_valid_down(self) -> None:
        """Rating 'down' is accepted."""
        req = FeedbackRequest(
            session_id="s1",
            message_id="m1",
            rating="down",
        )
        assert req.rating == "down"

    def test_feedback_request_invalid_rating(self) -> None:
        """Ratings other than 'up'/'down' are rejected."""
        with pytest.raises(ValidationError):
            FeedbackRequest(
                session_id="s1",
                message_id="m1",
                rating="neutral",  # type: ignore[arg-type]
            )

    def test_feedback_request_with_comment(self) -> None:
        """Optional comment field is included when provided."""
        req = FeedbackRequest(
            session_id="s1",
            message_id="m1",
            rating="up",
            comment="Ottima risposta!",
        )
        assert req.comment == "Ottima risposta!"

    def test_feedback_request_comment_too_long(self) -> None:
        """Comment exceeding max_length=1000 is rejected."""
        with pytest.raises(ValidationError):
            FeedbackRequest(
                session_id="s1",
                message_id="m1",
                rating="up",
                comment="x" * 1001,
            )

    def test_feedback_request_missing_required_fields(self) -> None:
        """Omitting required fields raises ValidationError."""
        with pytest.raises(ValidationError):
            FeedbackRequest(rating="up")  # type: ignore[call-arg]


class TestBillData:
    """Validate BillData and LineItem models."""

    def test_bill_data_complete(self) -> None:
        """All fields populated correctly."""
        bill = BillData(
            bill_ref="BILL-2024-001",
            total_amount=150.75,
            currency="EUR",
            billing_period_start="2024-01-01",
            billing_period_end="2024-01-31",
            consumption_kwh=200.0,
            consumption_smc=50.0,
            tariff_code="TD-MONO",
            tariff_name="Tariffa Monoraria",
            payment_status="pagata",
            due_date="2024-02-15",
        )
        assert bill.bill_ref == "BILL-2024-001"
        assert bill.total_amount == 150.75
        assert bill.currency == "EUR"

    def test_bill_data_optional_fields_default(self) -> None:
        """Optional fields default to None; line_items defaults to empty list."""
        bill = BillData(
            bill_ref="REF-001",
            total_amount=50.0,
            billing_period_start="2024-01-01",
            billing_period_end="2024-01-31",
        )
        assert bill.consumption_kwh is None
        assert bill.tariff_code is None
        assert bill.line_items == []
        assert bill.currency == "EUR"  # default

    def test_line_item_model(self) -> None:
        """LineItem contains description, amount, optional unit and quantity."""
        item = LineItem(
            description="Quota fissa",
            amount=20.50,
            unit="EUR/mese",
            quantity=1.0,
        )
        assert item.description == "Quota fissa"
        assert item.amount == 20.50
        assert item.unit == "EUR/mese"
        assert item.quantity == 1.0

    def test_line_item_minimal(self) -> None:
        """LineItem with only required fields."""
        item = LineItem(description="IVA", amount=12.30)
        assert item.unit is None
        assert item.quantity is None


class TestSearchResult:
    """Validate SearchResult model."""

    def test_search_result_model(self) -> None:
        """All fields present and correct."""
        sr = SearchResult(
            content="Test content about tariffs",
            source_document="tariff_guide.pdf",
            category="tariffe",
            score=0.95,
            title="Tariff Guide",
        )
        assert sr.content == "Test content about tariffs"
        assert sr.source_document == "tariff_guide.pdf"
        assert sr.category == "tariffe"
        assert sr.score == 0.95
        assert sr.title == "Tariff Guide"

    def test_search_result_defaults(self) -> None:
        """Optional fields default correctly."""
        sr = SearchResult(content="Minimal result")
        assert sr.source_document is None
        assert sr.category is None
        assert sr.score == 0.0
        assert sr.title is None


class TestModelClassification:
    """Validate ModelClassification model."""

    def test_model_classification_complete(self) -> None:
        """Full classification with all fields."""
        mc = ModelClassification(
            model="gpt-4o",
            needs_billing_data=True,
            reasoning="Bill reference provided",
        )
        assert mc.model == "gpt-4o"
        assert mc.needs_billing_data is True
        assert mc.reasoning == "Bill reference provided"

    def test_model_classification_defaults(self) -> None:
        """Default values for optional fields."""
        mc = ModelClassification(model="gpt-4o-mini")
        assert mc.needs_billing_data is False
        assert mc.reasoning == ""


class TestChatStreamEvent:
    """Validate ChatStreamEvent model."""

    def test_streaming_event(self) -> None:
        """Intermediate streaming event."""
        ev = ChatStreamEvent(token="Buon", done=False)
        assert ev.token == "Buon"
        assert ev.done is False
        assert ev.session_id is None
        assert ev.message_id is None

    def test_final_event(self) -> None:
        """Final streaming event with session and message IDs."""
        ev = ChatStreamEvent(
            token="",
            done=True,
            session_id="s1",
            message_id="m1",
        )
        assert ev.done is True
        assert ev.session_id == "s1"
        assert ev.message_id == "m1"


class TestHealthResponse:
    """Validate HealthResponse model."""

    def test_health_response(self) -> None:
        """Health response with services dict."""
        hr = HealthResponse(
            status="healthy",
            services={"cosmos_db": "healthy", "openai": "healthy"},
        )
        assert hr.status == "healthy"
        assert hr.services["cosmos_db"] == "healthy"


class TestSessionResponse:
    """Validate SessionResponse model."""

    def test_session_response_minimal(self) -> None:
        """Session response with required fields only."""
        sr = SessionResponse(
            session_id="s1",
            created_at="2024-06-01T10:00:00Z",
            last_active="2024-06-01T10:05:00Z",
        )
        assert sr.session_id == "s1"
        assert sr.bill_ref is None
        assert sr.message_count == 0
        assert sr.messages == []


class TestMessageResponse:
    """Validate MessageResponse model."""

    def test_message_response(self) -> None:
        """Message response with all fields."""
        mr = MessageResponse(
            message_id="m1",
            role="assistant",
            content="Risposta di test",
            timestamp="2024-06-01T10:00:00Z",
            model_used="gpt-4o",
        )
        assert mr.role == "assistant"
        assert mr.model_used == "gpt-4o"

    def test_message_response_user(self) -> None:
        """User message without model_used."""
        mr = MessageResponse(
            message_id="m2",
            role="user",
            content="Domanda di test",
            timestamp="2024-06-01T10:00:00Z",
        )
        assert mr.model_used is None
