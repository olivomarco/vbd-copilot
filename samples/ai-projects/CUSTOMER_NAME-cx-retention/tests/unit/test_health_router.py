"""Tests for routers/health.py -- liveness and readiness probes.

Covers the liveness endpoint (always healthy), readiness endpoint
with all services up, and readiness with degraded service.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestLiveness:
    """Test GET /health (liveness probe)."""

    def test_health_liveness(self, test_client: TestClient) -> None:
        """Liveness probe always returns 200 with 'healthy' status."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["services"] == {}


class TestReadiness:
    """Test GET /health/ready (readiness probe)."""

    def test_health_ready_all_ok(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """All services healthy returns 200 with status 'healthy'."""
        test_app.state.conversation_manager.health_check.return_value = True
        test_app.state.search_service.health_check.return_value = True
        test_app.state.openai_service.health_check.return_value = True

        response = test_client.get("/health/ready")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["services"]["cosmos_db"] == "healthy"
        assert data["services"]["ai_search"] == "healthy"
        assert data["services"]["openai"] == "healthy"

    def test_health_ready_cosmos_down(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """Cosmos DB unhealthy returns 503 with status 'degraded'."""
        test_app.state.conversation_manager.health_check.return_value = False
        test_app.state.search_service.health_check.return_value = True
        test_app.state.openai_service.health_check.return_value = True

        response = test_client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["cosmos_db"] == "unhealthy"
        assert data["services"]["ai_search"] == "healthy"

    def test_health_ready_search_down(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """AI Search unhealthy returns 503 with status 'degraded'."""
        test_app.state.conversation_manager.health_check.return_value = True
        test_app.state.search_service.health_check.return_value = False
        test_app.state.openai_service.health_check.return_value = True

        response = test_client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["ai_search"] == "unhealthy"

    def test_health_ready_openai_down(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """OpenAI unhealthy returns 503 with status 'degraded'."""
        test_app.state.conversation_manager.health_check.return_value = True
        test_app.state.search_service.health_check.return_value = True
        test_app.state.openai_service.health_check.return_value = False

        response = test_client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["services"]["openai"] == "unhealthy"

    def test_health_ready_all_down(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """All services down returns 503 with all unhealthy."""
        test_app.state.conversation_manager.health_check.return_value = False
        test_app.state.search_service.health_check.return_value = False
        test_app.state.openai_service.health_check.return_value = False

        response = test_client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert all(v == "unhealthy" for v in data["services"].values())

    def test_health_ready_service_exception(
        self, test_app: FastAPI, test_client: TestClient
    ) -> None:
        """Exception during health check marks service as unhealthy."""
        test_app.state.conversation_manager.health_check.side_effect = Exception("DB error")
        test_app.state.search_service.health_check.return_value = True
        test_app.state.openai_service.health_check.return_value = True

        response = test_client.get("/health/ready")

        assert response.status_code == 503
        data = response.json()
        assert data["services"]["cosmos_db"] == "unhealthy"
