"""Shared fixtures and mocks for the Bill Explainer test suite.

Provides reusable fixtures that mock all Azure service dependencies,
sample data objects, and a FastAPI TestClient configured with
dependency overrides.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.models.schemas import (
    BillData,
    ChatRequest,
    FeedbackRequest,
    LineItem,
    ModelClassification,
    SearchResult,
    SessionResponse,
)


# -----------------------------------------------------------------------
# pytest configuration
# -----------------------------------------------------------------------

def pytest_configure(config: Any) -> None:
    """Register custom markers."""
    config.addinivalue_line("markers", "asyncio: mark a test as async")


# -----------------------------------------------------------------------
# Azure credential
# -----------------------------------------------------------------------

@pytest.fixture
def mock_credential() -> MagicMock:
    """Return a mocked DefaultAzureCredential."""
    with patch("azure.identity.DefaultAzureCredential") as mock_cls:
        credential = MagicMock()
        mock_cls.return_value = credential
        yield credential


# -----------------------------------------------------------------------
# Application settings
# -----------------------------------------------------------------------

@pytest.fixture
def mock_settings() -> MagicMock:
    """Return a mock Settings object with realistic test values."""
    settings = MagicMock()
    settings.azure_openai_endpoint = "https://test-oai.openai.azure.com/"
    settings.azure_openai_gpt4o_deployment = "gpt-4o"
    settings.azure_openai_gpt4o_mini_deployment = "gpt-4o-mini"
    settings.azure_openai_embedding_deployment = "text-embedding-3-small"
    settings.azure_search_endpoint = "https://test-search.search.windows.net"
    settings.azure_search_index_name = "knowledge-base"
    settings.cosmos_db_endpoint = "https://test-cosmos.documents.azure.com:443/"
    settings.cosmos_db_database_name = "billexplainer"
    settings.billing_api_base_url = "https://billing-api.CUSTOMER_NAME.test"
    settings.billing_api_client_id = "test-client-id"
    settings.billing_api_scope = "api://billing/.default"
    settings.key_vault_url = "https://test-kv.vault.azure.net/"
    settings.app_insights_connection_string = None
    settings.log_level = "DEBUG"
    settings.cors_allowed_origins = "*"
    settings.cors_origins_list = ["*"]
    return settings


# -----------------------------------------------------------------------
# Cosmos DB
# -----------------------------------------------------------------------

@pytest.fixture
def mock_cosmos_container() -> AsyncMock:
    """Return a mocked Cosmos DB container proxy."""
    container = AsyncMock()
    container.create_item = AsyncMock()
    container.read_item = AsyncMock()
    container.upsert_item = AsyncMock()
    container.delete_item = AsyncMock()
    container.query_items = MagicMock()
    return container


@pytest.fixture
def mock_cosmos_client(mock_cosmos_container: AsyncMock) -> AsyncMock:
    """Return a mocked CosmosClient whose containers return mock_cosmos_container."""
    client = AsyncMock()
    database = MagicMock()
    database.get_container_client = MagicMock(return_value=mock_cosmos_container)
    database.read = AsyncMock()
    client.get_database_client = MagicMock(return_value=database)
    return client


# -----------------------------------------------------------------------
# AI Search
# -----------------------------------------------------------------------

@pytest.fixture
def mock_search_client() -> AsyncMock:
    """Return a mocked Azure AI SearchClient."""
    client = AsyncMock()
    client.search = AsyncMock()
    client.close = AsyncMock()
    return client


# -----------------------------------------------------------------------
# OpenAI
# -----------------------------------------------------------------------

@pytest.fixture
def mock_openai_client() -> AsyncMock:
    """Return a mocked AsyncAzureOpenAI client."""
    client = AsyncMock()

    # Chat completions -- streaming mock
    chat_completions = AsyncMock()
    client.chat = MagicMock()
    client.chat.completions = MagicMock()
    client.chat.completions.create = chat_completions

    # Embeddings mock
    embeddings = AsyncMock()
    client.embeddings = MagicMock()
    client.embeddings.create = embeddings

    client.close = AsyncMock()
    return client


# -----------------------------------------------------------------------
# HTTP (httpx) for billing API
# -----------------------------------------------------------------------

@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    """Return a mocked httpx.AsyncClient."""
    client = AsyncMock()
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.aclose = AsyncMock()
    return client


# -----------------------------------------------------------------------
# Sample data fixtures
# -----------------------------------------------------------------------

@pytest.fixture
def sample_line_items() -> list[LineItem]:
    """Return a list of sample bill line items."""
    return [
        LineItem(
            description="Energia elettrica - quota fissa",
            amount=25.50,
            unit="EUR/mese",
            quantity=1.0,
        ),
        LineItem(
            description="Energia elettrica - quota variabile",
            amount=45.30,
            unit="kWh",
            quantity=180.0,
        ),
        LineItem(
            description="Oneri di sistema",
            amount=12.80,
        ),
    ]


@pytest.fixture
def sample_bill_data(sample_line_items: list[LineItem]) -> BillData:
    """Return a fully-populated BillData instance."""
    return BillData(
        bill_ref="BILL-2024-001",
        total_amount=125.60,
        currency="EUR",
        billing_period_start="2024-01-01",
        billing_period_end="2024-01-31",
        consumption_kwh=180.0,
        consumption_smc=45.0,
        tariff_code="TD-MONO",
        tariff_name="Tariffa Monoraria",
        line_items=sample_line_items,
        payment_status="pagata",
        due_date="2024-02-15",
    )


@pytest.fixture
def sample_search_results() -> list[SearchResult]:
    """Return a list of sample AI Search results."""
    return [
        SearchResult(
            content="Le tariffe monorarie applicano un prezzo unico per kWh.",
            source_document="guida_tariffe.pdf",
            category="tariffe",
            score=0.92,
            title="Guida alle tariffe",
        ),
        SearchResult(
            content="Gli oneri di sistema sono stabiliti da ARERA.",
            source_document="faq_oneri.pdf",
            category="oneri",
            score=0.85,
            title="FAQ Oneri di sistema",
        ),
    ]


@pytest.fixture
def sample_conversation_history() -> list[dict]:
    """Return a list of conversation history messages."""
    return [
        {
            "id": str(uuid.uuid4()),
            "sessionId": "session-abc-123",
            "role": "user",
            "content": "Quanto ho consumato il mese scorso?",
            "timestamp": "2024-06-01T10:00:00Z",
        },
        {
            "id": str(uuid.uuid4()),
            "sessionId": "session-abc-123",
            "role": "assistant",
            "content": "Secondo la sua bolletta, il consumo e' stato di 180 kWh.",
            "timestamp": "2024-06-01T10:00:05Z",
            "modelUsed": "gpt-4o-mini",
        },
    ]


@pytest.fixture
def sample_chat_request() -> ChatRequest:
    """Return a valid ChatRequest instance."""
    return ChatRequest(
        message="Perche' la mia bolletta e' aumentata?",
        session_id=None,
        bill_ref=None,
    )


@pytest.fixture
def sample_feedback_request() -> FeedbackRequest:
    """Return a valid FeedbackRequest instance."""
    return FeedbackRequest(
        session_id="session-abc-123",
        message_id="msg-def-456",
        rating="up",
        comment="Risposta molto chiara, grazie!",
    )


@pytest.fixture
def sample_session_doc() -> dict:
    """Return a raw Cosmos DB session document."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": "session-abc-123",
        "sessionId": "session-abc-123",
        "createdAt": now,
        "lastActive": now,
        "billRef": None,
        "messageCount": 2,
    }


# -----------------------------------------------------------------------
# FastAPI TestClient
# -----------------------------------------------------------------------

@pytest.fixture
def test_app() -> FastAPI:
    """Return a minimal FastAPI app with routers registered and mocked state."""
    from app.routers import chat, health, sessions

    app = FastAPI()
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(sessions.router)

    # Wire up mocked services on app.state
    app.state.conversation_manager = AsyncMock()
    app.state.rag_pipeline = AsyncMock()
    app.state.feedback_service = AsyncMock()
    app.state.openai_service = AsyncMock()
    app.state.search_service = AsyncMock()
    app.state.billing_api = AsyncMock()

    return app


@pytest.fixture
def test_client(test_app: FastAPI) -> TestClient:
    """Return a TestClient bound to the test FastAPI app."""
    return TestClient(test_app)
