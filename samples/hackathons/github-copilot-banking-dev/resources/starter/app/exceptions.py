from __future__ import annotations


class BankingError(Exception):
    """Base class for all FinCore Bank domain errors."""

    def __init__(self, message: str, error_code: str = "BANKING_ERROR") -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


class AccountNotFoundError(BankingError):
    """Raised when an account lookup returns no result."""

    def __init__(self, account_id: int | str) -> None:
        super().__init__(
            message=f"Account {account_id} not found",
            error_code="ACCOUNT_NOT_FOUND",
        )


class InsufficientFundsError(BankingError):
    """Raised when a debit or transfer would take an account below zero."""

    def __init__(self, account_id: int, requested: float, available: float) -> None:
        super().__init__(
            message=(
                f"Insufficient funds in account {account_id}: "
                f"requested {requested:.2f}, available {available:.2f}"
            ),
            error_code="INSUFFICIENT_FUNDS",
        )


class AccountClosedError(BankingError):
    """Raised when an operation is attempted on a closed account."""

    def __init__(self, account_id: int) -> None:
        super().__init__(
            message=f"Account {account_id} is closed and cannot be modified",
            error_code="ACCOUNT_CLOSED",
        )


class ValidationError(BankingError):
    """Raised when business-rule validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message=message, error_code="VALIDATION_ERROR")


class DuplicateAccountError(BankingError):
    """Raised when an account number is already in use."""

    def __init__(self, account_number: str) -> None:
        super().__init__(
            message=f"Account number {account_number} is already registered",
            error_code="DUPLICATE_ACCOUNT",
        )


class TransactionNotFoundError(BankingError):
    """Raised when a transaction lookup returns no result."""

    def __init__(self, transaction_id: int) -> None:
        super().__init__(
            message=f"Transaction {transaction_id} not found",
            error_code="TRANSACTION_NOT_FOUND",
        )
