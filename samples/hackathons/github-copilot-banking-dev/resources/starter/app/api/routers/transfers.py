from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user
from app.exceptions import ValidationError
from app.models.transaction import TransactionCreate
from app.models.transfer import TransferRequest, TransferResponse
from app.services.account_service import AccountService
from app.services.transaction_service import TransactionService

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=TransferResponse,
    status_code=201,
    summary="Transfer funds between accounts",
)
async def create_transfer(
    transfer: TransferRequest,
    current_user: dict = Depends(get_current_user),
    # Missing: idempotency - transfer.reference_id is recorded but not checked
    # for uniqueness. A duplicate POST with the same reference_id will execute
    # a second transfer. This is the primary target for challenge-08.
    # Missing: rate limiting. No protection against bulk transfer attacks.
) -> TransferResponse:
    """Move funds from one FinCore account to another.

    Executes as two transaction records: a transfer_out on the source and a
    transfer_in on the destination. There is currently no database transaction
    wrapping these two operations - a failure after the debit but before the
    credit would leave the accounts in an inconsistent state.
    """
    if transfer.source_account_id == transfer.destination_account_id:
        raise ValidationError("Source and destination accounts must be different")

    account_service = AccountService()

    # Verify both accounts exist before touching either balance
    account_service.get_account(transfer.source_account_id)
    account_service.get_account(transfer.destination_account_id)

    transaction_service = TransactionService(account_service=account_service)

    debit = transaction_service.create_transaction(
        TransactionCreate(
            account_id=transfer.source_account_id,
            transaction_type="transfer_out",
            amount=transfer.amount,
            currency=transfer.currency,
            description=transfer.description
            or f"Transfer to account {transfer.destination_account_id}",
            reference_id=transfer.reference_id,
        )
    )

    credit = transaction_service.create_transaction(
        TransactionCreate(
            account_id=transfer.destination_account_id,
            transaction_type="transfer_in",
            amount=transfer.amount,
            currency=transfer.currency,
            description=transfer.description
            or f"Transfer from account {transfer.source_account_id}",
            reference_id=transfer.reference_id,
        )
    )

    logger.info(
        "transfer_completed",
        source=transfer.source_account_id,
        destination=transfer.destination_account_id,
        amount=transfer.amount,
        debit_id=debit.id,
        credit_id=credit.id,
    )

    return TransferResponse(
        transfer_id=str(uuid.uuid4()),
        source_account_id=transfer.source_account_id,
        destination_account_id=transfer.destination_account_id,
        amount=transfer.amount,
        currency=transfer.currency,
        status="completed",
        debit_transaction_id=debit.id,
        credit_transaction_id=credit.id,
    )
