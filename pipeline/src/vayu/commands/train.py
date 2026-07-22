"""`vayu train` — cross-validate nowcast + backtest forecast on the feature store.

Produces the real acceptance-2/3 numbers (nowcast LOSO vs IDW, forecast skill vs
persistence + seasonal-naive) and caches them for `vayu publish` to fold into receipts.
"""

from __future__ import annotations

import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "train",
        help="Cross-validate nowcast (LOSO vs IDW) and backtest forecast (skill) on the feature store.",
    )
    p.add_argument("--city", required=True, help="delhi | mumbai | bengaluru | all")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from vayu.cityconfig import resolve_cities
    from vayu.models.run import train_city

    rc = 0
    for slug in resolve_cities(args.city):
        rc |= train_city(slug)
    return rc
