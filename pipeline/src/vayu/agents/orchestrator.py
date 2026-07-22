"""The bounded 4-role orchestration (spec 14): Situation Analyst -> Causal Strategist ->
Action Drafter -> Adversarial Verifier, then the authoritative deterministic resolver gate.

Token frugality is structural: the digest front-loads signals, each role gets a hard
reasoning-budget cap, drill-down tool rounds are bounded, the drafter repairs at most twice,
and a global call counter trips before any run can spend without limit. Every NIM call is
logged (redacted) into the agentlog.

The NIM call is injected as ``call_fn`` so the whole loop is unit-testable with a scripted
fake and zero network (repair-loop, gate, and failure-semantics tests).
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from vayu.agents import resolver, roles, tools
from vayu.agents.contracts import AgentLogDoc, Brief, BriefsDoc
from vayu.agents.nim import NIM_MODEL_ID, ChatResult, NimError
from vayu.agents.roles import RoleConfig
from vayu.logging_setup import get_logger

log = get_logger("vayu.agents")

# Hard ceiling on NIM calls per city run (4 roles + drill-down + <=2 repairs, bounded).
MAX_CALLS = 16
MAX_TOOL_ROUNDS = 2
MAX_REPAIRS = 2

CallFn = Callable[..., ChatResult]


@dataclass(slots=True)
class AgentRunner:
    """Wraps the injected NIM call with a call budget and an agentlog accumulator."""

    call_fn: CallFn
    model: str = NIM_MODEL_ID
    max_calls: int = MAX_CALLS
    calls: int = 0
    runs: list[dict[str, Any]] = field(default_factory=list)

    def call(
        self,
        cfg: RoleConfig,
        *,
        city: str,
        messages: list[dict[str, Any]],
        tools_arg: list[dict[str, Any]] | None,
        tool_choice: Any,
        repairs: int = 0,
    ) -> ChatResult:
        if self.calls >= self.max_calls:
            raise NimError(f"NIM call budget exceeded ({self.max_calls})")
        t0 = time.monotonic()
        result = self.call_fn(
            messages=messages,
            tools=tools_arg,
            tool_choice=tool_choice,
            reasoning_budget=cfg.reasoning_budget,
            temperature=cfg.temperature,
            top_p=cfg.top_p,
            max_tokens=cfg.max_tokens,
        )
        self.calls += 1
        self.runs.append(
            {
                "role": cfg.role,
                "city": city,
                "model": self.model,
                "reasoning_budget": cfg.reasoning_budget,
                "tokens_in": result.usage.tokens_in,
                "tokens_out": result.usage.tokens_out,
                "duration_ms": int((time.monotonic() - t0) * 1000),
                "repairs": repairs,
            }
        )
        return result

    def totals(self) -> dict[str, int]:
        ti = sum(r["tokens_in"] for r in self.runs)
        to = sum(r["tokens_out"] for r in self.runs)
        return {"tokens_in": ti, "tokens_out": to, "total": ti + to, "calls": self.calls}


def _parse_args(raw: str) -> dict[str, Any]:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def _assistant_echo(result: ChatResult) -> dict[str, Any]:
    return {
        "role": "assistant",
        "content": result.content or None,
        "tool_calls": [
            {
                "id": c["id"],
                "type": "function",
                "function": {"name": c["name"], "arguments": c["arguments"]},
            }
            for c in result.tool_calls
        ],
    }


def _run_role(
    runner: AgentRunner,
    cfg: RoleConfig,
    *,
    city: str,
    system: str,
    user: str,
    ctx: tools.ToolContext,
    submit_tool: dict[str, Any],
    offer_tools: bool = True,
    repairs: int = 0,
) -> dict[str, Any]:
    """Drive one role: optional bounded drill-down tool rounds, then a submit. Returns the
    submit tool's parsed arguments (``{}`` if the model never submits cleanly)."""
    submit_name = submit_tool["function"]["name"]
    available = ([submit_tool] + list(tools.TOOL_SCHEMAS)) if offer_tools else [submit_tool]
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]

    for _round in range(MAX_TOOL_ROUNDS):
        result = runner.call(
            cfg,
            city=city,
            messages=messages,
            tools_arg=available,
            tool_choice="auto",
            repairs=repairs,
        )
        submit_call = next((c for c in result.tool_calls if c["name"] == submit_name), None)
        if submit_call is not None:
            return _parse_args(submit_call["arguments"])
        drill = [c for c in result.tool_calls if c["name"] in tools.TOOL_NAMES]
        if not drill:
            break  # no tools, no submit -> force a submit below
        messages.append(_assistant_echo(result))
        for c in drill:
            out = tools.execute(ctx, c["name"], _parse_args(c["arguments"]))
            messages.append(
                {"role": "tool", "tool_call_id": c["id"], "content": json.dumps(out)[:6000]}
            )

    # Force the submit tool for a final, decisive turn.
    result = runner.call(
        cfg,
        city=city,
        messages=messages,
        tools_arg=[submit_tool],
        tool_choice={"type": "function", "function": {"name": submit_name}},
        repairs=repairs,
    )
    submit_call = next((c for c in result.tool_calls if c["name"] == submit_name), None)
    return _parse_args(submit_call["arguments"]) if submit_call else {}


def _normalize(raw: dict[str, Any]) -> dict[str, Any]:
    """Fill the fields the drafter is not asked to set (resolved flag, defaults, placeholder
    verifier) so the brief can be validated and ground-truthed."""
    b = dict(raw)
    b.setdefault("brief_type", "action")
    for ref in b.get("evidence_refs") or []:
        ref["resolved"] = True
    b.setdefault("verifier", {"passed": True, "notes": ""})
    return b


def _validate_and_ground(
    artifacts: dict[str, Any], raw_briefs: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Resolve + ground-truth + schema-validate each brief. Returns (kept, errors_by_id)."""
    kept: list[dict[str, Any]] = []
    errors: dict[str, list[str]] = {}
    for raw in raw_briefs:
        bid = str(raw.get("id", f"anon-{len(kept) + len(errors)}"))
        nb = _normalize(raw)
        res = resolver.verify_brief(artifacts, nb)
        if not res.ok:
            errors[bid] = res.errors
            continue
        try:
            Brief.model_validate(res.brief)
        except Exception as exc:  # noqa: BLE001 - pydantic ValidationError -> repair signal
            errors[bid] = [f"schema: {type(exc).__name__}"]
            continue
        kept.append(res.brief)
    return kept, errors


def generate_briefs(
    artifacts: dict[str, Any],
    city: str,
    call_fn: CallFn,
    *,
    model: str = NIM_MODEL_ID,
    max_calls: int = MAX_CALLS,
) -> tuple[BriefsDoc, AgentLogDoc]:
    """Run the four roles over the city's artifacts and return (briefs, agentlog).

    A NIM failure propagates as :class:`NimError` (the command applies stale-keep). A run that
    simply finds no groundable risk returns an empty-briefs doc (not a failure)."""
    from vayu.agents.digest import build_digest
    from vayu.timeutils import now_utc, utc_iso_z

    runner = AgentRunner(call_fn=call_fn, model=model, max_calls=max_calls)
    ctx = tools.ToolContext(artifacts=artifacts, city=city)
    fixture = any(bool((a or {}).get("fixture")) for a in artifacts.values() if isinstance(a, dict))

    digest = build_digest(artifacts, city)

    # 1. Situation Analyst
    situations = _run_role(
        runner,
        roles.ANALYST,
        city=city,
        system=roles.ANALYST_SYSTEM,
        user=roles.analyst_user(digest),
        ctx=ctx,
        submit_tool=roles.SUBMIT_SITUATIONS_TOOL,
    ).get("situations", [])

    # 2. Causal Strategist
    strategies = []
    if situations:
        strategies = _run_role(
            runner,
            roles.STRATEGIST,
            city=city,
            system=roles.STRATEGIST_SYSTEM,
            user=roles.strategist_user(situations, digest),
            ctx=ctx,
            submit_tool=roles.SUBMIT_STRATEGIES_TOOL,
        ).get("strategies", [])

    # 3. Action Drafter (+ bounded repair loop against the deterministic gate)
    kept: list[dict[str, Any]] = []
    if situations:
        submit_name = roles.SUBMIT_BRIEFS_TOOL["function"]["name"]
        messages = [
            {"role": "system", "content": roles.DRAFTER_SYSTEM},
            {"role": "user", "content": roles.drafter_user(situations, strategies, city)},
        ]
        for attempt in range(MAX_REPAIRS + 1):
            result = runner.call(
                roles.DRAFTER,
                city=city,
                messages=messages,
                tools_arg=[roles.SUBMIT_BRIEFS_TOOL],
                tool_choice={"type": "function", "function": {"name": submit_name}},
                repairs=attempt,
            )
            call = next((c for c in result.tool_calls if c["name"] == submit_name), None)
            raw_briefs = _parse_args(call["arguments"]).get("briefs", []) if call else []
            round_kept, errors = _validate_and_ground(artifacts, raw_briefs)
            # Accumulate newly-passing briefs (dedupe by id).
            have = {b["id"] for b in kept}
            kept.extend(b for b in round_kept if b["id"] not in have)
            if not errors or attempt == MAX_REPAIRS:
                if errors:
                    log.warning("briefs_dropped", city=city, dropped=list(errors), reasons=errors)
                break
            messages.append(_assistant_echo(result))
            messages.append({"role": "user", "content": roles.repair_user(errors)})

    kept = kept[: roles.MAX_BRIEFS]

    # 4. Adversarial Verifier (advisory; resolver already authoritative)
    if kept:
        verdicts = _run_role(
            runner,
            roles.VERIFIER,
            city=city,
            system=roles.VERIFIER_SYSTEM,
            user=roles.verifier_user(kept),
            ctx=ctx,
            submit_tool=roles.SUBMIT_VERDICTS_TOOL,
            offer_tools=False,
        ).get("verdicts", [])
        by_id = {str(v.get("brief_id")): v for v in verdicts}
        verified: list[dict[str, Any]] = []
        for b in kept:
            v = by_id.get(b["id"])
            if v is None:
                b["verifier"] = {
                    "passed": True,
                    "notes": "resolver-verified; no explicit adjudication",
                }
                verified.append(b)
            elif v.get("passed"):
                b["verifier"] = {"passed": True, "notes": str(v.get("notes", ""))[:500]}
                verified.append(b)
            else:
                log.info("verifier_rejected", city=city, brief_id=b["id"], notes=v.get("notes"))
        kept = verified

    generated_at = utc_iso_z(now_utc())
    briefs_doc = BriefsDoc.model_validate(
        {"generated_at": generated_at, "fixture": fixture or None, "model": model, "briefs": kept}
    )
    log_doc = AgentLogDoc.model_validate(
        {
            "generated_at": generated_at,
            "fixture": fixture or None,
            "model": model,
            "runs": runner.runs,
            "totals": runner.totals(),
        }
    )
    return briefs_doc, log_doc


__all__ = ["AgentRunner", "generate_briefs", "MAX_CALLS", "MAX_REPAIRS", "MAX_TOOL_ROUNDS"]
