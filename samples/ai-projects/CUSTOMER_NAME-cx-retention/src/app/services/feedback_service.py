"""Feedback storage service for Cosmos DB.

Persists user thumbs-up / thumbs-down ratings (and optional comments)
linked to specific assistant messages and sessions.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from azure.cosmos.aio import CosmosClient
from azure.identity import DefaultAzureCredential

from app.config import Settings

logger = logging.getLogger(__name__)


class FeedbackService:
    """Store and query user feedback in the Cosmos DB feedback container."""

    def __init__(
        self,
        settings: Settings,
        credential: DefaultAzureCredential,
    ) -> None:
        self._endpoint = settings.cosmos_db_endpoint
        self._database_name = settings.cosmos_db_database_name
        self._credential = credential
        self._client: Optional[CosmosClient] = None
        logger.info("FeedbackService configured (endpoint=%s)", self._endpoint)

    async def _ensure_client(self) -> CosmosClient:
        """Lazily initialise the Cosmos DB async client."""
        if self._client is None:
            self._client = CosmosClient(
                url=self._endpoint,
                credential=self._credential,
            )
        return self._client

    async def _get_container(self) -> Any:
        """Return the feedback container proxy."""
        client = await self._ensure_client()
        database = client.get_database_client(self._database_name)
        return database.get_container_client("feedback")

    async def save_feedback(
        self,
        session_id: str,
        message_id: str,
        rating: str,
        comment: Optional[str] = None,
    ) -> str:
        """Persist a feedback record.

        Args:
            session_id: Session that owns the message.
            message_id: The assistant message being rated.
            rating: "up" or "down".
            comment: Optional free-text comment.

        Returns:
            The generated feedback record UUID.
        """
        feedback_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        feedback_doc = {
            "id": feedback_id,
            "sessionId": session_id,
            "messageId": message_id,
            "rating": rating,
            "comment": comment,
            "timestamp": now,
        }

        container = await self._get_container()
        await container.create_item(feedback_doc)

        logger.info(
            "Feedback saved: id=%s session=%s message=%s rating=%s",
            feedback_id,
            session_id,
            message_id,
            rating,
        )
        return feedback_id

    async def close(self) -> None:
        """Close the Cosmos DB client."""
        if self._client:
            await self._client.close()
            self._client = None
