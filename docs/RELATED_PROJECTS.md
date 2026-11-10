# Related open-source projects

A survey (November 2026) of open-source exoplanet transit search and vetting
code, what each does well, and what this toolkit borrowed. Star counts are
GitHub stars at the time of the survey. Where a project is published as a pip
package we **depend on it** rather than copying code, and cite the authors.

## Libraries we now use directly

| Project | What it does | Stars | License | How we use it |
|---|---|---|---|---|
| [hippke/tls](https://github.com/hippke/tls) — Transit Least Squares (Hippke & Heller 2019) | Period search with a limb-darkened transit template instead of a box; more sensitive than BLS to small planets at the same false-alarm rate | 66 | MIT | `search_transits.py --method tls\|both` via `pip install transitleastsquares` |
| [hippke/wotan](https://github.com/hippke/wotan) (Hippke et al. 2019) | Time-series detrending; the time-windowed biweight is the recommended filter for transit searches | 180 | MIT | Per-sector biweight detrending in `lc_utils.clean_lc` (already used) |
| [stevengiacalone/triceratops](https://github.com/stevengiacalone/triceratops) (Giacalone & Dressing 2020; Giacalone et al. 2021) | Bayesian false-positive probability (FPP/NFPP) against eclipsing-binary and nearby-star scenarios | 33 | MIT | `scripts/fpp_triceratops.py` (optional dependency, graceful skip) |
| [spacetelescope/exovetter](https://github.com/spacetelescope/exovetter) | Python port of Kepler/TESS vetting metrics: ModShift, SWEET, odd/even, centroid, LEO transit events | 8 | BSD-3 | ModShift + SWEET as an advisory check in `vet_candidate.py`; optional centroid cross-check in `centroid_check.py --exovetter` |
| [lightkurve/lightkurve](https://github.com/lightkurve/lightkurve) | TESS/Kepler data access and light-curve tools | 550 | MIT | Light-curve and cutout I/O (already used) |

## Projects we studied (ideas borrowed, no code copied)

| Project | What it does | Stars | License | What it does better / what we borrowed |
|---|---|---|---|---|
| [paraschopra/tess-planet-candidates](https://github.com/paraschopra/tess-planet-candidates) (Paras Chopra, [@paraschopra](https://x.com/paraschopra)) | FFI-only search of 526 nearby stars that found two Earth-sized candidates; vetting, preregistration, CTOI draft | 3 | see repo | The inspiration for this toolkit: holdout-sector test, inverted light curve, preregistered predictions. Its stated open caveat (pixel-level blends) is why we added `centroid_check.py` and TRICERATOPS. |
| [noraeisner/LATTE](https://github.com/noraeisner/LATTE) (Eisner et al. 2020) | Interactive vetting reports for TESS candidates (Planet Hunters TESS) | 41 | LGPL-3.0 | Per-candidate diagnostic report with in/out-of-transit difference images and nearby-star overlays. Borrowed the difference-image idea. |
| [mkunimoto/LEO-Vetter](https://github.com/mkunimoto/LEO-Vetter) (Kunimoto et al. 2025) | Robovetter-style automated flux- and pixel-level vetting for TESS | 13 | GPL-3.0 | Threshold-based metric vetting and pixel-level checks. Inspired the metric list in our ranking score (not copied: GPL). |
| [exoplanetvetting/DAVE](https://github.com/exoplanetvetting/DAVE) (Kostov et al. 2019) | Discovery and vetting pipeline for K2/TESS, incl. ModShift and centroid tests | 12 | MIT | Centroid-offset significance from per-transit difference images; ModShift (now via exovetter). |
| [nasa/kepler-robovetter](https://github.com/nasa/kepler-robovetter) (Coughlin et al. 2016; Thompson et al. 2018) | The Kepler DR24/DR25 automated vetting thresholds | 32 | none stated | MS1/MS2-style ModShift cuts used in our advisory exovetter check. |
| [franpoz/SHERLOCK](https://github.com/franpoz/SHERLOCK) (Pozuelos et al. 2020; Dévora-Pajares et al. 2024) | End-to-end search → vet → validate → fit → follow-up planning, with multi-detrend TLS | 29 | MIT | Running TLS on shortlisted stars and an end-to-end flow. We kept BLS as the fast default and TLS as the deep option. |
| [eumemic/exoplanets](https://github.com/eumemic/exoplanets) | Multi-sector TESS search of ~10k nearby K/M dwarfs with public candidate tables | 14 | MIT | Public candidate tables and a transit planner; matches our `candidates/` publishing approach. |
| [jlillo/tpfplotter](https://github.com/jlillo/tpfplotter) (Aller et al. 2020) | TESS pixel plots with Gaia sources and apertures | 41 | MIT | Listing catalogued neighbours that could cause the dip, with their delta-mag; we list TIC neighbours bright enough to mimic the depth. |
| [afeinstein20/eleanor](https://github.com/afeinstein20/eleanor) (Feinstein et al. 2019) | Custom FFI light-curve extraction | 101 | MIT | Useful for stars without SPOC/QLP light curves; a possible future fetch backend. |
| [nasa/ExoMiner](https://github.com/nasa/ExoMiner) (Valizadegan et al. 2022) | Deep-learning classifier for Kepler/TESS candidates | 106 | none stated | Shows the value of a learned ranking; ours is a transparent CPU-only weighted score instead (no GPU, no training set). |
| [google-research/exoplanet-ml](https://github.com/google-research/exoplanet-ml) (Shallue & Vanderburg 2018) | AstroNet CNN classifier for Kepler candidates | 324 | Apache-2.0 | Same as above; archived since 2022. |
| [maxkroft/Alfred](https://github.com/maxkroft/Alfred) (Kroft et al. 2026) | Pip-installable detection and characterisation library | 3 | MIT | General-purpose detection library; noted as an alternative backend. |
| [break-the-build/astrosearch](https://github.com/break-the-build/astrosearch) | Rust transit search with a Python vetting gate and injection-calibrated tiers | 1 | MIT | Injection-calibrated detection thresholds; a good next step for our scan thresholds. |
| [exoplanet-spaceapps/exoplanet-starter](https://github.com/exoplanet-spaceapps/exoplanet-starter) | NASA Space Apps 2025 starter: BLS/TLS baseline plus ML classifiers and visualisation | 0 | Apache-2.0 | BLS + TLS side by side; we added the same option. |
| [hposborn/MonoTools](https://github.com/hposborn/MonoTools) | Detection/modelling of single- and duo-transits | 10 | BSD-2 | Not adopted (long-period monotransits are out of scope for now). |

## Comparison: what this toolkit adds

Most classifier repositories on GitHub (e.g. the
[exoplanet-classification topic](https://github.com/topics/exoplanet-classification))
re-label already-catalogued Kepler signals. This toolkit instead searches
fresh TESS FFI light curves for uncatalogued signals and takes them through to
an ExoFOP CTOI submission:

| Capability | This toolkit | Typical classifier repo |
|---|---|---|
| Search new data (BLS + TLS) | yes | no |
| Odd/even, secondary, inverted LC, holdout sector, injection | yes | rarely |
| Difference-image centroid + neighbour list | yes (`centroid_check.py`) | no |
| Statistical FPP (TRICERATOPS) | yes (optional) | no |
| Candidate ranking score | transparent weighted score | trained model |
| ExoFOP CTOI fields + preregistration | yes | no |

## Possible next borrowings

- Injection-recovery grids to calibrate SNR/SDE thresholds per magnitude bin (astrosearch, SHERLOCK).
- eleanor or TESS-Gaia light curves for stars without SPOC/QLP products.
- A full MCMC transit fit (e.g. `exoplanet`, `juliet`) for final CTOI uncertainties.

Please cite the original papers above when you use results that depend on these tools.
