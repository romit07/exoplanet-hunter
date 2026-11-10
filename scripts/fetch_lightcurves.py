#!/usr/bin/env python3
"""Download TESS-SPOC and QLP full-frame-image light curves for a TIC."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from exoplanet_hunter import lc_utils


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("tic", type=int, help="TESS Input Catalog ID")
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .npz path (default data/lightcurves/TIC.npz)",
    )
    p.add_argument("--cache-dir", type=Path, default=Path("data/mast_cache"))
    p.add_argument("--json-summary", type=Path, default=None, help="Optional metadata JSON")
    args = p.parse_args()

    out = args.output or Path(f"data/lightcurves/{args.tic}.npz")
    meta = lc_utils.fetch_tic_lightcurves(args.tic, out_path=out, cache_dir=args.cache_dir)
    summary = {
        "tic": args.tic,
        "n_points": int(meta["time"].shape[0]),
        "sectors": sorted({int(s) for s in meta["sector"]}),
        "spoc_sectors": meta.get("spoc_sectors", []),
        "qlp_sectors": meta.get("qlp_sectors", []),
        "time_span_btjd": [float(meta["time"].min()), float(meta["time"].max())],
        "authors": meta.get("authors", []),
    }
    print(json.dumps(summary, indent=2))
    if args.json_summary:
        args.json_summary.parent.mkdir(parents=True, exist_ok=True)
        args.json_summary.write_text(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
