# Candidates

This folder holds packaged **community transit candidates** from the `exoplanet-hunter` search and vetting scripts. Each object lives in its own `TIC<id>/` directory with a summary README, copies of the search/vetting/prediction outputs, and a CTOI-ready parameter write-up.

**Nothing in this folder is a confirmed planet.** A periodic dip in a TESS full-frame-image light curve can be a planet, an eclipsing binary, a neighbouring star, stellar variability, or an instrumental artefact. Automated vetting is necessary but not sufficient.

## How a candidate is added

After `search_transits.py`, `vet_candidate.py`, `predict_transits.py`, and `make_ctoi_report.py` have been run and vetting reports `overall_pass: true`:

```bash
python scripts/publish_candidate.py <TIC>
# optional: commit and push the packaged folder
python scripts/publish_candidate.py <TIC> --git-commit --git-push
```

The script refuses to publish if automated vetting failed, unless you pass `--force` (for archiving a rejected signal, not for ExoFOP submission).

The index of every packaged candidate is [INDEX.md](INDEX.md).

## Status values

Update the status in the candidate README and in `INDEX.md` as the object moves through review. Typical values:

| Status | Meaning |
|--------|---------|
| Community candidate, unconfirmed | Packaged after a passing (or forced) vetting report. Default for new folders. |
| Submitted as CTOI | Parameters and supporting files have been accepted on [ExoFOP](https://exofop.ipac.caltech.edu/) as a Community TESS Object of Interest (or other community candidate). |
| TOI assigned | The TESS Object of Interest working group has adopted the signal and issued a TOI designation (for example TOI-1234.01). Still a candidate, not a confirmed planet. |
| Confirmed | Validated or confirmed as a planet in the refereed literature (and typically listed as such by the NASA Exoplanet Archive). Official designations then use a lowercase letter (for example TOI-1234 b). |
| False positive | Follow-up or further vetting has shown the dip is not a planet (eclipsing binary, blend, artefact, or similar). |

See [docs/SUBMITTING_TO_NASA.md](../docs/SUBMITTING_TO_NASA.md) for the checks, publication, and ExoFOP steps that sit between “candidate” and “submitted,” and [docs/NAMING.md](../docs/NAMING.md) for why discoverers cannot officially name the star or the planet.
