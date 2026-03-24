"""Tests for services/rag_pipeline.py -- RAG orchestration.

Validates the end-to-end flow: classify -> billing fetch -> search ->
prompt build -> stream LLM. All external dependencies are mocked.
"""

from __future__ import annotations

from typing import AsyncGenerator, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import BillData, LineItem, ModelClassification, SearchResult
from app.services.billing_api import BillingAPIError
from app.services.rag_pipeline import RAGPipeline


@pytest.fixture
def mock_model_router() -> MagicMock:
    """Mock ModelRouter returning simple classification by default."""
    router = MagicMock()
    router.classify.return_value = ModelClassification(
        model="gpt-4o-mini",
        needs_billing_data=False,
        reasoning="Simple FAQ query -- using cost-effective model",
    )
    return router


@pytest.fixture
def mock_search_service() -> AsyncMock:
    """Mock SearchService returning two results by default."""
    svc = AsyncMock()
    svc.hybrid_search.return_value = [
        SearchResult(
            content="Le tariffe monorarie hanno un prezzo unico.",
            source_document="tariffe.pdf",
            category="tariffe",
            score=0.9,
            title="Guida tariffe",
        ),
        SearchResult(
            content="Gli oneri di sistema sono stabiliti da ARERA.",
            source_document="faq.pdf",
            category="oneri",
            score=0.8,
            title="FAQ Oneri",
        ),
    ]
    return svc


@pytest.fixture
def mock_openai_service() -> AsyncMock:
    """Mock OpenAIService with a streaming generator."""
    svc = AsyncMock()

    async def fake_stream(*args, **kwargs):  # type: ignore[no-untyped-def]
        for token in ["La ", "risposta ", "e' ", "questa."]:
            yield token

    svc.stream_chat = MagicMock(side_effect=fake_stream)
    return svc


@pytest.fixture
def mock_billing_api() -> AsyncMock:
    """Mock BillingAPIClient."""
    api = AsyncMock()
    api.get_bill.return_value = None
    return api


@pytest.fixture
def pipeline(
    mock_model_router: MagicMock,
    mock_search_service: AsyncMock,
    mock_openai_service: AsyncMock,
    mock_billing_api: AsyncMock,
) -> RAGPipeline:
    """Build a RAGPipeline with all dependencies mocked."""
    return RAGPipeline(
        model_router=mock_model_router,
        search_service=mock_search_service,
        openai_service=mock_openai_service,
        billing_api=mock_billing_api,
    )


async def _collect_tokens(pipeline: RAGPipeline, **kwargs) -> tuple[list[str], Optional[ModelClassification]]:  # type: ignore[no-untyped-def]
    """Helper to collect all tokens from process_query."""
    tokens: list[str] = []
    classification = None
    defaults = {
        "session_id": "test-session",
        "message": "Quanto costa la bolletta?",
        "conversation_history": [],
    }
    defaults.update(kwargs)
    async for token, cls in pipeline.process_query(**defaults):
        tokens.append(token)
        classification = cls
    return tokens, classification


class TestFAQFlow:
    """Simple FAQ queries (no billing data)."""

    @pytest.mark.asyncio
    async def test_faq_query_flow(
        self,
        pipeline: RAGPipeline,
        mock_search_service: AsyncMock,
        mock_model_router: MagicMock,
    ) -> None:
        """General question triggers search -> mini model -> response."""
        tokens, classification = await _collect_tokens(pipeline)

        # Search was called
        mock_search_service.hybrid_search.assert_awaited_once()
        # Classification was invoked
        mock_model_router.classify.assert_called_once()
        # Tokens were yielded
        assert len(tokens) > 0
        assert "".join(tokens) == "La risposta e' questa."
        assert classification is not None
        assert classification.model == "gpt-4o-mini"

    @pytest.mark.asyncio
    async def test_empty_search_results(
        self,
        pipeline: RAGPipeline,
        mock_search_service: AsyncMock,
    ) -> None:
        """No search results -- LLM still generates from conversation."""
        mock_search_service.hybrid_search.return_value = []

        tokens, classification = await _collect_tokens(pipeline)

        # Should still produce tokens
        assert len(tokens) > 0
        assert classification is not None


class TestBillLookupFlow:
    """Queries with bill reference that trigger billing API."""

    @pytest.mark.asyncio
    async def test_bill_lookup_flow(
        self,
        pipeline: RAGPipeline,
        mock_model_router: MagicMock,
        mock_billing_api: AsyncMock,
        mock_openai_service: AsyncMock,
    ) -> None:
        """bill_ref provided -> billing API -> search -> GPT-4o -> response."""
        # Configure router to return complex classification
        mock_model_router.classify.return_value = ModelClassification(
            model="gpt-4o",
            needs_billing_data=True,
            reasoning="bill reference provided",
        )
        # Configure billing API to return data
        mock_billing_api.get_bill.return_value = BillData(
            bill_ref="BILL-2024-001",
            total_amount=125.60,
            billing_period_start="2024-01-01",
            billing_period_end="2024-01-31",
        )

        tokens, classification = await _collect_tokens(
            pipeline,
            message="Spiega la mia bolletta",
            bill_ref="BILL-2024-001",
        )

        mock_billing_api.get_bill.assert_awaited_once_with("BILL-2024-001")
        assert classification is not None
        assert classification.model == "gpt-4o"
        assert len(tokens) > 0

    @pytest.mark.asyncio
    async def test_billing_api_failure_fallback(
        self,
        pipeline: RAGPipeline,
        mock_model_router: MagicMock,
        mock_billing_api: AsyncMock,
    ) -> None:
        """Billing API failure -> pipeline continues with search only."""
        mock_model_router.classify.return_value = ModelClassification(
            model="gpt-4o",
            needs_billing_data=True,
            reasoning="bill reference provided",
        )
        mock_billing_api.get_bill.side_effect = BillingAPIError("API down")

        tokens, classification = await _collect_tokens(
            pipeline,
            bill_ref="BILL-2024-001",
        )

        # Pipeline completes despite billing failure
        assert len(tokens) > 0
        assert classification is not None

    @pytest.mark.asyncio
    async def test_bill_data_injected_in_prompt(
        self,
        pipeline: RAGPipeline,
        mock_model_router: MagicMock,
        mock_billing_api: AsyncMock,
        mock_openai_service: AsyncMock,
    ) -> None:
        """Verify bill data appears in prompt context sent to LLM."""
        mock_model_router.classify.return_value = ModelClassification(
            model="gpt-4o",
            needs_billing_data=True,
            reasoning="bill reference provided",
        )
        mock_billing_api.get_bill.return_value = BillData(
            bill_ref="BILL-2024-001",
            total_amount=125.60,
            billing_period_start="2024-01-01",
            billing_period_end="2024-01-31",
        )

        await _collect_tokens(
            pipeline,
            message="Spiega la bolletta",
            bill_ref="BILL-2024-001",
        )

        # Check the messages passed to stream_chat
        call_args = mock_openai_service.stream_chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]
        system_content = messages[0]["content"]
        assert "BILL-2024-001" in system_content
        assert "125.60" in system_content


class TestConversationHistory:
    """Verify conversation history is included in prompts."""

    @pytest.mark.asyncio
    async def test_conversation_history_included(
        self,
        pipeline: RAGPipeline,
        mock_openai_service: AsyncMock,
    ) -> None:
        """History messages are passed through to the LLM prompt."""
        history = [
            {"role": "user", "content": "Quanto costa?"},
            {"role": "assistant", "content": "La bolletta e' 125 EUR."},
        ]

        await _collect_tokens(
            pipeline,
            conversation_history=history,
        )

        call_args = mock_openai_service.stream_chat.call_args
        messages = call_args.kwargs.get("messages") or call_args[0][0]
        # System message + 2 history messages + 1 current user message = 4
        assert len(messages) >= 4
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Quanto costa?"
        assert messages[2]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_streaming_yields_tokens(
        self,
        pipeline: RAGPipeline,
    ) -> None:
        """Verify async generator yields individual tokens."""
        tokens, _ = await _collect_tokens(pipeline)
        assert tokens == ["La ", "risposta ", "e' ", "questa."]


class TestBuildMessages:
    """Test the static _build_messages helper directly."""

    def test_build_messages_no_bill_no_history(self) -> None:
        """Messages array with system + user only."""
        messages = RAGPipeline._build_messages(
            search_results=[],
            bill_data=None,
            conversation_history=[],
            user_message="Ciao",
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "Ciao"

    def test_build_messages_with_search_results(self) -> None:
        """Search results appear in system prompt context."""
        results = [
            SearchResult(
                content="Info sulle tariffe",
                source_document="doc.pdf",
                category="tariffe",
                score=0.9,
            ),
        ]
        messages = RAGPipeline._build_messages(
            search_results=results,
            bill_data=None,
            conversation_history=[],
            user_message="Domanda",
        )
        assert "Info sulle tariffe" in messages[0]["content"]

    def test_build_messages_with_bill_data(self) -> None:
        """Bill data is appended to the system prompt."""
        bill = BillData(
            bill_ref="REF-001",
            total_amount=100.0,
            billing_period_start="2024-01-01",
            billing_period_end="2024-01-31",
        )
        messages = RAGPipeline._build_messages(
            search_results=[],
            bill_data=bill,
            conversation_history=[],
            user_message="Spiega",
        )
        assert "REF-001" in messages[0]["content"]
        assert "100.00" in messages[0]["content"]

    def test_build_messages_filters_empty_history(self) -> None:
        """Empty-content history entries are excluded."""
        history = [
            {"role": "user", "content": "Hello"},
            {"role": "system", "content": "System msg"},
            {"role": "user", "content": ""},
        ]
        messages = RAGPipeline._build_messages(
            search_results=[],
            bill_data=None,
            conversation_history=history,
            user_message="Domanda",
        )
        # System (from template) + "Hello" (user from history) + "Domanda" (current)
        # "System msg" role is "system" so filtered; empty content is filtered
        assert len(messages) == 3

    def test_build_knowledge_context(self) -> None:
        """_build_knowledge_context formats results with source references."""
        results = [
            SearchResult(
                content="Contenuto 1",
                source_document="doc1.pdf",
                category="tariffe",
                score=0.9,
            ),
            SearchResult(
                content="Contenuto 2",
                source_document="doc2.pdf",
                category="FAQ",
                score=0.8,
            ),
        ]
        context = RAGPipeline._build_knowledge_context(results)
        assert "Fonte 1" in context
        assert "Fonte 2" in context
        assert "Contenuto 1" in context
        assert "tariffe" in context

    def test_build_knowledge_context_empty(self) -> None:
        """Empty results list returns empty string."""
        context = RAGPipeline._build_knowledge_context([])
        assert context == ""
