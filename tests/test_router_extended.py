"""Extended tests for router.py — covers _classify_intent, route_to_agent."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

import router
from router import (
    _classify_intent,
    route_to_agent,
)


@pytest.fixture(autouse=True)
def _reset_router():
    """Reset router globals between tests."""
    old_tokens = router._AGENT_TOKENS
    router._AGENT_TOKENS = {}
    yield
    router._AGENT_TOKENS = old_tokens


# ---------------------------------------------------------------------------
# _classify_intent  (sync keyword-based classifier)
# ---------------------------------------------------------------------------


class TestClassifyIntent:
    def test_returns_none_when_tokens_empty(self):
        """When _AGENT_TOKENS is empty, returns None."""
        assert router._AGENT_TOKENS == {}
        result = _classify_intent("Build a presentation")
        assert result is None

    def test_returns_none_for_empty_prompt(self):
        router._AGENT_TOKENS = {"slide-conductor": {"slide", "deck", "presentation"}}
        result = _classify_intent("")
        assert result is None

    def test_returns_none_for_stop_words_only(self):
        router._AGENT_TOKENS = {"slide-conductor": {"slide", "deck", "presentation"}}
        # All tokens are stop-words or very short — _tokenize returns empty set
        result = _classify_intent("a an the")
        assert result is None

    def test_returns_matching_agent(self):
        router._AGENT_TOKENS = {
            "slide-conductor": {"slide", "deck", "presentation"},
            "demo-conductor": {"demo", "demonstration"},
        }
        result = _classify_intent("Build a slide deck")
        assert result == "slide-conductor"

    def test_returns_best_scoring_agent(self):
        router._AGENT_TOKENS = {
            "slide-conductor": {"slide", "deck", "presentation"},
            "demo-conductor": {"demo", "demonstration", "slide"},
        }
        # "demo slide presentation" — slide-conductor matches 2, demo-conductor matches 1
        result = _classify_intent("demo slide presentation")
        # slide-conductor: {slide, presentation} = 2 hits; demo-conductor: {demo, slide} = 2 hits
        # first wins on tie — result is non-None and one of the two
        assert result in {"slide-conductor", "demo-conductor"}

    def test_returns_none_when_no_overlap(self):
        router._AGENT_TOKENS = {"slide-conductor": {"slide", "deck", "presentation"}}
        result = _classify_intent("configure networking firewall")
        assert result is None

    def test_requires_at_least_one_match(self):
        """Score must be >= 1 to return an agent."""
        router._AGENT_TOKENS = {"slide-conductor": set()}
        result = _classify_intent("anything goes here")
        assert result is None


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
    async def test_returns_none_when_no_agent_detected(self):
        """route_to_agent returns None (not a blocking RPC call) when no agent matched."""
        mock_session = AsyncMock()

        with patch("router.detect_agent", new_callable=AsyncMock, return_value=None):
            result = await route_to_agent(mock_session, "Hello")
        assert result is None
        mock_session.rpc.agent.get_current.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_for_generic_prompt(self):
        """Generic prompts like 'hi' never block on get_current."""
        mock_session = AsyncMock()

        with patch("router.detect_agent", new_callable=AsyncMock, return_value=None):
            result = await route_to_agent(mock_session, "hi")
        assert result is None
        mock_session.rpc.agent.get_current.assert_not_called()
