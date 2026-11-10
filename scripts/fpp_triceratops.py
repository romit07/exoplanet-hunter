#!/usr/bin/env python3
"""Estimate a candidate's false-positive probability with TRICERATOPS.

TRICERATOPS (Giacalone & Dressing 2020; Giacalone et al. 2021) compares the
phase-folded transit against planet, eclipsing-binary and blended
nearby-star scenarios, using the TIC/Gaia stars around the target and the TESS
pixel apertures. It returns:

* FPP  - probability the signal is NOT a planet on the target star
* NFPP - probability it comes from a resolved nearby star

Commonly used thresholds (Giacalone et al. 2021): FPP < 0.015 and NFPP < 0.001
for statistical validation; FPP < 0.5 and NFPP < 0.001 for "likely planet".

Optional dependency: ``pip install triceratops`` (needs a C++ compiler for
one of its dependencies on some systems). If the package is missing or the
MAST/Gaia queries fail, the script writes a JSON with ``"skipped": true`` and
exits 0 so batch scans keep going.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exoplanet_hunter import lc_utils

VALIDATED_FPP = 0.015
LIKELY_FPP = 0.5
NFPP_MAX = 1e-3


def patch_tic_name_lookup() -> None:
    """Fall back to a TIC-ID catalog lookup when the MAST name resolver is down.

    TRICERATOPS looks the target up by name ("TIC123"), which goes through the
    MAST name resolver. If that service errors, resolve the coordinates from the
    TIC catalog itself and run the same cone search.
    """
    from astroquery.mast import Catalogs

    if getattr(Catalogs, "_tic_fallback", False):
        return
    original = Catalogs.query_object

    def query_object(objectname, *args, **kwargs):
        try:
            return original(objectname, *args, **kwargs)
        except Exception:
            name = str(objectname).replace(" ", "").upper()
            if not name.startswith("TIC") or not name[3:].isdigit():
                raise
            from astropy.coordinates import SkyCoord

            row = Catalogs.query_criteria(catalog="TIC", ID=int(name[3:]))
            coord = SkyCoord(float(row["ra"][0]), float(row["dec"][0]), unit="deg")
            return Catalogs.query_region(coord, *args, **kwargs)

    Catalogs.query_object = query_object
    Catalogs._tic_fallback = True


def write(out: Path, payload: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, default=float))
    print(json.dumps(payload, indent=2, default=float))


def run_fpp(tic: int, search: dict, lc_path: Path, n_draws: int, sectors: list[int] | None,
            parallel: bool) -> dict:
    import triceratops.triceratops as tr

    patch_tic_name_lookup()

    lc = lc_utils.load_npz(lc_path)
    lc, _ = lc_utils.reject_bad_sectors(lc)
    cleaned = lc_utils.bin_lc(lc_utils.clean_lc(lc))
    period, epoch, dur = search["period_d"], search["epoch_btjd"], search["duration_d"]
    depth = max(float(search["depth_frac"]), 1e-6)

    if not sectors:
        sectors = sorted(int(s) for s in np.unique(cleaned["sector"]))
    # TRICERATOPS wants time in days from mid-transit, within ~2 durations
    phase_t = lc_utils.phase_fold(cleaned["time"], period, epoch) * period
    win = np.abs(phase_t) < 2.0 * dur
    time = phase_t[win]
    flux = cleaned["flux"][win]
    flux_err = float(lc_utils.robust_std(cleaned["flux"][~win])) if (~win).any() else float(np.median(cleaned["flux_err"]))

    target = tr.target(ID=tic, sectors=np.array(sectors))
    # SPOC/QLP FFI light curves are corrected for crowding, so dilution_corrected=True
    kw = dict(time=time, flux_0=flux, flux_err_0=flux_err, P_orb=float(period),
              N=n_draws, parallel=parallel, verbose=0,
              exptime=float(np.median(cleaned["exptime"])) / 86400.0)
    try:
        target.calc_depths(tdepth=depth, dilution_corrected=True)
        target.calc_probs(**kw, dilution_corrected=True)
    except TypeError:  # triceratops < 1.1 has no dilution_corrected argument
        target.calc_depths(tdepth=depth)
        target.calc_probs(**kw)
    fpp, nfpp = float(target.FPP), float(target.NFPP)
    probs = target.probs
    pv = np.asarray(probs["prob"], dtype=float)
    if (not np.all(np.isfinite(pv)) or np.ptp(pv) < 1e-9 or getattr(target, "FPP_degenerate", False)
            or not np.isfinite(fpp)):
        raise RuntimeError(
            "degenerate TRICERATOPS result (uniform/NaN scenario probabilities); usually the "
            "TESScut pixel download or a catalog query failed - retry later"
        )
    top = probs.sort_values("prob", ascending=False).head(5)
    return {
        "fpp": fpp,
        "nfpp": nfpp,
        "pass": bool(fpp < LIKELY_FPP and nfpp < NFPP_MAX),
        "validated_level": bool(fpp < VALIDATED_FPP and nfpp < NFPP_MAX),
        "degenerate": bool(getattr(target, "FPP_degenerate", False)),
        "top_scenarios": [
            {"scenario": str(r["scenario"]), "ID": int(r["ID"]), "prob": float(r["prob"])}
            for _, r in top.iterrows()
        ],
        "sectors": sectors,
        "n_draws": n_draws,
        "n_nearby_stars": int(len(target.stars)) - 1,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tic", type=int)
    p.add_argument("--search-json", type=Path, default=None)
    p.add_argument("--lc", type=Path, default=None)
    p.add_argument("--sectors", type=int, nargs="*", default=None, help="Sectors for apertures (default: all in LC)")
    p.add_argument("--draws", type=int, default=200_000, help="Monte Carlo draws (paper default 1e6; lower is faster)")
    p.add_argument("--repeats", type=int, default=1, help="Repeat and report mean/std FPP (recommended: 5-20)")
    p.add_argument("--parallel", action="store_true")
    p.add_argument("-o", type=Path, default=Path("results/fpp"))
    args = p.parse_args()

    out = args.o / f"{args.tic}_fpp.json"
    search_path = args.search_json or lc_utils.default_search_json(args.tic)
    lc_path = args.lc or Path(f"data/lightcurves/{args.tic}.npz")

    try:
        import triceratops.triceratops  # noqa: F401
    except Exception as exc:
        write(out, {"tic": args.tic, "skipped": True,
                    "reason": f"triceratops not installed ({exc.__class__.__name__}); pip install triceratops"})
        return 0

    search = json.loads(search_path.read_text())
    runs = []
    try:
        for _ in range(max(args.repeats, 1)):
            runs.append(run_fpp(args.tic, search, lc_path, args.draws, args.sectors, args.parallel))
    except Exception as exc:
        write(out, {"tic": args.tic, "skipped": True,
                    "reason": f"TRICERATOPS run failed: {exc}",
                    "traceback": traceback.format_exc(limit=3)})
        return 0

    fpps = np.array([r["fpp"] for r in runs])
    nfpps = np.array([r["nfpp"] for r in runs])
    result = {**runs[-1], "tic": args.tic, "search_json": str(search_path),
              "fpp": float(fpps.mean()), "fpp_std": float(fpps.std()),
              "nfpp": float(nfpps.mean()), "nfpp_std": float(nfpps.std()),
              "repeats": len(runs)}
    result["pass"] = bool(result["fpp"] < LIKELY_FPP and result["nfpp"] < NFPP_MAX)
    result["validated_level"] = bool(result["fpp"] < VALIDATED_FPP and result["nfpp"] < NFPP_MAX)
    write(out, result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
