"""RAG pipeline orchestrator.

Coordinates the end-to-end flow for each user query:
  1. Classify query complexity (model_router)
  2. Fetch billing data if needed (billing_api)
  3. Hybrid search for relevant knowledge (search_service)
  4. Build the prompt (system prompt + context + history + user message)
  5. Stream the LLM response (openai_service)
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator, Optional

from app.models.schemas import BillData, ModelClassification, SearchResult
from app.prompts.system_prompt import get_bill_context_prompt, get_system_prompt
from app.services.billing_api import BillingAPIClient, BillingAPIError
from app.services.model_router import ModelRouter
from app.services.openai_service import MAX_TOKENS_BILL, MAX_TOKENS_FAQ, OpenAIService
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


class RAGPipeline:
    """Main orchestrator that ties retrieval, enrichment, and generation."""

    def __init__(
        self,
        model_router: ModelRouter,
        search_service: SearchService,
        openai_service: OpenAIService,
        billing_api: BillingAPIClient,
    ) -> None:
        self._model_router = model_router
        self._search_service = search_service
        self._openai_service = openai_service
        self._billing_api = billing_api

    async def process_query(
        self,
        session_id: str,
        message: str,
        conversation_history: list[dict],
        bill_ref: Optional[str] = None,
        conversation_turn: int = 0,
    ) -> AsyncGenerator[tuple[str, ModelClassification], None]:
        """Process a user query through the full RAG pipeline.

        Yields (token, classification) tuples. The classification is the
        same object on every yield -- it carries metadata about model
        selection for the caller to persist.

        Args:
            session_id: Current conversation session.
            message: The user's question.
            conversation_history: Previous messages as dicts with role/content.
            bill_ref: Optional bill reference for personalised lookup.
            conversation_turn: Current turn number in the conversation.

        Yields:
            Tuples of (token_text, ModelClassification).
        """
        # 1. Classify query
        classification = self._model_router.classify(
            message,
            bill_ref=bill_ref,
            conversation_turn=conversation_turn,
        )
        logger.info(
            "Pipeline: session=%s model=%s needs_billing=%s",
            session_id,
            classification.model,
            classification.needs_billing_data,
        )

        # 2. Fetch billing data (if needed)
        bill_data: Optional[BillData] = None
        if classification.needs_billing_data and bill_ref:
            bill_data = await self._fetch_billing_data(bill_ref)

        # 3. Search knowledge base
        search_results = await self._search_service.hybrid_search(message)

        # 4. Build prompt messages
        messages = self._build_messages(
            search_results=search_results,
            bill_data=bill_data,
            conversation_history=conversation_history,
            user_message=message,
        )

        # 5. Select token limit
        max_tokens = MAX_TOKENS_BILL if bill_data else MAX_TOKENS_FAQ

        # 6. Stream LLM response
        async for token in self._openai_service.stream_chat(
            messages=messages,
            deployment_name=classification.model,
            max_tokens=max_tokens,
        ):
            yield token, classification

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _fetch_billing_data(self, bill_ref: str) -> Optional[BillData]:
        """Attempt to fetch bill data, returning None on failure."""
        try:
            bill_data = await self._billing_api.get_bill(bill_ref)
            if bill_data:
                logger.info("Bill data retrieved for ref=%s", bill_ref)
            else:
                logger.info("No bill data found for ref=%s", bill_ref)
            return bill_data
        except BillingAPIError as exc:
            logger.warning("Billing API error for ref=%s: %s", bill_ref, exc)
            return None

    @staticmethod
    def _build_knowledge_context(search_results: list[SearchResult]) -> str:
        """Format search results into a context block for the prompt."""
        if not search_results:
            return ""

        parts: list[str] = []
        for i, result in enumerate(search_results, 1):
            source = result.source_document or "documento"
            category = result.category or "generale"
            parts.append(
                f"[Fonte {i} - {category} ({source})]:\n{result.content}"
            )
        return "\n\n".join(parts)

    @classmethod
    def _build_messages(
        cls,
        search_results: list[SearchResult],
        bill_data: Optional[BillData],
        conversation_history: list[dict],
        user_message: str,
    ) -> list[dict[str, str]]:
        """Assemble the OpenAI messages array.

        Structure:
          - System message (with knowledge context and optional bill data)
          - Conversation history (alternating user/assistant)
          - Current user message
        """
        # System prompt with knowledge context
        knowledge_context = cls._build_knowledge_context(search_results)
        system_content = get_system_prompt(knowledge_context)

        # Append bill data section if available
        if bill_data:
            system_content += "\n\n" + get_bill_context_prompt(bill_data)

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_content},
        ]

        # Append conversation history (keep only role + content)
        for msg in conversation_history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        # Append current user message
        messages.append({"role": "user", "content": user_message})

        return messages
