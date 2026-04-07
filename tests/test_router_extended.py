"""Extended tests for router.py — covers _classify_intent, route_to_agent, _ensure_classifier."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import router
from router import (
    _auto_approve,
    _classify_intent,
    _ensure_classifier,
    init_router,
    route_to_agent,
)


@pytest.fixture(autouse=True)
def _reset_router():
    """Reset router globals between tests."""
    old_client = router._copilot_client
    old_session = router._classifier_session
    router._copilot_client = None
    router._classifier_session = None
    yield
    router._copilot_client = old_client
    router._classifier_session = old_session


# ---------------------------------------------------------------------------
# _auto_approve
# ---------------------------------------------------------------------------


class TestAutoApprove:
    @pytest.mark.asyncio
    async def test_auto_approve_returns_approved(self):
        result = await _auto_approve(MagicMock(), {})
        assert result["kind"] == "approved"


# ---------------------------------------------------------------------------
# _ensure_classifier
# ---------------------------------------------------------------------------


class TestEnsureClassifier:
    @pytest.mark.asyncio
    async def test_raises_without_init(self):
        """Calling _ensure_classifier without init_router should fail."""
        with pytest.raises(RuntimeError, match="Router not initialised"):
            await _ensure_classifier()

    @pytest.mark.asyncio
    async def test_creates_session(self):
        mock_client = AsyncMock()
        mock_session = MagicMock()
        mock_client.create_session.return_value = mock_session
        await init_router(mock_client)

        session = await _ensure_classifier()
        assert session is mock_session
        mock_client.create_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_cached_session(self):
        mock_client = AsyncMock()
        mock_session = MagicMock()
        mock_client.create_session.return_value = mock_session
        await init_router(mock_client)

        s1 = await _ensure_classifier()
        s2 = await _ensure_classifier()
        assert s1 is s2
        # Should only create once
        assert mock_client.create_session.call_count == 1


# ---------------------------------------------------------------------------
# _classify_intent
# ---------------------------------------------------------------------------


class TestClassifyIntent:
    @pytest.mark.asyncio
    async def test_returns_known_agent_from_stream(self):
        from copilot.generated.session_events import SessionEventType

        mock_session = AsyncMock()
        events_captured = []

        def mock_on(handler):
            events_captured.append(handler)
            return MagicMock()  # unsubscribe function

        mock_session.on = mock_on
        mock_session.send_and_wait = AsyncMock(return_value=None)

        with patch(
            "router._ensure_classifier",
            new_callable=AsyncMock,
            return_value=mock_session,
        ):

            async def send_with_events(*args, **kwargs):
                # Simulate streamed event
                handler = events_captured[0]
                event = SimpleNamespace(
                    type=SessionEventType.ASSISTANT_MESSAGE_DELTA,
                    data=SimpleNamespace(delta_content="slide-conductor"),
                )
                handler(event)
                return None

            mock_session.send_and_wait = send_with_events
            result = await _classify_intent("Build a presentation")

        assert result == "slide-conductor"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_agent(self):
        mock_session = AsyncMock()
        mock_session.on = MagicMock(return_value=MagicMock())
        reply = SimpleNamespace(data=SimpleNamespace(content="none"))
        mock_session.send_and_wait = AsyncMock(return_value=reply)

        with patch(
            "router._ensure_classifier",
            new_callable=AsyncMock,
            return_value=mock_session,
        ):
            result = await _classify_intent("Hello world")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_exception(self):
        with patch(
            "router._ensure_classifier",
            new_callable=AsyncMock,
            side_effect=Exception("boom"),
        ):
            result = await _classify_intent("test prompt")
        assert result is None
        # Session should be reset
        assert router._classifier_session is None

    @pytest.mark.asyncio
    async def test_uses_reply_content_as_fallback(self):
        mock_session = AsyncMock()
        mock_session.on = MagicMock(return_value=MagicMock())
        reply = SimpleNamespace(data=SimpleNamespace(content="demo-conductor"))
        mock_session.send_and_wait = AsyncMock(return_value=reply)

        with patch(
            "router._ensure_classifier",
            new_callable=AsyncMock,
            return_value=mock_session,
        ):
            result = await _classify_intent("Create demos")
        assert result == "demo-conductor"


# ---------------------------------------------------------------------------
# route_to_agent
# ---------------------------------------------------------------------------


class TestRouteToAgent:
    @pytest.mark.asyncio
    async def test_routes_to_detected_agent(self):
        mock_session = AsyncMock()
        mock_session.rpc.agent.select = AsyncMock()
        mock_session.rpc.model.switch_to = AsyncMock()

        with patch(
            "router.detect_agent",
            new_callable=AsyncMock,
            return_value="slide-conductor",
        ):
            result = await route_to_agent(mock_session, "Build a deck")
        assert result == "slide-conductor"
        mock_session.rpc.agent.select.assert_called_once()
        mock_session.rpc.model.switch_to.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_current_agent_when_no_match(self):
        mock_session = AsyncMock()
        mock_agent = SimpleNamespace(name="existing-agent")
        mock_session.rpc.agent.get_current = AsyncMock(
            return_value=SimpleNamespace(agent=mock_agent)
        )

        with patch("router.detect_agent", new_callable=AsyncMock, return_value=None):
            result = await route_to_agent(mock_session, "Hello")
        assert result == "existing-agent"

    @pytest.mark.asyncio
    async def test_returns_none_when_no_current_agent(self):
        mock_session = AsyncMock()
        mock_session.rpc.agent.get_current = AsyncMock(
            return_value=SimpleNamespace(agent=None)
        )

        with patch("router.detect_agent", new_callable=AsyncMock, return_value=None):
            result = await route_to_agent(mock_session, "Hello")
        assert result is None
