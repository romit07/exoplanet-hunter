#!/usr/bin/env python3
"""Detrend a stored light curve and run a Box Least Squares transit search."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exoplanet_hunter import lc_utils


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tic", type=int)
    p.add_argument("--lc", type=Path, default=None, help="Input .npz (default data/lightcurves/TIC.npz)")
    p.add_argument("--rho", type=float, default=1.0, help="Stellar density (solar units) for BLS grid")
    p.add_argument("--period-min", type=float, default=None)
    p.add_argument("--period-max", type=float, default=None)
    p.add_argument("--tls", action="store_true", help="Also run Transit Least Squares (slower)")
    p.add_argument("-o", type=Path, default=Path("results/search"))
    args = p.parse_args()

    lc_path = args.lc or Path(f"data/lightcurves/{args.tic}.npz")
    lc = lc_utils.load_npz(lc_path)
    lc, bad = lc_utils.reject_bad_sectors(lc)
    cleaned = lc_utils.bin_lc(lc_utils.clean_lc(lc))
    result = lc_utils.bls_search(
        cleaned,
        rho_sun=args.rho,
        period_min=args.period_min,
        period_max=args.period_max,
    )

    if args.tls:
        try:
            import transitleastsquares as tls

            model = tls(cleaned["time"], cleaned["flux"], cleaned["flux_err"])
            out = model.power(args.rho)
            result["tls_period_d"] = float(out.period)
            result["tls_snr"] = float(out.snr)
        except Exception as exc:
            result["tls_error"] = str(exc)

    args.o.mkdir(parents=True, exist_ok=True)
    json_path = args.o / f"{args.tic}_bls.json"
    json_path.write_text(json.dumps(result, indent=2))

    period, epoch, dur = result["period_d"], result["epoch_btjd"], result["duration_d"]
    phase = lc_utils.phase_fold(cleaned["time"], period, epoch)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.scatter(phase, cleaned["flux"], s=1, c=cleaned["sector"], cmap="tab20", alpha=0.5)
    ax.set_xlabel("Phase")
    ax.set_ylabel("Normalized flux")
    ax.set_title(
        f"TIC {args.tic}: P={period:.6f} d, depth={result['depth_ppm']:.0f} ppm, SNR={result['snr']:.1f}"
    )
    plot_path = args.o / f"{args.tic}_folded.png"
    fig.tight_layout()
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)

    print(json.dumps(result, indent=2))
    print(f"Wrote {json_path} and {plot_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
