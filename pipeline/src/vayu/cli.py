"""vayu CLI — extensible subcommand registry.

Command modules live in `vayu.commands`. Each module exposes
`register(subparsers)`, which adds one subparser and sets `func` (a handler
taking parsed args and returning an int exit code). Commands are auto-discovered,
so `vayu-models` adds `train`/`predict`/`publish` by dropping a module into
`vayu/commands/` — no edit to this file.
"""

from __future__ import annotations

import argparse
import importlib
import pkgutil
import sys

from vayu import commands as commands_pkg
from vayu.logging_setup import configure_logging


def _discover(subparsers: argparse._SubParsersAction) -> None:
    for mod in sorted(pkgutil.iter_modules(commands_pkg.__path__), key=lambda m: m.name):
        module = importlib.import_module(f"vayu.commands.{mod.name}")
        register = getattr(module, "register", None)
        if callable(register):
            register(subparsers)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vayu", description="VayuDrishti pipeline CLI")
    parser.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error"],
        help="Log verbosity (structlog JSON to stdout).",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    _discover(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(getattr(args, "log_level", "info"))
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    return int(func(args) or 0)


if __name__ == "__main__":
    sys.exit(main())
