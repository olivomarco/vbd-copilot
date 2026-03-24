"""Tests for routers/sessions.py -- session management endpoints.

Covers GET /api/v1/sessions/{id} and DELETE /api/v1/sessions/{id}
with mocked ConversationManager.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.schemas import MessageResponse, SessionResponse


class TestGetSession:
    """Test GET /api/v1/sessions/{session_id}."""

    def test_get_session(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """Known session ID returns session data with 200."""
        conversation_manager = test_app.state.conversation_manager
        now = datetime.now(timezone.utc)

        conversation_manager.get_session.return_value = SessionResponse(
            session_id="session-abc",
            created_at=now,
            last_active=now,
            bill_ref="BILL-001",
            message_count=3,
            messages=[
                MessageResponse(
                    message_id="msg-1",
                    role="user",
                    content="Ciao",
                    timestamp=now,
                ),
            ],
        )

        response = test_client.get("/api/v1/sessions/session-abc")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == "session-abc"
        assert data["bill_ref"] == "BILL-001"
        assert data["message_count"] == 3
        assert len(data["messages"]) == 1
        assert data["messages"][0]["role"] == "user"

    def test_get_session_not_found(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """Unknown session ID returns 404."""
        conversation_manager = test_app.state.conversation_manager
        conversation_manager.get_session.return_value = None

        response = test_client.get("/api/v1/sessions/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestDeleteSession:
    """Test DELETE /api/v1/sessions/{session_id}."""

    def test_delete_session(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """Successful deletion returns 204."""
        conversation_manager = test_app.state.conversation_manager
        conversation_manager.delete_session.return_value = True

        response = test_client.delete("/api/v1/sessions/session-to-delete")

        assert response.status_code == 204
        conversation_manager.delete_session.assert_awaited_once_with("session-to-delete")

    def test_delete_session_not_found(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """Deleting unknown session returns 404."""
        conversation_manager = test_app.state.conversation_manager
        conversation_manager.delete_session.return_value = False

        response = test_client.delete("/api/v1/sessions/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
