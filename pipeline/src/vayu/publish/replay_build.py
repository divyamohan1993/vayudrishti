"""Replay publish: Nov-2025 OUT-OF-FOLD nowcast + forecast (spec 5.2, acceptance 11).

Trains the nowcast + forecast models EXCLUDING the Nov-2025 window, then predicts at held-out
Nov-2025 dates -- so the replay answers "trained on the replay?" with a clean no. grid_features
auto-uses the ERA5 archive for these historical timestamps; forecast target meteo comes from the
parquet (archived). Same JSON shapes as the live surfaces. Emitted via the content models.
"""

from __future__ import annotations

import pandas as pd

from vayu.logging_setup import get_logger
from vayu.models.forecast import HORIZONS, build_ward_hourly, train_forecast
from vayu.models.run import load_feature_store
from vayu.publish import forecast_build, nowcast_build
from vayu.publish.contentmodels import ReplayIndexDoc
from vayu.publish.emit import emit_model
from vayu.publish.sanitize import sanitize_text
from vayu.timeutils import now_utc, utc_iso_z

log = get_logger("replay")

REPLAY_DATES = ["2025-11-08", "2025-11-11", "2025-11-14", "2025-11-19", "2025-11-24"]
_OOF_START = pd.Timestamp("2025-11-01T00:00:00Z")
_OOF_END = pd.Timestamp("2025-12-01T00:00:00Z")


def publish(city: str = "delhi") -> int:
    df = load_feature_store(city)
    oof = df[~((df["ts_utc"] >= _OOF_START) & (df["ts_utc"] < _OOF_END))]
    log.info("replay.oof", city=city, full=len(df), oof=len(oof), held_out=len(df) - len(oof))

    # Train OOF models ONCE (Nov-2025 excluded) and reuse for every replay date.
    nc_model = nowcast_build._train(oof)
    fc_models = {h: train_forecast(build_ward_hourly(oof), h) for h in HORIZONS}

    dates = []
    for d in REPLAY_DATES:
        ts = pd.Timestamp(f"{d}T12:00:00Z")
        gen = f"{d}T12:00:00Z"
        nc = nowcast_build.build(city, ts=ts, model=nc_model).model_copy(update={"generated_at": gen})
        fc = forecast_build.build(city, origin=ts, archive_meteo=True, models=fc_models).model_copy(
            update={"generated_at": gen})
        emit_model(nc, f"{city}/replay/{d}/nowcast.json")
        emit_model(fc, f"{city}/replay/{d}/forecast.json")
        dates.append(d)
        log.info("replay.date", city=city, date=d, cells=len(nc.grid), wards=len(fc.wards))

    index = ReplayIndexDoc(
        city=city, generated_at=utc_iso_z(now_utc()),
        window={"start": REPLAY_DATES[0], "end": REPLAY_DATES[-1]}, dates=dates,
        note=sanitize_text("Out-of-fold: models trained EXCLUDING the Nov-2025 window "
                           "(2025-11-01 to 2025-12-01); predictions at held-out Nov-2025 dates."),
    )
    emit_model(index, f"{city}/replay/index.json")
    log.info("replay.published", city=city, dates=len(dates))
    return 0


__all__ = ["publish", "REPLAY_DATES"]
