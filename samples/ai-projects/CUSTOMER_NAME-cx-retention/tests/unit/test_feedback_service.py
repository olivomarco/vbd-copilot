"""Tests for services/feedback_service.py -- Cosmos DB feedback storage.

Covers saving feedback with different ratings and optional comments.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.feedback_service import FeedbackService


@pytest.fixture
def service(mock_settings: MagicMock, mock_credential: MagicMock) -> FeedbackService:
    """Create a FeedbackService with mocked Cosmos DB."""
    svc = FeedbackService(mock_settings, mock_credential)
    return svc


@pytest.fixture
def patched_service(
    service: FeedbackService,
    mock_cosmos_client: AsyncMock,
    mock_cosmos_container: AsyncMock,
) -> FeedbackService:
    """Service with pre-initialised mock Cosmos client."""
    service._client = mock_cosmos_client
    return service


class TestSaveFeedback:
    """Test feedback persistence."""

    @pytest.mark.asyncio
    async def test_save_feedback_up(
        self,
        patched_service: FeedbackService,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Rating 'up' saved correctly."""
        feedback_id = await patched_service.save_feedback(
            session_id="session-1",
            message_id="msg-1",
            rating="up",
        )

        assert isinstance(feedback_id, str)
        assert len(feedback_id) > 0

        mock_cosmos_container.create_item.assert_awaited_once()
        doc = mock_cosmos_container.create_item.call_args[0][0]
        assert doc["sessionId"] == "session-1"
        assert doc["messageId"] == "msg-1"
        assert doc["rating"] == "up"
        assert doc["comment"] is None
        assert "timestamp" in doc

    @pytest.mark.asyncio
    async def test_save_feedback_down(
        self,
        patched_service: FeedbackService,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Rating 'down' saved correctly."""
        feedback_id = await patched_service.save_feedback(
            session_id="session-2",
            message_id="msg-2",
            rating="down",
        )

        assert isinstance(feedback_id, str)
        doc = mock_cosmos_container.create_item.call_args[0][0]
        assert doc["rating"] == "down"

    @pytest.mark.asyncio
    async def test_save_feedback_with_comment(
        self,
        patched_service: FeedbackService,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Optional comment is included in the document."""
        await patched_service.save_feedback(
            session_id="session-3",
            message_id="msg-3",
            rating="up",
            comment="Risposta molto chiara!",
        )

        doc = mock_cosmos_container.create_item.call_args[0][0]
        assert doc["comment"] == "Risposta molto chiara!"

    @pytest.mark.asyncio
    async def test_save_feedback_generates_unique_id(
        self,
        patched_service: FeedbackService,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Each feedback record gets a unique UUID."""
        id1 = await patched_service.save_feedback(
            session_id="s1", message_id="m1", rating="up"
        )
        id2 = await patched_service.save_feedback(
            session_id="s1", message_id="m2", rating="down"
        )
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_save_feedback_document_structure(
        self,
        patched_service: FeedbackService,
        mock_cosmos_container: AsyncMock,
    ) -> None:
        """Document has all required Cosmos DB fields."""
        await patched_service.save_feedback(
            session_id="session-x",
            message_id="msg-y",
            rating="down",
            comment="Non pertinente",
        )

        doc = mock_cosmos_container.create_item.call_args[0][0]
        required_keys = {"id", "sessionId", "messageId", "rating", "comment", "timestamp"}
        assert required_keys.issubset(set(doc.keys()))


class TestFeedbackServiceClose:
    """Test client lifecycle."""

    @pytest.mark.asyncio
    async def test_close(
        self,
        patched_service: FeedbackService,
        mock_cosmos_client: AsyncMock,
    ) -> None:
        """close() calls close on the Cosmos client and resets to None."""
        await patched_service.close()
        mock_cosmos_client.close.assert_awaited_once()
        assert patched_service._client is None

    @pytest.mark.asyncio
    async def test_close_when_no_client(
        self,
        service: FeedbackService,
    ) -> None:
        """close() is safe to call when client is not initialised."""
        await service.close()  # Should not raise
