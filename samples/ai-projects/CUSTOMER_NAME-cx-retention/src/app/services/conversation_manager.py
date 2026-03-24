"""Cosmos DB conversation and session management.

Manages three containers:
  - sessions: conversation session metadata (TTL 24h)
  - messages: individual chat messages (TTL 30d)
  - feedback: linked to sessions for GDPR batch deletion

All operations use async Cosmos DB SDK with DefaultAzureCredential.
Partition key is /sessionId on every container.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity import DefaultAzureCredential

from app.config import Settings
from app.models.schemas import MessageResponse, SessionResponse

logger = logging.getLogger(__name__)


class ConversationManager:
    """CRUD operations for sessions, messages, and feedback in Cosmos DB."""

    def __init__(
        self,
        settings: Settings,
        credential: DefaultAzureCredential,
    ) -> None:
        self._endpoint = settings.cosmos_db_endpoint
        self._database_name = settings.cosmos_db_database_name
        self._credential = credential
        self._client: Optional[CosmosClient] = None
        logger.info(
            "ConversationManager configured (endpoint=%s, db=%s)",
            self._endpoint,
            self._database_name,
        )

    async def _ensure_client(self) -> CosmosClient:
        """Lazily initialise the Cosmos DB async client."""
        if self._client is None:
            self._client = CosmosClient(
                url=self._endpoint,
                credential=self._credential,
            )
        return self._client

    async def _get_container(self, container_name: str) -> Any:
        """Return a container proxy for the given container name."""
        client = await self._ensure_client()
        database = client.get_database_client(self._database_name)
        return database.get_container_client(container_name)

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        bill_ref: Optional[str] = None,
    ) -> dict:
        """Load an existing session or create a new one.

        Args:
            session_id: Existing session UUID, or None to create new.
            bill_ref: Optional bill reference to associate with the session.

        Returns:
            Session document dict.
        """
        container = await self._get_container("sessions")

        if session_id:
            try:
                session = await container.read_item(
                    item=session_id,
                    partition_key=session_id,
                )
                # Update last_active timestamp
                session["lastActive"] = datetime.now(timezone.utc).isoformat()
                if bill_ref and not session.get("billRef"):
                    session["billRef"] = bill_ref
                await container.upsert_item(session)
                logger.debug("Session loaded: %s", session_id)
                return session
            except CosmosResourceNotFoundError:
                logger.info(
                    "Session %s not found, creating new session", session_id
                )

        # Create new session
        new_id = session_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        session = {
            "id": new_id,
            "sessionId": new_id,
            "createdAt": now,
            "lastActive": now,
            "billRef": bill_ref,
            "messageCount": 0,
        }
        await container.create_item(session)
        logger.info("New session created: %s", new_id)
        return session

    async def get_session(self, session_id: str) -> Optional[SessionResponse]:
        """Retrieve session info with message history.

        Args:
            session_id: Session UUID.

        Returns:
            SessionResponse or None if not found.
        """
        container = await self._get_container("sessions")
        try:
            session = await container.read_item(
                item=session_id,
                partition_key=session_id,
            )
        except Exception:
            return None

        messages = await self.get_conversation_history(session_id, limit=100)

        return SessionResponse(
            session_id=session["sessionId"],
            created_at=session["createdAt"],
            last_active=session["lastActive"],
            bill_ref=session.get("billRef"),
            message_count=session.get("messageCount", 0),
            messages=[
                MessageResponse(
                    message_id=m["id"],
                    role=m["role"],
                    content=m["content"],
                    timestamp=m["timestamp"],
                    model_used=m.get("modelUsed"),
                )
                for m in messages
            ],
        )

    # ------------------------------------------------------------------
    # Messages
    # ------------------------------------------------------------------

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """Persist a chat message and increment the session message count.

        Args:
            session_id: Owning session UUID.
            role: One of "user", "assistant", "system".
            content: Message text.
            metadata: Optional dict with model_used, token counts, etc.

        Returns:
            The generated message UUID.
        """
        message_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        message_doc = {
            "id": message_id,
            "sessionId": session_id,
            "role": role,
            "content": content,
            "timestamp": now,
        }
        if metadata:
            message_doc["modelUsed"] = metadata.get("model_used")
            message_doc["promptTokens"] = metadata.get("prompt_tokens")
            message_doc["completionTokens"] = metadata.get("completion_tokens")

        messages_container = await self._get_container("messages")
        await messages_container.create_item(message_doc)

        # Increment session message count
        try:
            sessions_container = await self._get_container("sessions")
            session = await sessions_container.read_item(
                item=session_id,
                partition_key=session_id,
            )
            session["messageCount"] = session.get("messageCount", 0) + 1
            session["lastActive"] = now
            await sessions_container.upsert_item(session)
        except Exception:
            logger.warning("Failed to update session message count for %s", session_id)

        logger.debug("Message saved: id=%s session=%s role=%s", message_id, session_id, role)
        return message_id

    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 10,
    ) -> list[dict]:
        """Retrieve the most recent messages for a session.

        Args:
            session_id: Session UUID.
            limit: Maximum number of messages to return (most recent).

        Returns:
            List of message dicts ordered by timestamp ascending.
        """
        container = await self._get_container("messages")

        query = (
            "SELECT * FROM c WHERE c.sessionId = @sessionId "
            "ORDER BY c.timestamp DESC OFFSET 0 LIMIT @limit"
        )
        parameters = [
            {"name": "@sessionId", "value": session_id},
            {"name": "@limit", "value": limit},
        ]

        items: list[dict] = []
        async for item in container.query_items(
            query=query,
            parameters=parameters,
            partition_key=session_id,
        ):
            items.append(item)

        # Return in chronological order
        items.reverse()
        return items

    # ------------------------------------------------------------------
    # GDPR deletion
    # ------------------------------------------------------------------

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all associated messages and feedback (GDPR erasure).

        Args:
            session_id: Session UUID to erase.

        Returns:
            True if deletion was performed, False if session not found.
        """
        # Delete session document
        sessions_container = await self._get_container("sessions")
        try:
            await sessions_container.delete_item(
                item=session_id,
                partition_key=session_id,
            )
        except Exception:
            logger.info("Session %s not found for deletion", session_id)
            return False

        # Delete all messages for this session
        await self._delete_all_in_partition("messages", session_id)

        # Delete all feedback for this session
        await self._delete_all_in_partition("feedback", session_id)

        logger.info("GDPR erasure completed for session %s", session_id)
        return True

    async def _delete_all_in_partition(
        self,
        container_name: str,
        session_id: str,
    ) -> int:
        """Delete all documents in a container with the given partition key.

        Returns the count of deleted documents.
        """
        container = await self._get_container(container_name)
        query = "SELECT c.id FROM c WHERE c.sessionId = @sessionId"
        parameters = [{"name": "@sessionId", "value": session_id}]

        count = 0
        async for item in container.query_items(
            query=query,
            parameters=parameters,
            partition_key=session_id,
        ):
            await container.delete_item(
                item=item["id"],
                partition_key=session_id,
            )
            count += 1

        logger.debug("Deleted %d items from %s for session %s", count, container_name, session_id)
        return count

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health_check(self) -> bool:
        """Return True if Cosmos DB is reachable and the database exists."""
        try:
            client = await self._ensure_client()
            database = client.get_database_client(self._database_name)
            await database.read()
            return True
        except Exception:
            logger.warning("Cosmos DB health check failed", exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the Cosmos DB client."""
        if self._client:
            await self._client.close()
            self._client = None
