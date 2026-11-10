#!/usr/bin/env python3
"""Query TIC for nearby stars with TESS FFI coverage, excluding known planet hosts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from astropy import units as u
from astropy.coordinates import SkyCoord
from astroquery.ipac.nexsci.nasa_exoplanet_archive import NasaExoplanetArchive
from astroquery.mast import Catalogs


def load_toi_tics() -> set[int]:
    try:
        tbl = NasaExoplanetArchive.query_criteria(table="toi", select="tic_id")
        return {int(x) for x in tbl["tic_id"] if x}
    except Exception:
        return set()


def load_confirmed_tics() -> set[int]:
    try:
        tbl = NasaExoplanetArchive.query_criteria(
            table="pscomppars", select="tic_id", where="default_flag=1"
        )
        return {int(x) for x in tbl["tic_id"] if x}
    except Exception:
        return set()


def has_2min_tess(tic: int) -> bool:
    import lightkurve as lk

    sr = lk.search_lightcurve(f"TIC {tic}", mission="TESS", exop_time=[120, 180])
    return len(sr) > 0


def query_tic_fields(
    tmag_max: float,
    radius_min: float,
    radius_max: float,
    dist_pc_max: float,
) -> pd.DataFrame:
    """Cone-search several high-latitude fields to sample the CTL."""
    fields = [
        (60.0, 45.0),
        (150.0, 45.0),
        (240.0, 45.0),
        (330.0, 45.0),
        (90.0, 70.0),
    ]
    frames = []
    colnames = (
        "ID,Tmag,radius,Teff,contratio,"
        "ra,dec,dist"
    )
    for ra, dec in fields:
        coord = SkyCoord(ra=ra * u.deg, dec=dec * u.deg)
        try:
            tbl = Catalogs.query_region(
                coord,
                catalog="Tic",
                radius=18 * u.deg,
                columns=colnames,
            )
        except Exception as exc:
            print(f"Query failed at ra={ra}: {exc}", file=sys.stderr)
            continue
        df = tbl.to_pandas()
        df = df.rename(columns={"ID": "tic"})
        if "dist" in df.columns:
            df = df[df["dist"].fillna(1e9) <= dist_pc_max]
        df = df[(df["Tmag"] <= tmag_max) & df["Tmag"].notna()]
        df = df[(df["radius"] >= radius_min) & (df["radius"] <= radius_max)]
        frames.append(df)
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True).drop_duplicates("tic")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dist-pc", type=float, default=60.0, help="Maximum distance (pc)")
    p.add_argument("--tmag-max", type=float, default=12.0, help="Brightness cut")
    p.add_argument("--r-min", type=float, default=0.5, help="Minimum radius (R_sun)")
    p.add_argument("--r-max", type=float, default=1.5, help="Maximum radius (R_sun)")
    p.add_argument("--limit", type=int, default=500, help="Max rows to keep after cuts")
    p.add_argument("--skip-2min-check", action="store_true", help="Faster but keeps 2-min targets")
    p.add_argument("-o", "--output", type=Path, default=Path("data/targets.csv"))
    args = p.parse_args()

    print("Querying TIC via cone searches...", file=sys.stderr)
    df = query_tic_fields(args.tmag_max, args.r_min, args.r_max, args.dist_pc)
    if df.empty:
        print("No targets returned — check MAST connectivity.", file=sys.stderr)
        return 1

    exclude = load_toi_tics() | load_confirmed_tics()
    df = df[~df["tic"].isin(exclude)]
    print(f"After removing {len(exclude)} known hosts: {len(df)} stars", file=sys.stderr)

    if not args.skip_2min_check:
        ffi_only = []
        for tic in df["tic"].astype(int):
            if not has_2min_tess(int(tic)):
                ffi_only.append(tic)
        df = df[df["tic"].isin(ffi_only)]
        print(f"FFI-only (no 2-min TESS): {len(df)} stars", file=sys.stderr)

    if len(df) > args.limit:
        df = df.sort_values("Tmag").head(args.limit)

    contam = df.get("contratio", pd.Series(0.01, index=df.index)).astype(float)
    df["snr_ref"] = 1.0 / np.clip(contam * 0.001 + 0.0003, 0.0003, None)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.output, index=False)
    print(f"Wrote {len(df)} targets to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
