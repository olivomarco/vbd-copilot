from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class TransferRequest(BaseModel):
    """Request body for a funds transfer between two FinCore accounts."""

    source_account_id: int
    destination_account_id: int
    # TODO: Decimal
    amount: float = Field(..., gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    description: Optional[str] = Field(None, max_length=255)
    # reference_id is accepted but NOT checked for uniqueness - missing idempotency
    reference_id: Optional[str] = Field(
        None,
        description="Optional caller reference. Not currently checked for uniqueness.",
    )


class TransferResponse(BaseModel):
    """Response body confirming a completed transfer."""

    transfer_id: str
    source_account_id: int
    destination_account_id: int
    # TODO: Decimal
    amount: float
    currency: str
    status: str
    debit_transaction_id: int
    credit_transaction_id: int
    message: str = "Transfer completed successfully"
