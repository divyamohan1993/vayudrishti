"""`vayu publish` — publish all web JSON surfaces for a city, then gate (acceptance 1).

Runs the tier-appropriate producers (nowcast/forecast/attribution/enforcement/advisories/
interventions/ledger/replay for deep; nowcast/forecast/advisories for standard/config-only),
plus global receipts + manifest, and exits non-zero if the content gate rejects the output.
This is the command GitHub Actions' 6h refresh invokes.
"""

from __future__ import annotations

import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "publish",
        help="Publish all web JSON for a city (nowcast, forecast, attribution, enforcement, "
             "advisories, Ledger, replay, receipts, manifest), then gate.",
    )
    p.add_argument("--city", required=True, help="delhi | mumbai | bengaluru | all")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from vayu.publish.orchestrate import run as orchestrate

    return orchestrate(args.city)
