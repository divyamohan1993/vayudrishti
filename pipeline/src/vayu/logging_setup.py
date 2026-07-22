"""structlog JSON logging. No secrets in logs (spec 7)."""

from __future__ import annotations

import logging
import re

import structlog

# Redact anything that looks like a key=value secret slipping into a log event.
_SECRET_KEYS = re.compile(r"(api[-_]?key|api-key|token|secret|password|access[-_]?key)", re.I)


def _redact_secrets(_logger, _method, event_dict):
    for key in list(event_dict):
        if _SECRET_KEYS.search(key):
            event_dict[key] = "***"
    return event_dict


def configure_logging(level: str = "info") -> None:
    """Configure structlog to emit JSON to stdout at the given level."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(format="%(message)s", level=numeric)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            _redact_secrets,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
