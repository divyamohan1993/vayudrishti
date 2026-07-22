"""Live NIM smoke test (spec 14 first task). NOT collected by pytest.

Run: ``uv run python -m vayu.agents.smoke``

Makes ONE tiny real call to verify: key loads, model id resolves, thinking mode
returns a parseable ``</think>`` trace. On a model 404 it lists available models so
the integration can adapt. NEVER prints the API key.
"""

from __future__ import annotations

import json
import sys

from vayu.agents import nim
from vayu.settings import get_settings


def main() -> int:
    settings = get_settings()
    key = settings.nvidia_api_key
    if not key:
        print(json.dumps({"ok": False, "error": "NVIDIA_API_KEY not set in .env"}))
        return 1

    client = nim.build_client(key)
    try:
        result = nim.chat(
            client,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You are testing an API. Think briefly, then reply with "
                        "exactly the token: VAYU_OK"
                    ),
                }
            ],
            reasoning_budget=256,
            max_tokens=400,
            temperature=0.2,
        )
    except nim.NimError as exc:
        # Distinguish a model-id 404 from other failures by probing the model list.
        detail = str(exc)
        try:
            models = nim.list_models(client)
        except nim.NimError:
            models = []
        nemotron = [m for m in models if "nemotron" in m.lower()]
        print(
            json.dumps(
                {
                    "ok": False,
                    "error": detail,
                    "configured_model": nim.NIM_MODEL_ID,
                    "model_count": len(models),
                    "nemotron_models": nemotron[:20],
                },
                indent=2,
            )
        )
        return 1

    thinking_seen = bool(result.reasoning)
    answer_clean = nim.THINK_LEAK.search(result.content) is None
    print(
        json.dumps(
            {
                "ok": True,
                "model": nim.NIM_MODEL_ID,
                "endpoint": nim.NIM_BASE_URL,
                "finish_reason": result.finish_reason,
                "thinking_parsed": thinking_seen,
                "reasoning_chars": len(result.reasoning),
                "answer": result.content[:200],
                "answer_has_no_think_leak": answer_clean,
                "tokens_in": result.usage.tokens_in,
                "tokens_out": result.usage.tokens_out,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
