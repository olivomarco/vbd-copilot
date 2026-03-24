"""Tests for services/billing_api.py -- billing API client.

Covers bill reference validation, circuit breaker state transitions,
HTTP retry logic, OAuth token caching, and response parsing.
"""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.schemas import BillData
from app.services.billing_api import (
    BillingAPIClient,
    BillingAPIError,
    CircuitState,
    _BILL_REF_PATTERN,
    _CB_FAILURE_THRESHOLD,
    _CB_RECOVERY_TIMEOUT,
)


@pytest.fixture
def client(mock_settings: MagicMock, mock_credential: MagicMock) -> BillingAPIClient:
    """Create a BillingAPIClient with mocked dependencies."""
    with patch("app.services.billing_api.httpx.AsyncClient") as mock_http_cls:
        mock_http = AsyncMock()
        mock_http.get = AsyncMock()
        mock_http.post = AsyncMock()
        mock_http.aclose = AsyncMock()
        mock_http_cls.return_value = mock_http

        api_client = BillingAPIClient(mock_settings, mock_credential)
        api_client._http_client = mock_http
        yield api_client


class TestBillRefValidation:
    """Validate bill reference format checking."""

    def test_bill_ref_validation_valid_alphanumeric(self) -> None:
        """Standard alphanumeric references (8-20 chars) pass."""
        assert _BILL_REF_PATTERN.match("BILL2024001")
        assert _BILL_REF_PATTERN.match("BILL-2024-001")
        assert _BILL_REF_PATTERN.match("ABC12345")

    def test_bill_ref_validation_valid_boundary(self) -> None:
        """Exactly 8 and 20 character references pass."""
        assert _BILL_REF_PATTERN.match("A" * 8)
        assert _BILL_REF_PATTERN.match("B" * 20)

    def test_bill_ref_validation_invalid_too_short(self) -> None:
        """References shorter than 8 chars are rejected."""
        assert not _BILL_REF_PATTERN.match("SHORT")
        assert not _BILL_REF_PATTERN.match("AB12345")

    def test_bill_ref_validation_invalid_too_long(self) -> None:
        """References longer than 20 chars are rejected."""
        assert not _BILL_REF_PATTERN.match("A" * 21)

    def test_bill_ref_validation_invalid_special_chars(self) -> None:
        """References with special characters (other than hyphen) are rejected."""
        assert not _BILL_REF_PATTERN.match("BILL@2024!")
        assert not _BILL_REF_PATTERN.match("BILL 2024 001")

    def test_validate_bill_ref_method(self, client: BillingAPIClient) -> None:
        """The _validate_bill_ref static method works correctly."""
        assert client._validate_bill_ref("BILL-2024-001") is True
        assert client._validate_bill_ref("short") is False


class TestGetBill:
    """Test the get_bill public API."""

    @pytest.mark.asyncio
    async def test_get_bill_success(self, client: BillingAPIClient) -> None:
        """Successful API response returns BillData."""
        # Mock token retrieval
        client._get_access_token = AsyncMock(return_value="fake-token")

        # Mock successful bill response
        bill_response = {
            "total_amount": 125.60,
            "currency": "EUR",
            "billing_period_start": "2024-01-01",
            "billing_period_end": "2024-01-31",
            "consumption_kwh": 180.0,
            "payment_status": "pagata",
            "due_date": "2024-02-15",
            "line_items": [
                {"description": "Quota fissa", "amount": 25.00},
            ],
        }
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = bill_response
        mock_response.raise_for_status = MagicMock()
        client._http_client.get.return_value = mock_response

        result = await client.get_bill("BILL-2024-001")

        assert result is not None
        assert isinstance(result, BillData)
        assert result.bill_ref == "BILL-2024-001"
        assert result.total_amount == 125.60
        assert result.payment_status == "pagata"
        assert len(result.line_items) == 1

    @pytest.mark.asyncio
    async def test_get_bill_not_found(self, client: BillingAPIClient) -> None:
        """404 response returns None."""
        client._get_access_token = AsyncMock(return_value="fake-token")

        mock_response = MagicMock()
        mock_response.status_code = 404
        client._http_client.get.return_value = mock_response

        result = await client.get_bill("BILL-9999-999")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_bill_invalid_ref(self, client: BillingAPIClient) -> None:
        """Invalid bill reference returns None without making API call."""
        result = await client.get_bill("bad")
        assert result is None
        client._http_client.get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_get_bill_timeout(self, client: BillingAPIClient) -> None:
        """Timeout results in BillingAPIError."""
        client._get_access_token = AsyncMock(return_value="fake-token")
        client._http_client.get.side_effect = httpx.TimeoutException("timed out")

        with pytest.raises(BillingAPIError):
            await client.get_bill("BILL-2024-001")


class TestRetry:
    """Test HTTP retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_500(self, client: BillingAPIClient) -> None:
        """500 error triggers retry; second attempt succeeds."""
        client._get_access_token = AsyncMock(return_value="fake-token")

        # First call: 500 error; second call: success
        error_response = MagicMock()
        error_response.status_code = 500
        error_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error",
            request=MagicMock(),
            response=error_response,
        )

        success_response = MagicMock()
        success_response.status_code = 200
        success_response.json.return_value = {
            "total_amount": 50.0,
            "billing_period_start": "2024-01-01",
            "billing_period_end": "2024-01-31",
        }
        success_response.raise_for_status = MagicMock()

        client._http_client.get.side_effect = [error_response, success_response]

        # Patch asyncio.sleep to avoid actual delay
        with patch("app.services.billing_api.asyncio.sleep", new_callable=AsyncMock):
            result = await client.get_bill("BILL-2024-001")

        assert result is not None
        assert result.total_amount == 50.0
        assert client._http_client.get.await_count == 2


class TestCircuitBreaker:
    """Test circuit breaker state transitions."""

    def test_initial_state_is_closed(self, client: BillingAPIClient) -> None:
        """Circuit breaker starts in CLOSED state."""
        assert client._cb_state == CircuitState.CLOSED

    def test_circuit_breaker_opens(self, client: BillingAPIClient) -> None:
        """5 consecutive failures transition to OPEN."""
        for _ in range(_CB_FAILURE_THRESHOLD):
            client._on_failure()

        assert client._cb_state == CircuitState.OPEN
        assert client._cb_failure_count == _CB_FAILURE_THRESHOLD

    def test_circuit_breaker_open_rejects_calls(self, client: BillingAPIClient) -> None:
        """OPEN circuit raises BillingAPIError immediately."""
        for _ in range(_CB_FAILURE_THRESHOLD):
            client._on_failure()

        with pytest.raises(BillingAPIError, match="Circuit breaker OPEN"):
            client._check_circuit_breaker()

    def test_circuit_breaker_half_open(self, client: BillingAPIClient) -> None:
        """After cooldown period, circuit transitions to HALF_OPEN."""
        for _ in range(_CB_FAILURE_THRESHOLD):
            client._on_failure()

        assert client._cb_state == CircuitState.OPEN

        # Simulate time passing beyond recovery timeout
        client._cb_last_failure_time = time.monotonic() - _CB_RECOVERY_TIMEOUT - 1
        client._check_circuit_breaker()

        assert client._cb_state == CircuitState.HALF_OPEN

    def test_circuit_breaker_closes_on_success(self, client: BillingAPIClient) -> None:
        """Successful call after HALF_OPEN transitions to CLOSED."""
        client._cb_state = CircuitState.HALF_OPEN
        client._cb_failure_count = 3

        client._on_success()

        assert client._cb_state == CircuitState.CLOSED
        assert client._cb_failure_count == 0

    def test_failure_below_threshold_stays_closed(self, client: BillingAPIClient) -> None:
        """Fewer than threshold failures keeps circuit CLOSED."""
        for _ in range(_CB_FAILURE_THRESHOLD - 1):
            client._on_failure()

        assert client._cb_state == CircuitState.CLOSED


class TestOAuthTokenCaching:
    """Test OAuth token acquisition and caching."""

    @pytest.mark.asyncio
    async def test_oauth_token_caching(self, client: BillingAPIClient) -> None:
        """Token is reused when not expired."""
        client._access_token = "cached-token"
        client._token_expires_at = time.monotonic() + 3600  # 1 hour from now

        token = await client._get_access_token()
        assert token == "cached-token"
        # No HTTP call should have been made
        client._http_client.post.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_oauth_token_refresh(self, client: BillingAPIClient) -> None:
        """Token is refreshed when near expiry."""
        client._access_token = "old-token"
        client._token_expires_at = time.monotonic() - 10  # Already expired

        # Mock Key Vault secret retrieval
        client._client_secret = "test-secret"

        # Mock token endpoint response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new-token",
            "expires_in": 3600,
        }
        mock_response.raise_for_status = MagicMock()
        client._http_client.post.return_value = mock_response

        token = await client._get_access_token()
        assert token == "new-token"
        client._http_client.post.assert_awaited_once()


class TestResponseParsing:
    """Test _parse_response static method."""

    def test_parse_empty_response(self) -> None:
        """Empty dict returns None."""
        result = BillingAPIClient._parse_response({}, "BILL-001")
        assert result is None

    def test_parse_full_response(self) -> None:
        """Complete response data produces correct BillData."""
        data = {
            "total_amount": 200.50,
            "currency": "EUR",
            "billing_period_start": "2024-02-01",
            "billing_period_end": "2024-02-28",
            "consumption_kwh": 250.0,
            "consumption_smc": 60.0,
            "tariff_code": "TD-BIOR",
            "tariff_name": "Tariffa Bioraria",
            "payment_status": "da pagare",
            "due_date": "2024-03-15",
            "line_items": [
                {"description": "Quota fissa", "amount": 30.0, "unit": "EUR", "quantity": 1},
                {"description": "Energia", "amount": 80.0},
            ],
        }
        result = BillingAPIClient._parse_response(data, "BILL-2024-002")
        assert result is not None
        assert result.bill_ref == "BILL-2024-002"
        assert result.total_amount == 200.50
        assert len(result.line_items) == 2
        assert result.line_items[0].description == "Quota fissa"
        assert result.line_items[1].unit is None

    def test_parse_response_missing_optional_fields(self) -> None:
        """Response with only required fields still parses."""
        data = {
            "total_amount": 50.0,
            "billing_period_start": "2024-01-01",
            "billing_period_end": "2024-01-31",
        }
        result = BillingAPIClient._parse_response(data, "BILL-BASIC")
        assert result is not None
        assert result.consumption_kwh is None
        assert result.tariff_code is None
        assert result.line_items == []


class TestHealthCheck:
    """Test the billing API health probe."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, client: BillingAPIClient) -> None:
        """Healthy endpoint returns True."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        client._http_client.get.return_value = mock_resp

        result = await client.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_server_error(self, client: BillingAPIClient) -> None:
        """500 response returns False."""
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        client._http_client.get.return_value = mock_resp

        result = await client.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_health_check_exception(self, client: BillingAPIClient) -> None:
        """Connection error returns False."""
        client._http_client.get.side_effect = Exception("Connection refused")

        result = await client.health_check()
        assert result is False


class TestClose:
    """Test client lifecycle."""

    @pytest.mark.asyncio
    async def test_close(self, client: BillingAPIClient) -> None:
        """close() calls aclose on the HTTP client."""
        await client.close()
        client._http_client.aclose.assert_awaited_once()
