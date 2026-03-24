"""Health-check endpoints for liveness and readiness probes.

GET /health       -- Liveness: always returns 200.
GET /health/ready -- Readiness: verifies Cosmos DB, AI Search, and OpenAI.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.models.schemas import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def liveness() -> HealthResponse:
    """Liveness probe -- always healthy if the process is running."""
    return HealthResponse(status="healthy", services={})


@router.get("/health/ready", response_model=HealthResponse)
async def readiness(request: Request) -> HealthResponse:
    """Readiness probe -- checks connectivity to all backend services.

    Returns HTTP 200 with status 'healthy' when all services are reachable,
    or HTTP 503 with status 'degraded' when one or more checks fail.
    """
    services: dict[str, str] = {}
    all_healthy = True

    # Cosmos DB
    try:
        cosmos_ok = await request.app.state.conversation_manager.health_check()
        services["cosmos_db"] = "healthy" if cosmos_ok else "unhealthy"
        if not cosmos_ok:
            all_healthy = False
    except Exception:
        services["cosmos_db"] = "unhealthy"
        all_healthy = False
        logger.warning("Cosmos DB readiness check raised exception", exc_info=True)

    # Azure AI Search
    try:
        search_ok = await request.app.state.search_service.health_check()
        services["ai_search"] = "healthy" if search_ok else "unhealthy"
        if not search_ok:
            all_healthy = False
    except Exception:
        services["ai_search"] = "unhealthy"
        all_healthy = False
        logger.warning("AI Search readiness check raised exception", exc_info=True)

    # Azure OpenAI
    try:
        openai_ok = await request.app.state.openai_service.health_check()
        services["openai"] = "healthy" if openai_ok else "unhealthy"
        if not openai_ok:
            all_healthy = False
    except Exception:
        services["openai"] = "unhealthy"
        all_healthy = False
        logger.warning("OpenAI readiness check raised exception", exc_info=True)

    status = "healthy" if all_healthy else "degraded"
    response = HealthResponse(status=status, services=services)

    if not all_healthy:
        from fastapi.responses import JSONResponse
        return JSONResponse(  # type: ignore[return-value]
            status_code=503,
            content=response.model_dump(),
        )

    return response
