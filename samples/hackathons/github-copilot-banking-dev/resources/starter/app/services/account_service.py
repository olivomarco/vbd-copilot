from __future__ import annotations

from datetime import datetime
from typing import Dict, List

import structlog

from app.exceptions import (
    AccountClosedError,
    AccountNotFoundError,
    DuplicateAccountError,
    InsufficientFundsError,
    ValidationError,
)
from app.models.account import Account, AccountCreate, AccountUpdate

logger = structlog.get_logger(__name__)

# In-memory store. In production this would delegate to a SQLAlchemy repository.
_store: Dict[int, Account] = {}
_next_id: int = 1


class AccountService:
    """Business logic for account lifecycle management."""

    def get_account(self, account_id: int) -> Account:
        """Retrieve a single account by ID. Raises AccountNotFoundError if absent."""
        account = _store.get(account_id)
        if account is None:
            raise AccountNotFoundError(account_id)
        # Missing: audit log of read access for sensitive accounts
        return account

    def list_accounts(self, active_only: bool = True) -> List[Account]:
        """Return all accounts, optionally filtering to active ones only."""
        accounts = list(_store.values())
        if active_only:
            accounts = [a for a in accounts if a.is_active]
        return accounts

    def create_account(self, data: AccountCreate) -> Account:
        """Open a new account. Raises DuplicateAccountError if account_number exists."""
        global _next_id

        for existing in _store.values():
            if existing.account_number == data.account_number:
                raise DuplicateAccountError(data.account_number)

        now = datetime.utcnow()
        account = Account(
            id=_next_id,
            account_number=data.account_number,
            account_type=data.account_type,
            owner_name=data.owner_name,
            balance=data.initial_balance,  # float (deliberate gap - should be Decimal)
            currency=data.currency,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        _store[_next_id] = account
        _next_id += 1

        # Missing: structured audit log entry for account creation (gap for challenge-06)
        logger.info(
            "account_created",
            account_id=account.id,
            account_number=account.account_number,
            owner=account.owner_name,
        )
        return account

    def update_account(self, account_id: int, data: AccountUpdate) -> Account:
        """Apply a partial update to non-financial account fields."""
        account = self.get_account(account_id)
        if not account.is_active:
            raise AccountClosedError(account_id)

        update_data = data.model_dump(exclude_none=True)
        update_data["updated_at"] = datetime.utcnow()
        updated = account.model_copy(update=update_data)
        _store[account_id] = updated

        # Missing: audit log entry with before/after diff (gap for challenge-06)
        return updated

    def update_balance(self, account_id: int, new_balance: float) -> Account:
        """Overwrite the balance field. Called by TransactionService after validation."""
        account = self.get_account(account_id)
        if not account.is_active:
            raise AccountClosedError(account_id)

        updated = account.model_copy(
            update={"balance": new_balance, "updated_at": datetime.utcnow()}
        )
        _store[account_id] = updated

        # Missing: audit log with previous balance and new balance (gap for challenge-06)
        return updated

    def close_account(self, account_id: int) -> Account:
        """Mark an account as inactive. Balance must be zero before closing."""
        account = self.get_account(account_id)
        if not account.is_active:
            raise AccountClosedError(account_id)

        # BUG: float equality comparison is unreliable for monetary values.
        # 0.1 + 0.2 - 0.3 does not equal 0.0 in IEEE 754 floating point.
        # This should use Decimal comparison or an epsilon tolerance check.
        if account.balance != 0.0:
            raise ValidationError(
                f"Cannot close account {account_id}: "
                f"balance must be zero (current: {account.balance})"
            )

        updated = account.model_copy(
            update={"is_active": False, "updated_at": datetime.utcnow()}
        )
        _store[account_id] = updated

        # Missing: audit log entry for account closure (gap for challenge-06)
        logger.info("account_closed", account_id=account_id)
        return updated
