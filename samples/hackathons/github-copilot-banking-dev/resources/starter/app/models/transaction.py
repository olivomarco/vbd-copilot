from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


TransactionType = Literal[
    "debit",
    "credit",
    "transfer_in",
    "transfer_out",
    "fee",
    "interest",
    "reversal",
]

TransactionStatus = Literal["pending", "completed", "failed", "reversed"]


class Transaction(BaseModel):
    """A completed or in-flight transaction record."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    transaction_type: TransactionType
    # TODO: Decimal for monetary precision
    amount: float
    currency: str = "USD"
    description: str
    reference_id: Optional[str] = None
    status: TransactionStatus = "pending"
    created_at: datetime
    # TODO: Decimal
    balance_after: float


class TransactionCreate(BaseModel):
    """Request body for recording a new transaction against an account."""

    account_id: int
    transaction_type: TransactionType
    # TODO: Decimal
    amount: float = Field(..., gt=0, description="Transaction amount, must be positive")
    currency: str = Field(default="USD", min_length=3, max_length=3)
    description: str = Field(..., min_length=1, max_length=255)
    reference_id: Optional[str] = Field(
        None,
        description="Caller-supplied idempotency reference",
    )
