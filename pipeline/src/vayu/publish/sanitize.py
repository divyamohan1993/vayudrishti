"""String sanitization + strict validators for the content gate (spec 7).

Two roles, deliberately asymmetric:

- ``sanitize_text`` runs at PUBLISH time on untrusted upstream strings (ward / POI
  names from geojson, advisory text). It STRIPS HTML markup and control characters
  so emitted JSON is always clean.
- ``validate_clean`` (and the ``CleanStr`` / URL types) are STRICT validators used by
  the pydantic content models. They REJECT (never transform) any string carrying HTML
  markup, HTML entities, or control characters. Because publish sanitizes before
  constructing a model, real output passes; a poisoned or tampered file fails the gate
  (acceptance 13).
"""

from __future__ import annotations

import re
import unicodedata
from typing import Annotated

from pydantic import AfterValidator

# Angle brackets defuse the whole class of ``<script>`` / tag injections.
_ANGLE = re.compile(r"[<>]")
# C0 control characters plus DEL (includes tab and newline: emitted data strings are
# single-line names / short advisory text, so control chars are always suspect).
_CTRL = re.compile(r"[\x00-\x1f\x7f]")
# HTML numeric or named entities (encoded injection), e.g. &#60; &lt; &#x3c;
_ENTITY = re.compile(r"&(#x?[0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]{1,31});")
# Dangerous URI scheme fragments that can appear inside a data string.
_BAD_SCHEMES = ("javascript:", "vbscript:", "data:text/html")

# Secret-token shapes: hard-reject a leaked credential embedded in any data string
# (defence in depth with the ops secret-scan). NVIDIA nvapi-, OpenAI sk-, GitHub gh[opsu]_.
# Length floors avoid false positives on ordinary hyphenated words (e.g. "task-force").
_SECRET_TOKEN = re.compile(
    r"\b(nvapi-[A-Za-z0-9_-]{16,}|sk-[A-Za-z0-9]{20,}|gh[opsu]_[A-Za-z0-9]{20,})"
)

_HTTP = re.compile(r"^https?://", re.IGNORECASE)


def sanitize_text(value: str) -> str:
    """Publish-time cleaner: drop HTML markup + entities + control chars, collapse ws."""
    if not isinstance(value, str):
        value = str(value)
    value = unicodedata.normalize("NFC", value)
    value = _ANGLE.sub(" ", value)
    value = _ENTITY.sub(" ", value)
    value = _CTRL.sub(" ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def validate_clean(value: str) -> str:
    """Strict gate validator: reject HTML markup, entities, control chars, bad schemes."""
    if _ANGLE.search(value):
        raise ValueError("angle-bracket / HTML markup not permitted in emitted strings")
    if _CTRL.search(value):
        raise ValueError("control characters not permitted in emitted strings")
    if _ENTITY.search(value):
        raise ValueError("HTML entities not permitted in emitted strings")
    low = value.lower()
    for bad in _BAD_SCHEMES:
        if bad in low:
            raise ValueError(f"disallowed URI scheme fragment: {bad}")
    if _SECRET_TOKEN.search(value):
        raise ValueError("secret-token-shaped substring not permitted in emitted strings")
    return value


def validate_citation_url(value: str) -> str:
    """A public citation/source URL: clean + http(s). Query string allowed."""
    validate_clean(value)
    if not _HTTP.match(value):
        raise ValueError("url must be http(s)")
    return value


def validate_lineage_url(value: str) -> str:
    """A lineage base_url: clean + http(s) + NO query string (data.gov.in key leak, spec 7)."""
    validate_citation_url(value)
    if "?" in value:
        raise ValueError("lineage base_url must not contain a query string (secret-leak guard)")
    return value


# Reusable annotated string types for the content models.
CleanStr = Annotated[str, AfterValidator(validate_clean)]
CitationUrl = Annotated[str, AfterValidator(validate_citation_url)]
LineageUrl = Annotated[str, AfterValidator(validate_lineage_url)]


def clean_scalar(value):
    """Sanitize a value if it is a string, else pass through (for str|number fields)."""
    if isinstance(value, str):
        return validate_clean(value)
    return value


__all__ = [
    "sanitize_text",
    "validate_clean",
    "validate_citation_url",
    "validate_lineage_url",
    "clean_scalar",
    "CleanStr",
    "CitationUrl",
    "LineageUrl",
]
