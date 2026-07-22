"""Thin, honest wrapper over the hosted Nemotron NIM endpoint (spec 14).

Facts (fixed by the NIM reference; do not guess):
- Endpoint ``https://integrate.api.nvidia.com/v1`` (OpenAI-compatible; the ``openai``
  Python client with a ``base_url`` override).
- Model id ``nvidia/nemotron-3-ultra-550b-a55b``.
- Key ``NVIDIA_API_KEY`` from pydantic-settings. NEVER logged or published.
- Thinking mode via ``extra_body`` (``enable_thinking`` + ``force_nonempty_content``,
  the latter REQUIRED when tool calling is combined with reasoning) and a
  top-level ``reasoning_budget`` hard ceiling.
- No native ``response_format`` json-schema: structured answers arrive through a
  ``submit_brief`` tool whose parameters mirror the briefs schema.

This module owns ONLY transport + trace parsing + usage accounting. It contains no
prompts and no brief logic; the agent roles live in ``vayu.agents.roles``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Fixed integration facts (spec 14). Kept here as the single source of truth.
NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"
NIM_MODEL_ID = "nvidia/nemotron-3-ultra-550b-a55b"

# The model emits its chain-of-thought wrapped in <think>...</think>. Some template
# variants omit the opening tag and emit only the closing </think>; handle both.
_THINK_CLOSE = "</think>"
_THINK_OPEN = "<think>"
# Belt-and-braces leak guard used by the publish gate too (acceptance 20).
THINK_LEAK = re.compile(r"</?think\b", re.IGNORECASE)


class NimError(RuntimeError):
    """Any NIM transport/protocol failure. The briefs command catches this and keeps
    the previous briefs.json (stale), never failing the publish pipeline (spec 14)."""


@dataclass(slots=True)
class Usage:
    tokens_in: int = 0
    tokens_out: int = 0

    @property
    def total(self) -> int:
        return self.tokens_in + self.tokens_out


@dataclass(slots=True)
class ChatResult:
    """Parsed result of one chat turn: reasoning stripped from the visible content,
    any tool calls surfaced, token usage accounted."""

    content: str
    reasoning: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    finish_reason: str | None = None
    usage: Usage = field(default_factory=Usage)
    raw_message: Any = None


def split_thinking(text: str | None) -> tuple[str, str]:
    """Split model content into (reasoning, answer).

    Everything up to and including the first ``</think>`` is reasoning (a leading
    ``<think>`` is dropped); the remainder is the visible answer. Text with no think
    tag is treated as pure answer. Raw reasoning is returned so the caller can log it
    LOCALLY only (gitignored); it is never published (spec 14).
    """
    if not text:
        return "", ""
    idx = text.find(_THINK_CLOSE)
    if idx == -1:
        return "", text.strip()
    reasoning = text[:idx]
    if reasoning.lstrip().startswith(_THINK_OPEN):
        reasoning = reasoning.lstrip()[len(_THINK_OPEN) :]
    answer = text[idx + len(_THINK_CLOSE) :]
    return reasoning.strip(), answer.strip()


def build_client(api_key: str):
    """Construct an OpenAI client pointed at the NIM endpoint.

    Imported lazily so the pipeline imports cleanly without ``openai`` at hand and so
    tests can run fully mocked.
    """
    from openai import OpenAI

    # Reasoning-mode calls legitimately take 60-90s; a generous per-attempt timeout plus
    # client-side retries rides out the hosted endpoint's intermittent slowness. A call that
    # still fails surfaces as NimError and the briefs stage keeps the previous briefs (stale).
    return OpenAI(api_key=api_key, base_url=NIM_BASE_URL, max_retries=3, timeout=180.0)


def _extract_usage(response: Any) -> Usage:
    usage = getattr(response, "usage", None)
    if usage is None:
        return Usage()
    return Usage(
        tokens_in=int(getattr(usage, "prompt_tokens", 0) or 0),
        tokens_out=int(getattr(usage, "completion_tokens", 0) or 0),
    )


def _extract_tool_calls(message: Any) -> list[dict[str, Any]]:
    calls = getattr(message, "tool_calls", None) or []
    out: list[dict[str, Any]] = []
    for call in calls:
        fn = getattr(call, "function", None)
        out.append(
            {
                "id": getattr(call, "id", None),
                "name": getattr(fn, "name", None) if fn else None,
                "arguments": getattr(fn, "arguments", "") if fn else "",
            }
        )
    return out


def chat(
    client: Any,
    *,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    tool_choice: Any = None,
    reasoning_budget: int = 4096,
    temperature: float = 1.0,
    top_p: float = 0.95,
    max_tokens: int = 2048,
    model: str = NIM_MODEL_ID,
    enable_thinking: bool = True,
) -> ChatResult:
    """One reasoning-mode chat turn. Raises :class:`NimError` on any failure so the
    caller can apply stale-keep failure semantics.
    """
    extra_body: dict[str, Any] = {
        "chat_template_kwargs": {
            "enable_thinking": enable_thinking,
            # REQUIRED when combining tool calling with reasoning (spec 14).
            "force_nonempty_content": True,
        },
        "reasoning_budget": int(reasoning_budget),
    }
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "extra_body": extra_body,
    }
    if tools:
        kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

    try:
        response = client.chat.completions.create(**kwargs)
    except Exception as exc:  # noqa: BLE001 - normalize every transport error
        raise NimError(f"NIM chat call failed: {type(exc).__name__}") from exc

    try:
        choice = response.choices[0]
        message = choice.message
    except (AttributeError, IndexError) as exc:
        raise NimError("NIM response missing choices/message") from exc

    # Reasoning may arrive in a dedicated field OR inline within content.
    reasoning_field = getattr(message, "reasoning_content", None) or ""
    reasoning_inline, answer = split_thinking(getattr(message, "content", None))
    reasoning = (
        (reasoning_field.strip() + "\n" + reasoning_inline).strip()
        if reasoning_field
        else reasoning_inline
    )

    return ChatResult(
        content=answer,
        reasoning=reasoning,
        tool_calls=_extract_tool_calls(message),
        finish_reason=getattr(choice, "finish_reason", None),
        usage=_extract_usage(response),
        raw_message=message,
    )


def list_models(client: Any) -> list[str]:
    """Return available model ids (used to adapt if the hosted id 404s)."""
    try:
        page = client.models.list()
    except Exception as exc:  # noqa: BLE001
        raise NimError(f"NIM models.list failed: {type(exc).__name__}") from exc
    return [getattr(m, "id", "") for m in getattr(page, "data", [])]


__all__ = [
    "NIM_BASE_URL",
    "NIM_MODEL_ID",
    "THINK_LEAK",
    "NimError",
    "Usage",
    "ChatResult",
    "split_thinking",
    "build_client",
    "chat",
    "list_models",
]
