---
type: initiative
title: cbx-jackal
parent: none
covers: ["R1", "R2", "R3", "R4"]
risk: medium
---

# cbx-jackal

## Description

A command-line tool that turns a comic archive's pages into a smaller archive without touching anything the
owner did not ask it to touch. The spec owns the capabilities, constraints and non-goals for the transcoder
that shipped; this initiative delivers the capabilities the owner has queued on top of it.

## Outcome

An owner with a large scanned library shrinks it with one command, can get their pages back, and can read
the result in the reader they already use; the spec's success signal, named not restated, is the measure.

## Requirements

The numbered spec at `_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/spec-cbz-jxl.md` is the source for the
shipped transcoder. The four requirements below have no spec text yet; each cites its origin and is expanded
by `bmad-spec` at its epic's inception, into a `spec-<slug>/` inside that epic's folder whose ids map back
here through `covers`.

- **R1** — Bounded downscaling of oversized pages, with orientation honoured and spreads recognised but
  never split. Detailed as CAP-6 in
  `_bmad-output/initiative-cbx-jackal/change-bounded-page-downscaling/change-bounded-page-downscaling.md`
  section 4.2, which is approved but not yet applied to the spec. (origin: owner, 2026-10-06)
- **R2** — WebP as an alternative target format: lossless by default, configurable quality, the same shape
  as jpg -> jxl. (origin: owner, 2026-10-06)
- **R3** — A quality audit of a run, delivered as an HTML report. (origin: owner, 2026-10-06)
- **R4** — RAR, CB7 and 7Z read as input containers, with output always CBZ. (origin: owner, 2026-10-06)

## Done when

1. Given a box, every page of a book of mixed page sizes fits it, no spread is split, no page is enlarged,
   and entry count and order are unchanged.
2. With no box requested, every page is byte-identically recoverable and the shipped suite passes unchanged.
3. An owner can choose WebP as the target and gets pixel-exact pages by default, with the report stating per
   page that they are not byte-recoverable.
4. An owner can produce an HTML audit of a run naming every entry, every downscale and every exemption.
5. A book in RAR, CB7 or 7Z converts to CBZ with entry order, entry count and entry bytes preserved.
6. Every external tool each capability needs is documented in `README.md` for linux, mac and windows, and
   named by the preflight before any archive opens.

## Boundaries

One capability boundary: the transcoding tool and its reporting surface. Not page authoring, not library or
collection management, not long-term archival preservation — see the spec's non-goals. Tracer path: one
book, run once with a box and a format choice, producing a CBZ plus an HTML audit.

- Touch point: `README.md` — install documentation per external tool, linux/mac/windows; owner:
  epic-bounded-downscaling, extended by each later epic for the tool it adds
- Touch point: `tests/` and `tests/fixtures/` — the shared harness, and fixtures whose bytes are load-bearing
  for roughly forty existing tests; owner: epic-bounded-downscaling, extended by each later epic for the
  fixtures and the oracle it needs
- Touch point: `AGENTS.md` — the `bmad:context` block, refreshed by `bmad-project-context` after the code
  lands, never hand-edited; owner: epic-bounded-downscaling
- Touch point: the spec folder and its two companions — amended per epic; owner: epic-bounded-downscaling
- Shared seam: `discover.py` — `OUTPUT_SUFFIX` names the output, `ARCHIVE_SUFFIXES` and `is_archive` decide
  what an input is; written by epic-bounded-downscaling and epic-webp-target on the suffix, and by
  epic-archive-containers on the suffixes; owner: epic-bounded-downscaling settles the suffix contract
- Shared seam: `report.py` — the per-page outcome statement, already decided in two places
  (`encode.is_lossless` and `report.py:152`) and to become the one place a third format reports through;
  written by epic-bounded-downscaling, epic-webp-target and epic-quality-audit; owner: epic-bounded-downscaling
- Shared seam: the classification gate at `archive.py:66-95` — the three-way decision that separates a raw
  page from an archive entry; rewritten by epic-bounded-downscaling and epic-archive-containers; owner:
  epic-bounded-downscaling
- Shared seam: `preflight.py` — one tool today, `TOOL = "cjxl"`; generalises to N as epic-bounded-downscaling
  adds `magick` and epic-archive-containers adds `7z`; owner: epic-bounded-downscaling

## References

- spec — _bmad-output/initiative-cbx-jackal/spec-cbz-jxl/spec-cbz-jxl.md, sections Capabilities,
  Constraints, Non-goals, Success signal, Assumptions
- companion — _bmad-output/initiative-cbx-jackal/spec-cbz-jxl/conventions.md
- companion — _bmad-output/initiative-cbx-jackal/spec-cbz-jxl/entry-transformations.md
- constraint — the same spec, section Constraints. No Python imaging libraries; `cjxl` never bundled;
  ZIP entries STORED; page order is the source's stored order; output atomic and never in place
- constraint — this initiative must not regress the shipped transcoder. CAP-1 through CAP-5 are realised in
  the tree at commit `da961cf` and evidenced by `plan-cbz-jxl.md` (`status: built`, its frozen I/O matrix
  implemented and its review findings trialled); they are not covered here because this initiative delivers
  queued capability, not the contract the transcoder already meets
- change — _bmad-output/initiative-cbx-jackal/change-bounded-page-downscaling/change-bounded-page-downscaling.md
- plan — _bmad-output/initiative-cbx-jackal/plan-cbz-jxl.md (shipped; the evidence for CAP-1 through CAP-5)
- plan — _bmad-output/initiative-cbx-jackal/plan-directory-discovery.md (shipped; directory and pattern input)

## Notes

- Decision: the four capabilities are treated as order-free; the owner ruled order irrelevant (2026-10-06).
  Their shared seams are resolved by contract entries in the opening epic rather than by sequencing features.
- Decision: WebP is an alternative target format, lossless by default with configurable quality, the same
  shape as jpg -> jxl. Details deferred to that epic's inception (maintainer, 2026-10-06).
- Decision: RAR, CB7 and 7Z are read with `7z`; output is always CBZ, so no proprietary archiver writer is
  ever required (maintainer, 2026-10-06).
- Decision: no platform-baseline epic. The baseline shipped with the transcoder — packaging, type config,
  commit hook, docs — and this is a CLI with no deploy target (2026-10-06).
- Decision: CAP-1 through CAP-5 are cited in References as a constraint this initiative must not regress,
  not in `covers`. They shipped under `plan-cbz-jxl.md` and no epic owns them (maintainer, 2026-10-06).
- Decision: epic-bounded-downscaling and epic-archive-containers are NOT merged. Both rewrite the
  classification gate at `archive.py:66-95`, so that gate becomes a shared seam owned by
  epic-bounded-downscaling and the container epic waits on it (maintainer, 2026-10-06). This is the ruling most
  likely to be re-opened, because merging is the tidier-looking answer.
- Source conflict: CAP-6 exists only in the approved change proposal, not in the spec; the proposal states
  of itself that it changes nothing. R1 resolves through the initiative, and epic-bounded-downscaling's
  `covers` cites R1, so the map resolves today. The spec text lands when that proposal is applied.
- Source conflict: the spec's non-goal "Output is JXL-only and will not display in most comic readers" is
  contradicted by R2, which exists to make output displayable. The spec's constraint "ZIP entries are
  STORED" and its whole container model are contradicted by R4. Both need a spec amendment before their
  epic is incepted; neither amendment is drafted here, and both are unowned work.
- Unknown: the R1 spread heuristic (1.35:1, on **display** aspect only) is reasoned, not measured, and is
  unvalidated against a real comic library. epic-bounded-downscaling owns the answer.
- This is a solo project. The maintainer is also the product owner, the developer, and the person who marks
  work done, so no `assignee` is set anywhere and every `hitl` entry waits on the maintainer alone. Where
  this file says "owner: epic-<slug>" it means the ticket that owns the work there, not a person.
- Parked: none.
- The two shipped build plans, `plan-cbz-jxl.md` and `plan-directory-discovery.md`, sit in this folder as
  pre-store history and are cited from References above. They carry `ticket: ''` because they predate the
  store, so `tickets.py status` lists them under `problems` as skipped. That is the tool reporting them
  correctly, not a broken tree: they are plans, not tickets. Moving them would break the cross-references
  from the change proposal and from epic-bounded-downscaling, which would cost more than the warning.
