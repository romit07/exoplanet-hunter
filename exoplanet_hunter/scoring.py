"""Transparent candidate ranking score built from vetting metrics.

This is a hand-weighted logistic score, not a trained neural network: every
term is an interpretable vetting metric and the weights are listed below, so a
reviewer can see exactly why a candidate ranks where it does. It runs on CPU in
microseconds and needs no training data. Use it to sort a scan's survivors for
manual review; it is not a planet probability (use TRICERATOPS FPP for that).

The feature set follows the metrics used by the Kepler Robovetter / LEO-Vetter
style of threshold vetting (SNR, odd/even, secondary, duration, centroid
offset) plus the checks specific to this toolkit (inverted light curve,
hold-out sector, cross-reduction agreement).
"""

from __future__ import annotations

import math
from typing import Any

# log-odds contribution per feature (positive = more planet-like)
WEIGHTS = {
    "bias": -1.0,
    "snr": 1.6,            # sigmoid-ish ramp around SNR 7..15
    "odd_even": 1.2,       # |log(odd/even)| small
    "secondary": 1.2,      # no significant secondary eclipse
    "t14": 0.8,            # duration consistent with a planet around this star
    "inverted": 1.0,       # inverted light curve shows no equally strong dip
    "holdout": 1.0,        # blind period recovered with a sector held out
    "injection": 0.5,      # pipeline recovers an injected copy of the signal
    "cross_reduction": 0.8,
    "centroid": 1.5,       # difference-image centroid on target
    "fpp": 2.0,            # TRICERATOPS false-positive probability
    "exovetter_modshift": 0.8,
}


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _tri(check: dict | None) -> float | None:
    """+1 pass, -1 fail, None skipped / missing."""
    if not check or "reason" in check or check.get("skipped"):
        return None
    return 1.0 if check.get("pass") else -1.0


def candidate_score(report: dict[str, Any]) -> dict[str, Any]:
    checks = report.get("checks", {})
    eph = report.get("ephemeris", {})
    terms: dict[str, float] = {"bias": WEIGHTS["bias"]}

    snr = eph.get("snr")
    if snr is not None and math.isfinite(snr):
        terms["snr"] = WEIGHTS["snr"] * (2 * _sigmoid((snr - 9.0) / 2.5) - 1)

    oe = checks.get("odd_even", {})
    if "ratio" in oe and oe["ratio"] and oe["ratio"] > 0 and math.isfinite(oe["ratio"]):
        dev = abs(math.log(oe["ratio"]))
        terms["odd_even"] = WEIGHTS["odd_even"] * (1 - 2 * min(dev / math.log(2), 1.5))

    sec = checks.get("secondary", {})
    if sec.get("primary_depth_frac", 0) > 0:
        r = max(sec.get("secondary_depth_frac", 0.0), 0.0) / sec["primary_depth_frac"]
        terms["secondary"] = WEIGHTS["secondary"] * (1 - 4 * min(r, 0.5))

    t14 = checks.get("t14_consistency", {})
    if t14.get("ratio") and math.isfinite(t14["ratio"]) and t14["ratio"] > 0:
        dev = abs(math.log(t14["ratio"]))
        terms["t14"] = WEIGHTS["t14"] * (1 - 2 * min(dev / math.log(2.5), 1.5))

    for key, name in (
        ("inverted", "inverted_lc"),
        ("holdout", "holdout_year"),
        ("injection", "injection_recovery"),
        ("cross_reduction", "cross_reduction"),
        ("centroid", "centroid"),
        ("exovetter_modshift", "exovetter"),
    ):
        v = _tri(checks.get(name))
        if v is not None:
            terms[key] = WEIGHTS[key] * v

    fpp_check = checks.get("fpp", {})
    fpp = fpp_check.get("fpp")
    if fpp is not None and "reason" not in fpp_check and math.isfinite(fpp):
        # FPP 0 -> +w, 0.5 -> 0, 1 -> -w
        terms["fpp"] = WEIGHTS["fpp"] * (1 - 2 * fpp)

    logit = sum(terms.values())
    score = _sigmoid(logit)
    tier = "strong" if score >= 0.8 else "promising" if score >= 0.5 else "weak"
    if checks.get("catalog", {}).get("toi"):
        tier += " (known TOI)"
    return {
        "score": round(score, 4),
        "tier": tier,
        "logit": round(logit, 3),
        "terms": {k: round(v, 3) for k, v in terms.items()},
        "missing_inputs": sorted(set(WEIGHTS) - set(terms)),
        "note": "Heuristic ranking score for ordering candidates; not a false-positive probability.",
    }
