"""`vayu features` — build the hourly feature-store parquet for a city."""

from __future__ import annotations

import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "features",
        help="Join raw sources into the frozen hourly feature-store parquet.",
    )
    p.add_argument("--city", required=True, help="delhi | mumbai | bengaluru | all")
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from vayu.features.build import build_features

    return build_features(city=args.city)
