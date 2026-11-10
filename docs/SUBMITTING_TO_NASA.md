# Submitting a TESS candidate to NASA for community review

This guide walks through checking a star on **ExoFOP**, preparing parameters from the `exoplanet-hunter` scripts, and registering future transit predictions. ExoFOP is the operational hub for the TESS Follow-up Observing Program (TFOP).

Official references (verify periodically — the site is updated):

- ExoFOP home: https://exofop.ipac.caltech.edu/
- TESS help and upload overview: https://exofop.ipac.caltech.edu/tess/help.php
- Request an account: link from the help page (“Request an account” under **Uploading Data to ExoFOP**)
- TFOP membership: https://tess.mit.edu/followup/apply-join-tfop/
- NASA Exoplanet Archive (cross-check TOIs and confirmed planets): https://exoplanetarchive.ipac.caltech.edu/
- MAST / TESS data: https://mast.stsci.edu/

## 1. Before you submit

1. **Crossmatch catalogs** — Run `scripts/vet_candidate.py` (catalog check) and manually confirm the TIC is not already a [TOI](https://exoplanetarchive.ipac.caltech.edu/cgi-bin/TblView/nph-tblView?app=ExoTbls&config=toi) or confirmed planet host.
2. **Open the ExoFOP target page** — `https://exofop.ipac.caltech.edu/tess/target.php?id=<TIC>`
3. **Understand status** — Community uploads are *candidates*, not confirmed planets. Most periodic dips fail vetting (stellar variability, eclipsing binaries, instrument artifacts).

## 2. Create an ExoFOP account

1. Go to https://exofop.ipac.caltech.edu/tess/help.php
2. Under **Uploading Data to ExoFOP**, follow **Request an account**
3. Log in before any upload; anonymous users cannot add parameters or files

## 3. Community TESS Objects of Interest (CTOIs)

CTOIs are TESS-based candidates **not** already issued as project TOIs. ExoFOP distinguishes:

- **TOI** — TESS project object of interest
- **CTOI** — community-reported TESS candidate (your upload)
- **Community Candidates** (broader program) — see the July 2025 release notes on the help page for non-TESS discovery sources

### Minimum parameters

From ExoFOP’s [Guidelines for Submitting Community Planet Candidates](https://exofop.ipac.caltech.edu/tess/help.php#community):

| Requirement | Detail |
|-------------|--------|
| General | At least **two of three**: period (d), transit midpoint (BJD/BTJD), depth (ppm), all > 0 |
| **CTOI / TOI-WG consideration** | All **four**: period, epoch, depth, **duration** (> 0) |
| Supporting material | Upload a folded light-curve plot (same **data tag** as parameters) |
| Duplicates | Do not create a new candidate if the star already has a TOI/CTOI or a period that is 2×/3× a known signal — add a parameter set instead |

Generate a starting parameter table with:

```bash
python scripts/make_ctoi_report.py <TIC> --notes "Your description"
```

Then transcribe values into ExoFOP’s web form or a bulk parameter file (templates linked from the help page under **Bulk Parameter Upload**).

### Data tags

Every upload needs a **data tag** (format `YYYYMMDD_username_description_nnn`). Tags tie together planet parameters, files, and observations. You may use the autotag option on the web form; see the help page section **Uploading Data to ExoFOP**.

### Typical workflow on the target page

1. Log in → open `target.php?id=<TIC>`
2. Confirm no existing planet candidate you would duplicate
3. **Add new** → **Planet Parameters** — enter period, epoch (BTJD or BJD per form), depth (ppm), duration (hours), uncertainties, disposition `PC` (planet candidate)
4. **Add new** → **Files** — upload `results/search/<TIC>_folded.png` and `results/vetting/<TIC>_vet.md`
5. Reuse the same data tag on parameters and files
6. Add an observing **note** summarizing vetting (odd/even, holdout year, dual SPOC/QLP agreement)

Bulk uploads: use **BULK UPLOADS → Stellar and Planet Parameters** on ExoFOP (see help page). Run the **verify** step before ingest.

## 4. TFOP follow-up

After a CTOI is public, TFOP observers may schedule ground-based imaging and spectroscopy to rule out false positives. Joining TFOP is optional but recommended if you plan ongoing follow-up:

- Apply: https://tess.mit.edu/followup/apply-join-tfop/
- TFOP workspace and optional 12-month proprietary group uploads are described on the ExoFOP help page under **TESS Follow-up Observing Program (TFOP) Working Group**

Planet Hunters TESS (https://www.planethunterstess.org/) is another venue for citizen-science vetting; it is independent of ExoFOP submission.

## 5. Preregister transit predictions (Zenodo)

Before the next TESS sector covering your target, publish a machine-readable ephemeris so later data can falsify the candidate:

```bash
python scripts/predict_transits.py <TIC> --months-ahead 24
```

Deposit `results/predictions/<TIC>_predictions.json` on [Zenodo](https://zenodo.org/) (or similar) and cite the DOI in your ExoFOP note and any paper. Example community practice: [doi:10.5281/zenodo.23257784](https://doi.org/10.5281/zenodo.23257784) for TIC 370612437 / HIP 114417 predictions.

## 6. Peer-reviewed “Community Candidate” track

ExoFOP also supports **published** community candidates (journal or RNAAS with prior methods citation) via a separate approval path — see **Published Candidate Upload Request** on the help page. CTOI web uploads are the path for sharing parameters ahead of publication; requirements differ slightly (paper URL mandatory for the published track).

## 7. Support

- ExoFOP staff: exofop-support@ipac.caltech.edu
- TESS science support: https://heasarc.gsfc.nasa.gov/docs/tess/
