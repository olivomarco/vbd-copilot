"""Tests for router.py - agent routing logic."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from router import detect_agent, _build_system_prompt, init_router


class TestInitRouter:

    @pytest.mark.asyncio
    async def test_init_router_stores_client(self):
        mock_client = MagicMock()
        await init_router(mock_client)
        import router
        assert router._copilot_client is mock_client
        # Clean up
        router._copilot_client = None


class TestDetectAgent:
    """Tests for the detect_agent function."""

    # ── Explicit @mention routing ─────────────────────────────────────────

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value=None)
    async def test_explicit_slide_conductor(self, mock_classify):
        assert await detect_agent("@slide-conductor make me a deck about AKS") == "slide-conductor"
        mock_classify.assert_not_called()

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value=None)
    async def test_explicit_demo_conductor(self, mock_classify):
        assert await detect_agent("@demo-conductor create a demo") == "demo-conductor"
        mock_classify.assert_not_called()

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value=None)
    async def test_explicit_ai_brainstorming(self, mock_classify):
        assert await detect_agent("@ai-brainstorming ideas for Contoso") == "ai-brainstorming"
        mock_classify.assert_not_called()

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value=None)
    async def test_explicit_unknown_agent(self, mock_classify):
        """Unknown @mention falls through to LLM classifier."""
        result = await detect_agent("@unknown-agent hello")
        assert result is None
        mock_classify.assert_called_once()

    # ── LLM classifier routing ────────────────────────────────────────────

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value="slide-conductor")
    async def test_llm_routes_slide(self, mock_classify):
        result = await detect_agent("I need a presentation about Azure")
        assert result == "slide-conductor"
        mock_classify.assert_called_once_with("I need a presentation about Azure")

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value="demo-conductor")
    async def test_llm_routes_demo(self, mock_classify):
        result = await detect_agent("Create demos for AKS")
        assert result == "demo-conductor"

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value="ai-brainstorming")
    async def test_llm_routes_brainstorming(self, mock_classify):
        result = await detect_agent("Let's brainstorm project ideas")
        assert result == "ai-brainstorming"

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value="ai-solution-architect")
    async def test_llm_routes_architect(self, mock_classify):
        result = await detect_agent("Design the solution architecture")
        assert result == "ai-solution-architect"

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value="ai-implementor")
    async def test_llm_routes_implementor(self, mock_classify):
        result = await detect_agent("Implement the solution with Bicep")
        assert result == "ai-implementor"

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value=None)
    async def test_llm_no_match(self, mock_classify):
        result = await detect_agent("Hello, how are you?")
        assert result is None

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value=None)
    async def test_empty_prompt(self, mock_classify):
        result = await detect_agent("")
        assert result is None

    # ── @mention takes priority over LLM ──────────────────────────────────

    @pytest.mark.asyncio
    @patch("router._classify_intent", new_callable=AsyncMock, return_value="demo-conductor")
    async def test_mention_overrides_llm(self, mock_classify):
        """Explicit @mention should take priority, LLM should not be called."""
        result = await detect_agent("@slide-conductor make me a demo deck")
        assert result == "slide-conductor"
        mock_classify.assert_not_called()


class TestBuildSystemPrompt:

    def test_prompt_contains_agents(self):
        prompt = _build_system_prompt()
        assert "intent classifier" in prompt.lower()
        assert "agent" in prompt.lower()

    def test_prompt_contains_rules(self):
        prompt = _build_system_prompt()
        assert "none" in prompt.lower()
