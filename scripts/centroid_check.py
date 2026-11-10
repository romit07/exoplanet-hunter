#!/usr/bin/env python3
"""Pixel-level blend check: difference-image centroid from TESS FFI cutouts.

For each sector, a TESScut cutout around the target is downloaded and two
average images are built: in-transit cadences and the out-of-transit cadences
just before/after each transit. The difference (out - in) shows which pixels
actually dim. If the flux-weighted centroid of the difference image sits on
the target, the dip is probably on the target; a significant offset points to
a nearby eclipsing star (a blend).

This follows the difference-image approach used by the Kepler/TESS pipelines,
DAVE, LATTE, LEO-Vetter and exovetter. Optionally (``--exovetter``) the
exovetter Centroid vetter is run on the same cutouts as an independent
implementation.

Also lists catalogued (TIC) stars bright enough to produce the observed depth
if they were fully eclipsed, with their distance to the difference centroid.

Network access to MAST is required. On failure the script writes a JSON with
``"skipped": true`` and exits 0, so batch runs keep going.
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exoplanet_hunter import lc_utils

TESS_PIX_ARCSEC = 21.0
OFFSET_FAIL_PIX = 1.0     # > ~21 arcsec
OFFSET_FAIL_SIGMA = 3.0


def flux_centroid(img: np.ndarray, around: tuple[float, float] | None = None, radius: float = 2.5) -> tuple[float, float]:
    """Flux-weighted centroid (col, row) of positive pixels, optionally within radius of a point."""
    rows, cols = np.indices(img.shape)
    w = np.where(np.isfinite(img), img, 0.0)
    w = np.clip(w, 0, None)
    if around is not None:
        w = w * (np.hypot(cols - around[0], rows - around[1]) <= radius)
    tot = w.sum()
    if tot <= 0:
        return float("nan"), float("nan")
    return float((w * cols).sum() / tot), float((w * rows).sum() / tot)


def sector_diff(tpf, period: float, epoch: float, dur: float) -> dict | None:
    t = np.asarray(tpf.time.value, dtype=float)
    cube = np.asarray(tpf.flux.value, dtype=float)
    good = np.isfinite(t) & np.all(np.isfinite(cube.reshape(len(t), -1)), axis=1)
    if hasattr(tpf, "quality"):
        good &= np.asarray(tpf.quality) == 0
    t, cube = t[good], cube[good]
    if len(t) < 20:
        return None
    dt = lc_utils.phase_fold(t, period, epoch) * period
    n = np.round((t - epoch) / period).astype(int)
    in_tr = np.abs(dt) < 0.4 * dur
    oot = (np.abs(dt) > 0.75 * dur) & (np.abs(dt) < 2.0 * dur)
    per_transit = []
    for k in np.unique(n[in_tr]):
        mi, mo = in_tr & (n == k), oot & (n == k)
        if mi.sum() >= 2 and mo.sum() >= 4:
            per_transit.append(np.nanmedian(cube[mo], axis=0) - np.nanmedian(cube[mi], axis=0))
    if len(per_transit) < 1:
        return None
    diffs = np.array(per_transit)
    return {
        "diff": np.nanmean(diffs, axis=0),
        "per_transit": diffs,
        "oot": np.nanmedian(cube[oot], axis=0),
        "n_transits": len(per_transit),
    }


def tic_coords(tic: int):
    """SkyCoord from the TIC catalog (avoids the MAST name resolver, which is flaky)."""
    try:
        from astroquery.mast import Catalogs

        row = Catalogs.query_criteria(catalog="TIC", ID=tic)
        if len(row):
            from astropy.coordinates import SkyCoord

            return SkyCoord(float(row["ra"][0]), float(row["dec"][0]), unit="deg")
    except Exception:
        pass
    return None


def download_cutouts(tic: int, max_sectors: int, size: int, cache_dir: Path) -> list:
    """FFI cutouts via astroquery Tesscut by TIC coordinates (no name resolver), newest sectors first."""
    import lightkurve as lk
    from astroquery.mast import Tesscut

    coord = tic_coords(tic)
    if coord is None:
        raise RuntimeError(f"could not get TIC {tic} coordinates from MAST")
    cache_dir.mkdir(parents=True, exist_ok=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        sectors = sorted({int(x) for x in Tesscut.get_sectors(coordinates=coord)["sector"]})[-max_sectors:]
        tpfs = []
        for sec in sectors:
            for attempt in range(3):
                try:
                    manifest = Tesscut.download_cutouts(coordinates=coord, size=size, sector=sec, path=str(cache_dir))
                    tpfs.append(lk.read(manifest["Local Path"][0]))
                    break
                except Exception:
                    if attempt == 2:
                        raise
    return tpfs


def nearby_tic(tic: int, ra: float, dec: float, depth: float, radius_arcsec: float) -> list[dict]:
    from astroquery.mast import Catalogs

    cat = Catalogs.query_region(f"{ra} {dec}", radius=radius_arcsec / 3600.0, catalog="TIC")
    if len(cat) == 0:
        return []
    tmag_t = float(cat[cat["ID"] == str(tic)]["Tmag"][0]) if (cat["ID"] == str(tic)).any() else float(np.nanmin(cat["Tmag"]))
    dm_max = -2.5 * np.log10(max(depth, 1e-6))  # fully eclipsed star must be within this delta-mag
    out = []
    for r in cat:
        dmag = float(r["Tmag"]) - tmag_t
        if str(r["ID"]) == str(tic) or not np.isfinite(dmag) or dmag > dm_max:
            continue
        out.append({"tic": int(r["ID"]), "tmag": float(r["Tmag"]), "delta_mag": round(dmag, 2),
                    "ra": float(r["ra"]), "dec": float(r["dec"]), "sep_arcsec": round(float(r["dstArcSec"]), 1)})
    return sorted(out, key=lambda s: s["sep_arcsec"])


def run_exovetter(tpf, period: float, epoch: float, dur: float, depth: float) -> dict:
    import astropy.units as u
    from exovetter import const as exo_const
    from exovetter import vetters
    from exovetter.tce import Tce

    tce = Tce(period=period * u.day, epoch=epoch * u.day, epoch_offset=exo_const.btjd,
              duration=dur * u.day, depth=depth * exo_const.frac_amp)
    m = vetters.Centroid(lc_name="flux").run(tce, tpf)
    return {k: (float(v) if np.isscalar(v) else str(v)) for k, v in m.items()}


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tic", type=int)
    p.add_argument("--search-json", type=Path, default=None)
    p.add_argument("--max-sectors", type=int, default=4, help="Cutouts to download (each ~10-40 MB)")
    p.add_argument("--size", type=int, default=11, help="Cutout size in pixels")
    p.add_argument("--exovetter", action="store_true", help="Also run the exovetter Centroid vetter")
    p.add_argument("--cache-dir", type=Path, default=Path("data/mast_cache"))
    p.add_argument("-o", type=Path, default=Path("results/centroid"))
    args = p.parse_args()

    out = args.o / f"{args.tic}_centroid.json"
    args.o.mkdir(parents=True, exist_ok=True)

    def finish(payload: dict) -> int:
        out.write_text(json.dumps(payload, indent=2, default=float))
        print(json.dumps(payload, indent=2, default=float))
        return 0

    search_path = args.search_json or lc_utils.default_search_json(args.tic)
    search = json.loads(search_path.read_text())
    period, epoch, dur = search["period_d"], search["epoch_btjd"], search["duration_d"]
    depth = max(float(search["depth_frac"]), 1e-6)

    try:
        tpfs = download_cutouts(args.tic, args.max_sectors, args.size, args.cache_dir)
        if not tpfs:
            return finish({"tic": args.tic, "skipped": True, "reason": "no TESScut coverage"})
    except Exception as exc:
        return finish({"tic": args.tic, "skipped": True, "reason": f"TESScut download failed: {exc}",
                       "traceback": traceback.format_exc(limit=3)})

    sectors, offsets, per_tr_offsets, exo = [], [], [], []
    stack_diff = None
    target_px = None
    for tpf in tpfs:
        res = sector_diff(tpf, period, epoch, dur)
        if res is None:
            continue
        col, row = tpf.wcs.world_to_pixel_values(tpf.ra, tpf.dec)
        tgt = (float(col), float(row))
        target_px = tgt
        dcx, dcy = flux_centroid(res["diff"], around=tgt, radius=3.0)
        ocx, ocy = flux_centroid(res["oot"], around=tgt, radius=2.0)
        # Offset relative to out-of-transit light centroid (cancels PSF/pointing biases)
        off = float(np.hypot(dcx - ocx, dcy - ocy))
        offsets.append(off)
        for d in res["per_transit"]:
            cx, cy = flux_centroid(d, around=tgt, radius=3.0)
            if np.isfinite(cx):
                per_tr_offsets.append((cx - ocx, cy - ocy))
        sectors.append({"sector": int(tpf.sector), "n_transits": res["n_transits"],
                        "diff_centroid_px": [dcx, dcy], "oot_centroid_px": [ocx, ocy],
                        "target_px": list(tgt), "offset_px": off})
        stack_diff = res["diff"] if stack_diff is None else stack_diff
        if args.exovetter:
            try:
                exo.append({"sector": int(tpf.sector), **run_exovetter(tpf, period, epoch, dur, depth)})
            except Exception as exc:
                exo.append({"sector": int(tpf.sector), "error": str(exc)})

    if not sectors:
        return finish({"tic": args.tic, "skipped": True,
                       "reason": "no usable in/out-of-transit cadences in downloaded cutouts"})

    pts = np.array(per_tr_offsets) if per_tr_offsets else np.zeros((0, 2))
    if len(pts) >= 3:
        mean = pts.mean(axis=0)
        err = pts.std(axis=0, ddof=1) / np.sqrt(len(pts))
        offset = float(np.hypot(*mean))
        sigma = float(offset / max(np.hypot(*err), 1e-6))
    else:
        offset, sigma = float(np.median(offsets)), float("nan")
    blended = offset > OFFSET_FAIL_PIX and (not np.isfinite(sigma) or sigma > OFFSET_FAIL_SIGMA)

    neighbours: list[dict] = []
    try:
        neighbours = nearby_tic(args.tic, float(tpfs[0].ra), float(tpfs[0].dec), depth, 2.5 * TESS_PIX_ARCSEC)
    except Exception as exc:
        neighbours = [{"error": f"TIC query failed: {exc}"}]

    # Diagnostic plot from the first usable sector
    fig, axes = plt.subplots(1, 2, figsize=(9, 4))
    first = sectors[0]
    tpf0 = next(t for t in tpfs if int(t.sector) == first["sector"])
    r0 = sector_diff(tpf0, period, epoch, dur)
    for ax, img, title in ((axes[0], r0["oot"], "Out of transit"), (axes[1], r0["diff"], "Difference (out - in)")):
        ax.imshow(img, origin="lower", cmap="viridis")
        ax.plot(*first["target_px"], "r+", ms=14, mew=2, label="target")
        ax.plot(*first["diff_centroid_px"], "wx", ms=10, mew=2, label="diff centroid")
        ax.set_title(f"{title} S{first['sector']}")
    axes[1].legend(loc="upper right", fontsize=7)
    fig.suptitle(f"TIC {args.tic} centroid check: offset {offset:.2f} px ({offset * TESS_PIX_ARCSEC:.0f}\")")
    fig.tight_layout()
    png = args.o / f"{args.tic}_diff_image.png"
    fig.savefig(png, dpi=120)
    plt.close(fig)

    payload = {
        "tic": args.tic,
        "pass": not blended,
        "offset_px": offset,
        "offset_arcsec": offset * TESS_PIX_ARCSEC,
        "offset_sigma": sigma,
        "n_transit_images": int(len(pts)),
        "sectors": sectors,
        "contaminant_candidates": neighbours,
        "diff_image_png": str(png),
        "criteria": f"fail if offset > {OFFSET_FAIL_PIX} px and > {OFFSET_FAIL_SIGMA} sigma",
    }
    if exo:
        payload["exovetter_centroid"] = exo
    if len(pts) < 3:
        payload["note"] = "fewer than 3 per-transit images; offset significance not computed"
    return finish(payload)


if __name__ == "__main__":
    raise SystemExit(main())
