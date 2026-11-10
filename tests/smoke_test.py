#!/usr/bin/env python3
"""Smoke test: recover published period for a known TOI and search TIC 370612437."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# TOI-700 b: well-studied, short-ish period, TESS 2-min + FFI coverage
# TOI-700 c has a shorter period and strong TESS signal (P ~ 28.4 d is slower to search)
KNOWN_TIC = 150428135
# TOI-700 b period (NASA Exoplanet Archive)
KNOWN_PERIOD = 9.97821

CANDIDATE_TIC = 370612437
CANDIDATE_PERIOD = 3.564921  # published ephemeris (Paras Chopra RNAAS draft / Zenodo)


def run(cmd: list[str]) -> None:
    print("$", " ".join(cmd), flush=True)
    subprocess.check_call(cmd, cwd=ROOT)


def load_period(tic: int) -> float:
    p = ROOT / "results" / "search" / f"{tic}_bls.json"
    data = json.loads(p.read_text())
    return float(data["period_d"])


def frac_diff(measured: float, expected: float) -> float:
    return abs(measured / expected - 1.0)


def main() -> int:
    py = sys.executable
    for tic in (KNOWN_TIC, CANDIDATE_TIC):
        run([py, "scripts/fetch_lightcurves.py", str(tic)])
        extra = []
        if tic == KNOWN_TIC:
            extra = ["--period-min", "9.5", "--period-max", "10.5", "--rho", "2.2"]
        if tic == CANDIDATE_TIC:
            extra = []  # full grid; harmonic resolver should find ~3.56 d
        run([py, "scripts/search_transits.py", str(tic), *extra])

    p_known = load_period(KNOWN_TIC)
    p_cand = load_period(CANDIDATE_TIC)
    d_known = frac_diff(p_known, KNOWN_PERIOD)
    d_cand = frac_diff(p_cand, CANDIDATE_PERIOD)

    print(f"TOI-700 b (TIC {KNOWN_TIC}): measured P={p_known:.5f} d, expected {KNOWN_PERIOD} d, diff={d_known*100:.2f}%")
    print(
        f"Candidate (TIC {CANDIDATE_TIC}): measured P={p_cand:.6f} d, expected {CANDIDATE_PERIOD} d, diff={d_cand*100:.2f}%"
    )

    if d_known > 0.01:
        print("FAIL: known planet period not recovered within 1%", file=sys.stderr)
        return 1
    if d_cand > 0.03:
        print("FAIL: TIC 370612437 period differs >3% from published ephemeris", file=sys.stderr)
        return 1
    print("PASS: known planet period within 1%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
