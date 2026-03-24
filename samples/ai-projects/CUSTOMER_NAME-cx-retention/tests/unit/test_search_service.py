"""Tests for services/search_service.py -- Azure AI Search integration.

Covers hybrid search execution, result mapping, embedding calls,
top-k limits, and error handling. All Azure clients are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import SearchResult
from app.services.search_service import SearchService, _TOP_K


@pytest.fixture
def mock_openai_svc() -> AsyncMock:
    """Mock OpenAIService with a fixed embedding vector."""
    svc = AsyncMock()
    svc.embed.return_value = [0.1] * 1536
    return svc


@pytest.fixture
def service(
    mock_settings: MagicMock,
    mock_credential: MagicMock,
    mock_openai_svc: AsyncMock,
) -> SearchService:
    """Create a SearchService with mocked dependencies."""
    with patch("app.services.search_service.SearchClient") as mock_search_cls:
        mock_client = AsyncMock()
        mock_search_cls.return_value = mock_client

        svc = SearchService(mock_settings, mock_credential, mock_openai_svc)
        svc._client = mock_client
        return svc


class TestHybridSearch:
    """Test the hybrid_search method."""

    @pytest.mark.asyncio
    async def test_hybrid_search_returns_results(
        self,
        service: SearchService,
        mock_openai_svc: AsyncMock,
    ) -> None:
        """Mock search returns a list of SearchResult objects."""
        raw_results = [
            {
                "content": "Tariffe monorarie info",
                "sourceDocument": "tariffe.pdf",
                "category": "tariffe",
                "@search.reranker_score": 0.95,
                "title": "Guida tariffe",
            },
            {
                "content": "Oneri di sistema spiegazione",
                "sourceDocument": "faq.pdf",
                "category": "FAQ",
                "@search.score": 0.80,
                "title": "FAQ Oneri",
            },
        ]

        async def mock_search_iter():  # type: ignore[no-untyped-def]
            for item in raw_results:
                yield item

        # Configure the search mock
        service._client.search = AsyncMock(return_value=mock_search_iter())
        # Make the context manager work
        service._client.__aenter__ = AsyncMock(return_value=service._client)
        service._client.__aexit__ = AsyncMock(return_value=False)

        results = await service.hybrid_search("Come funzionano le tariffe?")

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].content == "Tariffe monorarie info"
        assert results[0].source_document == "tariffe.pdf"
        assert results[0].score == 0.95

    @pytest.mark.asyncio
    async def test_hybrid_search_empty(
        self,
        service: SearchService,
    ) -> None:
        """No results from search returns empty list."""
        async def mock_search_iter():  # type: ignore[no-untyped-def]
            return
            yield  # Make this an async generator

        service._client.search = AsyncMock(return_value=mock_search_iter())
        service._client.__aenter__ = AsyncMock(return_value=service._client)
        service._client.__aexit__ = AsyncMock(return_value=False)

        results = await service.hybrid_search("Query with no matches")
        assert results == []

    @pytest.mark.asyncio
    async def test_search_result_mapping(
        self,
        service: SearchService,
    ) -> None:
        """Raw search document fields mapped to SearchResult model correctly."""
        raw = [
            {
                "content": "Contenuto test",
                "sourceDocument": "source.pdf",
                "category": "categoria",
                "@search.reranker_score": 0.88,
                "title": "Titolo Test",
            },
        ]

        async def mock_search_iter():  # type: ignore[no-untyped-def]
            for item in raw:
                yield item

        service._client.search = AsyncMock(return_value=mock_search_iter())
        service._client.__aenter__ = AsyncMock(return_value=service._client)
        service._client.__aexit__ = AsyncMock(return_value=False)

        results = await service.hybrid_search("test query")

        assert len(results) == 1
        r = results[0]
        assert r.content == "Contenuto test"
        assert r.source_document == "source.pdf"
        assert r.category == "categoria"
        assert r.score == 0.88
        assert r.title == "Titolo Test"

    @pytest.mark.asyncio
    async def test_embedding_called(
        self,
        service: SearchService,
        mock_openai_svc: AsyncMock,
    ) -> None:
        """Verify openai_service.embed() is called with the query."""
        async def mock_search_iter():  # type: ignore[no-untyped-def]
            return
            yield

        service._client.search = AsyncMock(return_value=mock_search_iter())
        service._client.__aenter__ = AsyncMock(return_value=service._client)
        service._client.__aexit__ = AsyncMock(return_value=False)

        await service.hybrid_search("Quanto costa l'energia?")

        mock_openai_svc.embed.assert_awaited_once_with("Quanto costa l'energia?")

    @pytest.mark.asyncio
    async def test_top_k_limit(
        self,
        service: SearchService,
    ) -> None:
        """Verify search uses the default top=5 parameter."""
        async def mock_search_iter():  # type: ignore[no-untyped-def]
            return
            yield

        service._client.search = AsyncMock(return_value=mock_search_iter())
        service._client.__aenter__ = AsyncMock(return_value=service._client)
        service._client.__aexit__ = AsyncMock(return_value=False)

        await service.hybrid_search("test")

        call_kwargs = service._client.search.call_args.kwargs
        assert call_kwargs.get("top") == _TOP_K

    @pytest.mark.asyncio
    async def test_search_error_handling(
        self,
        service: SearchService,
        mock_openai_svc: AsyncMock,
    ) -> None:
        """Search failure raises exception (caller must handle)."""
        service._client.__aenter__ = AsyncMock(return_value=service._client)
        service._client.__aexit__ = AsyncMock(return_value=False)
        service._client.search = AsyncMock(side_effect=Exception("Search unavailable"))

        with pytest.raises(Exception, match="Search unavailable"):
            await service.hybrid_search("test query")

    @pytest.mark.asyncio
    async def test_custom_top_parameter(
        self,
        service: SearchService,
    ) -> None:
        """Custom top parameter is passed through to search."""
        async def mock_search_iter():  # type: ignore[no-untyped-def]
            return
            yield

        service._client.search = AsyncMock(return_value=mock_search_iter())
        service._client.__aenter__ = AsyncMock(return_value=service._client)
        service._client.__aexit__ = AsyncMock(return_value=False)

        await service.hybrid_search("test", top=10)

        call_kwargs = service._client.search.call_args.kwargs
        assert call_kwargs.get("top") == 10


class TestSearchServiceHealthCheck:
    """Test the AI Search health probe."""

    @pytest.mark.asyncio
    async def test_health_check_success(self, service: SearchService) -> None:
        """Healthy AI Search returns True."""
        async def mock_search_iter():  # type: ignore[no-untyped-def]
            return
            yield

        service._client.search = AsyncMock(return_value=mock_search_iter())
        service._client.__aenter__ = AsyncMock(return_value=service._client)
        service._client.__aexit__ = AsyncMock(return_value=False)

        result = await service.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self, service: SearchService) -> None:
        """Unhealthy AI Search returns False."""
        service._client.__aenter__ = AsyncMock(return_value=service._client)
        service._client.__aexit__ = AsyncMock(return_value=False)
        service._client.search = AsyncMock(side_effect=Exception("Down"))

        result = await service.health_check()
        assert result is False


class TestSearchServiceClose:
    """Test the close method."""

    @pytest.mark.asyncio
    async def test_close(self, service: SearchService) -> None:
        """close() delegates to underlying client."""
        service._client.close = AsyncMock()
        await service.close()
        service._client.close.assert_awaited_once()
