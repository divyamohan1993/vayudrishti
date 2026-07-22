"""The four agent roles (spec 14): declarative prompts, submit-tool schemas, per-role
generation configs. The orchestrator wires these into the bounded loop.

Contract rules encoded in the prompts and enforced downstream by pydantic + the resolver:
- NUMBERS live only in expected_effect and evidence_refs[].value; headline / situation /
  action are qualitative plain text.
- Every evidence_ref must be copied verbatim (artifact + path + value) from a digest signal
  or a tool result, so the deterministic resolver can re-resolve it. Invented refs die.
- No angle brackets / HTML / control characters in any emitted string.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RoleConfig:
    role: str
    reasoning_budget: int
    temperature: float
    top_p: float
    max_tokens: int


# Per-role budgets/temperatures (spec 14): generative roles hot, verifier cold.
# max_tokens is TOTAL completion (reasoning + answer) and MUST exceed reasoning_budget plus
# the answer, or a full reasoning trace truncates the submit tool call. Caps bound cost only
# when hit; typical usage is far below (the model stops when done).
ANALYST = RoleConfig("situation_analyst", 8192, 1.0, 0.95, 11000)
STRATEGIST = RoleConfig("causal_strategist", 8192, 1.0, 0.95, 11000)
DRAFTER = RoleConfig("action_drafter", 4096, 1.0, 0.95, 8500)
VERIFIER = RoleConfig("adversarial_verifier", 4096, 0.2, 0.90, 6500)

MAX_BRIEFS = 6

# ---------------------------------------------------------------- submit-tool schemas

_REF = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "description": "Human label for the evidence chip."},
        "artifact": {
            "type": "string",
            "enum": [
                "nowcast",
                "forecast",
                "attribution",
                "enforcement",
                "ledger",
                "interventions",
                "receipts",
            ],
        },
        "path": {
            "type": "string",
            "description": "Dotted-path copied verbatim from a digest signal or tool result.",
        },
        "value": {
            "description": "The value at that path, copied verbatim (number / string / bool)."
        },
    },
    "required": ["label", "artifact", "path", "value"],
}

_SUBMIT_SITUATIONS = {
    "type": "function",
    "function": {
        "name": "submit_situations",
        "description": "Submit the compound emerging-risk situations you found.",
        "parameters": {
            "type": "object",
            "properties": {
                "situations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "short slug, e.g. nw-severe-01",
                            },
                            "target_wards": {"type": "array", "items": {"type": "string"}},
                            "summary": {
                                "type": "string",
                                "description": "Qualitative compound-risk narrative, no numbers.",
                            },
                            "signal_refs": {
                                "type": "array",
                                "items": _REF,
                                "description": "Evidence for the situation, refs copied verbatim.",
                            },
                        },
                        "required": ["id", "target_wards", "summary", "signal_refs"],
                    },
                }
            },
            "required": ["situations"],
        },
    },
}

_SUBMIT_STRATEGIES = {
    "type": "function",
    "function": {
        "name": "submit_strategies",
        "description": "Per situation: the grounded measure and its causal-effect basis.",
        "parameters": {
            "type": "object",
            "properties": {
                "strategies": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "situation_id": {"type": "string"},
                            "measure": {
                                "type": "string",
                                "description": "The recommended measure, qualitative.",
                            },
                            "action_code": {
                                "type": ["string", "null"],
                                "enum": [
                                    "deploy_water_sprinkling",
                                    "halt_construction_dust",
                                    "intensify_mechanized_sweeping",
                                    "reroute_divert_heavy_traffic",
                                    "inspect_industrial_emissions",
                                    "ban_open_biomass_burning",
                                    "issue_public_health_advisory",
                                    "monitor_no_action",
                                    None,
                                ],
                            },
                            "owner": {
                                "type": "string",
                                "description": "Owner agency, e.g. MCD, DPCC.",
                            },
                            "basis_ref": {
                                "type": ["string", "null"],
                                "description": "ledger/interventions path for the effect, or null.",
                            },
                            "effect_refs": {
                                "type": "array",
                                "items": _REF,
                                "description": "Causal-effect refs, copied verbatim.",
                            },
                        },
                        "required": ["situation_id", "measure", "owner", "effect_refs"],
                    },
                }
            },
            "required": ["strategies"],
        },
    },
}

_BRIEF_ITEM = {
    "type": "object",
    "properties": {
        "id": {"type": "string", "description": "slug, e.g. delhi-2025-11-08-nw-stubble-01"},
        "brief_type": {
            "type": "string",
            "enum": ["action", "trigger-watch", "plume-alert", "data-quality"],
        },
        "headline": {"type": "string", "description": "Qualitative one-liner, NO numbers."},
        "situation": {"type": "string", "description": "Qualitative narrative, NO numbers."},
        "action": {"type": "string", "description": "Specific recommended action, plain text."},
        "action_code": {
            "type": ["string", "null"],
            "enum": [
                "deploy_water_sprinkling",
                "halt_construction_dust",
                "intensify_mechanized_sweeping",
                "reroute_divert_heavy_traffic",
                "inspect_industrial_emissions",
                "ban_open_biomass_burning",
                "issue_public_health_advisory",
                "monitor_no_action",
                None,
            ],
        },
        "target_wards": {"type": "array", "items": {"type": "string"}},
        "trigger_window": {
            "type": "object",
            "properties": {"start_utc": {"type": "string"}, "end_utc": {"type": "string"}},
            "required": ["start_utc", "end_utc"],
        },
        "expected_effect": {
            "type": ["object", "null"],
            "properties": {
                "ugm3": {
                    "type": "number",
                    "description": "Point effect, from the strategy basis (ledger/interventions).",
                },
                "ci_low": {
                    "type": "number",
                    "description": "From the SAME row as ugm3; grounded from there.",
                },
                "ci_high": {
                    "type": "number",
                    "description": "From the SAME row as ugm3; grounded from there.",
                },
                "basis_ref": {
                    "type": "string",
                    "description": "Path to the ledger/interventions effect; grounds ugm3 + CI.",
                },
            },
            "required": ["ugm3", "ci_low", "ci_high", "basis_ref"],
        },
        "owner": {"type": "string"},
        "advisory_langs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "ISO-639-1, e.g. [en, hi]",
        },
        "evidence_refs": {
            "type": "array",
            "items": _REF,
            "description": "At least one; each resolvable, copied verbatim.",
        },
        "ledger_ref": {
            "type": ["object", "null"],
            "properties": {"stage_transition": {"type": "string"}, "scenario": {"type": "string"}},
        },
    },
    "required": [
        "id",
        "headline",
        "situation",
        "action",
        "target_wards",
        "trigger_window",
        "expected_effect",
        "owner",
        "advisory_langs",
        "evidence_refs",
    ],
}

_SUBMIT_BRIEFS = {
    "type": "function",
    "function": {
        "name": "submit_briefs",
        "description": "Submit the final ranked action briefs (highest priority first).",
        "parameters": {
            "type": "object",
            "properties": {"briefs": {"type": "array", "items": _BRIEF_ITEM}},
            "required": ["briefs"],
        },
    },
}

_SUBMIT_VERDICTS = {
    "type": "function",
    "function": {
        "name": "submit_verdicts",
        "description": "Adversarial verdict: does every claim follow from cited evidence?",
        "parameters": {
            "type": "object",
            "properties": {
                "verdicts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "brief_id": {"type": "string"},
                            "passed": {"type": "boolean"},
                            "notes": {"type": "string", "description": "Terse reason, plain text."},
                        },
                        "required": ["brief_id", "passed", "notes"],
                    },
                }
            },
            "required": ["verdicts"],
        },
    },
}

SUBMIT_SITUATIONS_TOOL = _SUBMIT_SITUATIONS
SUBMIT_STRATEGIES_TOOL = _SUBMIT_STRATEGIES
SUBMIT_BRIEFS_TOOL = _SUBMIT_BRIEFS
SUBMIT_VERDICTS_TOOL = _SUBMIT_VERDICTS

# ---------------------------------------------------------------- prompts

_RULES = (
    "Rules you MUST follow:\n"
    "- Put NUMBERS only in expected_effect and evidence_refs[].value. Keep headline, "
    "situation, action, summary qualitative (no figures in prose).\n"
    "- Every evidence_ref / signal_ref MUST be an object copied WHOLE and VERBATIM (label, "
    "artifact, path, value) from a `citable_refs` list in the digest, from a situation's "
    "signal_refs, or from a tool result's `refs`. NEVER write your own `path` and never edit a "
    "value: only those exact ref objects resolve. A ref you construct or alter is dropped.\n"
    "- Do NOT turn a digest field like `worsens`, `category`, or a nested value into a path; if "
    "it is not already a ref object in citable_refs, you cannot cite it.\n"
    "- No angle brackets, HTML, or control characters in any text.\n"
    "- Ground every claim. If evidence is not in citable_refs or a tool result, do not claim it."
)

ANALYST_SYSTEM = (
    "You are the Situation Analyst for VayuDrishti, an urban air-quality command centre. "
    "From the compound-risk digest (forecast band crossings, enforcement priority, causal "
    "effects, active GRAP stage, dominant source), identify the few genuinely compound emerging "
    "risks (e.g. forecast crossing into a worse category WHILE a source is dominant AND "
    "enforcement persistence is high). Prefer 2-5 high-signal situations over many weak ones. "
    "Call read-only tools only if the digest lacks a value you need.\n\n" + _RULES
)

STRATEGIST_SYSTEM = (
    "You are the Causal Strategist. For each situation, choose the measure that OUR Intervention "
    "Ledger / interventions data shows historically moved this condition, and cite the "
    "weather-adjusted effect from our causal receipts (never folklore). If no quantified effect "
    "exists for a situation, set basis_ref null and effect_refs empty; the brief will carry no "
    "expected_effect. Use get_ledger / get_interventions to fetch exact effect refs.\n\n" + _RULES
)

DRAFTER_SYSTEM = (
    "You are the Action Drafter. Turn the situations and strategies into ranked, verifiable "
    "action briefs. Each brief: a crisp qualitative headline and situation, a specific action, "
    "an owner agency, target wards, a trigger_window in UTC, advisory languages (en + hi for "
    "Delhi), and evidence_refs copied verbatim from the situations/strategies. Include "
    "expected_effect ONLY when a strategy gave a numeric basis_ref; otherwise set it null. "
    f"At most {MAX_BRIEFS} briefs. brief_type is 'action' unless told otherwise.\n"
    "DISCIPLINE (an adversarial verifier will reject overreach): headline and situation restate "
    "ONLY what a citable ref or the active GRAP-stage ref establishes. FORBIDDEN: any statement "
    "without a backing ref, including time-of-day/diurnal patterns ('evening', 'typically peaks'), "
    "assumed behaviours, 'usually/often', meteorological causes, or source attribution phrased as "
    "measured emissions. If you name the active GRAP stage, include its ref. Keep prose terse and "
    "literal, mirroring the evidence.\n\n" + _RULES
)

VERIFIER_SYSTEM = (
    "You are the Adversarial Verifier. The deterministic resolver has ALREADY confirmed every "
    "evidence_ref resolves and has GROUNDED expected_effect.ugm3, ci_low and ci_high from the "
    "ledger/interventions row named by expected_effect.basis_ref: that single basis_ref is "
    "sufficient citation for the effect AND its confidence interval, so do NOT ask for separate "
    "refs for those three numbers.\n"
    "FAIL a brief ONLY for MATERIAL overreach that would mislead a decision-maker: (a) a NUMBER "
    "not backed by a resolved ref, (b) source attribution stated as MEASURED emissions rather "
    "than an estimate, (c) a quantified effect with no ledger/interventions basis, (d) a claim "
    "that CONTRADICTS the cited evidence, or (e) an action grossly unsupported by the situation. "
    "Otherwise PASS. Do NOT fail a brief for harmless hedged qualitative context, tone, or "
    "phrasing; if such a phrase is imperfect, PASS and note it. Give a terse reason either way."
)


def _json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


def analyst_user(digest: dict[str, Any]) -> str:
    return (
        f"City: {digest.get('city')}. "
        f"Active GRAP stage: {_json(digest.get('active_grap_stage'))}.\n"
        f"Compound-risk digest ({digest.get('candidate_count', 0)} candidate wards, each signal "
        f"carries its resolvable ref):\n{_json(digest.get('candidates'))}\n\n"
        "Identify the compound emerging risks and call submit_situations."
    )


def strategist_user(situations: list[dict[str, Any]], digest: dict[str, Any]) -> str:
    return (
        f"Situations from the Analyst:\n{_json(situations)}\n\n"
        f"Active GRAP stage: {_json(digest.get('active_grap_stage'))}. "
        "For each situation pick the measure our ledger/interventions data supports and call "
        "submit_strategies with the effect refs."
    )


def drafter_user(
    situations: list[dict[str, Any]], strategies: list[dict[str, Any]], city: str
) -> str:
    return (
        f"City: {city}.\nSituations:\n{_json(situations)}\n\nStrategies:\n{_json(strategies)}\n\n"
        "Draft the ranked action briefs and call submit_briefs."
    )


def repair_user(errors_by_id: dict[str, list[str]]) -> str:
    return (
        "Some briefs were REJECTED by the deterministic gate. Fix ONLY these and resubmit ALL "
        "briefs you still stand behind via submit_briefs. Drop any you cannot ground. Failures:\n"
        f"{_json(errors_by_id)}\n"
        "Remember: evidence_refs must be copied verbatim from the tools/digest; a path that does "
        "not resolve, or a value that does not match the artifact, is rejected again."
    )


def verifier_user(briefs: list[dict[str, Any]]) -> str:
    slim = [
        {
            k: b.get(k)
            for k in ("id", "headline", "situation", "action", "expected_effect", "evidence_refs")
        }
        for b in briefs
    ]
    return (
        f"Briefs to adjudicate (refs already resolve):\n{_json(slim)}\n\n"
        "Call submit_verdicts with a verdict for every brief_id."
    )


__all__ = [
    "RoleConfig",
    "ANALYST",
    "STRATEGIST",
    "DRAFTER",
    "VERIFIER",
    "MAX_BRIEFS",
    "SUBMIT_SITUATIONS_TOOL",
    "SUBMIT_STRATEGIES_TOOL",
    "SUBMIT_BRIEFS_TOOL",
    "SUBMIT_VERDICTS_TOOL",
    "ANALYST_SYSTEM",
    "STRATEGIST_SYSTEM",
    "DRAFTER_SYSTEM",
    "VERIFIER_SYSTEM",
    "analyst_user",
    "strategist_user",
    "drafter_user",
    "repair_user",
    "verifier_user",
]
