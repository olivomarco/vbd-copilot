from __future__ import annotations

from typing import List

import structlog
from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.models.transaction import Transaction, TransactionCreate
from app.services.transaction_service import TransactionService

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=Transaction,
    status_code=201,
    summary="Record a transaction",
)
async def create_transaction(
    transaction_data: TransactionCreate,
    current_user: dict = Depends(get_current_user),
    # Missing: rate-limiting middleware or decorator. A high-frequency caller can
    # flood this endpoint, causing runaway balance mutations. Challenge-08 adds
    # protection here.
    # Missing: idempotency key header (X-Idempotency-Key). Without it, network
    # retries produce duplicate transactions.
) -> Transaction:
    """Record a debit, credit, fee, or interest transaction against an account."""
    service = TransactionService()
    return service.create_transaction(transaction_data)


@router.get(
    "/{account_id}",
    response_model=List[Transaction],
    summary="List transactions for an account",
)
async def get_transactions(
    account_id: int,
    current_user: dict = Depends(get_current_user),
) -> List[Transaction]:
    """Return all transactions for the specified account, newest first."""
    service = TransactionService()
    return service.get_transactions(account_id)


@router.get(
    "/detail/{transaction_id}",
    response_model=Transaction,
    summary="Get transaction by ID",
)
async def get_transaction(
    transaction_id: int,
    current_user: dict = Depends(get_current_user),
) -> Transaction:
    service = TransactionService()
    return service.get_transaction(transaction_id)
