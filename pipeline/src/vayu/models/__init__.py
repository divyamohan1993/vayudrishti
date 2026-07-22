"""Modeling layer (owner: vayu-models).

- ``metrics``: RMSE / MAE / honest skill percentage.
- ``features``: parquet -> model feature matrix (wind vector, satellite missing
  indicators, calendar-from-IST, IDW-of-other-stations, station density).
- ``baseline_idw``: inverse-distance-weighting spatial baseline (the honesty yardstick).
- ``nowcast``: LightGBM quantile (p50/p90) spatial fusion + LOSO CV stratified by
  distance-to-nearest-retained-station (spec 5.1, acceptance 3).
- ``forecast``: ward-level 24/48/72h with rolling-origin backtest (spec 5.2, acceptance 2).
"""
