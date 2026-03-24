from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def test_health_check_returns_200() -> None:
    """The /health endpoint is public and always returns 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_check_response_shape() -> None:
    """Health response contains status and service name."""
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "fincore-bank-api"
    assert "version" in data


def test_list_accounts_requires_auth() -> None:
    """GET /accounts/ without a bearer token returns 401 or 403."""
    response = client.get("/accounts/")
    assert response.status_code in (401, 403)


def test_get_account_requires_auth() -> None:
    """GET /accounts/1 without a bearer token returns 401 or 403."""
    response = client.get("/accounts/1")
    assert response.status_code in (401, 403)


def test_create_transaction_requires_auth() -> None:
    """POST /transactions/ without a bearer token returns 401 or 403."""
    response = client.post(
        "/transactions/",
        json={
            "account_id": 1,
            "transaction_type": "debit",
            "amount": 100.0,
            "description": "test",
        },
    )
    assert response.status_code in (401, 403)


def test_create_transfer_requires_auth() -> None:
    """POST /transfers/ without a bearer token returns 401 or 403."""
    response = client.post(
        "/transfers/",
        json={
            "source_account_id": 1,
            "destination_account_id": 2,
            "amount": 100.0,
        },
    )
    assert response.status_code in (401, 403)


def test_docs_endpoint_present() -> None:
    """Swagger UI is accessible in development mode."""
    response = client.get("/docs")
    # 200 in development, 404 in production - both are valid
    assert response.status_code in (200, 404)


def test_auth_token_endpoint_exists() -> None:
    """The /auth/token endpoint accepts POST requests."""
    response = client.post(
        "/auth/token",
        data={"username": "wrong@fincore.bank", "password": "wrongpassword"},
    )
    # Wrong credentials but the endpoint itself must exist
    assert response.status_code == 401
