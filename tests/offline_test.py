#!/usr/bin/env python3
"""Offline test (no network): inject a transit into synthetic noise, recover it
with BLS and TLS, and check the ranking score orders good vs bad candidates."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exoplanet_hunter import lc_utils  # noqa: E402
from exoplanet_hunter.scoring import candidate_score  # noqa: E402

P_TRUE, T0, DUR, DEPTH = 3.2, 1.1, 0.10, 1500e-6


def synthetic_lc(seed: int = 1) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    t = np.arange(0.0, 54.0, 30 / 1440)  # two 27-d sectors at 30-min cadence
    t = t[(t % 27) > 1.0]  # sector-start gaps
    f = 1.0 + rng.normal(0, 400e-6, t.size) + 2e-3 * np.sin(2 * np.pi * t / 6.0)
    ph = lc_utils.phase_fold(t, P_TRUE, T0) * P_TRUE
    f[np.abs(ph) < DUR / 2] -= DEPTH
    return {
        "time": t, "flux": f, "flux_err": np.full_like(t, 400e-6),
        "sector": np.where(t < 27, 1, 2), "exptime": np.full_like(t, 1800.0),
        "author_id": np.zeros_like(t, dtype=int),
    }


def main() -> int:
    cleaned = lc_utils.bin_lc(lc_utils.clean_lc(synthetic_lc()))
    ok = True
    bls = lc_utils.bls_search(cleaned)
    print(f"BLS: P={bls['period_d']:.5f} d (true {P_TRUE}), SNR={bls['snr']:.1f}")
    ok &= abs(bls["period_d"] / P_TRUE - 1) < 0.01
    try:
        t0 = time.time()
        tls = lc_utils.tls_search(cleaned, period_min=1.0, period_max=10.0)
        print(f"TLS: P={tls['period_d']:.5f} d, SDE={tls['sde']:.1f} ({time.time() - t0:.0f}s)")
        ok &= abs(tls["period_d"] / P_TRUE - 1) < 0.01
    except ImportError:
        print("TLS: skipped (transitleastsquares not installed)")

    good = {"ephemeris": {"snr": 15.0}, "checks": {
        "odd_even": {"pass": True, "ratio": 1.02},
        "secondary": {"pass": True, "primary_depth_frac": 1e-3, "secondary_depth_frac": 0.0},
        "t14_consistency": {"pass": True, "ratio": 1.0},
        "inverted_lc": {"pass": True}, "holdout_year": {"pass": True},
        "centroid": {"pass": True}, "fpp": {"fpp": 0.01, "pass": True}}}
    bad = {"ephemeris": {"snr": 7.0}, "checks": {
        "odd_even": {"pass": False, "ratio": 2.5},
        "secondary": {"pass": False, "primary_depth_frac": 1e-3, "secondary_depth_frac": 6e-4},
        "t14_consistency": {"pass": True, "ratio": 1.8},
        "inverted_lc": {"pass": False}, "centroid": {"pass": False}, "fpp": {"fpp": 0.9}}}
    sg, sb = candidate_score(good), candidate_score(bad)
    print(f"Ranking: good={sg['score']} ({sg['tier']}), bad={sb['score']} ({sb['tier']})")
    ok &= sg["score"] > 0.8 > 0.2 > sb["score"]
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
