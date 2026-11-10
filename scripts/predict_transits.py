#!/usr/bin/env python3
"""Predict future transit midtimes for preregistration (e.g. Zenodo)."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from astropy.time import Time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exoplanet_hunter import lc_utils  # noqa: E402

BJD_OFFSET = 2457000.0  # BTJD = BJD - 2457000


def btjd_to_utc(btjd: float) -> str:
    t = Time(btjd + BJD_OFFSET, format="jd", scale="tdb")
    return t.utc.isot


def predict_transits(
    period_d: float,
    epoch_btjd: float,
    duration_d: float,
    start_btjd: float,
    end_btjd: float,
    period_sigma: float = 0.0,
    epoch_sigma: float = 0.0,
) -> list[dict]:
    n0 = int(np.floor((start_btjd - epoch_btjd) / period_d))
    n1 = int(np.ceil((end_btjd - epoch_btjd) / period_d))
    out = []
    for n in range(n0, n1 + 1):
        t_mid = epoch_btjd + n * period_d
        if start_btjd <= t_mid <= end_btjd:
            # Simple uncertainty propagation for midtime
            t_sigma = np.sqrt(epoch_sigma**2 + (n * period_sigma) ** 2)
            out.append(
                {
                    "cycle": n,
                    "midtime_btjd": float(t_mid),
                    "midtime_bjd": float(t_mid + BJD_OFFSET),
                    "midtime_utc": btjd_to_utc(t_mid),
                    "midtime_sigma_d": float(t_sigma),
                    "duration_hr": float(duration_d * 24),
                }
            )
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tic", type=int)
    p.add_argument("--search-json", type=Path, default=None)
    p.add_argument("--period-sigma", type=float, default=1e-5, help="Period uncertainty (days)")
    p.add_argument("--epoch-sigma", type=float, default=0.001, help="Epoch uncertainty (BTJD)")
    p.add_argument("--months-ahead", type=float, default=24.0)
    p.add_argument("-o", type=Path, default=Path("results/predictions"))
    args = p.parse_args()

    search_path = args.search_json or lc_utils.default_search_json(args.tic)
    search = json.loads(search_path.read_text())
    period = search["period_d"]
    epoch = search["epoch_btjd"]
    dur = search["duration_d"]

    now = datetime.now(timezone.utc)
    start_btjd = (Time(now, scale="utc").jd - BJD_OFFSET) - period
    end_btjd = start_btjd + args.months_ahead * 30.437 + period

    preds = predict_transits(
        period,
        epoch,
        dur,
        start_btjd,
        end_btjd,
        period_sigma=args.period_sigma,
        epoch_sigma=args.epoch_sigma,
    )
    payload = {
        "tic": args.tic,
        "period_d": period,
        "period_sigma_d": args.period_sigma,
        "epoch_btjd": epoch,
        "epoch_sigma_btjd": args.epoch_sigma,
        "duration_d": dur,
        "window_btjd": [start_btjd, end_btjd],
        "predictions": preds,
        "citation_note": "Deposit this file on Zenodo before the next observing season.",
    }
    args.o.mkdir(parents=True, exist_ok=True)
    out = args.o / f"{args.tic}_predictions.json"
    out.write_text(json.dumps(payload, indent=2))
    print(json.dumps(payload, indent=2))
    print(f"Wrote {out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
