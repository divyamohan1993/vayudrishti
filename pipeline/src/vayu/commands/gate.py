"""`vayu gate` — pure-local content gate over published JSON (acceptance 13).

Signatures locked with vayu-ops (uniform `--city <name|all>` per the CLI registry):
  vayu gate --city all --data-root <abs>    (refresh.yml, post-publish/pre-commit)
  vayu gate --city <slug> --data-root <p>   (ci.yml poisoned-fixture must-fail step)
Non-zero exit on any schema/range/sanitization/invariant violation. No network/secrets.
"""

from __future__ import annotations

import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "gate",
        help="Validate published JSON: schema + ranges + sanitization + invariants (no network).",
    )
    p.add_argument("--city", required=True, help="delhi | mumbai | bengaluru | all")
    p.add_argument(
        "--data-root",
        default=None,
        help="Root directory to scan (default: web/public/data). Relative or absolute.",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from vayu.publish.gate import run_gate

    return run_gate(city=args.city, data_root=args.data_root)
