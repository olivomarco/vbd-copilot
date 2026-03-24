"""Tests for routers/chat.py -- chat and feedback endpoints.

Uses FastAPI TestClient with mocked services to verify SSE streaming,
session management, and feedback submission.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.schemas import ModelClassification


class TestChatEndpoint:
    """Test POST /api/v1/chat."""

    def test_chat_endpoint_returns_sse(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """POST /api/v1/chat returns text/event-stream content type."""
        # Configure mocks
        conversation_manager = test_app.state.conversation_manager
        rag_pipeline = test_app.state.rag_pipeline

        conversation_manager.get_or_create_session.return_value = {
            "sessionId": "new-session-id",
            "messageCount": 0,
        }
        conversation_manager.save_message.return_value = "msg-id-123"
        conversation_manager.get_conversation_history.return_value = []

        classification = ModelClassification(
            model="gpt-4o-mini",
            needs_billing_data=False,
            reasoning="Simple FAQ",
        )

        async def mock_process_query(**kwargs):  # type: ignore[no-untyped-def]
            yield "Risposta ", classification
            yield "di test.", classification

        rag_pipeline.process_query = mock_process_query

        response = test_client.post(
            "/api/v1/chat",
            json={"message": "Come pago la bolletta?"},
        )

        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")

    def test_chat_endpoint_new_session(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """No session_id in request creates a new session."""
        conversation_manager = test_app.state.conversation_manager
        rag_pipeline = test_app.state.rag_pipeline

        conversation_manager.get_or_create_session.return_value = {
            "sessionId": "fresh-session",
            "messageCount": 0,
        }
        conversation_manager.save_message.return_value = "msg-001"
        conversation_manager.get_conversation_history.return_value = []

        classification = ModelClassification(
            model="gpt-4o-mini",
            needs_billing_data=False,
            reasoning="Simple",
        )

        async def mock_process_query(**kwargs):  # type: ignore[no-untyped-def]
            yield "Ok.", classification

        rag_pipeline.process_query = mock_process_query

        response = test_client.post(
            "/api/v1/chat",
            json={"message": "Ciao"},
        )

        assert response.status_code == 200
        # Verify get_or_create_session was called with session_id=None
        call_kwargs = conversation_manager.get_or_create_session.call_args.kwargs
        assert call_kwargs.get("session_id") is None

    def test_chat_endpoint_existing_session(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """Providing session_id reuses existing session."""
        conversation_manager = test_app.state.conversation_manager
        rag_pipeline = test_app.state.rag_pipeline

        conversation_manager.get_or_create_session.return_value = {
            "sessionId": "existing-session",
            "messageCount": 5,
        }
        conversation_manager.save_message.return_value = "msg-002"
        conversation_manager.get_conversation_history.return_value = [
            {"role": "user", "content": "Hi"},
        ]

        classification = ModelClassification(
            model="gpt-4o-mini",
            needs_billing_data=False,
            reasoning="Simple",
        )

        async def mock_process_query(**kwargs):  # type: ignore[no-untyped-def]
            yield "Risposta.", classification

        rag_pipeline.process_query = mock_process_query

        response = test_client.post(
            "/api/v1/chat",
            json={
                "message": "Ancora una domanda",
                "session_id": "existing-session",
            },
        )

        assert response.status_code == 200
        call_kwargs = conversation_manager.get_or_create_session.call_args.kwargs
        assert call_kwargs.get("session_id") == "existing-session"

    def test_chat_endpoint_sse_events_structure(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """SSE events contain valid JSON with token and done fields."""
        conversation_manager = test_app.state.conversation_manager
        rag_pipeline = test_app.state.rag_pipeline

        conversation_manager.get_or_create_session.return_value = {
            "sessionId": "test-session",
            "messageCount": 0,
        }
        conversation_manager.save_message.return_value = "msg-003"
        conversation_manager.get_conversation_history.return_value = []

        classification = ModelClassification(
            model="gpt-4o-mini",
            needs_billing_data=False,
            reasoning="Simple",
        )

        async def mock_process_query(**kwargs):  # type: ignore[no-untyped-def]
            yield "Token1", classification

        rag_pipeline.process_query = mock_process_query

        response = test_client.post(
            "/api/v1/chat",
            json={"message": "Test"},
        )

        assert response.status_code == 200
        # Parse SSE data lines
        body = response.text
        data_lines = [
            line.replace("data: ", "")
            for line in body.split("\n")
            if line.startswith("data: ")
        ]
        assert len(data_lines) >= 1

        # Each data line should be valid JSON
        for line in data_lines:
            parsed = json.loads(line)
            assert "token" in parsed
            assert "done" in parsed

    def test_chat_endpoint_validation_error(
        self, test_client: TestClient
    ) -> None:
        """Missing message field returns 422."""
        response = test_client.post(
            "/api/v1/chat",
            json={},
        )
        assert response.status_code == 422


class TestFeedbackEndpoint:
    """Test POST /api/v1/chat/feedback."""

    def test_chat_feedback_success(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """Valid feedback returns 200 with feedback_id."""
        feedback_service = test_app.state.feedback_service
        feedback_service.save_feedback.return_value = "fb-id-001"

        response = test_client.post(
            "/api/v1/chat/feedback",
            json={
                "session_id": "session-1",
                "message_id": "msg-1",
                "rating": "up",
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["feedback_id"] == "fb-id-001"
        assert data["status"] == "recorded"

    def test_chat_feedback_with_comment(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """Feedback with comment is accepted."""
        feedback_service = test_app.state.feedback_service
        feedback_service.save_feedback.return_value = "fb-id-002"

        response = test_client.post(
            "/api/v1/chat/feedback",
            json={
                "session_id": "session-1",
                "message_id": "msg-1",
                "rating": "down",
                "comment": "Non era pertinente",
            },
        )

        assert response.status_code == 200
        # Verify comment was passed to service
        call_kwargs = feedback_service.save_feedback.call_args.kwargs
        assert call_kwargs.get("comment") == "Non era pertinente"

    def test_chat_feedback_invalid_rating(
        self, test_client: TestClient
    ) -> None:
        """Invalid rating value returns 422."""
        response = test_client.post(
            "/api/v1/chat/feedback",
            json={
                "session_id": "session-1",
                "message_id": "msg-1",
                "rating": "neutral",
            },
        )
        assert response.status_code == 422

    def test_chat_feedback_missing_fields(
        self, test_client: TestClient
    ) -> None:
        """Missing required fields return 422."""
        response = test_client.post(
            "/api/v1/chat/feedback",
            json={"rating": "up"},
        )
        assert response.status_code == 422

    def test_chat_feedback_service_error(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """Internal error in feedback service returns 500."""
        feedback_service = test_app.state.feedback_service
        feedback_service.save_feedback.side_effect = Exception("Cosmos DB error")

        response = test_client.post(
            "/api/v1/chat/feedback",
            json={
                "session_id": "session-1",
                "message_id": "msg-1",
                "rating": "up",
            },
        )
        assert response.status_code == 500
