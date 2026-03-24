"""CUSTOMER_NAME billing API client with circuit breaker and token caching.

Retrieves structured bill data for a given bill reference via OAuth 2.0
client-credentials flow. The client secret is fetched from Azure Key Vault
and cached in memory.

Resilience features:
  - Circuit breaker (5 consecutive failures -> open, half-open after 30s)
  - 5-second timeout per request
  - 1 retry with 500ms backoff
  - Bill reference format validation
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from enum import Enum
from typing import Optional

import httpx
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets.aio import SecretClient as AsyncSecretClient

from app.config import Settings
from app.models.schemas import BillData, LineItem

logger = logging.getLogger(__name__)

# Bill reference format: alphanumeric, 8-20 characters
_BILL_REF_PATTERN = re.compile(r"^[A-Za-z0-9\-]{8,20}$")

# Circuit-breaker settings
_CB_FAILURE_THRESHOLD = 5
_CB_RECOVERY_TIMEOUT = 30.0  # seconds

# HTTP settings
_REQUEST_TIMEOUT = 5.0  # seconds
_RETRY_BACKOFF = 0.5  # seconds
_MAX_RETRIES = 1

# Token cache window
_TOKEN_REFRESH_MARGIN = 300  # 5 minutes before expiry


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BillingAPIError(Exception):
    """Raised when the billing API call fails after retries."""


class BillingAPIClient:
    """Async client for the CUSTOMER_NAME billing API."""

    def __init__(
        self,
        settings: Settings,
        credential: DefaultAzureCredential,
    ) -> None:
        self._base_url = settings.billing_api_base_url.rstrip("/")
        self._client_id = settings.billing_api_client_id
        self._scope = settings.billing_api_scope
        self._key_vault_url = settings.key_vault_url

        self._credential = credential
        self._http_client = httpx.AsyncClient(timeout=_REQUEST_TIMEOUT)

        # Client secret cache (from Key Vault)
        self._client_secret: Optional[str] = None

        # OAuth token cache
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0.0

        # Circuit breaker state
        self._cb_state = CircuitState.CLOSED
        self._cb_failure_count = 0
        self._cb_last_failure_time: float = 0.0

        logger.info("BillingAPIClient initialised (base_url=%s)", self._base_url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_bill(self, bill_ref: str) -> Optional[BillData]:
        """Fetch billing data for the given bill reference.

        Args:
            bill_ref: Alphanumeric bill reference (8-20 chars).

        Returns:
            BillData if found, None if the reference is invalid or not found.

        Raises:
            BillingAPIError: If the API call fails after retries.
        """
        if not self._validate_bill_ref(bill_ref):
            logger.warning("Invalid bill reference format: %s", bill_ref)
            return None

        self._check_circuit_breaker()

        try:
            token = await self._get_access_token()
            response = await self._call_with_retry(bill_ref, token)
            self._on_success()
            return self._parse_response(response, bill_ref)
        except BillingAPIError:
            raise
        except Exception as exc:
            self._on_failure()
            logger.error("Billing API call failed for ref=%s: %s", bill_ref, exc)
            raise BillingAPIError(f"Failed to retrieve bill {bill_ref}") from exc

    async def health_check(self) -> bool:
        """Return True if the billing API base URL is reachable."""
        try:
            response = await self._http_client.get(
                f"{self._base_url}/health",
                timeout=3.0,
            )
            return response.status_code < 500
        except Exception:
            logger.warning("Billing API health check failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # OAuth 2.0 client credentials
    # ------------------------------------------------------------------

    async def _get_client_secret(self) -> str:
        """Retrieve (and cache) the client secret from Key Vault."""
        if self._client_secret is not None:
            return self._client_secret

        async with AsyncSecretClient(
            vault_url=self._key_vault_url,
            credential=self._credential,
        ) as kv_client:
            secret = await kv_client.get_secret("billing-api-client-secret")
            self._client_secret = secret.value
            logger.info("Billing API client secret retrieved from Key Vault")
            return self._client_secret  # type: ignore[return-value]

    async def _get_access_token(self) -> str:
        """Obtain an OAuth 2.0 access token using client credentials flow.

        Tokens are cached and refreshed 5 minutes before expiry.
        """
        now = time.monotonic()
        if self._access_token and now < self._token_expires_at - _TOKEN_REFRESH_MARGIN:
            return self._access_token

        client_secret = await self._get_client_secret()

        # Token endpoint (standard Microsoft Entra ID v2)
        token_url = f"{self._base_url}/oauth2/v2.0/token"

        payload = {
            "grant_type": "client_credentials",
            "client_id": self._client_id,
            "client_secret": client_secret,
            "scope": self._scope,
        }

        response = await self._http_client.post(token_url, data=payload)
        response.raise_for_status()
        data = response.json()

        self._access_token = data["access_token"]
        expires_in = int(data.get("expires_in", 3600))
        self._token_expires_at = now + expires_in

        logger.debug("Billing API token refreshed, expires_in=%ds", expires_in)
        return self._access_token  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # HTTP call with retry
    # ------------------------------------------------------------------

    async def _call_with_retry(
        self,
        bill_ref: str,
        token: str,
    ) -> dict:
        """Call the billing API with one retry on transient failures."""
        url = f"{self._base_url}/api/v1/bills/{bill_ref}"
        headers = {"Authorization": f"Bearer {token}"}
        last_exc: Optional[Exception] = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = await self._http_client.get(url, headers=headers)
                if response.status_code == 404:
                    logger.info("Bill not found: %s", bill_ref)
                    return {}
                response.raise_for_status()
                return response.json()
            except (httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < _MAX_RETRIES:
                    logger.warning(
                        "Billing API attempt %d failed, retrying in %.1fs: %s",
                        attempt + 1,
                        _RETRY_BACKOFF,
                        exc,
                    )
                    await asyncio.sleep(_RETRY_BACKOFF)

        raise BillingAPIError(
            f"Billing API failed after {_MAX_RETRIES + 1} attempts"
        ) from last_exc

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_response(data: dict, bill_ref: str) -> Optional[BillData]:
        """Parse the raw API response into a BillData model."""
        if not data:
            return None

        line_items = [
            LineItem(
                description=item.get("description", ""),
                amount=float(item.get("amount", 0)),
                unit=item.get("unit"),
                quantity=item.get("quantity"),
            )
            for item in data.get("line_items", [])
        ]

        return BillData(
            bill_ref=bill_ref,
            total_amount=float(data.get("total_amount", 0)),
            currency=data.get("currency", "EUR"),
            billing_period_start=data.get("billing_period_start", ""),
            billing_period_end=data.get("billing_period_end", ""),
            consumption_kwh=data.get("consumption_kwh"),
            consumption_smc=data.get("consumption_smc"),
            tariff_code=data.get("tariff_code"),
            tariff_name=data.get("tariff_name"),
            line_items=line_items,
            payment_status=data.get("payment_status"),
            due_date=data.get("due_date"),
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_bill_ref(bill_ref: str) -> bool:
        """Validate the format of a bill reference string."""
        return bool(_BILL_REF_PATTERN.match(bill_ref))

    # ------------------------------------------------------------------
    # Circuit breaker
    # ------------------------------------------------------------------

    def _check_circuit_breaker(self) -> None:
        """Raise if the circuit is open (and not yet ready to half-open)."""
        if self._cb_state == CircuitState.OPEN:
            elapsed = time.monotonic() - self._cb_last_failure_time
            if elapsed >= _CB_RECOVERY_TIMEOUT:
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                self._cb_state = CircuitState.HALF_OPEN
            else:
                raise BillingAPIError(
                    f"Circuit breaker OPEN -- retry after {_CB_RECOVERY_TIMEOUT - elapsed:.0f}s"
                )

    def _on_success(self) -> None:
        """Reset failure counter on a successful call."""
        if self._cb_state != CircuitState.CLOSED:
            logger.info("Circuit breaker CLOSED after successful call")
        self._cb_state = CircuitState.CLOSED
        self._cb_failure_count = 0

    def _on_failure(self) -> None:
        """Increment failure counter; trip to OPEN if threshold reached."""
        self._cb_failure_count += 1
        self._cb_last_failure_time = time.monotonic()
        if self._cb_failure_count >= _CB_FAILURE_THRESHOLD:
            self._cb_state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker OPEN after %d consecutive failures",
                self._cb_failure_count,
            )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._http_client.aclose()
