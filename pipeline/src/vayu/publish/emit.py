"""Serialize a validated content model to its web/public/data path (owner: vayu-models).

Emit is validate-by-construction: callers pass an already-constructed pydantic content
model, so nothing schema/range/sanitization/invariant-invalid can reach disk. The
standalone ``vayu gate`` re-reads and re-validates as defense in depth.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel

from vayu.settings import repo_root


def web_data_dir() -> Path:
    """Published web data root: web/public/data (spec 8)."""
    return repo_root() / "web" / "public" / "data"


def emit_model(model: BaseModel, rel_path: str, *, data_root: Path | None = None, indent: int | None = None) -> Path:
    """Write a validated model to ``{data_root}/{rel_path}`` as UTF-8 JSON.

    ``by_alias`` emits ``pass`` (not ``passed``); ``exclude_none`` drops optional
    absent fields (so real output omits ``fixture`` rather than emitting ``null``).
    """
    root = data_root or web_data_dir()
    out = root / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = model.model_dump(by_alias=True, exclude_none=True)
    separators = (",", ": ") if indent else (",", ":")
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=indent, separators=separators),
        encoding="utf-8",
    )
    return out


__all__ = ["web_data_dir", "emit_model"]
