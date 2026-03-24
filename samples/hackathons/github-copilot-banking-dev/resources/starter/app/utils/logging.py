from __future__ import annotations

import logging

import structlog


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for structured logging throughout the application.

    In development mode the output is human-readable console format.
    In production it emits JSON lines compatible with Azure Monitor and
    Application Insights ingestion pipelines.
    """
    import os

    level = getattr(logging, os.environ.get("FINCORE_LOG_LEVEL", log_level).upper(), logging.INFO)

    logging.basicConfig(
        format="%(message)s",
        level=level,
    )

    is_dev = os.environ.get("FINCORE_ENVIRONMENT", "development") == "development"

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_dev:
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
