"""Data lineage + URL hygiene (spec 7, acceptance 7).

Every real fetch records {source, base_url, resource_id, fetched_at, rows}. The
stored/logged URL is stripped of its query string and fragment, because
data.gov.in carries the API key in the query string. The key never reaches
lineage, logs, or published JSON.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel

from vayu.timeutils import now_utc, utc_iso_z


def strip_query(url: str) -> str:
    """Return the URL with query string and fragment removed (base URL only)."""
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


class LineageRecord(BaseModel):
    source: str
    base_url: str
    resource_id: str
    fetched_at: str  # UTC ISO-8601 Z
    rows: int


class LineageLog:
    """Accumulates lineage records for one ingest run, then writes them to disk."""

    def __init__(self) -> None:
        self._records: list[LineageRecord] = []

    def add(
        self,
        *,
        source: str,
        url: str,
        resource_id: str,
        rows: int,
        fetched_at: datetime | None = None,
    ) -> LineageRecord:
        rec = LineageRecord(
            source=source,
            base_url=strip_query(url),
            resource_id=resource_id,
            fetched_at=utc_iso_z(fetched_at or now_utc()),
            rows=int(rows),
        )
        self._records.append(rec)
        return rec

    @property
    def records(self) -> list[LineageRecord]:
        return list(self._records)

    def total_rows(self) -> int:
        return sum(r.rows for r in self._records)

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [r.model_dump() for r in self._records]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    @staticmethod
    def read(path: Path) -> list[LineageRecord]:
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8"))
        return [LineageRecord(**r) for r in raw]
