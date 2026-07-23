"""Open-Meteo request resilience: timeout/429 retry + archive chunking."""

from datetime import date, timedelta

import requests

from vayu.ingest import openmeteo


class _Resp:
    def __init__(self, status=200, payload=None):
        self.status_code = status
        self._payload = payload or {"ok": True}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(str(self.status_code))

    def json(self):
        return self._payload


def test_request_json_retries_timeout_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, params=None, timeout=None, headers=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise requests.exceptions.ReadTimeout("read timed out")
        return _Resp(200, {"value": 42})

    monkeypatch.setattr(openmeteo.requests, "get", fake_get)
    monkeypatch.setattr(openmeteo.time, "sleep", lambda _s: None)

    out = openmeteo._request_json("https://x", {})
    assert out == {"value": 42}
    assert calls["n"] == 2  # timed out once, then succeeded


def test_request_json_retries_429_then_succeeds(monkeypatch):
    calls = {"n": 0}

    def fake_get(*_a, **_k):
        calls["n"] += 1
        return _Resp(429) if calls["n"] == 1 else _Resp(200, {"ok": 1})

    monkeypatch.setattr(openmeteo.requests, "get", fake_get)
    monkeypatch.setattr(openmeteo.time, "sleep", lambda _s: None)

    assert openmeteo._request_json("https://x", {}) == {"ok": 1}
    assert calls["n"] == 2


def test_request_json_raises_after_exhausting_retries(monkeypatch):
    def always_timeout(*_a, **_k):
        raise requests.exceptions.ConnectTimeout("nope")

    monkeypatch.setattr(openmeteo.requests, "get", always_timeout)
    monkeypatch.setattr(openmeteo.time, "sleep", lambda _s: None)

    try:
        openmeteo._request_json("https://x", {}, retries=3)
    except requests.exceptions.ConnectTimeout:
        return
    raise AssertionError("expected ConnectTimeout to propagate after retries")


def test_date_chunks_splits_long_span_contiguously():
    chunks = list(openmeteo._date_chunks("2025-02-01", "2026-07-19"))
    assert len(chunks) >= 5  # ~17 months at ~3-month chunks
    assert chunks[0][0] == "2025-02-01"
    assert chunks[-1][1] == "2026-07-19"
    for (_s1, e1), (s2, _e2) in zip(chunks, chunks[1:], strict=False):
        assert date.fromisoformat(s2) == date.fromisoformat(e1) + timedelta(days=1)
    # no chunk exceeds the cap
    for s, e in chunks:
        span = (date.fromisoformat(e) - date.fromisoformat(s)).days + 1
        assert span <= openmeteo.ARCHIVE_CHUNK_DAYS
