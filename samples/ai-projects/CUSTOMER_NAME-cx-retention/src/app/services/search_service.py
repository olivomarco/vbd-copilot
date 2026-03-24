"""Azure AI Search hybrid search service.

Executes hybrid queries combining:
  - BM25 keyword search
  - Vector search (via text-embedding-3-small embeddings)
  - Semantic ranker for re-ranking

Authentication uses DefaultAzureCredential (Managed Identity).
"""

from __future__ import annotations

import logging
from typing import Optional

from azure.identity import DefaultAzureCredential
from azure.search.documents.aio import SearchClient
from azure.search.documents.models import (
    VectorizedQuery,
)

from app.config import Settings
from app.models.schemas import SearchResult
from app.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

_TOP_K = 5


class SearchService:
    """Hybrid search over the CUSTOMER_NAME knowledge base index."""

    def __init__(
        self,
        settings: Settings,
        credential: DefaultAzureCredential,
        openai_service: OpenAIService,
    ) -> None:
        self._client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index_name,
            credential=credential,
        )
        self._openai_service = openai_service
        logger.info(
            "SearchService initialised (endpoint=%s, index=%s)",
            settings.azure_search_endpoint,
            settings.azure_search_index_name,
        )

    async def hybrid_search(
        self,
        query: str,
        *,
        top: int = _TOP_K,
        filter_expression: Optional[str] = None,
    ) -> list[SearchResult]:
        """Execute a hybrid (keyword + vector + semantic) search.

        Args:
            query: Natural-language query from the user.
            top: Maximum number of results to return.
            filter_expression: Optional OData filter expression.

        Returns:
            Ranked list of SearchResult objects.
        """
        # Generate embedding for the query
        query_vector = await self._openai_service.embed(query)

        vector_query = VectorizedQuery(
            vector=query_vector,
            k_nearest_neighbors=top,
            fields="contentVector",
        )

        logger.debug("Executing hybrid search: query=%r top=%d", query[:80], top)

        results: list[SearchResult] = []
        search_results = await self._client.search(
            search_text=query,
            vector_queries=[vector_query],
            query_type="semantic",
            semantic_configuration_name="default",
            top=top,
            filter=filter_expression,
            select=["content", "sourceDocument", "category", "title"],
        )

        async for result in search_results:
            score = result.get("@search.reranker_score") or result.get("@search.score", 0.0)
            results.append(
                SearchResult(
                    content=result.get("content", ""),
                    source_document=result.get("sourceDocument"),
                    category=result.get("category"),
                    score=float(score),
                    title=result.get("title"),
                )
            )

        logger.info("Hybrid search returned %d results for query=%r", len(results), query[:60])
        return results

    async def health_check(self) -> bool:
        """Return True if the AI Search index is reachable."""
        try:
            await self._client.search(search_text="*", top=1)
            return True
        except Exception:
            logger.warning("AI Search health check failed", exc_info=True)
            return False

    async def close(self) -> None:
        """Close the underlying HTTP transport."""
        await self._client.close()
