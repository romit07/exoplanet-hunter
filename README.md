# exoplanet-hunter

A reusable toolkit for searching **NASA TESS full-frame-image (FFI)** light curves for new transit candidates, vetting periodic dips, preregistering future transit times, and preparing **Community TESS Object of Interest (CTOI)** submissions on [ExoFOP](https://exofop.ipac.caltech.edu/).

**Candidates are not confirmed planets.** TESS’s large pixels and sparse cadence favor false positives (eclipsing binaries, stellar variability, instrumental glitches). Expect most signals to fail vetting; only a subset warrant ExoFOP upload and ground follow-up.

## Quickstart

```bash
git clone https://github.com/romit07/exoplanet-hunter.git && cd exoplanet-hunter
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Download + search one star
python3 scripts/fetch_lightcurves.py 370612437
python3 scripts/search_transits.py 370612437
python3 scripts/vet_candidate.py 370612437

# Automated sanity check (known TOI + candidate star)
python3 tests/smoke_test.py
```

Structured end-to-end steps live in **[SKILL.md](SKILL.md)**. NASA submission details: **[docs/SUBMITTING_TO_NASA.md](docs/SUBMITTING_TO_NASA.md)**. Naming (catalog IDs vs official IAU names): **[docs/NAMING.md](docs/NAMING.md)**. Packaged candidates: **[candidates/](candidates/)**. Walkthrough notebook: **[notebooks/exoplanet_search.ipynb](notebooks/exoplanet_search.ipynb)**.

## What’s in the repo

| Component | Role |
|-----------|------|
| `scripts/select_targets.py` | TIC query: nearby stars, FFI-friendly, exclude known TOI/planet hosts |
| `scripts/fetch_lightcurves.py` | SPOC + QLP FFI download per sector |
| `scripts/search_transits.py` | Detrend, BLS transit search, folded plot |
| `scripts/vet_candidate.py` | Odd/even, secondary, holdout, injection, catalog checks → JSON + Markdown |
| `scripts/predict_transits.py` | Future midtransit table for Zenodo preregistration |
| `scripts/make_ctoi_report.py` | ExoFOP parameter summary |
| `scripts/publish_candidate.py` | Package a vetted hit into `candidates/TIC<id>/` and update the index |
| `candidates/` | Public candidate folders plus [INDEX.md](candidates/INDEX.md) |
| `exoplanet_hunter/lc_utils.py` | Shared light-curve I/O, cleaning, BLS |
| `tests/smoke_test.py` | Period recovery on TOI-700 b and TIC 370612437 |

Optional: `search_transits.py --tls` uses [Transit Least Squares](https://github.com/hippke/transitleastsquares) when installed.

## Method (summary)

The pipeline mirrors community practice for **FFI-only** nearby stars:

1. Target stars observed at 30-min / 10-min / 200-s cadence but **not** at TESS 2-minute precision, and not already on the TOI or confirmed-planet lists.
2. Download independent reductions (**TESS-SPOC** and **QLP** where available).
3. Biweight detrend per sector, bin to 10 minutes, **Box Least Squares** search (0.5–25 d) with harmonic alias checks.
4. Vetting: catalog crossmatch, odd/even and secondary eclipse tests, SPOC/QLP agreement, inverted light-curve control, leave-one-sector holdout, simple injection–recovery, transit-duration sanity check.
5. Preregister ephemeris on Zenodo before upcoming sectors; package a passing candidate with `publish_candidate.py`; after a refereed write-up, upload parameters and plots to ExoFOP as a community candidate / CTOI (see [docs/SUBMITTING_TO_NASA.md](docs/SUBMITTING_TO_NASA.md) for the current publication-first policy).

Advanced steps (pixel centroids, TRICERATOPS, full MCMC transit fits, dilution from Gaia neighbors) are documented in SKILL.md as manual follow-ups — implement as you harden a candidate.

## Inspiration

This project is inspired by **Paras Chopra** ([@paraschopra](https://x.com/paraschopra)), who reported two Earth-sized TESS planet candidates on 9 October 2026. From his announcement:

> “I may have found two new Earth-sized planets in our galaxy this morning!”

- Post: https://x.com/paraschopra/status/2108486193419882775  
- Code: https://github.com/paraschopra/tess-planet-candidates (MIT; studied for methodology, not copied verbatim)  
- Preregistered transit times: https://doi.org/10.5281/zenodo.23257784  
- Candidates: **TIC 370612437** (Cygnus, ~158 ly; ~210 ppm; P ≈ 3.56 d; ~1.0 R⊕) and **HIP 114417** / **TIC 252721481** (Andromeda, ~134 ly; ~279 ppm; P ≈ 4.93 d; ~1.1 R⊕)  
- ExoFOP: [TIC 370612437](https://exofop.ipac.caltech.edu/tess/target.php?id=370612437), [TIC 252721481](https://exofop.ipac.caltech.edu/tess/target.php?id=252721481)

Independent discussion: [Space Data Rig review](https://x.com/SpaceDataRig/status/2109473341526757448). Related open pipeline: [break-the-build/astrosearch](https://github.com/break-the-build/astrosearch).

## Caveats

- **FFI photometry is shallow and noisy.** Earth-size transits around sun-like stars are at the edge of detectability.
- **Vetting here is necessary but not sufficient.** A passing automated report does not validate a planet.
- **MAST downloads** need network access; full target lists can be hundreds of MB.
- `select_targets.py` TIC cuts are approximate; always eyeball contamination and cadence on MAST.

## License

MIT — see [LICENSE](LICENSE). Use NASA/MAST data under their terms; cite TESS, SPOC, and QLP as appropriate in publications.
