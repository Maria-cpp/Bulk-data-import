"""Structured logging configuration using structlog."""

import logging
import sys
from typing import Any
from uuid import UUID, uuid4

import structlog
from structlog.types import Processor

from app.config import get_settings

settings = get_settings()

# Context variable for correlation ID
_correlation_id_var: UUID | None = None


def get_correlation_id() -> UUID:
    """Get or create correlation ID for current request."""
    global _correlation_id_var
    if _correlation_id_var is None:
        _correlation_id_var = uuid4()
    return _correlation_id_var


def set_correlation_id(correlation_id: UUID) -> None:
    """Set correlation ID for current request."""
    global _correlation_id_var
    _correlation_id_var = correlation_id


def reset_correlation_id() -> None:
    """Reset correlation ID (call at end of request)."""
    global _correlation_id_var
    _correlation_id_var = None


def add_correlation_id(
    logger: Any,
    method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add correlation ID to log events."""
    correlation_id = get_correlation_id()
    event_dict["correlation_id"] = str(correlation_id)
    return event_dict


def configure_logging() -> None:
    """Configure structured logging for the application."""
    # Determine processors based on format
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        add_correlation_id,
    ]

    if settings.LOG_FORMAT == "json":
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, settings.LOG_LEVEL.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)
