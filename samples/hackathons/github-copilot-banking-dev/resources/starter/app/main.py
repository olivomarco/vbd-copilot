from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routers import accounts, auth, transactions, transfers
from app.config import settings
from app.exceptions import BankingError
from app.utils.logging import configure_logging

configure_logging()

import structlog  # noqa: E402

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="FinCore Bank API",
    description="Retail banking API for FinCore Bank internal engineering systems.",
    version="1.0.0",
    docs_url="/docs" if settings.is_development else None,
    redoc_url="/redoc" if settings.is_development else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BankingError)
async def banking_error_handler(request: Request, exc: BankingError) -> JSONResponse:
    """Convert domain errors to structured HTTP responses."""
    logger.warning(
        "banking_error",
        error_code=exc.error_code,
        message=exc.message,
        path=str(request.url),
    )
    status_map = {
        "ACCOUNT_NOT_FOUND": 404,
        "TRANSACTION_NOT_FOUND": 404,
        "INSUFFICIENT_FUNDS": 422,
        "ACCOUNT_CLOSED": 422,
        "VALIDATION_ERROR": 400,
        "DUPLICATE_ACCOUNT": 409,
    }
    status_code = status_map.get(exc.error_code, 400)
    return JSONResponse(
        status_code=status_code,
        content={"error": exc.error_code, "message": exc.message},
    )


app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
app.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
app.include_router(transfers.router, prefix="/transfers", tags=["transfers"])


@app.get("/health", tags=["system"])
async def health_check() -> dict:
    """Public health-check endpoint used by load balancers and monitors."""
    return {"status": "ok", "service": "fincore-bank-api", "version": "1.0.0"}
