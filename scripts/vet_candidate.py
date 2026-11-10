#!/usr/bin/env python3
"""Run vetting diagnostics on a transit candidate and emit pass/fail report."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from astroquery.ipac.nexsci.nasa_exoplanet_archive import NasaExoplanetArchive

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exoplanet_hunter import lc_utils


def catalog_crossmatch(tic: int) -> dict:
    out = {"tic": tic, "toi": False, "confirmed": False, "notes": []}
    try:
        toi = NasaExoplanetArchive.query_criteria(table="toi", where=f"tic_id={tic}")
        out["toi"] = len(toi) > 0
        if out["toi"]:
            out["notes"].append("Target appears on NASA TOI list")
    except Exception as exc:
        out["notes"].append(f"TOI query failed: {exc}")
    try:
        ps = NasaExoplanetArchive.query_criteria(
            table="pscomppars", where=f"tic_id={tic} and default_flag=1"
        )
        out["confirmed"] = len(ps) > 0
        if out["confirmed"]:
            out["notes"].append("Host star has confirmed planet(s) in NASA archive")
    except Exception as exc:
        out["notes"].append(f"Archive query failed: {exc}")
    return out


def odd_even_depth(lc: dict, period: float, epoch: float, duration_d: float) -> dict:
    phases = lc_utils.phase_fold(lc["time"], period, epoch)
    in_tr = np.abs(phases) < (duration_d / period) / 2
    tr_times = lc["time"][in_tr]
    if len(tr_times) < 4:
        return {"pass": False, "reason": "too few in-transit points"}
    tr_idx = np.unique(np.round((tr_times - epoch) / period).astype(int))
    depths = []
    for k in tr_idx:
        m = np.abs(np.round((lc["time"] - epoch) / period).astype(int) - k) == 0
        m &= np.abs(lc_utils.phase_fold(lc["time"], period, epoch)) < duration_d / period / 2
        if m.sum() > 5:
            depths.append(1.0 - np.nanmedian(lc["flux"][m]))
    if len(depths) < 2:
        return {"pass": True, "reason": "insufficient transits for odd/even"}
    odd = np.mean(depths[0::2])
    even = np.mean(depths[1::2])
    ratio = odd / even if even > 0 else np.nan
    return {
        "pass": 0.5 < ratio < 2.0,
        "odd_depth_frac": float(odd),
        "even_depth_frac": float(even),
        "ratio": float(ratio),
    }


def secondary_check(lc: dict, period: float, epoch: float, duration_d: float) -> dict:
    phases = lc_utils.phase_fold(lc["time"], period, epoch)
    primary = np.abs(phases) < duration_d / period / 2
    secondary = np.abs(phases - 0.5) < duration_d / period / 2
    d_pri = 1.0 - np.nanmedian(lc["flux"][primary]) if primary.any() else 0.0
    d_sec = 1.0 - np.nanmedian(lc["flux"][secondary]) if secondary.any() else 0.0
    return {
        "pass": d_sec < 0.5 * d_pri,
        "primary_depth_frac": float(d_pri),
        "secondary_depth_frac": float(d_sec),
    }


def cross_reduction_agreement(lc: dict, period: float, epoch: float, duration_d: float) -> dict:
    splits = lc_utils.split_by_author(lc)
    if "spoc" not in splits or "qlp" not in splits:
        return {"pass": True, "reason": "single reduction only — download both SPOC and QLP"}
    depths = {}
    for name, sub in splits.items():
        c = lc_utils.bin_lc(lc_utils.clean_lc(sub))
        ph = lc_utils.phase_fold(c["time"], period, epoch)
        m = np.abs(ph) < duration_d / period / 2
        depths[name] = 1.0 - np.nanmedian(c["flux"][m]) if m.any() else np.nan
    agree = abs(depths["spoc"] - depths["qlp"]) < max(0.3 * depths["spoc"], 5e-5)
    return {
        "pass": bool(agree),
        "depths_frac": {k: float(v) for k, v in depths.items()},
    }


def inverted_lc_test(lc: dict, rho: float) -> dict:
    flipped = {**lc, "flux": 2.0 - lc["flux"]}
    hit = lc_utils.bls_search(lc_utils.bin_lc(lc_utils.clean_lc(flipped)), rho_sun=rho)
    return {
        "pass": hit["snr"] < 6.0,
        "inverted_snr": hit["snr"],
        "inverted_period_d": hit["period_d"],
    }


def holdout_year(lc: dict, period: float, epoch: float, duration_d: float, rho: float) -> dict:
    sectors = np.unique(lc["sector"])
    if len(sectors) < 3:
        return {"pass": True, "reason": "fewer than 3 sectors — skip holdout"}
    hold = int(sectors[-1])
    train = {k: v[lc["sector"] != hold] for k, v in lc.items() if isinstance(v, np.ndarray)}
    test = {k: v[lc["sector"] == hold] for k, v in lc.items() if isinstance(v, np.ndarray)}
    train_c = lc_utils.bin_lc(lc_utils.clean_lc(train))
    blind = lc_utils.bls_search(train_c, rho_sun=rho)
    recovers = abs(blind["period_d"] / period - 1) < 0.01
    ph = lc_utils.phase_fold(test["time"], blind["period_d"], blind["epoch_btjd"])
    in_tr = np.abs(ph) < duration_d / 2
    depth = 1.0 - np.nanmedian(test["flux"][in_tr]) if in_tr.any() else 0.0
    return {
        "pass": recovers and depth > 0,
        "held_out_sector": hold,
        "blind_period_d": blind["period_d"],
        "holdout_depth_frac": float(depth),
        "recovers_period": recovers,
    }


def injection_recovery(lc: dict, period: float, epoch: float, depth_frac: float) -> dict:
    rng = np.random.default_rng(42)
    inj = lc.copy()
    ph = lc_utils.phase_fold(inj["time"], period, epoch)
    in_tr = np.abs(ph) < (period * 0.04) / 2
    inj["flux"] = inj["flux"].copy()
    inj["flux"][in_tr] -= depth_frac
    recovered = lc_utils.bls_search(lc_utils.bin_lc(lc_utils.clean_lc(inj)))
    ok = abs(recovered["period_d"] / period - 1) < 0.02
    return {
        "pass": ok,
        "injected_depth_ppm": depth_frac * 1e6,
        "recovered_period_d": recovered["period_d"],
        "recovered_snr": recovered["snr"],
    }


def t14_consistency(duration_d: float, period_d: float, rho_sun: float = 1.0) -> dict:
    expected = lc_utils.duration_days(period_d, rho_sun)
    ratio = duration_d / expected if expected > 0 else np.nan
    return {
        "pass": 0.4 < ratio < 2.5,
        "duration_d": duration_d,
        "expected_duration_d": expected,
        "ratio": float(ratio),
    }


def build_report(tic: int, search: dict, lc_path: Path, rho: float) -> dict:
    lc = lc_utils.load_npz(lc_path)
    lc, _ = lc_utils.reject_bad_sectors(lc)
    cleaned = lc_utils.bin_lc(lc_utils.clean_lc(lc))
    period = search["period_d"]
    epoch = search["epoch_btjd"]
    dur = search["duration_d"]
    checks = {
        "catalog": catalog_crossmatch(tic),
        "odd_even": odd_even_depth(cleaned, period, epoch, dur),
        "secondary": secondary_check(cleaned, period, epoch, dur),
        "cross_reduction": cross_reduction_agreement(lc, period, epoch, dur),
        "inverted_lc": inverted_lc_test(lc, rho),
        "holdout_year": holdout_year(lc, period, epoch, dur, rho),
        "injection_recovery": injection_recovery(
            lc, period, epoch, max(search["depth_frac"], 5e-5)
        ),
        "t14_consistency": t14_consistency(dur, period, rho),
    }
    failures = [
        name
        for name, c in checks.items()
        if not c.get("pass", True) and "reason" not in c
    ]
    soft_skip = [name for name, c in checks.items() if "reason" in c]
    overall = len(failures) == 0 and not checks["catalog"]["toi"]
    return {
        "tic": tic,
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "ephemeris": {
            "period_d": period,
            "epoch_btjd": epoch,
            "duration_d": dur,
            "depth_ppm": search["depth_ppm"],
        },
        "checks": checks,
        "failed_checks": failures,
        "skipped_checks": soft_skip,
        "overall_pass": overall,
    }


def markdown_report(report: dict) -> str:
    lines = [
        f"# Vetting report — TIC {report['tic']}",
        "",
        f"Generated: {report['generated_utc']}",
        "",
        "## Ephemeris (from search)",
        f"- Period: {report['ephemeris']['period_d']:.6f} d",
        f"- Epoch (BTJD): {report['ephemeris']['epoch_btjd']:.5f}",
        f"- Duration: {report['ephemeris']['duration_d'] * 24:.3f} h",
        f"- Depth: {report['ephemeris']['depth_ppm']:.0f} ppm",
        "",
        f"## Overall: **{'PASS' if report['overall_pass'] else 'FAIL'}**",
        "",
    ]
    for name, check in report["checks"].items():
        status = "pass" if check.get("pass") else ("skip" if "reason" in check else "fail")
        lines.append(f"### {name} ({status})")
        for k, v in check.items():
            if k != "pass":
                lines.append(f"- {k}: {v}")
        lines.append("")
    if report["failed_checks"]:
        lines.append(f"Failed: {', '.join(report['failed_checks'])}")
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tic", type=int)
    p.add_argument("--search-json", type=Path, default=None)
    p.add_argument("--lc", type=Path, default=None)
    p.add_argument("--rho", type=float, default=1.0)
    p.add_argument("-o", type=Path, default=Path("results/vetting"))
    args = p.parse_args()

    search_path = args.search_json or Path(f"results/search/{args.tic}_bls.json")
    search = json.loads(search_path.read_text())
    lc_path = args.lc or Path(f"data/lightcurves/{args.tic}.npz")

    report = build_report(args.tic, search, lc_path, args.rho)
    args.o.mkdir(parents=True, exist_ok=True)
    json_out = args.o / f"{args.tic}_vet.json"
    md_out = args.o / f"{args.tic}_vet.md"
    json_out.write_text(
        json.dumps(
            report,
            indent=2,
            default=lambda o: o.item() if isinstance(o, np.generic) else o,
        )
    )
    md_out.write_text(markdown_report(report))
    print(markdown_report(report))
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
