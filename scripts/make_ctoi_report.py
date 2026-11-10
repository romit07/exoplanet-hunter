#!/usr/bin/env python3
"""Format Community TESS Object of Interest (CTOI) submission fields."""

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
    p.add_argument("tic", type=int)
    p.add_argument("--search-json", type=Path, default=None)
    p.add_argument("--vet-json", type=Path, default=None)
    p.add_argument("--predictions-json", type=Path, default=None)
    p.add_argument("--disposition", default="PC", choices=["PC", "FP"])
    p.add_argument("--notes", default="", help="Free-text notes for ExoFOP")
    p.add_argument("-o", type=Path, default=Path("results/ctoi"))
    args = p.parse_args()

    search = json.loads(
        (args.search_json or lc_utils.default_search_json(args.tic)).read_text()
    )
    vet_path = args.vet_json or Path(f"results/vetting/{args.tic}_vet.json")
    vet = json.loads(vet_path.read_text()) if vet_path.exists() else {}

    pred_path = args.predictions_json or Path(f"results/predictions/{args.tic}_predictions.json")
    zenodo = str(pred_path) if pred_path.exists() else ""

    ephem = vet.get("ephemeris", search)
    checks = vet.get("checks", {})
    centroid = checks.get("centroid", {})
    fpp = checks.get("fpp", {})
    ranking = vet.get("ranking", {})
    fields = {
        "tic_id": args.tic,
        "discovery_data_source": "TESS",
        "disposition": args.disposition,
        "orbital_period_days": ephem["period_d"],
        "transit_epoch_btjd": ephem.get("epoch_btjd", search["epoch_btjd"]),
        "transit_depth_ppm": ephem.get("depth_ppm", search["depth_ppm"]),
        "transit_duration_hours": ephem.get("duration_d", search["duration_d"]) * 24,
        "period_uncertainty_days": "see search / fit — attach MCMC if available",
        "epoch_uncertainty_btjd": "see search / fit",
        "vetting_summary": vet.get("overall_pass"),
        "failed_vetting_checks": vet.get("failed_checks", []),
        "skipped_vetting_checks": vet.get("skipped_checks", []),
        "search_method": search.get("method", "bls"),
        "search_snr": search.get("snr"),
        "search_sde": search.get("sde"),
        "centroid_offset_arcsec": centroid.get("offset_arcsec"),
        "centroid_offset_sigma": centroid.get("offset_sigma"),
        "triceratops_fpp": fpp.get("fpp"),
        "triceratops_nfpp": fpp.get("nfpp"),
        "ranking_score": ranking.get("score"),
        "supporting_plots": [
            f"results/search/{args.tic}_folded.png",
            f"results/vetting/{args.tic}_vet.md",
            *([centroid["diff_image_png"]] if centroid.get("diff_image_png") else []),
        ],
        "preregistered_predictions": zenodo,
        "exofop_target_url": f"https://exofop.ipac.caltech.edu/tess/target.php?id={args.tic}",
        "submission_notes": args.notes
        or "Community candidate from FFI-only TESS search (exoplanet-hunter toolkit). "
        "Not a TESS project TOI. Attach folded LC plot and vetting report via ExoFOP Files.",
    }

    args.o.mkdir(parents=True, exist_ok=True)
    json_out = args.o / f"{args.tic}_ctoi_fields.json"
    md_out = args.o / f"{args.tic}_ctoi_fields.md"
    json_out.write_text(json.dumps(fields, indent=2))

    md_lines = [
        f"# CTOI field summary — TIC {args.tic}",
        "",
        "Use these values when uploading planet parameters on ExoFOP "
        "(logged-in **Add new** → Planet Parameters, or bulk upload).",
        "",
        f"- **TIC ID**: {fields['tic_id']}",
        f"- **Discovery source**: {fields['discovery_data_source']}",
        f"- **Disposition**: {fields['disposition']}",
        f"- **Period (d)**: {fields['orbital_period_days']}",
        f"- **Transit epoch (BTJD)**: {fields['transit_epoch_btjd']}",
        f"- **Depth (ppm)**: {fields['transit_depth_ppm']:.1f}",
        f"- **Duration (h)**: {fields['transit_duration_hours']:.3f}",
        "",
        "## Vetting evidence (paste into ExoFOP notes)",
        f"- Search: {fields['search_method'].upper()}, SNR {fields['search_snr']}, SDE {fields['search_sde']}",
        f"- Vetting overall pass: {fields['vetting_summary']}; failed: {fields['failed_vetting_checks'] or 'none'}; "
        f"skipped: {fields['skipped_vetting_checks'] or 'none'}",
        "- Difference-image centroid offset: "
        + (f"{fields['centroid_offset_arcsec']:.1f}\" ({fields['centroid_offset_sigma']:.1f} sigma)"
           if fields["centroid_offset_arcsec"] is not None else "not run"),
        "- TRICERATOPS FPP / NFPP: "
        + (f"{fields['triceratops_fpp']:.4f} / {fields['triceratops_nfpp']:.4g}"
           if fields["triceratops_fpp"] is not None else "not run"),
        f"- Ranking score (heuristic): {fields['ranking_score']}",
        "",
        "## Notes",
        fields["submission_notes"],
        "",
        f"Target page: {fields['exofop_target_url']}",
    ]
    md_out.write_text("\n".join(md_lines))
    print(json.dumps(fields, indent=2))
    print(f"Wrote {json_out} and {md_out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
