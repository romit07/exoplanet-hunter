#!/usr/bin/env python3
"""Detrend a stored light curve (wotan biweight) and run a BLS or TLS transit search.

BLS (astropy Box Least Squares) is fast and is the default for large scans.
TLS (transitleastsquares, Hippke & Heller 2019) fits a limb-darkened transit
shape and is more sensitive to small planets; it is slower, so use it on
shortlisted stars or with ``--method both`` as a cross-check.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exoplanet_hunter import lc_utils


def plot_fold(cleaned: dict, result: dict, tic: int, path: Path) -> None:
    period, epoch = result["period_d"], result["epoch_btjd"]
    phase = lc_utils.phase_fold(cleaned["time"], period, epoch)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.scatter(phase, cleaned["flux"], s=1, c=cleaned["sector"], cmap="tab20", alpha=0.5)
    ax.set_xlabel("Phase")
    ax.set_ylabel("Normalized flux")
    ax.set_title(
        f"TIC {tic} [{result['method'].upper()}]: P={period:.6f} d, "
        f"depth={result['depth_ppm']:.0f} ppm, SNR={result['snr']:.1f}"
    )
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tic", type=int)
    p.add_argument("--lc", type=Path, default=None, help="Input .npz (default data/lightcurves/TIC.npz)")
    p.add_argument("--method", choices=["bls", "tls", "both"], default="bls",
                   help="Search algorithm (default bls; 'both' runs BLS then TLS and compares)")
    p.add_argument("--tls", action="store_true", help="Deprecated alias for --method both")
    p.add_argument("--rho", type=float, default=1.0, help="Stellar density (solar units) for the period/duration grid")
    p.add_argument("--period-min", type=float, default=None)
    p.add_argument("--period-max", type=float, default=None)
    p.add_argument("--threads", type=int, default=None, help="TLS worker threads (default: all CPUs)")
    p.add_argument("-o", type=Path, default=Path("results/search"))
    args = p.parse_args()
    method = "both" if args.tls and args.method == "bls" else args.method

    lc_path = args.lc or Path(f"data/lightcurves/{args.tic}.npz")
    lc = lc_utils.load_npz(lc_path)
    lc, bad = lc_utils.reject_bad_sectors(lc)
    cleaned = lc_utils.bin_lc(lc_utils.clean_lc(lc))
    args.o.mkdir(parents=True, exist_ok=True)

    results: dict[str, dict] = {}
    if method in ("bls", "both"):
        results["bls"] = lc_utils.bls_search(
            cleaned, rho_sun=args.rho, period_min=args.period_min, period_max=args.period_max
        )
    if method in ("tls", "both"):
        try:
            results["tls"] = lc_utils.tls_search(
                cleaned, rho_sun=args.rho, period_min=args.period_min,
                period_max=args.period_max, threads=args.threads,
            )
        except Exception as exc:  # keep BLS output usable if TLS is missing/fails
            if method == "tls":
                raise
            results["bls"]["tls_error"] = str(exc)

    if "bls" in results and "tls" in results:
        pb, pt = results["bls"]["period_d"], results["tls"]["period_d"]
        ratio = pt / pb
        agree = any(abs(ratio - h) < 0.01 * h for h in (1.0, 2.0, 0.5, 3.0, 1 / 3))
        cross = {"bls_period_d": pb, "tls_period_d": pt, "period_ratio": ratio, "agree_or_harmonic": agree}
        for r in results.values():
            r["bls_tls_crosscheck"] = cross

    for name, result in results.items():
        result["rejected_sectors"] = bad
        json_path = args.o / f"{args.tic}_{name}.json"
        json_path.write_text(json.dumps(result, indent=2))
        plot_path = args.o / f"{args.tic}_{name}_folded.png" if name == "tls" else args.o / f"{args.tic}_folded.png"
        plot_fold(cleaned, result, args.tic, plot_path)
        print(json.dumps(result, indent=2))
        print(f"Wrote {json_path} and {plot_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
