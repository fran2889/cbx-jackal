---
type: epic
title: "An owner can see what happened to every page"
parent: initiative-cbx-jackal
covers: ["R3"]
after: ["epic-bounded-downscaling"]
assignee: ""
risk: medium
---

# An owner can see what happened to every page

## Description

An owner gets one HTML report per run that names every entry, its outcome, and why — including the pages
that were downscaled and the spreads that were exempted, which the text report states only as counts and
one line. It reads the report's existing data model rather than re-deriving outcomes.

## Outcome

An owner opens one file after a run and sees every page's fate without scrolling text; the initiative's
R3 measure is the signal.

## Requirements

- **R3** — A quality audit of a run, delivered as an HTML report. (parent initiative, Requirements; origin:
  owner, 2026-10-06)

## Done when

1. One run produces an HTML report naming every entry and its outcome class.
2. Every downscaled page is listed with its dimensions before and after.
3. Every spread exempted from the width rule is listed by name, so the exemption is never silent.
4. Every failure is listed with the one-line reason the text report already gives.
5. The text report is byte-identical for an owner who does not ask for HTML.
6. A run over a directory of several archives reports every archive, not only the first.
7. `README.md` documents how to produce the report and where the file is written.
8. The released version installs and runs from a clean environment on all three platforms.

## Boundaries

The reporting surface. It consumes `Report` as its data source and adds an output format. Not the geometry
decision (epic-bounded-downscaling), the target format (epic-webp-target), or the input container
(epic-archive-containers).

## References

- parent — _bmad-output/initiative-cbx-jackal/initiative-cbx-jackal.md, section Requirements
- companion — _bmad-output/initiative-cbx-jackal/spec-cbz-jxl/spec-cbz-jxl.md, section Capabilities,
  CAP-4. This epic is the same guarantee in a surface an owner can read
- companion — _bmad-output/initiative-cbx-jackal/change-bounded-page-downscaling/change-bounded-page-downscaling.md,
  section 4.6, for the summary and exemption-line format this epic renders
- constraint — the initiative's References, section Constraints: entry payload bytes are not the archive's
  size on disk, and the published figure is `os.path.getsize` of the file actually written

## Notes

- Open question: the report's owner — one file per invocation, or one per archive in a multi-archive run.
  `cli.py` prints one block per path, so both are defensible; not decided here.
- Open question: "quality audit" in the requirement and "report" in the title may not be the same artifact.
  If a per-page quality metric is wanted, that is further scope than rendering what already exists.
- Handoff: epic-bounded-downscaling produces the fields this epic renders — the downscaled flag, the
  before-and-after dimensions, and the exemption list. This epic must not re-derive any of them; it waits
  on that epic's outcome-vocabulary contract rather than assuming the fields.
- Decision: this epic consumes the shared contracts from the opening epic rather than a spine, because it
  was sliced with them (2026-10-06).
