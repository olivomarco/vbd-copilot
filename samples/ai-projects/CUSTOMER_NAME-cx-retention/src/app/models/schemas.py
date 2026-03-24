"""Pydantic request/response models for the Bill Explainer API.

All models use Pydantic v2 conventions. Field descriptions are included
so they propagate to the auto-generated OpenAPI documentation.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    """Incoming chat message from the user."""

    session_id: Optional[str] = Field(
        default=None,
        description="Existing session UUID. Omit to create a new session.",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User question text.",
    )
    bill_ref: Optional[str] = Field(
        default=None,
        description="Optional bill reference for personalised lookup.",
    )


class ChatStreamEvent(BaseModel):
    """Single Server-Sent Event payload during streaming."""

    token: str = Field(description="Incremental text token (empty on final event).")
    done: bool = Field(description="True when the response is complete.")
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier (present on final event).",
    )
    message_id: Optional[str] = Field(
        default=None,
        description="Persisted message identifier (present on final event).",
    )


# ---------------------------------------------------------------------------
# Feedback
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    """Thumbs-up / thumbs-down feedback for an assistant message."""

    session_id: str = Field(..., description="Session that contains the message.")
    message_id: str = Field(..., description="The assistant message being rated.")
    rating: Literal["up", "down"] = Field(..., description="User rating.")
    comment: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Optional free-text comment.",
    )


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------

class MessageResponse(BaseModel):
    """A single message within a conversation."""

    message_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime
    model_used: Optional[str] = None


class SessionResponse(BaseModel):
    """Session overview returned by the sessions endpoint."""

    session_id: str
    created_at: datetime
    last_active: datetime
    bill_ref: Optional[str] = None
    message_count: int = 0
    messages: list[MessageResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Health-check response with per-service status."""

    status: str = Field(description="Overall status: healthy or degraded.")
    services: dict[str, str] = Field(
        default_factory=dict,
        description="Individual service statuses.",
    )


# ---------------------------------------------------------------------------
# Billing data
# ---------------------------------------------------------------------------

class LineItem(BaseModel):
    """Single line item on an energy bill."""

    description: str
    amount: float
    unit: Optional[str] = None
    quantity: Optional[float] = None


class BillData(BaseModel):
    """Structured representation of a CUSTOMER_NAME energy bill."""

    bill_ref: str
    total_amount: float
    currency: str = "EUR"
    billing_period_start: str
    billing_period_end: str
    consumption_kwh: Optional[float] = None
    consumption_smc: Optional[float] = None
    tariff_code: Optional[str] = None
    tariff_name: Optional[str] = None
    line_items: list[LineItem] = Field(default_factory=list)
    payment_status: Optional[str] = None
    due_date: Optional[str] = None


# ---------------------------------------------------------------------------
# AI Search
# ---------------------------------------------------------------------------

class SearchResult(BaseModel):
    """A single result from Azure AI Search."""

    content: str
    source_document: Optional[str] = None
    category: Optional[str] = None
    score: float = 0.0
    title: Optional[str] = None


# ---------------------------------------------------------------------------
# Model routing
# ---------------------------------------------------------------------------

class ModelClassification(BaseModel):
    """Classification output that determines which LLM to use."""

    model: str = Field(description="Deployment name: gpt-4o-mini or gpt-4o.")
    needs_billing_data: bool = Field(
        default=False,
        description="Whether the query requires billing API lookup.",
    )
    reasoning: str = Field(
        default="",
        description="Short explanation of the routing decision.",
    )
