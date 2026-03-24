from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import structlog

from app.exceptions import (
    AccountClosedError,
    InsufficientFundsError,
    TransactionNotFoundError,
    ValidationError,
)
from app.models.transaction import Transaction, TransactionCreate
from app.services.account_service import AccountService

logger = structlog.get_logger(__name__)

_transactions: Dict[int, Transaction] = {}
_next_id: int = 1

DEBIT_TYPES = {"debit", "transfer_out", "fee"}
CREDIT_TYPES = {"credit", "transfer_in", "interest"}


class TransactionService:
    """Business logic for transaction processing."""

    def __init__(self, account_service: AccountService | None = None) -> None:
        self.account_service = account_service or AccountService()

    def validate_transaction(
        self, account_id: int, amount: float, transaction_type: str
    ) -> None:
        """Check that a transaction is permissible before it is committed.

        Validates account status and available funds for debit-type transactions.
        """
        account = self.account_service.get_account(account_id)

        if not account.is_active:
            raise AccountClosedError(account_id)

        # BUG: float equality is not reliable - 0.1 + 0.2 == 0.3 is False in Python.
        # Zero-amount transactions should be caught by the Pydantic Field(gt=0)
        # constraint on TransactionCreate, but this defence-in-depth check is broken.
        if amount == 0.0:
            raise ValidationError("Transaction amount cannot be zero")

        if transaction_type in DEBIT_TYPES:
            # BUG: float subtraction can produce precision artifacts.
            # e.g. 0.1 + 0.2 - 0.3 yields 5.55e-17, not 0.0.
            # Should use Decimal arithmetic to be safe.
            remaining = account.balance - amount
            if remaining < 0:
                raise InsufficientFundsError(account_id, amount, account.balance)

    def create_transaction(self, data: TransactionCreate) -> Transaction:
        """Record a transaction and update the account balance atomically."""
        global _next_id

        self.validate_transaction(data.account_id, data.amount, data.transaction_type)

        account = self.account_service.get_account(data.account_id)

        if data.transaction_type in DEBIT_TYPES:
            new_balance = account.balance - data.amount
        elif data.transaction_type in CREDIT_TYPES:
            new_balance = account.balance + data.amount
        else:
            new_balance = account.balance

        self.account_service.update_balance(data.account_id, new_balance)

        transaction = Transaction(
            id=_next_id,
            account_id=data.account_id,
            transaction_type=data.transaction_type,
            amount=data.amount,
            currency=data.currency,
            description=data.description,
            reference_id=data.reference_id,
            status="completed",
            created_at=datetime.utcnow(),
            balance_after=new_balance,
        )
        _transactions[_next_id] = transaction
        _next_id += 1

        # Missing: audit log entry linking transaction to the requesting user
        # (gap for challenge-06)
        logger.info(
            "transaction_created",
            transaction_id=transaction.id,
            account_id=data.account_id,
            type=data.transaction_type,
            amount=data.amount,
        )
        return transaction

    def get_transaction(self, transaction_id: int) -> Transaction:
        """Retrieve a single transaction by ID."""
        transaction = _transactions.get(transaction_id)
        if transaction is None:
            raise TransactionNotFoundError(transaction_id)
        return transaction

    def get_transactions(self, account_id: int) -> List[Transaction]:
        """Return all transactions for a given account, most recent first."""
        account_transactions = [
            t for t in _transactions.values() if t.account_id == account_id
        ]
        return sorted(account_transactions, key=lambda t: t.created_at, reverse=True)
