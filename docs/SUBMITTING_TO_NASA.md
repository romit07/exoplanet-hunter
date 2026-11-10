# Submitting a TESS candidate to NASA for community review

This guide is a checklist from a **passing vetting report** through extra false-positive tests, prediction preregistration, publication, and upload to **ExoFOP**. ExoFOP is the operational hub for the TESS Follow-up Observing Program (TFOP).

**A packaged candidate is not a confirmed planet.** Most periodic dips fail some combination of vetting, blend tests, or ground follow-up.

Official references (re-check these pages before you submit — ExoFOP updates its policy):

- ExoFOP home: https://exofop.ipac.caltech.edu/
- TESS help and upload overview: https://exofop.ipac.caltech.edu/tess/help.php
- Candidate guidelines (published community candidates): https://exofop.ipac.caltech.edu/tess/candidate_help.php
- ExoFOP news (policy changes): https://exofop.ipac.caltech.edu/tess/news.php
- Published Candidate Upload Request (login required): https://exofop.ipac.caltech.edu/tess/pub_candidate_upload_request.php
- Request an account: linked from the help page under **Uploading Data to ExoFOP** (“Request an account”)
- TFOP membership: https://tess.mit.edu/followup/apply-join-tfop/
- NASA Exoplanet Archive (TOIs and confirmed planets): https://exoplanetarchive.ipac.caltech.edu/
- TOI table: https://exoplanetarchive.ipac.caltech.edu/cgi-bin/TblView/nph-tblView?app=ExoTbls&config=toi
- MAST / TESS data: https://mast.stsci.edu/
- Target page for a given TIC: `https://exofop.ipac.caltech.edu/tess/target.php?id=<TIC>`

On the ExoFOP home page, also open **List of all TOIs**, **List of all CTOIs**, and **List of Community Candidates** (in the PLANETS box) and confirm you are not duplicating an existing object.

## Current ExoFOP policy (as of 19 August 2026)

ExoFOP paused new community-candidate (CTOI) uploads on 31 March 2026, then [reopened the programme on 19 August 2026](https://exofop.ipac.caltech.edu/tess/news.php) with stricter rules. As stated on the help page and news post:

- Candidates must first be **published in a peer-reviewed journal with online access** before they are uploaded to ExoFOP.
- A [Research Note of the AAS (RNAAS)](https://exofop.ipac.caltech.edu/tess/help.php) is acceptable **if** the methodology used to detect and vet the candidate has already been published in a peer-reviewed journal that is available online, and that paper is cited in the Research Note.
- **Approval is required** before upload. After logging in, complete the [Published Candidate Upload Request](https://exofop.ipac.caltech.edu/tess/pub_candidate_upload_request.php). Submit candidates only after that request is approved.
- The **paper URL is required** on the candidate form.

The older workflow of posting an unpublished CTOI “ahead of a paper” is **not** the current path. If a later news post changes this again, follow the live help page.

## Checklist

### 1. Extra checks after automated vetting

`scripts/vet_candidate.py` covers catalog, odd/even, secondary eclipse, SPOC/QLP agreement, inverted-light-curve, holdout, injection–recovery, and duration-consistency tests. Before you treat a passing report as submission-ready, run the checks that those scripts do not yet perform:

1. **Catalog crossmatch (again, manually).** Confirm the TIC is not already a [TOI](https://exoplanetarchive.ipac.caltech.edu/cgi-bin/TblView/nph-tblView?app=ExoTbls&config=toi), a confirmed-planet host in the [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/), or an existing CTOI / community candidate on ExoFOP. Open `https://exofop.ipac.caltech.edu/tess/target.php?id=<TIC>` and the TOI, CTOI, and Community Candidate lists. ExoFOP will remove duplicates; repeated duplicates can lead to account suspension. If the period is a near match or an integer multiple (2×, 3×, …) of a known signal on the same star, add a new parameter set to the existing object instead of creating a new candidate ([candidate guidelines](https://exofop.ipac.caltech.edu/tess/candidate_help.php)).
2. **Nearby-star / dilution check.** Identify Gaia neighbours inside the TESS pixel and estimate how much they dilute the transit. A deep transit on a faint neighbour can look like a shallow transit on the target. The TIC contamination ratio is a starting point, not a substitute for a neighbour list.
3. **Pixel-level or centroid blend test.** Check whether the dip is on the target star or a nearby source (difference imaging, centroid shift, or a comparable pixel-level test). TESS pixels are large; this is one of the main ways nearby eclipsing binaries mimic planets. Run `python scripts/centroid_check.py <TIC>` (difference-image centroid offset plus the list of catalogued neighbours bright enough to mimic the depth) and inspect the saved difference image.
4. **TRICERATOPS (or a similar statistical FPP).** Estimate the false-positive probability given the TESS aperture, nearby stars, and the observed transit. Record the FPP, the adopted prior assumptions, and whether the result clears a conservative threshold. Run `python scripts/fpp_triceratops.py <TIC> --repeats 5` (optional dependency: `pip install -r requirements-optional.txt`) and cite Giacalone & Dressing (2020) and Giacalone et al. (2021).

Keep plots and a short write-up of each test with the candidate package.

### 2. Package the candidate in this repository

```bash
python scripts/predict_transits.py <TIC> --months-ahead 24
python scripts/make_ctoi_report.py <TIC> --notes "Your description"
python scripts/publish_candidate.py <TIC>
# when you are ready to put the folder on GitHub:
python scripts/publish_candidate.py <TIC> --git-commit --git-push
```

`publish_candidate.py` writes `candidates/TIC<id>/` (summary README, copies of plots and JSON, CTOI-ready text) and updates `candidates/INDEX.md`. It refuses unless vetting `overall_pass` is true, unless you pass `--force`. Default status is “Community candidate, unconfirmed.” See `candidates/README.md`.

### 3. Preregister transit predictions (Zenodo)

Publish a machine-readable ephemeris **before** the next TESS sector that covers the star, so later photometry can confirm or falsify the signal:

```bash
python scripts/predict_transits.py <TIC> --months-ahead 24
```

Deposit `results/predictions/<TIC>_predictions.json` (or the copy under `candidates/TIC<id>/`) on [Zenodo](https://zenodo.org/) and cite the DOI in the paper, the ExoFOP note, and the candidate README. Example community practice: [doi:10.5281/zenodo.23257784](https://doi.org/10.5281/zenodo.23257784) for TIC 370612437 / HIP 114417 predictions.

### 4. Write and publish the candidate

Under the 19 August 2026 rules, ExoFOP will only ingest community candidates that are already in the refereed literature (or an RNAAS that cites a previously published methods paper). Typical contents:

- Target, ephemeris (period, epoch, depth, duration) with uncertainties
- Data reductions used (SPOC, QLP, sectors)
- Vetting results, including the extra checks in step 1
- Preregistered transit times and the Zenodo DOI
- A clear statement that the object is a *candidate*, not a confirmed planet

Do not assign a lowercase letter (`b`, `c`, …) until the planet is confirmed in the refereed literature. Official public names are a separate IAU process; see [NAMING.md](NAMING.md).

### 5. Create an ExoFOP account (if you do not have one)

1. Go to https://exofop.ipac.caltech.edu/tess/help.php
2. Under **Uploading Data to ExoFOP**, follow **Request an account**
3. Log in before requesting upload approval or submitting anything; anonymous users cannot add parameters or files

### 6. Request approval to upload

1. Log in and open the [Published Candidate Upload Request](https://exofop.ipac.caltech.edu/tess/pub_candidate_upload_request.php)
2. Wait for approval from ExoFOP staff
3. Do not attempt to create a new candidate until that approval arrives

Questions: exofop-support@ipac.caltech.edu

### 7. Submit the candidate on ExoFOP

After approval, add the candidate from the target page or via a bulk parameter file (templates are linked from the help page under **Bulk Parameter Upload**). Generate a starting table with `scripts/make_ctoi_report.py` and transcribe values carefully.

#### Minimum parameters

From ExoFOP’s [candidate guidelines](https://exofop.ipac.caltech.edu/tess/candidate_help.php) (re-verify on the live page):

| Requirement | Detail |
|-------------|--------|
| General | At least **two of three**: period (d), transit midpoint (BJD), depth (ppm), all > 0 |
| **CTOI / TOI-WG consideration** | All **four**: period, epoch, depth, **duration**, all > 0 |
| Paper URL | Required for the published-candidate track |
| Supporting material | Upload a folded light-curve plot (same **data tag** as the parameters). Candidates without supporting material may be removed. |
| Discovery source | TESS by default; change only if the detection is from another project |
| Disposition | `PC` (planet candidate) or `FP` (false positive). `CP` is not allowed for a new candidate |
| Name | Choose the next `TICID.nn` value from the form. Optional team “candidate name” from the paper must follow ExoFOP rules (see [NAMING.md](NAMING.md)) |
| Note | Required; include the paper URL, Zenodo DOI, and a short vetting summary |

#### Data tags

Every upload needs a **data tag** (format `YYYYMMDD_username_description_nnn`). Tags tie together planet parameters, files, and observations. You may use the autotag option on the web form; to keep parameters and files associated, reuse the **same** tag. Details are on the help page under **Uploading Data to ExoFOP**.

#### Typical steps on the target page

1. Log in → open `target.php?id=<TIC>`
2. Confirm you would not duplicate an existing TOI, CTOI, or community candidate
3. Use the form to add a new community planet candidate / planet parameters — period, epoch (BTJD or BJD as the form requests), depth (ppm), duration (hours), uncertainties, disposition `PC`, paper URL, and note
4. **Add new** → **Files** — upload the folded light curve (`results/search/<TIC>_folded.png` or the copy in `candidates/TIC<id>/`) and the vetting report
5. Reuse the same data tag on parameters and files
6. Initial parameters are fixed after creation; you can later update the disposition, add a new parameter set, and attach further files or observations

Bulk uploads: use **BULK UPLOADS → Stellar and Planet Parameters** on ExoFOP (see the help page). Run the **verify** step before ingest.

### 8. What happens next

- **Public candidate on ExoFOP.** Once ingested, the object is a community candidate (a CTOI if the discovery source is TESS), not a confirmed planet.
- **TFOP follow-up.** TFOP observers may schedule ground-based seeing-limited photometry, high-resolution imaging, and spectroscopy to rule out false positives and, where possible, measure a mass. Joining TFOP is optional but useful if you plan to stay involved:
  - Apply: https://tess.mit.edu/followup/apply-join-tfop/
  - TFOP workspace and the optional 12-month proprietary group uploads are described on the ExoFOP help page under **TESS Follow-up Observing Program (TFOP) Working Group**
- **TOI number.** If the TESS Object of Interest working group adopts the cTOI, the star/signal receives a TOI designation (for example TOI-1234.01). That is still a *candidate* designation.
- **Confirmed planet or false positive.** Confirmation typically requires follow-up plus a refereed paper. Confirmed planets then use a letter designation (TOI-1234 b). Update `candidates/INDEX.md` and the candidate README to “TOI assigned,” “Confirmed,” or “False positive” as appropriate.

Planet Hunters TESS (https://www.planethunterstess.org/) is an independent citizen-science vetting venue; it is not a substitute for ExoFOP submission.

## Support

- ExoFOP staff: exofop-support@ipac.caltech.edu
- TESS science support: https://heasarc.gsfc.nasa.gov/docs/tess/
