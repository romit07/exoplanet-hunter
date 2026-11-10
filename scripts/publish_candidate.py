#!/usr/bin/env python3
"""Package a vetted transit candidate into candidates/TIC<id>/ for the public repo.

Reads the JSON/plot outputs produced by search_transits.py, vet_candidate.py,
predict_transits.py, and make_ctoi_report.py (default paths under results/).
Refuses to publish unless vetting overall_pass is true, unless --force is set.

Examples
--------
    python scripts/publish_candidate.py 370612437
    python scripts/publish_candidate.py 370612437 --git-commit --git-push
    python scripts/publish_candidate.py 370612437 --force  # failed vetting, still archive
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_STATUS = "Community candidate, unconfirmed"
R_SUN_TO_REARTH = 109.2

INDEX_INTRO = """# Candidate index

This table lists transit candidates packaged under `candidates/`. **Nothing listed here is a confirmed planet.** Status values are explained in [README.md](README.md).

| TIC | Date found (UTC) | Period (d) | Depth (ppm) | Status | Folder |
|-----|------------------|------------|-------------|--------|--------|
"""


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def fmt(value, spec: str | None = None, fallback: str = "—") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return fallback
    if spec:
        try:
            return format(value, spec)
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def check_status(check: dict) -> str:
    if check.get("pass"):
        return "pass"
    if "reason" in check:
        return "skip"
    return "fail"


def utc_date(raw: str | None) -> str:
    if raw:
        text = raw.strip()
        try:
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            dt = datetime.fromisoformat(text)
            return dt.astimezone(timezone.utc).date().isoformat()
        except ValueError:
            if len(text) >= 10 and text[4] == "-" and text[7] == "-":
                return text[:10]
    return datetime.now(timezone.utc).date().isoformat()


def lookup_stellar(targets_csv: Path | None, tic: int) -> dict:
    out: dict = {}
    if targets_csv is None or not targets_csv.is_file():
        return out
    with targets_csv.open(newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            key = row.get("tic") or row.get("TIC") or row.get("ID") or row.get("id")
            if key is None:
                continue
            try:
                if int(float(key)) != tic:
                    continue
            except ValueError:
                continue
            for src, dest in (
                ("ra", "ra_deg"),
                ("RA", "ra_deg"),
                ("dec", "dec_deg"),
                ("DEC", "dec_deg"),
                ("Tmag", "tmag"),
                ("tmag", "tmag"),
                ("radius", "r_star_rsun"),
                ("dist", "distance_pc"),
                ("contratio", "contratio"),
                ("Teff", "teff_k"),
            ):
                if src in row and row[src] not in (None, "") and dest not in out:
                    try:
                        out[dest] = float(row[src])
                    except ValueError:
                        out[dest] = row[src]
            break
    return out


def estimated_radius_rearth(depth_frac: float | None, r_star: float | None) -> float | None:
    if depth_frac is None or r_star is None:
        return None
    try:
        if depth_frac <= 0 or r_star <= 0:
            return None
        return math.sqrt(depth_frac) * r_star * R_SUN_TO_REARTH
    except (TypeError, ValueError):
        return None


def first_present(data: dict, *keys):
    for key in keys:
        if key in data and data[key] not in (None, ""):
            return data[key]
    return None


def ctoi_markdown(tic: int, fields: dict) -> str:
    depth = fields.get("transit_depth_ppm")
    duration = fields.get("transit_duration_hours")
    depth_s = f"{depth:.1f}" if isinstance(depth, (int, float)) else fmt(depth)
    dur_s = f"{duration:.3f}" if isinstance(duration, (int, float)) else fmt(duration)
    notes = fields.get("submission_notes") or ""
    return "\n".join(
        [
            f"# CTOI field summary — TIC {tic}",
            "",
            "Use these values when uploading planet parameters on ExoFOP "
            "(logged-in **Add new** → Planet Parameters, or bulk upload).",
            "",
            f"- **TIC ID**: {fields.get('tic_id', tic)}",
            f"- **Discovery source**: {fields.get('discovery_data_source', 'TESS')}",
            f"- **Disposition**: {fields.get('disposition', 'PC')}",
            f"- **Period (d)**: {fields.get('orbital_period_days')}",
            f"- **Transit epoch (BTJD)**: {fields.get('transit_epoch_btjd')}",
            f"- **Depth (ppm)**: {depth_s}",
            f"- **Duration (h)**: {dur_s}",
            "",
            "## Notes",
            notes,
            "",
            f"Target page: {fields.get('exofop_target_url', '')}",
            "",
        ]
    )


def build_ctoi_fields(tic: int, search: dict, vet: dict, pred_rel: str, notes: str) -> dict:
    ephem = vet.get("ephemeris", search) if vet else search
    duration_d = ephem.get("duration_d", search.get("duration_d"))
    duration_h = duration_d * 24 if isinstance(duration_d, (int, float)) else None
    return {
        "tic_id": tic,
        "discovery_data_source": "TESS",
        "disposition": "PC",
        "orbital_period_days": ephem.get("period_d", search.get("period_d")),
        "transit_epoch_btjd": ephem.get("epoch_btjd", search.get("epoch_btjd")),
        "transit_depth_ppm": ephem.get("depth_ppm", search.get("depth_ppm")),
        "transit_duration_hours": duration_h,
        "period_uncertainty_days": "see search / fit — attach MCMC if available",
        "epoch_uncertainty_btjd": "see search / fit",
        "vetting_summary": vet.get("overall_pass") if vet else None,
        "failed_vetting_checks": vet.get("failed_checks", []),
        "supporting_plots": [
            f"results/search/{tic}_folded.png",
            f"results/vetting/{tic}_vet.md",
        ],
        "preregistered_predictions": pred_rel,
        "exofop_target_url": f"https://exofop.ipac.caltech.edu/tess/target.php?id={tic}",
        "submission_notes": notes
        or (
            "Community candidate from FFI-only TESS search (exoplanet-hunter toolkit). "
            "Not a TESS project TOI. Attach folded LC plot and vetting report via ExoFOP Files."
        ),
    }


def copy_if_exists(src: Path | None, dest_dir: Path) -> Path | None:
    if src is None or not src.is_file():
        return None
    dest = dest_dir / src.name
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return dest


def upsert_index(index_path: Path, tic: int, date_found: str, period, depth, status: str) -> None:
    folder = f"TIC{tic}"
    period_s = fmt(period, ".6f")
    depth_s = fmt(depth, ".1f")
    new_row = (
        f"| {tic} | {date_found} | {period_s} | {depth_s} | {status} | [{folder}]({folder}/) |"
    )
    if not index_path.exists():
        index_path.write_text(INDEX_INTRO + new_row + "\n")
        return
    lines = index_path.read_text().splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        if line.startswith("|") and "TIC" in line and "Status" in line:
            header_idx = i
            break
    if header_idx is None:
        text = index_path.read_text().rstrip() + "\n\n" + INDEX_INTRO + new_row + "\n"
        index_path.write_text(text)
        return
    sep_idx = header_idx + 1
    start = sep_idx + 1 if sep_idx < len(lines) and set(lines[sep_idx].replace("|", "").replace("-", "").replace(" ", "")) == set() else header_idx + 1
    updated = False
    for i in range(start, len(lines)):
        if not lines[i].startswith("|"):
            continue
        cells = [c.strip() for c in lines[i].strip("|").split("|")]
        if not cells:
            continue
        tic_cell = cells[0].split("]")[0].lstrip("[").strip()
        if tic_cell == str(tic):
            # Keep the original "date found" unless the existing cell is empty.
            old_date = cells[1] if len(cells) > 1 and cells[1] else date_found
            period_s = fmt(period, ".6f")
            depth_s = fmt(depth, ".1f")
            lines[i] = (
                f"| {tic} | {old_date} | {period_s} | {depth_s} | {status} | [{folder}]({folder}/) |"
            )
            updated = True
            break
    if not updated:
        insert_at = len(lines)
        for i in range(start, len(lines)):
            if not lines[i].startswith("|"):
                insert_at = i
                break
        lines.insert(insert_at, new_row)
    index_path.write_text("\n".join(lines).rstrip() + "\n")


def write_candidate_readme(
    path: Path,
    tic: int,
    status: str,
    date_found: str,
    search: dict,
    vet: dict,
    stellar: dict,
    radius_rearth: float | None,
    depth_frac: float | None,
    predictions: dict | None,
    nickname: str | None,
    forced: bool,
    copied: list[str],
) -> None:
    ephem = vet.get("ephemeris", search) if vet else search
    period = ephem.get("period_d", search.get("period_d"))
    epoch = ephem.get("epoch_btjd", search.get("epoch_btjd"))
    duration_d = ephem.get("duration_d", search.get("duration_d"))
    depth_ppm = ephem.get("depth_ppm", search.get("depth_ppm"))
    duration_h = duration_d * 24 if isinstance(duration_d, (int, float)) else None
    snr = search.get("snr")
    sde = search.get("sde")
    rp_rs = math.sqrt(depth_frac) if isinstance(depth_frac, (int, float)) and depth_frac > 0 else None

    overall = vet.get("overall_pass") if vet else None
    overall_s = "PASS" if overall else ("FAIL" if overall is False else "unknown")
    if forced and overall is False:
        overall_s = "FAIL (published with --force)"

    lines = [
        f"# TIC {tic}" + (f" (“{nickname}”)" if nickname else ""),
        "",
        f"**Status:** {status}",
        "",
        "This is a **community candidate, unconfirmed**. A periodic dip in a TESS "
        "FFI light curve is not a confirmed planet. See [docs/NAMING.md](../../docs/NAMING.md) "
        "for why this object keeps its catalog name, and "
        "[docs/SUBMITTING_TO_NASA.md](../../docs/SUBMITTING_TO_NASA.md) for review and ExoFOP steps.",
        "",
        "## Summary",
        "",
        "| Field | Value |",
        "|-------|-------|",
        f"| TIC | {tic} |",
    ]
    if nickname:
        lines.append(f"| Informal nickname | {nickname} (not an official name) |")
    lines.extend(
        [
            f"| RA (deg) | {fmt(stellar.get('ra_deg'), '.6f')} |",
            f"| Dec (deg) | {fmt(stellar.get('dec_deg'), '.6f')} |",
            f"| TESS magnitude | {fmt(stellar.get('tmag'), '.3f')} |",
            f"| Stellar radius (R☉) | {fmt(stellar.get('r_star_rsun'), '.3f')} |",
            f"| Distance (pc) | {fmt(stellar.get('distance_pc'), '.1f')} |",
            f"| Period (d) | {fmt(period, '.6f')} |",
            f"| Epoch (BTJD) | {fmt(epoch, '.5f')} |",
            f"| Depth (ppm) | {fmt(depth_ppm, '.1f')} |",
            f"| Duration (h) | {fmt(duration_h, '.3f')} |",
            f"| Estimated radius (R⊕) | {fmt(radius_rearth, '.2f')} |",
            f"| Rp/R⋆ (from depth) | {fmt(rp_rs, '.5f')} |",
            f"| SNR | {fmt(snr, '.2f')} |",
            f"| SDE | {fmt(sde, '.2f')} |",
            f"| Date found (UTC) | {date_found} |",
            f"| Automated vetting | {overall_s} |",
            f"| ExoFOP target | https://exofop.ipac.caltech.edu/tess/target.php?id={tic} |",
            "",
        ]
    )

    lines.extend(["## Vetting checks", "", "| Check | Result | Notes |", "|-------|--------|-------|"])
    checks = vet.get("checks") or {}
    if checks:
        for name, check in checks.items():
            result = check_status(check)
            note_bits = []
            if "reason" in check:
                note_bits.append(str(check["reason"]))
            # Keep the table compact: include a few numeric hints when present.
            for key in ("ratio", "inverted_snr", "toi", "confirmed"):
                if key in check:
                    note_bits.append(f"{key}={check[key]}")
            notes = "; ".join(note_bits) if note_bits else "—"
            lines.append(f"| {name} | {result} | {notes} |")
    else:
        lines.append("| (none) | — | Vetting JSON was missing a `checks` block. |")
    failed = vet.get("failed_checks") or []
    skipped = vet.get("skipped_checks") or []
    lines.append("")
    if failed:
        lines.append(f"Failed checks: {', '.join(failed)}")
        lines.append("")
    if skipped:
        lines.append(f"Skipped checks: {', '.join(skipped)}")
        lines.append("")

    lines.extend(["## Preregistered future transits", ""])
    if predictions and predictions.get("predictions"):
        preds = predictions["predictions"]
        lines.append(
            f"Ephemeris window: {len(preds)} midtimes in "
            f"`{tic}_predictions.json` (deposit on Zenodo before the next season; "
            "see [docs/SUBMITTING_TO_NASA.md](../../docs/SUBMITTING_TO_NASA.md))."
        )
        lines.append("")
        lines.append("| Cycle | Midtime (UTC) | Midtime (BTJD) | σ (d) |")
        lines.append("|------:|---------------|----------------|------:|")
        for row in preds[:12]:
            lines.append(
                f"| {row.get('cycle', '—')} | {fmt(row.get('midtime_utc'))} | "
                f"{fmt(row.get('midtime_btjd'), '.5f')} | {fmt(row.get('midtime_sigma_d'), '.6f')} |"
            )
        if len(preds) > 12:
            lines.append("")
            lines.append(f"First 12 of {len(preds)} predicted midtimes are shown; see the JSON for the full table.")
        lines.append("")
    else:
        lines.append(
            "No prediction file was supplied. Run `scripts/predict_transits.py` and re-publish, "
            "then deposit the JSON on Zenodo."
        )
        lines.append("")

    lines.extend(
        [
            "## Caveats",
            "",
            "- **Not a confirmed planet.** Passing automated vetting is necessary but not sufficient.",
            "- TESS FFI photometry is shallow; Earth-size signals around Sun-like stars sit near the noise floor.",
            "- Automated checks do not include a TRICERATOPS false-positive probability, a pixel-level or centroid blend test, or a Gaia nearby-star dilution analysis. Run those before treating the signal as submission-ready (see [docs/SUBMITTING_TO_NASA.md](../../docs/SUBMITTING_TO_NASA.md)).",
            "- Estimated radius, when given, is `sqrt(depth) × R⋆` in Earth units and ignores limb darkening, impact parameter, and dilution.",
        ]
    )
    if nickname:
        lines.append(
            f"- “{nickname}” is an informal nickname for this folder only. It is not an IAU name "
            "and should not be used as a formal designation."
        )
    if forced and overall is False:
        lines.append("- This package was written with `--force` after automated vetting failed. Do not submit it to ExoFOP as a new candidate without resolving the failed checks.")
    lines.append("")
    lines.extend(["## Packaged files", ""])
    if copied:
        for name in copied:
            lines.append(f"- `{name}`")
    else:
        lines.append("- (no supporting search/vet/prediction files were found to copy)")
    lines.append("")
    path.write_text("\n".join(lines))


def git_cmd(repo: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def resolve_repo(start: Path) -> Path:
    proc = git_cmd(start, ["rev-parse", "--show-toplevel"])
    if proc.returncode != 0:
        raise RuntimeError(
            f"{start} is not inside a git repository.\n{proc.stderr.strip() or proc.stdout.strip()}"
        )
    return Path(proc.stdout.strip())


def git_publish(repo: Path, paths: list[Path], tic: int, do_push: bool) -> None:
    for flag in paths:
        if not flag.exists():
            raise RuntimeError(f"Cannot git-add missing path: {flag}")
    rels = [str(p.resolve().relative_to(repo.resolve())) for p in paths]
    added = git_cmd(repo, ["add", "--", *rels])
    if added.returncode != 0:
        raise RuntimeError(f"git add failed:\n{added.stderr or added.stdout}")
    commit = git_cmd(repo, ["commit", "-m", f"Add candidate TIC{tic}", "--", *rels])
    if commit.returncode != 0:
        text = (commit.stdout or "") + (commit.stderr or "")
        if "nothing to commit" in text.lower() or "no changes added" in text.lower():
            print("No changes to commit (candidate folder already up to date).", file=sys.stderr)
        else:
            raise RuntimeError(f"git commit failed:\n{text}")
    else:
        print(commit.stdout.strip() or f"Committed candidate TIC{tic}", file=sys.stderr)
        head = git_cmd(repo, ["rev-parse", "--short", "HEAD"])
        if head.returncode == 0:
            print(f"Commit {head.stdout.strip()}", file=sys.stderr)
    if do_push:
        push = git_cmd(repo, ["push", "origin", "HEAD"])
        if push.returncode != 0:
            raise RuntimeError(f"git push failed:\n{push.stderr or push.stdout}")
        print(push.stdout.strip() or push.stderr.strip() or "Pushed to origin.", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("tic", type=int, help="TESS Input Catalog ID")
    p.add_argument("--search-json", type=Path, default=None, help="Default: results/search/<tic>_bls.json")
    p.add_argument("--vet-json", type=Path, default=None, help="Default: results/vetting/<tic>_vet.json")
    p.add_argument("--vet-md", type=Path, default=None, help="Default: results/vetting/<tic>_vet.md")
    p.add_argument("--predictions-json", type=Path, default=None, help="Default: results/predictions/<tic>_predictions.json")
    p.add_argument("--ctoi-json", type=Path, default=None, help="Default: results/ctoi/<tic>_ctoi_fields.json")
    p.add_argument("--ctoi-md", type=Path, default=None, help="Default: results/ctoi/<tic>_ctoi_fields.md")
    p.add_argument("--folded-plot", type=Path, default=None, help="Default: results/search/<tic>_folded.png")
    p.add_argument("--targets-csv", type=Path, default=Path("data/targets.csv"), help="Optional TIC table with ra, dec, Tmag, radius")
    p.add_argument("--ra", type=float, default=None, help="Right ascension (deg), overrides the target table")
    p.add_argument("--dec", type=float, default=None, help="Declination (deg), overrides the target table")
    p.add_argument("--tmag", type=float, default=None, help="TESS magnitude, overrides the target table")
    p.add_argument("--r-star", type=float, default=None, dest="r_star", help="Stellar radius (R_sun), for a simple Rp estimate")
    p.add_argument("--nickname", default=None, help="Informal nickname only; not an official IAU name")
    p.add_argument("--status", default=DEFAULT_STATUS, help=f'Default: "{DEFAULT_STATUS}"')
    p.add_argument("--date-found", default=None, help="UTC date YYYY-MM-DD (default: vetting generated_utc or today)")
    p.add_argument("--notes", default="", help="Extra notes copied into the generated CTOI summary if no CTOI JSON exists")
    p.add_argument("-o", type=Path, default=Path("candidates"), help="Parent folder for TIC<id>/ and INDEX.md")
    p.add_argument("--force", action="store_true", help="Publish even if vetting overall_pass is false")
    p.add_argument("--git-commit", action="store_true", help='git add the new folder and INDEX.md, then commit "Add candidate TIC<id>"')
    p.add_argument("--git-push", action="store_true", help="Push the new commit to origin (never force-pushes)")
    args = p.parse_args()

    if args.git_push and not args.git_commit:
        print("--git-push requires --git-commit", file=sys.stderr)
        return 2

    search_path = args.search_json or Path(f"results/search/{args.tic}_bls.json")
    vet_path = args.vet_json or Path(f"results/vetting/{args.tic}_vet.json")
    vet_md_path = args.vet_md or Path(f"results/vetting/{args.tic}_vet.md")
    pred_path = args.predictions_json or Path(f"results/predictions/{args.tic}_predictions.json")
    ctoi_json_path = args.ctoi_json or Path(f"results/ctoi/{args.tic}_ctoi_fields.json")
    ctoi_md_path = args.ctoi_md or Path(f"results/ctoi/{args.tic}_ctoi_fields.md")
    plot_path = args.folded_plot or Path(f"results/search/{args.tic}_folded.png")

    if not search_path.is_file():
        print(f"Search JSON not found: {search_path}", file=sys.stderr)
        return 1
    if not vet_path.is_file():
        print(f"Vetting JSON not found: {vet_path}", file=sys.stderr)
        return 1

    search = load_json(search_path)
    vet = load_json(vet_path)
    if "overall_pass" not in vet:
        print(f"{vet_path} has no overall_pass field", file=sys.stderr)
        return 1
    if not vet["overall_pass"] and not args.force:
        failed = ", ".join(vet.get("failed_checks") or []) or "see vetting report"
        print(
            f"Refusing to publish TIC {args.tic}: vetting overall_pass is false "
            f"({failed}). Re-run after the signal passes, or pass --force to archive it anyway.",
            file=sys.stderr,
        )
        return 1

    predictions = load_json(pred_path) if pred_path.is_file() else None
    ctoi_fields = load_json(ctoi_json_path) if ctoi_json_path.is_file() else None

    stellar = lookup_stellar(args.targets_csv, args.tic)
    if args.ra is not None:
        stellar["ra_deg"] = args.ra
    if args.dec is not None:
        stellar["dec_deg"] = args.dec
    if args.tmag is not None:
        stellar["tmag"] = args.tmag
    if args.r_star is not None:
        stellar["r_star_rsun"] = args.r_star
    # Allow optional stellar fields already stored on the search/vet JSON.
    for src, dest in (("ra", "ra_deg"), ("dec", "dec_deg"), ("tmag", "tmag"), ("r_star", "r_star_rsun"), ("radius", "r_star_rsun")):
        value = first_present(search, src, dest) or first_present(vet, src, dest)
        if value is not None and dest not in stellar:
            stellar[dest] = value

    ephem = vet.get("ephemeris", search)
    depth_ppm = ephem.get("depth_ppm", search.get("depth_ppm"))
    depth_frac = search.get("depth_frac")
    if depth_frac is None and isinstance(depth_ppm, (int, float)):
        depth_frac = depth_ppm / 1e6
    radius_rearth = estimated_radius_rearth(depth_frac, stellar.get("r_star_rsun"))
    date_found = args.date_found or utc_date(vet.get("generated_utc"))

    dest_root = args.o
    dest = dest_root / f"TIC{args.tic}"
    dest.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for src in (search_path, plot_path, vet_path, vet_md_path, pred_path, ctoi_json_path, ctoi_md_path):
        out = copy_if_exists(src if src.is_file() else None, dest)
        if out:
            copied.append(out.name)

    if ctoi_fields is None:
        ctoi_fields = build_ctoi_fields(
            args.tic,
            search,
            vet,
            pred_path.name if pred_path.is_file() else "",
            args.notes,
        )
        generated_json = dest / f"{args.tic}_ctoi_fields.json"
        generated_json.write_text(json.dumps(ctoi_fields, indent=2) + "\n")
        if generated_json.name not in copied:
            copied.append(generated_json.name)
    if not (dest / f"{args.tic}_ctoi_fields.md").is_file():
        md_path = dest / f"{args.tic}_ctoi_fields.md"
        md_path.write_text(ctoi_markdown(args.tic, ctoi_fields))
        if md_path.name not in copied:
            copied.append(md_path.name)

    write_candidate_readme(
        dest / "README.md",
        tic=args.tic,
        status=args.status,
        date_found=date_found,
        search=search,
        vet=vet,
        stellar=stellar,
        radius_rearth=radius_rearth,
        depth_frac=depth_frac,
        predictions=predictions,
        nickname=args.nickname,
        forced=args.force,
        copied=sorted(set(copied)),
    )

    index_path = dest_root / "INDEX.md"
    upsert_index(
        index_path,
        args.tic,
        date_found,
        ephem.get("period_d", search.get("period_d")),
        depth_ppm,
        args.status,
    )

    print(f"Wrote {dest}/", file=sys.stderr)
    print(f"Updated {index_path}", file=sys.stderr)

    if args.git_commit:
        repo = resolve_repo(dest_root if dest_root.is_absolute() else Path.cwd())
        try:
            dest_abs = dest.resolve()
            index_abs = index_path.resolve()
            dest_abs.relative_to(repo.resolve())
            index_abs.relative_to(repo.resolve())
        except ValueError:
            print("Refusing --git-commit: output paths are outside the git repository.", file=sys.stderr)
            return 1
        try:
            git_publish(repo, [dest, index_path], args.tic, do_push=args.git_push)
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
