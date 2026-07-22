"""`vayu ingest` — fetch real data for a city into the raw store + lineage."""

from __future__ import annotations

import argparse


def register(subparsers: argparse._SubParsersAction) -> None:
    p = subparsers.add_parser(
        "ingest",
        help="Fetch real data (OpenAQ archive, Open-Meteo, FIRMS, OSM, live, GEE) for a city.",
    )
    p.add_argument("--city", required=True, help="delhi | mumbai | bengaluru | all")
    p.add_argument(
        "--sources",
        default="all",
        help="Comma list: wards,openaq,live,openmeteo,osm,firms,gee (or 'all').",
    )
    p.add_argument(
        "--start",
        default=None,
        help="Backfill start date YYYY-MM-DD (default: city archive_start, e.g. 2025-02-01).",
    )
    p.set_defaults(func=run)


def run(args: argparse.Namespace) -> int:
    from vayu.ingest.runner import run_ingest

    return run_ingest(city=args.city, sources=args.sources, start=args.start)
