"""Content gate tests (acceptance 13): the gate rejects malformed publish output.

The poisoned fixtures at tests/fixtures/poisoned/ are hand-crafted invalid JSON that
bypass the emit path, so they exercise the standalone gate exactly as CI does.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from vayu.publish.contentmodels import NowcastDoc
from vayu.publish.emit import emit_model
from vayu.publish.gate import GateReport, gate_city, run_gate

POISONED = Path(__file__).parent / "fixtures" / "poisoned"


def _valid_nowcast_payload() -> dict:
    return {
        "generated_at": "2026-07-22T06:00:00Z",
        "fixture": True,
        "grid_meta": {"lat0": 28.4, "lon0": 76.83, "cell_deg": 0.01, "crs": "EPSG:4326"},
        "grid": [{"cell_id": "delhi_0_0", "row": 0, "col": 0, "pm25_p50": 40.0,
                  "pm25_p90": 60.0, "subindex24h": 75, "category": "Satisfactory"}],
        "wards": [{"ward_id": "delhi_273", "name": "Delhi Cantt", "pm25_p50": 40.0,
                   "pm25_p90": 60.0, "subindex24h": 75, "category": "Satisfactory", "confidence": "high"}],
    }


class TestPoisonedRejected:
    def test_gate_returns_nonzero(self):
        # The exact CI must-fail invocation (acceptance 13).
        assert run_gate(city="delhi", data_root=str(POISONED)) != 0

    def test_reports_range_and_html_violations(self):
        report = GateReport()
        gate_city("delhi", POISONED, report)
        assert not report.ok
        blob = " ".join(report.errors)
        assert "pm25_p50" in blob  # out-of-range 99999
        assert any("markup" in e or "name" in e for e in report.errors)  # <script> ward name

    def test_reports_lineage_query_string(self):
        report = GateReport()
        gate_city("delhi", POISONED, report)  # also scans poisoned/receipts.json
        assert any("query string" in e or "base_url" in e for e in report.errors)


class TestValidPasses:
    def test_emitted_valid_doc_passes_gate(self, tmp_path: Path):
        doc = NowcastDoc(**_valid_nowcast_payload())
        emit_model(doc, "delhi/nowcast.json", data_root=tmp_path)
        assert run_gate(city="delhi", data_root=str(tmp_path)) == 0

    def test_valid_payload_constructs(self):
        NowcastDoc(**_valid_nowcast_payload())  # no raise


class TestModelInvariants:
    def test_html_in_name_rejected(self):
        payload = _valid_nowcast_payload()
        payload["wards"][0]["name"] = "<b>x</b>"
        with pytest.raises(ValidationError):
            NowcastDoc(**payload)

    def test_p90_below_p50_rejected(self):
        payload = _valid_nowcast_payload()
        payload["grid"][0]["pm25_p90"] = 1.0
        with pytest.raises(ValidationError):
            NowcastDoc(**payload)

    def test_category_mismatch_rejected(self):
        payload = _valid_nowcast_payload()
        payload["grid"][0]["category"] = "Severe"
        with pytest.raises(ValidationError):
            NowcastDoc(**payload)
