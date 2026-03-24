from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.account import Account, AccountCreate
from app.models.transaction import Transaction, TransactionCreate


@pytest.fixture
def client() -> TestClient:
    """Synchronous test client for the FinCore Bank API.

    Uses raise_server_exceptions=False so 4xx/5xx responses are returned
    as normal responses rather than raising in the test body.
    """
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def sample_account() -> Account:
    """A fully-populated checking account fixture with a positive balance."""
    return Account(
        id=1,
        account_number="GB29NWBK60161331926819",
        account_type="checking",
        owner_name="Alice Johnson",
        balance=1500.00,  # float (deliberate gap - should be Decimal)
        currency="USD",
        is_active=True,
        created_at=datetime(2024, 1, 15, 9, 0, 0),
        updated_at=datetime(2024, 1, 15, 9, 0, 0),
    )


@pytest.fixture
def sample_savings_account() -> Account:
    """A savings account fixture for interest calculation tests."""
    return Account(
        id=2,
        account_number="GB82WEST12345698765432",
        account_type="savings",
        owner_name="Bob Martinez",
        balance=10000.00,
        currency="USD",
        is_active=True,
        created_at=datetime(2024, 2, 1, 10, 0, 0),
        updated_at=datetime(2024, 2, 1, 10, 0, 0),
    )


@pytest.fixture
def closed_account() -> Account:
    """A closed account with zero balance for negative-path tests."""
    return Account(
        id=3,
        account_number="GB33BUKB20201555555555",
        account_type="checking",
        owner_name="Charlie Evans",
        balance=0.00,
        currency="USD",
        is_active=False,
        created_at=datetime(2023, 6, 1, 9, 0, 0),
        updated_at=datetime(2024, 1, 1, 0, 0, 0),
    )


@pytest.fixture
def sample_transaction(sample_account: Account) -> Transaction:
    """A completed debit transaction fixture."""
    return Transaction(
        id=1,
        account_id=sample_account.id,
        transaction_type="debit",
        amount=50.00,
        currency="USD",
        description="ATM withdrawal - Main Street branch",
        status="completed",
        created_at=datetime(2024, 1, 15, 14, 30, 0),
        balance_after=1450.00,
    )


@pytest.fixture
def account_create_data() -> AccountCreate:
    """Valid AccountCreate payload for use in service-level tests."""
    return AccountCreate(
        account_number="GB29NWBK60161331926819",
        account_type="checking",
        owner_name="Carol White",
        initial_balance=1000.00,
        currency="USD",
    )
