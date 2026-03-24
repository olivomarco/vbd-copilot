"""Tests for services/conversation_manager.py -- Cosmos DB CRUD operations.

Covers session creation, message persistence, conversation history
retrieval, and GDPR deletion. All Cosmos DB operations are mocked.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.schemas import SessionResponse
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from app.services.conversation_manager import ConversationManager


@pytest.fixture
def manager(mock_settings: MagicMock, mock_credential: MagicMock) -> ConversationManager:
    """Create a ConversationManager with mocked Cosmos DB client."""
    mgr = ConversationManager(mock_settings, mock_credential)
    return mgr


@pytest.fixture
def patched_manager(
    manager: ConversationManager,
    mock_cosmos_client: AsyncMock,
    mock_cosmos_container: AsyncMock,
) -> ConversationManager:
    """Manager with pre-initialised mock Cosmos client."""
    manager._client = mock_cosmos_client
    return manager


class TestCreateSession:
    """Test session creation."""

    @pytest.mark.asyncio
    async def test_create_session(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """New session is created with correct fields."""
        session = await patched_manager.get_or_create_session()

        mock_cosmos_container.create_item.assert_awaited_once()
        created_doc = mock_cosmos_container.create_item.call_args[0][0]

        assert "id" in created_doc
        assert "sessionId" in created_doc
        assert created_doc["id"] == created_doc["sessionId"]
        assert "createdAt" in created_doc
        assert "lastActive" in created_doc
        assert created_doc["messageCount"] == 0

    @pytest.mark.asyncio
    async def test_create_session_with_bill_ref(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """New session includes the bill reference when provided."""
        session = await patched_manager.get_or_create_session(bill_ref="BILL-001")

        created_doc = mock_cosmos_container.create_item.call_args[0][0]
        assert created_doc["billRef"] == "BILL-001"


class TestGetExistingSession:
    """Test loading existing sessions."""

    @pytest.mark.asyncio
    async def test_get_existing_session(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Existing session is loaded and timestamp updated."""
        existing = {
            "id": "session-123",
            "sessionId": "session-123",
            "createdAt": "2024-06-01T10:00:00Z",
            "lastActive": "2024-06-01T10:00:00Z",
            "billRef": None,
            "messageCount": 5,
        }
        mock_cosmos_container.read_item.return_value = existing

        session = await patched_manager.get_or_create_session(session_id="session-123")

        mock_cosmos_container.read_item.assert_awaited_once_with(
            item="session-123",
            partition_key="session-123",
        )
        assert session["sessionId"] == "session-123"
        # lastActive should have been updated
        mock_cosmos_container.upsert_item.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_or_create_returns_new(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Session not found falls back to creation."""
        mock_cosmos_container.read_item.side_effect = CosmosResourceNotFoundError(status_code=404, message="Not found")

        session = await patched_manager.get_or_create_session(session_id="missing-id")

        # Should have attempted read, then created a new session
        mock_cosmos_container.read_item.assert_awaited_once()
        mock_cosmos_container.create_item.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_session(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """get_session returns a SessionResponse with message history."""
        existing = {
            "id": "session-456",
            "sessionId": "session-456",
            "createdAt": "2024-06-01T10:00:00Z",
            "lastActive": "2024-06-01T10:05:00Z",
            "billRef": "BILL-001",
            "messageCount": 1,
        }
        mock_cosmos_container.read_item.return_value = existing

        # Mock query_items to return messages
        messages = [
            {
                "id": "msg-1",
                "sessionId": "session-456",
                "role": "user",
                "content": "Ciao",
                "timestamp": "2024-06-01T10:00:00Z",
            },
        ]

        async def mock_query_iter(*args, **kwargs):  # type: ignore[no-untyped-def]
            for item in messages:
                yield item

        mock_cosmos_container.query_items.return_value = mock_query_iter()

        result = await patched_manager.get_session("session-456")

        assert result is not None
        assert isinstance(result, SessionResponse)
        assert result.session_id == "session-456"
        assert result.bill_ref == "BILL-001"

    @pytest.mark.asyncio
    async def test_get_session_not_found(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """get_session returns None for unknown session."""
        mock_cosmos_container.read_item.side_effect = CosmosResourceNotFoundError(status_code=404, message="Not found")

        result = await patched_manager.get_session("nonexistent")
        assert result is None


class TestSaveMessage:
    """Test message persistence."""

    @pytest.mark.asyncio
    async def test_save_user_message(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """User message saved with role='user'."""
        # Mock session read for counter update
        mock_cosmos_container.read_item.return_value = {
            "id": "session-1",
            "sessionId": "session-1",
            "messageCount": 0,
        }

        msg_id = await patched_manager.save_message(
            session_id="session-1",
            role="user",
            content="Quanto costa la bolletta?",
        )

        assert isinstance(msg_id, str)
        assert len(msg_id) > 0

        # Check message doc created
        create_calls = mock_cosmos_container.create_item.call_args_list
        msg_doc = create_calls[0][0][0]
        assert msg_doc["role"] == "user"
        assert msg_doc["content"] == "Quanto costa la bolletta?"
        assert msg_doc["sessionId"] == "session-1"
        assert "timestamp" in msg_doc

    @pytest.mark.asyncio
    async def test_save_assistant_message(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Assistant message saved with metadata (model, tokens)."""
        mock_cosmos_container.read_item.return_value = {
            "id": "session-1",
            "sessionId": "session-1",
            "messageCount": 1,
        }

        metadata = {
            "model_used": "gpt-4o",
            "prompt_tokens": 500,
            "completion_tokens": 200,
        }

        msg_id = await patched_manager.save_message(
            session_id="session-1",
            role="assistant",
            content="La bolletta ammonta a 125.60 EUR.",
            metadata=metadata,
        )

        assert isinstance(msg_id, str)

        create_calls = mock_cosmos_container.create_item.call_args_list
        msg_doc = create_calls[0][0][0]
        assert msg_doc["role"] == "assistant"
        assert msg_doc["modelUsed"] == "gpt-4o"
        assert msg_doc["promptTokens"] == 500
        assert msg_doc["completionTokens"] == 200


class TestGetConversationHistory:
    """Test message retrieval."""

    @pytest.mark.asyncio
    async def test_get_conversation_history(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Returns messages ordered by timestamp ascending (reversed)."""
        messages = [
            {"id": "msg-2", "role": "assistant", "content": "Resp", "timestamp": "T2"},
            {"id": "msg-1", "role": "user", "content": "Hello", "timestamp": "T1"},
        ]

        async def mock_query_iter(*args, **kwargs):  # type: ignore[no-untyped-def]
            for item in messages:
                yield item

        mock_cosmos_container.query_items.return_value = mock_query_iter()

        result = await patched_manager.get_conversation_history("session-1")

        assert len(result) == 2
        # Items should be reversed (chronological order)
        assert result[0]["id"] == "msg-1"
        assert result[1]["id"] == "msg-2"

    @pytest.mark.asyncio
    async def test_get_conversation_history_limit(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Respects the limit parameter."""
        async def mock_query_iter(*args, **kwargs):  # type: ignore[no-untyped-def]
            for item in []:
                yield item

        mock_cosmos_container.query_items.return_value = mock_query_iter()

        await patched_manager.get_conversation_history("session-1", limit=5)

        call_args = mock_cosmos_container.query_items.call_args
        parameters = call_args.kwargs.get("parameters") or call_args[1].get("parameters")
        limit_param = [p for p in parameters if p["name"] == "@limit"]
        assert len(limit_param) == 1
        assert limit_param[0]["value"] == 5


class TestDeleteSession:
    """Test GDPR session deletion."""

    @pytest.mark.asyncio
    async def test_delete_session_gdpr(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Deletes session + all messages + feedback."""
        # Mock query for messages and feedback
        async def mock_query_iter(*args, **kwargs):  # type: ignore[no-untyped-def]
            for item in [{"id": "item-1"}, {"id": "item-2"}]:
                yield item

        mock_cosmos_container.query_items.return_value = mock_query_iter()
        mock_cosmos_container.delete_item.return_value = None

        result = await patched_manager.delete_session("session-to-delete")

        assert result is True
        # Session delete was called
        assert mock_cosmos_container.delete_item.await_count >= 1

    @pytest.mark.asyncio
    async def test_delete_session_not_found(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Returns False if session not found."""
        mock_cosmos_container.delete_item.side_effect = Exception("Not found")

        result = await patched_manager.delete_session("nonexistent")
        assert result is False


class TestHealthCheck:
    """Test Cosmos DB health probe."""

    @pytest.mark.asyncio
    async def test_health_check_success(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_client: AsyncMock,
    ) -> None:
        """Healthy Cosmos DB returns True."""
        result = await patched_manager.health_check()
        assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_client: AsyncMock,
    ) -> None:
        """Failed Cosmos DB read returns False."""
        db_client = mock_cosmos_client.get_database_client.return_value
        db_client.read.side_effect = Exception("Connection failed")

        result = await patched_manager.health_check()
        assert result is False


class TestClose:
    """Test client lifecycle."""

    @pytest.mark.asyncio
    async def test_close(
        self,
        patched_manager: ConversationManager,
        mock_cosmos_client: AsyncMock,
    ) -> None:
        """close() calls close on the Cosmos client and resets to None."""
        await patched_manager.close()
        mock_cosmos_client.close.assert_awaited_once()
        assert patched_manager._client is None
