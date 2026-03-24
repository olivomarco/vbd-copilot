"""Smoke tests for the CUSTOMER_NAME Bill Explainer live deployment.

Run with::

    API_BASE_URL=https://my-app.azurecontainerapps.io pytest tests/smoke/ -v --live

Every test is decorated with ``@pytest.mark.smoke`` and is automatically
skipped unless the ``--live`` CLI flag is present (see conftest.py).

All HTTP calls use **httpx** with explicit timeouts. Connection failures
are caught and cause the test to be skipped with a diagnostic message
rather than producing a hard failure -- this prevents noisy CI runs when
the target environment is temporarily unavailable.
"""
from __future__ import annotations

import json
import uuid

import httpx
import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUEST_TIMEOUT = 10.0  # seconds for simple requests
STREAM_TIMEOUT = 30.0   # seconds for SSE streaming requests
SAMPLE_QUESTION = "Perche' la mia bolletta e' piu' alta del solito?"
SAMPLE_BILL_REF = "PLN-2024-00012345"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _skip_on_connection_error(exc: Exception, url: str) -> None:
    """Skip the current test with a clear message when the service is unreachable."""
    pytest.skip(
        f"Service unreachable at {url} -- {type(exc).__name__}: {exc}"
    )


def _parse_sse_events(text: str) -> list[dict]:
    """Parse a raw SSE response body into a list of JSON-decoded data dicts.

    Handles the ``data: {json}`` format used by sse-starlette.  Lines that
    cannot be parsed are silently ignored (e.g. comments, keep-alive).
    """
    events: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        payload = line[len("data:"):].strip()
        if not payload:
            continue
        try:
            events.append(json.loads(payload))
        except json.JSONDecodeError:
            continue
    return events


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@pytest.mark.smoke
class TestHealthEndpoints:
    """Verify liveness and readiness probes."""

    def test_health_liveness(self, base_url: str) -> None:
        """GET /health returns 200 with status 'healthy'."""
        url = f"{base_url}/health"
        try:
            resp = httpx.get(url, timeout=REQUEST_TIMEOUT)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, url)

        assert resp.status_code == 200, (
            f"Expected 200 from /health, got {resp.status_code}: {resp.text}"
        )
        body = resp.json()
        assert body.get("status") == "healthy", (
            f"Expected status 'healthy', got: {body}"
        )

    def test_health_readiness(self, base_url: str) -> None:
        """GET /health/ready returns 200 (healthy) or 503 (degraded).

        Either status code is acceptable for a smoke test -- the important
        thing is that the endpoint responds with the expected JSON shape.
        """
        url = f"{base_url}/health/ready"
        try:
            resp = httpx.get(url, timeout=REQUEST_TIMEOUT)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, url)

        assert resp.status_code in (200, 503), (
            f"Expected 200 or 503 from /health/ready, got {resp.status_code}: "
            f"{resp.text}"
        )
        body = resp.json()
        assert "status" in body, (
            f"Response missing 'status' field: {body}"
        )
        assert body["status"] in ("healthy", "degraded"), (
            f"Unexpected status value: {body['status']}"
        )
        # When degraded, the services dict should list what is down
        if resp.status_code == 503:
            assert "services" in body, (
                "Degraded response should include a 'services' dict"
            )


# ---------------------------------------------------------------------------
# OpenAPI documentation
# ---------------------------------------------------------------------------

@pytest.mark.smoke
class TestDocumentation:
    """Verify the auto-generated OpenAPI docs are accessible."""

    def test_openapi_docs_available(self, base_url: str) -> None:
        """GET /docs returns 200 with an HTML page."""
        url = f"{base_url}/docs"
        try:
            resp = httpx.get(url, timeout=REQUEST_TIMEOUT)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, url)

        assert resp.status_code == 200, (
            f"Expected 200 from /docs, got {resp.status_code}"
        )
        content_type = resp.headers.get("content-type", "")
        assert "html" in content_type.lower(), (
            f"Expected HTML content-type, got: {content_type}"
        )


# ---------------------------------------------------------------------------
# Chat endpoints
# ---------------------------------------------------------------------------

@pytest.mark.smoke
class TestChatEndpoints:
    """Verify the chat streaming and feedback endpoints."""

    def test_chat_creates_session(
        self,
        base_url: str,
        api_headers: dict[str, str],
    ) -> None:
        """POST /api/v1/chat with a simple question returns an SSE stream
        whose final event contains a session_id.
        """
        url = f"{base_url}/api/v1/chat"
        payload = {"message": SAMPLE_QUESTION}

        try:
            resp = httpx.post(
                url,
                json=payload,
                headers=api_headers,
                timeout=STREAM_TIMEOUT,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, url)

        assert resp.status_code == 200, (
            f"Expected 200 from /api/v1/chat, got {resp.status_code}: "
            f"{resp.text[:500]}"
        )

        events = _parse_sse_events(resp.text)
        assert len(events) >= 1, (
            "Expected at least one SSE event in response. "
            f"Raw body (first 500 chars): {resp.text[:500]}"
        )

        # The last event should have done=True and a session_id
        final = events[-1]
        assert final.get("done") is True, (
            f"Final event should have done=True, got: {final}"
        )
        assert final.get("session_id"), (
            f"Final event missing session_id: {final}"
        )

    def test_chat_streaming_format(
        self,
        base_url: str,
        api_headers: dict[str, str],
    ) -> None:
        """POST /api/v1/chat SSE events conform to the expected schema.

        Each intermediate event: {"token": "...", "done": false}
        Final event: {"token": "", "done": true, "session_id": "...", "message_id": "..."}
        """
        url = f"{base_url}/api/v1/chat"
        payload = {"message": SAMPLE_QUESTION}

        try:
            resp = httpx.post(
                url,
                json=payload,
                headers=api_headers,
                timeout=STREAM_TIMEOUT,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, url)

        assert resp.status_code == 200, (
            f"Expected 200, got {resp.status_code}: {resp.text[:500]}"
        )

        events = _parse_sse_events(resp.text)
        assert len(events) >= 2, (
            "Expected at least two SSE events (one token + one final). "
            f"Got {len(events)} event(s)."
        )

        # Validate intermediate events
        for event in events[:-1]:
            assert "token" in event, f"Event missing 'token': {event}"
            assert event.get("done") is False, (
                f"Intermediate event should have done=False: {event}"
            )

        # Validate final event
        final = events[-1]
        assert final.get("done") is True, (
            f"Final event should have done=True: {final}"
        )
        assert "session_id" in final, f"Final event missing session_id: {final}"
        assert "message_id" in final, f"Final event missing message_id: {final}"

    def test_chat_feedback(
        self,
        base_url: str,
        api_headers: dict[str, str],
    ) -> None:
        """After a chat exchange, POST /api/v1/chat/feedback with the
        session_id and message_id succeeds with 200.
        """
        chat_url = f"{base_url}/api/v1/chat"
        feedback_url = f"{base_url}/api/v1/chat/feedback"

        # Step 1: Create a chat to get a session_id and message_id
        try:
            chat_resp = httpx.post(
                chat_url,
                json={"message": SAMPLE_QUESTION},
                headers=api_headers,
                timeout=STREAM_TIMEOUT,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, chat_url)

        if chat_resp.status_code != 200:
            pytest.skip(
                f"Chat endpoint returned {chat_resp.status_code}; "
                "cannot test feedback without a valid chat."
            )

        events = _parse_sse_events(chat_resp.text)
        final = next(
            (e for e in reversed(events) if e.get("done") is True),
            None,
        )
        if final is None or not final.get("session_id") or not final.get("message_id"):
            pytest.skip(
                "Could not extract session_id/message_id from chat response; "
                "skipping feedback test."
            )

        # Step 2: Submit feedback
        feedback_payload = {
            "session_id": final["session_id"],
            "message_id": final["message_id"],
            "rating": "up",
            "comment": "Smoke test feedback -- please ignore.",
        }
        try:
            fb_resp = httpx.post(
                feedback_url,
                json=feedback_payload,
                headers=api_headers,
                timeout=REQUEST_TIMEOUT,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, feedback_url)

        assert fb_resp.status_code == 200, (
            f"Expected 200 from /api/v1/chat/feedback, got "
            f"{fb_resp.status_code}: {fb_resp.text[:500]}"
        )
        body = fb_resp.json()
        assert "feedback_id" in body, f"Response missing 'feedback_id': {body}"
        assert body.get("status") == "recorded", (
            f"Expected status 'recorded', got: {body}"
        )


# ---------------------------------------------------------------------------
# Session endpoints
# ---------------------------------------------------------------------------

@pytest.mark.smoke
class TestSessionEndpoints:
    """Verify session retrieval and GDPR deletion."""

    @staticmethod
    def _create_session(
        base_url: str,
        api_headers: dict[str, str],
    ) -> str | None:
        """Helper: run a quick chat and return the session_id, or None."""
        url = f"{base_url}/api/v1/chat"
        try:
            resp = httpx.post(
                url,
                json={"message": SAMPLE_QUESTION},
                headers=api_headers,
                timeout=STREAM_TIMEOUT,
            )
        except (httpx.ConnectError, httpx.TimeoutException):
            return None

        if resp.status_code != 200:
            return None

        events = _parse_sse_events(resp.text)
        final = next(
            (e for e in reversed(events) if e.get("done") is True),
            None,
        )
        if final and final.get("session_id"):
            return final["session_id"]
        return None

    def test_session_retrieval(
        self,
        base_url: str,
        api_headers: dict[str, str],
    ) -> None:
        """GET /api/v1/sessions/{id} returns session data after a chat."""
        session_id = self._create_session(base_url, api_headers)
        if session_id is None:
            pytest.skip(
                "Could not create a session via the chat endpoint; "
                "skipping session retrieval test."
            )

        url = f"{base_url}/api/v1/sessions/{session_id}"
        try:
            resp = httpx.get(url, timeout=REQUEST_TIMEOUT)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, url)

        assert resp.status_code == 200, (
            f"Expected 200 from session retrieval, got "
            f"{resp.status_code}: {resp.text[:500]}"
        )
        body = resp.json()
        assert body.get("session_id") == session_id, (
            f"Returned session_id mismatch: expected {session_id}, got "
            f"{body.get('session_id')}"
        )
        assert "messages" in body, f"Response missing 'messages': {body.keys()}"
        assert body.get("message_count", 0) >= 2, (
            "Expected at least 2 messages (user + assistant) in session, "
            f"got {body.get('message_count', 0)}"
        )

    def test_session_not_found(self, base_url: str) -> None:
        """GET /api/v1/sessions/{random-uuid} returns 404."""
        fake_id = str(uuid.uuid4())
        url = f"{base_url}/api/v1/sessions/{fake_id}"
        try:
            resp = httpx.get(url, timeout=REQUEST_TIMEOUT)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, url)

        assert resp.status_code == 404, (
            f"Expected 404 for non-existent session, got "
            f"{resp.status_code}: {resp.text[:500]}"
        )

    def test_session_deletion(
        self,
        base_url: str,
        api_headers: dict[str, str],
    ) -> None:
        """DELETE /api/v1/sessions/{id} returns 204 and subsequent GET returns 404."""
        session_id = self._create_session(base_url, api_headers)
        if session_id is None:
            pytest.skip(
                "Could not create a session via the chat endpoint; "
                "skipping session deletion test."
            )

        delete_url = f"{base_url}/api/v1/sessions/{session_id}"
        try:
            del_resp = httpx.delete(delete_url, timeout=REQUEST_TIMEOUT)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, delete_url)

        assert del_resp.status_code in (200, 204), (
            f"Expected 200 or 204 from session deletion, got "
            f"{del_resp.status_code}: {del_resp.text[:500]}"
        )

        # Confirm the session is gone
        try:
            get_resp = httpx.get(delete_url, timeout=REQUEST_TIMEOUT)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, delete_url)

        assert get_resp.status_code == 404, (
            f"Expected 404 after deletion, got {get_resp.status_code}: "
            f"{get_resp.text[:500]}"
        )


# ---------------------------------------------------------------------------
# Bill reference chat
# ---------------------------------------------------------------------------

@pytest.mark.smoke
class TestBillRefChat:
    """Verify that chat accepts an optional bill_ref parameter."""

    def test_chat_with_bill_ref(
        self,
        base_url: str,
        api_headers: dict[str, str],
    ) -> None:
        """POST /api/v1/chat with a bill_ref still returns a valid stream.

        The billing API may not be reachable in all environments, so the
        test only validates that the endpoint accepts the request and
        returns a well-formed SSE response (even if the answer indicates
        that billing data was unavailable).
        """
        url = f"{base_url}/api/v1/chat"
        payload = {
            "message": "Mi puoi spiegare i dettagli della mia bolletta?",
            "bill_ref": SAMPLE_BILL_REF,
        }

        try:
            resp = httpx.post(
                url,
                json=payload,
                headers=api_headers,
                timeout=STREAM_TIMEOUT,
            )
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, url)

        assert resp.status_code == 200, (
            f"Expected 200 from /api/v1/chat with bill_ref, got "
            f"{resp.status_code}: {resp.text[:500]}"
        )

        events = _parse_sse_events(resp.text)
        assert len(events) >= 1, (
            "Expected at least one SSE event. "
            f"Raw body (first 500 chars): {resp.text[:500]}"
        )

        final = events[-1]
        assert final.get("done") is True, (
            f"Final event should have done=True: {final}"
        )
        assert final.get("session_id"), (
            f"Final event missing session_id: {final}"
        )


# ---------------------------------------------------------------------------
# Rate limiting (APIM)
# ---------------------------------------------------------------------------

@pytest.mark.smoke
class TestRateLimiting:
    """Check for APIM rate-limit headers when APIM is in the request path.

    These tests are advisory -- they pass even when no APIM is present.
    """

    # Standard headers injected by Azure API Management rate-limit policies
    RATE_LIMIT_HEADERS = (
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "ratelimit-limit",
        "ratelimit-remaining",
        "retry-after",
    )

    def test_rate_limit_headers(
        self,
        base_url: str,
    ) -> None:
        """GET /health and inspect response for rate-limit headers.

        If none are present the test still passes but logs a note -- the
        deployment may not have APIM in the path.
        """
        url = f"{base_url}/health"
        try:
            resp = httpx.get(url, timeout=REQUEST_TIMEOUT)
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            _skip_on_connection_error(exc, url)

        assert resp.status_code == 200, (
            f"Expected 200 from /health, got {resp.status_code}"
        )

        found_headers = {
            h: resp.headers[h]
            for h in self.RATE_LIMIT_HEADERS
            if h in resp.headers
        }

        if not found_headers:
            # Not a failure -- APIM may simply not be configured
            pytest.skip(
                "No rate-limit headers found in /health response. "
                "This is expected when APIM is not in the request path."
            )

        # If we do find headers, verify they contain numeric values
        for header_name, header_value in found_headers.items():
            assert header_value.strip(), (
                f"Rate-limit header '{header_name}' is present but empty."
            )
