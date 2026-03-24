"""FastAPI application entry point for the CUSTOMER_NAME Bill Explainer.

Responsibilities:
  - Application lifespan: initialise and tear down service clients
  - CORS middleware with configurable origins
  - Router registration (chat, sessions, health)
  - Static file mount for the frontend chat widget
  - OpenTelemetry / Azure Monitor integration (when configured)
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from azure.identity import DefaultAzureCredential
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.routers import chat, health, sessions
from app.services.billing_api import BillingAPIClient
from app.services.conversation_manager import ConversationManager
from app.services.feedback_service import FeedbackService
from app.services.model_router import ModelRouter
from app.services.openai_service import OpenAIService
from app.services.rag_pipeline import RAGPipeline
from app.services.search_service import SearchService

logger = logging.getLogger(__name__)


def _configure_logging(settings: Settings) -> None:
    """Set up structured logging at the configured level."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def _configure_telemetry(settings: Settings) -> None:
    """Activate Azure Monitor OpenTelemetry if a connection string is present."""
    if not settings.app_insights_connection_string:
        logger.info("Application Insights not configured -- telemetry disabled")
        return

    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=settings.app_insights_connection_string,
        )
        logger.info("Azure Monitor OpenTelemetry configured")
    except ImportError:
        logger.warning(
            "azure-monitor-opentelemetry package not installed -- telemetry disabled"
        )
    except Exception:
        logger.warning("Failed to configure Azure Monitor", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: initialise services on startup, close on shutdown."""
    settings = get_settings()
    _configure_logging(settings)
    _configure_telemetry(settings)

    logger.info("Starting CUSTOMER_NAME Bill Explainer backend")

    # Shared credential for all Azure SDK clients
    credential = DefaultAzureCredential()

    # Initialise services
    openai_service = OpenAIService(settings, credential)
    search_service = SearchService(settings, credential, openai_service)
    conversation_manager = ConversationManager(settings, credential)
    feedback_service = FeedbackService(settings, credential)
    billing_api = BillingAPIClient(settings, credential)
    model_router = ModelRouter(settings)

    rag_pipeline = RAGPipeline(
        model_router=model_router,
        search_service=search_service,
        openai_service=openai_service,
        billing_api=billing_api,
    )

    # Attach to app state so routers can access them via request.app.state
    app.state.openai_service = openai_service
    app.state.search_service = search_service
    app.state.conversation_manager = conversation_manager
    app.state.feedback_service = feedback_service
    app.state.billing_api = billing_api
    app.state.rag_pipeline = rag_pipeline

    logger.info("All services initialised")

    yield

    # Shutdown: close all clients
    logger.info("Shutting down services")
    await openai_service.close()
    await search_service.close()
    await conversation_manager.close()
    await feedback_service.close()
    await billing_api.close()
    logger.info("All services closed")


def create_app() -> FastAPI:
    """Factory function that assembles the FastAPI application."""
    app = FastAPI(
        title="CUSTOMER_NAME Intelligent Bill Explainer",
        description="RAG-based chatbot that explains Italian energy bills",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS middleware -- origins are configurable via env
    settings = get_settings()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register API routers
    app.include_router(health.router)
    app.include_router(chat.router)
    app.include_router(sessions.router)

    # Mount frontend static files (if the directory exists)
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    if frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="static")
        logger.info("Frontend static files mounted from %s", frontend_dir)

    return app


# Module-level app instance used by ``uvicorn app.main:app``
app = create_app()
