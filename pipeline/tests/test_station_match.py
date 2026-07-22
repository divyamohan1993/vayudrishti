"""station_match: data.gov.in name -> canonical OpenAQ location id (spec 5.0)."""

from vayu import geo
from vayu.lineage import strip_query


def test_resolve_known_station_returns_string_id():
    match = {"Anand Vihar, Delhi - DPCC": 8118, "ITO, Delhi - CPCB": 2554}
    assert geo.resolve_station_id("Anand Vihar, Delhi - DPCC", match) == "8118"
    assert geo.resolve_station_id("ITO, Delhi - CPCB", match) == "2554"


def test_resolve_unknown_station_returns_none():
    assert geo.resolve_station_id("Nowhere - XYZ", {}) is None


def test_strip_query_removes_api_key():
    # data.gov.in carries the key in the query string; lineage must never see it.
    url = "https://api.data.gov.in/resource/3b01bcb8?api-key=SECRET&format=json&limit=10"
    assert strip_query(url) == "https://api.data.gov.in/resource/3b01bcb8"


def test_strip_query_no_query_is_noop():
    url = "https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/locationid=2178/"
    assert strip_query(url) == url
