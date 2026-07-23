# vayu: VayuDrishti pipeline

The data engine behind VayuDrishti. It turns real, free public air-quality and
weather feeds into a validated feature store and the JSON that the web app reads.

## Commands

```bash
uv sync                          # install deps into .venv
uv run vayu ingest --city delhi  # fetch real data into data/raw + lineage
uv run vayu features --city delhi# build the hourly feature-store parquet
uv run pytest                    # unit tests (network-free)
uv run ruff check                # lint
```

`--city` accepts `delhi`, `mumbai`, `bengaluru`, or `all`.

`vayu-models` registers `train`, `predict`, and `publish` as additional
subcommands by dropping modules into `src/vayu/commands/` (auto-discovered).

## Layout

- `src/vayu/grid.py`: frozen 0.01 deg grid conventions (spec 5.0).
- `src/vayu/upwind.py`: upwind FIRMS sector (spec 5.0).
- `src/vayu/timeutils.py`: IST to UTC at ingest, Asia/Kolkata calendar features.
- `src/vayu/geo.py`: ward_id baking, station_match, per-city UTM.
- `src/vayu/ingest/*`: one module per real source.
- `src/vayu/features/*`: feature-store builder.
- `src/vayu/commands/*`: thin CLI wrappers (auto-discovered registry).

## Data sources (all real, all free)

OpenAQ S3 archive (anonymous), Open-Meteo (zero-auth), NASA FIRMS CSV
(zero-auth), OSM/Geofabrik extracts (zero-auth), data.gov.in CPCB (free key),
OpenAQ v3 (free key), Google Earth Engine (service-account JSON). Keyed sources
degrade gracefully with a clear log line when the key is absent; satellite
parquet columns are always present, NaN when the numeric path is off.
