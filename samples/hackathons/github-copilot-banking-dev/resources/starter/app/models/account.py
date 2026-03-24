from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


AccountType = Literal["checking", "savings", "money_market"]


class Account(BaseModel):
    """Full account record returned from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_number: str = Field(..., description="IBAN-format account identifier")
    account_type: AccountType
    owner_name: str
    # TODO: consider using Decimal for monetary precision - float arithmetic can
    # introduce rounding errors on fractional cent calculations
    balance: float = Field(default=0.0, description="Current account balance")
    currency: str = Field(default="USD", max_length=3)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class AccountCreate(BaseModel):
    """Request body for opening a new account."""

    account_number: str = Field(
        ...,
        min_length=15,
        max_length=34,
        description="Must be a valid IBAN",
    )
    account_type: AccountType
    owner_name: str = Field(..., min_length=2, max_length=100)
    # TODO: Decimal would be safer here
    initial_balance: float = Field(default=0.0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    # Validate that account_number matches IBAN format


class AccountUpdate(BaseModel):
    """Request body for updating mutable account fields."""

    owner_name: Optional[str] = Field(None, min_length=2, max_length=100)
    is_active: Optional[bool] = None


class AccountSummary(BaseModel):
    """Lightweight account summary used in list responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    account_number: str
    account_type: AccountType
    owner_name: str
    # TODO: Decimal
    balance: float
    currency: str
    is_active: bool
