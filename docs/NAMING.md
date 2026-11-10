# Naming stars and exoplanet candidates

Discoverers **cannot officially name** a star or a planet on their own. A new transit signal keeps its catalog designation. Informal nicknames are fine in a repository README; they are not official names and do not replace the catalog ID.

## What a candidate is called

| Stage | Typical designation | Who assigns it |
|-------|---------------------|----------------|
| Search / this repo | TIC ID, for example TIC 370612437 | [TESS Input Catalog](https://exofop.ipac.caltech.edu/) |
| Uploaded community candidate | TIC ID plus an ExoFOP sequence such as `TICID.01` (and an optional team “candidate name” from the paper) | [ExoFOP](https://exofop.ipac.caltech.edu/tess/help.php) |
| Adopted by the TESS project | TOI designation such as TOI-700.01 | TESS Object of Interest working group |
| Confirmed in the refereed literature | Letter designation on the host-star name, such as TOI-700 b, starting at **b** then c, d, … | Community convention, used in the literature and the [NASA Exoplanet Archive](https://exoplanetarchive.ipac.caltech.edu/) |

ExoFOP’s candidate guidelines state that planet candidates **should not** be given a lowercase letter (`b`, `c`, …) until they are confirmed in the published, refereed literature, and that a team “candidate name” must not copy an existing confirmed-planet name. See [Guidelines for Submitting Published Planet Candidates](https://exofop.ipac.caltech.edu/tess/candidate_help.php).

A TOI number (TOI-xxxx.01) still marks a *candidate*. Confirmation, if it happens, comes later from follow-up and a refereed paper.

## Official public names

The [International Astronomical Union (IAU)](https://www.iau.org/) is the internationally recognised authority for official names of celestial bodies. Two IAU groups are relevant here:

- The [Working Group on Star Names (WGSN)](https://www.iau.org/WG280/WG280/Home.aspx) adopts official proper names for stars and maintains the IAU Catalog of Star Names. The catalog is linked from the IAU’s 12 February 2026 announcement, [IAU Selects New Star Names to Reflect Global Astronomical Culture](https://www.iau.org/IAU/News/Ann2026/New-Star-Names-2026.aspx), and is published at [exopla.net/star-names/modern-iau-star-names](https://exopla.net/star-names/modern-iau-star-names/).
- The [Executive Committee Working Group on Exoplanetary System Nomenclature](https://www.iau.org/WG331/WG331/Home.aspx) advises on naming exoplanets and their host stars and supports the IAU’s public naming campaigns.

Official *public* names for exoplanets and (when included) their host stars have been assigned through the IAU [NameExoWorlds](https://nameexoworlds.iau.org/) campaigns, not by individual discoverers acting alone. In those campaigns the public and the discoverers take part, and the IAU working group selects names that follow the published rules. The IAU has been explicit that:

- The selected public names **do not replace** the scientific alphanumeric designations (for example, GJ 1214 b remains the scientific designation even after it also received the public name Enaiposha). See the IAU press release [IAU Selects Names for 20 Exoplanetary Systems](https://www.iau.org/IAU/News/PR2023/iau-names-exoplanetary-systems.aspx) and the [NameExoWorlds 2022 naming rules](https://nameexoworlds.iau.org/2022naming-rules).
- Buying a name, or running an unofficial public vote, has no official standing. See [Can One Buy the Right to Name a Planet?](https://www.iau.org/IAU/News/PR2013/buying-rights-name-planet-iau-responds.aspx).

NameExoWorlds is a periodic campaign with its own target list and rules; there is not an open form to officially name an arbitrary new TESS candidate. Watch [nameexoworlds.iau.org](https://nameexoworlds.iau.org/) for any future round.

## Informal nicknames

A short informal nickname in a paper, a talk, or a candidate README is reasonable, as long as it is labelled informal and the catalog ID remains the identifier used in tables, filenames, and submissions.

An example from the work that inspired this toolkit: Paras Chopra ([@paraschopra](https://x.com/paraschopra)) used the informal name **Aakanksha** for one of his TESS candidates. That kind of nickname is fine in a folder README. It is not an IAU name, not a TOI designation, and should not be written as if it were “TOI-… b.”

ExoFOP also allows an optional “candidate name” drawn from the discovery paper when a published candidate is uploaded. That field is a project identifier inside ExoFOP, not an IAU proper name, and it must follow the ExoFOP naming rules linked above.
