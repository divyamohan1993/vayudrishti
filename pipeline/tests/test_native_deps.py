"""Native-extension smoke test (requested by vayu-ops/vayu-data).

Windows Smart App Control has blocked native DLLs on this box (pyogrio's GDAL). This
test forces LightGBM's native extension to load AND train, so CI catches a runner load
failure early instead of deep inside the model stack.
"""

from __future__ import annotations

import numpy as np


def test_lightgbm_native_loads_and_trains_quantile():
    import lightgbm as lgb

    rng = np.random.default_rng(0)
    x = rng.random((200, 5))
    y = x[:, 0] * 100 + rng.random(200) * 20
    dataset = lgb.Dataset(x, y)
    booster = lgb.train(
        {"objective": "quantile", "alpha": 0.9, "verbose": -1, "num_leaves": 7, "min_data_in_leaf": 5},
        dataset,
        num_boost_round=10,
    )
    # NaN robustness (spec 5.1 requires NaN-robust satellite features).
    x_nan = x[:3].copy()
    x_nan[0, 1] = np.nan
    preds = booster.predict(x_nan)
    assert preds.shape == (3,)


def test_sklearn_hist_gbr_fallback_available():
    # Native-DLL-free fallback with quantile loss + native NaN handling.
    from sklearn.ensemble import HistGradientBoostingRegressor

    rng = np.random.default_rng(1)
    x = rng.random((200, 5))
    y = x[:, 0] * 100
    model = HistGradientBoostingRegressor(loss="quantile", quantile=0.9, max_iter=20).fit(x, y)
    x_nan = x[:3].copy()
    x_nan[0, 1] = np.nan
    assert model.predict(x_nan).shape == (3,)
