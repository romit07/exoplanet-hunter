"""Light-curve loading, cleaning, binning, and BLS / TLS transit search."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
from astropy.timeseries import BoxLeastSquares

try:
    from wotan import flatten
except ImportError:  # pragma: no cover
    flatten = None  # type: ignore

import lightkurve as lk

AUTHOR_PREFERENCE = ("TESS-SPOC", "QLP")
QLP_FLUX_COLUMNS = ("kspsap_flux", "det_flux", "sap_flux")
DETREND_WINDOW_D = 0.75
FLARE_CLIP_SIGMA = 3.0
DROPOUT_CLIP_SIGMA = 10.0
BIN_S = 600
PERIOD_MIN_D = 0.5
PERIOD_MAX_D = 25.0
MIN_TRANSITS = 3
OVERSAMPLE = 3
SDE_THRESHOLD = 7.0
SNR_THRESHOLD = 6.0


def robust_std(x: np.ndarray) -> float:
    return float(1.4826 * np.median(np.abs(x - np.median(x))))


def ptp_noise(flux: np.ndarray) -> float:
    """Point-to-point scatter; slow trends do not inflate this measure."""
    return float(1.4826 * np.median(np.abs(np.diff(flux))) / np.sqrt(2))


def duration_days(period: float, rho_sun: float = 1.0) -> float:
    """Approximate central transit duration for a solar-density star (days)."""
    return 13.0 / 24 * (period / 365.25) ** (1 / 3) * rho_sun ** (-1 / 3)


def period_grid(baseline_d: float, rho_sun: float = 1.0) -> np.ndarray:
    """Geometric period grid, capped for runtime on long TESS baselines."""
    pmax = min(PERIOD_MAX_D, baseline_d / MIN_TRANSITS)
    pmin = PERIOD_MIN_D
    if pmax <= pmin:
        return np.array([pmin])
    # ~15 samples per trial duration across the baseline (see FFI BLS practice)
    min_dur = duration_days(pmin, rho_sun)
    n_freq = int(np.clip(baseline_d / (min_dur / OVERSAMPLE), 400, 2_500))
    return np.geomspace(pmin, pmax, n_freq)


def pick_products(sr: lk.SearchResult) -> Any:
    """One FFI product per sector (SPOC preferred over QLP)."""
    t = sr.table.to_pandas()
    t["row"] = np.arange(len(t))
    t["sector"] = t["mission"].str.extract(r"Sector (\d+)").astype(float)
    t = t[t["author"].isin(AUTHOR_PREFERENCE)].dropna(subset=["sector"])
    t["rank"] = t["author"].map({a: i for i, a in enumerate(AUTHOR_PREFERENCE)})
    t = t.sort_values(["sector", "rank", "exptime"]).drop_duplicates("sector")
    return t


def flux_arrays(lc: lk.LightCurve, author: str) -> tuple[np.ndarray, np.ndarray, np.ndarray, str]:
    if author == "QLP":
        col = next(c for c in QLP_FLUX_COLUMNS if c in lc.colnames)
    else:
        col = "pdcsap_flux"
    flux = np.asarray(lc[col].value, dtype=float)
    err_col = col + "_err" if col + "_err" in lc.colnames else "flux_err"
    err = np.asarray(lc[err_col].value, dtype=float)
    time = np.asarray(lc.time.value, dtype=float)
    ok = np.isfinite(time) & np.isfinite(flux) & np.isfinite(err) & (err > 0)
    time, flux, err = time[ok], flux[ok], err[ok]
    med = np.nanmedian(flux)
    if med <= 0 or not np.isfinite(med):
        med = 1.0
    return time, flux / med, err / med, col


def download_product(row: Any, cache_dir: Path) -> lk.LightCurve:
    cache_dir.mkdir(parents=True, exist_ok=True)
    for attempt in range(2):
        try:
            return row.download(download_dir=str(cache_dir), quality_bitmask="default")
        except lk.LightkurveError as exc:
            bad = re.search(r"product (\S+\.fits)", str(exc))
            if attempt == 1 or not bad:
                raise
            Path(bad.group(1)).unlink(missing_ok=True)
    raise RuntimeError("download failed")


def fetch_tic_lightcurves(
    tic: int,
    out_path: Path | None = None,
    cache_dir: Path | None = None,
) -> dict[str, Any]:
    """Download SPOC and QLP FFI light curves; save combined npz if out_path given."""
    cache_dir = cache_dir or Path.home() / ".exoplanet_hunter" / "mast_cache"
    sr = lk.search_lightcurve(f"TIC {tic}", mission="TESS")
    if len(sr) == 0:
        raise ValueError(f"No TESS light curves found for TIC {tic}")
    picks = pick_products(sr)
    spoc_sectors: list[int] = []
    qlp_sectors: list[int] = []
    chunks: dict[str, list[np.ndarray]] = {
        k: [] for k in ("time", "flux", "flux_err", "sector", "exptime", "author_id")
    }
    authors: list[str] = []

    for _, row in picks.iterrows():
        author = row["author"]
        lc = download_product(sr[int(row["row"])], cache_dir)
        time, flux, err, _ = flux_arrays(lc, author)
        sector = int(row["sector"])
        exptime = float(row["exptime"])
        aid = 0 if author == "TESS-SPOC" else 1
        if author == "TESS-SPOC":
            spoc_sectors.append(sector)
        else:
            qlp_sectors.append(sector)
        chunks["time"].append(time)
        chunks["flux"].append(flux)
        chunks["flux_err"].append(err)
        chunks["sector"].append(np.full_like(time, sector, dtype=int))
        chunks["exptime"].append(np.full_like(time, exptime))
        chunks["author_id"].append(np.full_like(time, aid, dtype=int))
        authors.append(f"{author} S{sector}")

    combined = {k: np.concatenate(v) for k, v in chunks.items()}
    order = np.argsort(combined["time"])
    combined = {k: v[order] for k, v in combined.items()}
    meta = {
        "tic": tic,
        "authors": authors,
        "spoc_sectors": spoc_sectors,
        "qlp_sectors": qlp_sectors,
    }
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(out_path, **combined, meta_authors=np.array(authors, dtype=object))
    return {**combined, **meta}


def load_npz(path: Path) -> dict[str, Any]:
    data = np.load(path, allow_pickle=True)
    out = {k: data[k] for k in data.files if k != "meta_authors"}
    if "meta_authors" in data.files:
        out["authors"] = list(data["meta_authors"])
    return out


def reject_bad_sectors(lc: dict[str, np.ndarray]) -> tuple[dict[str, np.ndarray], list[int]]:
    sectors = np.unique(lc["sector"])
    noise: dict[int, float] = {}
    for s in sectors:
        m = lc["sector"] == s
        noise[int(s)] = ptp_noise(lc["flux"][m]) * np.sqrt(np.median(lc["exptime"][m]) / 3600)
    typical = float(np.median(list(noise.values())))
    bad = [
        int(s)
        for s in sectors
        if noise[int(s)] > 0.01 or (len(sectors) >= 3 and noise[int(s)] > 3.0 * typical)
    ]
    keep = ~np.isin(lc["sector"], bad)
    out = {
        k: (v[keep] if isinstance(v, np.ndarray) and v.shape == lc["time"].shape else v)
        for k, v in lc.items()
        if k in ("time", "flux", "flux_err", "sector", "exptime", "author_id")
    }
    return out, bad


def clean_lc(lc: dict[str, np.ndarray], window: float = DETREND_WINDOW_D) -> dict[str, np.ndarray]:
    if flatten is None:
        raise ImportError("wotan is required for detrending; pip install wotan")
    t, f, sec = lc["time"], lc["flux"], lc["sector"]
    flat = np.full_like(f, np.nan)
    for s in np.unique(sec):
        m = sec == s
        flat[m] = flatten(
            t[m],
            f[m],
            method="biweight",
            window_length=window,
            break_tolerance=0.5,
            edge_cutoff=0.0,
        )
    keep = np.isfinite(flat)
    err = np.zeros_like(f)
    for s in np.unique(sec):
        m = (sec == s) & keep
        sd = robust_std(flat[m])
        resid = flat[m] - 1
        good = (resid < FLARE_CLIP_SIGMA * sd) & (resid > -DROPOUT_CLIP_SIGMA * sd)
        idx = np.where(m)[0]
        keep[idx[~good]] = False
        err[m] = sd
    return {
        "time": t[keep],
        "flux": flat[keep],
        "flux_err": err[keep],
        "sector": sec[keep],
        "exptime": lc["exptime"][keep],
        "author_id": lc.get("author_id", np.zeros_like(t))[keep],
    }


def bin_lc(lc: dict[str, np.ndarray], bin_s: float = BIN_S) -> dict[str, np.ndarray]:
    fast = lc["exptime"] < bin_s
    out: dict[str, list[np.ndarray]] = {k: [v[~fast]] for k, v in lc.items()}
    if fast.any():
        t, f, e, s = (lc[k][fast] for k in ("time", "flux", "flux_err", "sector"))
        aid = lc.get("author_id", np.zeros_like(t))[fast]
        width = bin_s / 86400
        key = np.floor((t - t.min()) / width).astype(np.int64)
        key = key * 1000 + s
        uniq, inv, counts = np.unique(key, return_inverse=True, return_counts=True)
        w = 1 / e**2
        out["time"].append(np.bincount(inv, t * w) / np.bincount(inv, w))
        out["flux"].append(np.bincount(inv, f * w) / np.bincount(inv, w))
        out["flux_err"].append(1 / np.sqrt(np.bincount(inv, w)))
        out["sector"].append(np.bincount(inv, s) / counts)
        out["exptime"].append(np.full(len(uniq), float(bin_s)))
        out["author_id"].append(np.bincount(inv, aid) / counts)
    merged = {k: np.concatenate(v) for k, v in out.items()}
    order = np.argsort(merged["time"])
    return {k: v[order] for k, v in merged.items()}


def _decimate_lc(lc: dict[str, np.ndarray], max_points: int = 25_000) -> dict[str, np.ndarray]:
    n = lc["time"].shape[0]
    if n <= max_points:
        return lc
    step = int(np.ceil(n / max_points))
    sl = slice(None, None, step)
    return {k: v[sl] for k, v in lc.items() if isinstance(v, np.ndarray) and v.shape[0] == n}


def bls_search(
    lc: dict[str, np.ndarray],
    rho_sun: float = 1.0,
    max_signals: int = 1,
    period_min: float | None = None,
    period_max: float | None = None,
) -> dict[str, Any]:
    lc_s = _decimate_lc(lc)
    baseline = float(lc_s["time"].max() - lc_s["time"].min())
    periods = period_grid(baseline, rho_sun)
    if period_min is not None:
        periods = periods[periods >= period_min]
    if period_max is not None:
        periods = periods[periods <= period_max]
    if periods.size == 0:
        raise ValueError("Empty period grid after period_min/period_max cuts")
    dur0 = duration_days(float(np.median(periods)), rho_sun)
    durs = np.full_like(periods, dur0)
    bls = BoxLeastSquares(lc_s["time"], lc_s["flux"], dy=lc_s["flux_err"])
    pg = bls.power(periods, durs, objective="snr", method="fast", oversample=5)
    best_idx = int(np.nanargmax(pg.power))
    period = float(pg.period[best_idx])
    # Retest small-integer harmonics (common BLS alias for Earth-sized FFI dips)
    candidates = [period * f for f in (1.0, 2.0, 3.0, 0.5, 2.0 / 3.0)]
    snrs: list[float] = []
    for cp in candidates:
        if cp < PERIOD_MIN_D or cp > min(PERIOD_MAX_D, baseline / MIN_TRANSITS):
            snrs.append(-np.inf)
            continue
        trial = bls.power(
            np.array([cp]),
            np.array([duration_days(cp, rho_sun)]),
            objective="snr",
            method="fast",
        )
        snrs.append(float(trial.power[0]))
    period = float(candidates[int(np.nanargmax(snrs))])
    # Refine ephemeris at full resolution near the peak
    fine_p = period * np.geomspace(0.992, 1.008, 120)
    bls_full = BoxLeastSquares(lc["time"], lc["flux"], dy=lc["flux_err"])
    pg_f = bls_full.power(fine_p, np.full_like(fine_p, dur0), objective="snr", method="fast", oversample=7)
    best_idx = int(np.nanargmax(pg_f.power))
    period = float(pg_f.period[best_idx])
    t0 = float(pg_f.transit_time[best_idx])
    dur = float(pg_f.duration[best_idx])
    # Box depth from the BLS fit (mean in-transit deficit); the old min-flux estimate
    # was biased high by single noisy points.
    depth = float(pg_f.depth[best_idx])
    if not np.isfinite(depth) or depth <= 0:
        ph = ((lc["time"] - t0 + 0.5 * period) % period) - 0.5 * period
        depth = 1.0 - float(np.nanmedian(lc["flux"][np.abs(ph) < dur / 2]))
    sde = float(pg_f.power[best_idx])
    snr = float(pg_f.snr[best_idx]) if hasattr(pg_f, "snr") and pg_f.snr is not None else sde
    return {
        "period_d": period,
        "epoch_btjd": t0,
        "duration_d": dur,
        "depth_frac": depth,
        "depth_ppm": depth * 1e6,
        "snr": snr,
        "sde": sde,
        "min_transits": int(baseline / period),
        "signals_requested": max_signals,
        "method": "bls",
    }


def phase_fold(time: np.ndarray, period: float, epoch: float) -> np.ndarray:
    ph = ((time - epoch) / period) % 1.0
    ph[ph > 0.5] -= 1.0
    return ph


def split_by_author(lc: dict[str, np.ndarray]) -> dict[str, dict[str, np.ndarray]]:
    if "author_id" not in lc:
        return {"combined": lc}
    out = {}
    for name, aid in (("spoc", 0), ("qlp", 1)):
        m = lc["author_id"] == aid
        if not m.any():
            continue
        out[name] = {k: lc[k][m] for k in lc if isinstance(lc[k], np.ndarray) and lc[k].shape == m.shape}
    return out


def tls_search(
    lc: dict[str, np.ndarray],
    rho_sun: float = 1.0,
    period_min: float | None = None,
    period_max: float | None = None,
    max_points: int = 15_000,
    threads: int | None = None,
    oversampling_factor: int = 3,
    duration_grid_step: float = 1.1,
) -> dict[str, Any]:
    """Transit Least Squares search (Hippke & Heller 2019) on a cleaned light curve.

    Uses a limb-darkened transit template instead of a box, which gives a higher
    detection efficiency for small planets than BLS. Returns the same keys as
    :func:`bls_search` plus TLS-specific diagnostics. Requires
    ``pip install transitleastsquares``.
    """
    try:
        from transitleastsquares import transitleastsquares
    except ImportError as exc:  # pragma: no cover
        raise ImportError("TLS search needs: pip install transitleastsquares") from exc
    import os

    lc_s = _decimate_lc(lc, max_points=max_points)
    t, f, e = lc_s["time"], lc_s["flux"], lc_s["flux_err"]
    baseline = float(t.max() - t.min())
    pmin = period_min if period_min is not None else PERIOD_MIN_D
    pmax = period_max if period_max is not None else min(PERIOD_MAX_D, baseline / MIN_TRANSITS)
    # Density enters via M_star with R_star = 1 R_sun (rho = M / R^3)
    model = transitleastsquares(t, f, e)
    res = model.power(
        period_min=pmin,
        period_max=pmax,
        M_star=float(np.clip(rho_sun, 0.1, 2.0)),
        R_star=1.0,
        M_star_min=0.1,
        M_star_max=2.0,
        R_star_min=0.13,
        R_star_max=3.5,
        oversampling_factor=oversampling_factor,
        duration_grid_step=duration_grid_step,
        use_threads=threads or os.cpu_count() or 1,
        show_progress_bar=False,
    )
    depth_frac = float(1.0 - res.depth) if np.isfinite(res.depth) else float("nan")
    return {
        "method": "tls",
        "period_d": float(res.period),
        "period_uncertainty_d": float(res.period_uncertainty),
        "epoch_btjd": float(res.T0),
        "duration_d": float(res.duration),
        "depth_frac": depth_frac,
        "depth_ppm": depth_frac * 1e6,
        "snr": float(res.snr),
        "sde": float(res.SDE),
        "fap": float(res.FAP) if res.FAP is not None else None,
        "rp_rs": float(res.rp_rs),
        "transit_count": int(res.transit_count),
        "distinct_transit_count": int(res.distinct_transit_count),
        "odd_even_mismatch_sigma": float(res.odd_even_mismatch),
        "min_transits": int(baseline / float(res.period)),
    }


def default_search_json(tic: int, search_dir: Path = Path("results/search")) -> Path:
    """Newest search result for a TIC (``<tic>_tls.json`` or ``<tic>_bls.json``)."""
    found = [p for p in (search_dir / f"{tic}_tls.json", search_dir / f"{tic}_bls.json") if p.exists()]
    if not found:
        return search_dir / f"{tic}_bls.json"
    return max(found, key=lambda p: p.stat().st_mtime)
