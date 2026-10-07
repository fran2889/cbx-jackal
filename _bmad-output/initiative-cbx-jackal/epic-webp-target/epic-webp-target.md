---
type: epic
title: "WebP as a target the owner's reader can actually open"
parent: initiative-cbx-jackal
covers: ["R2"]
after: ["epic-bounded-downscaling"]
assignee: ""
risk: medium
---

# WebP as a target the owner's reader can actually open

## Description

An owner whose reader cannot display JXL produces WebP pages instead. Lossless by default, configurable
quality, the same shape as jpg -> jxl. This inverts a decision the spec made knowingly — that output is
JXL-only and will not display in most comic readers — which is why it needs a spec amendment before it is
incepted, not because it is doubtful.

## Outcome

An owner can point the tool at a reader that will not open JXL and get pages that open; zero differing
pixels against the source JPEG's decoded pixels at the default, with the report stating per page that
WebP pages are not byte-recoverable.

## Requirements

- **R2** — WebP as an alternative target format: lossless by default, configurable quality, the same shape
  as jpg -> jxl. (parent initiative, Requirements; origin: owner, 2026-10-06)

## Done when

1. A book converts to WebP pages with zero differing pixels against the source JPEG's decoded pixels, using
   a pixel oracle that does not route both sides through libjxl — the existing helper deliberately does, so
   comparing through it would report differences that come from the decoders rather than from the encode.
2. `--quality N` below 100 produces lossy WebP smaller than the lossless output, and the run states the mode
   per page, as it already does for JXL.
3. Entry order, entry count and every non-converted entry are byte-identical, unchanged from today.
4. The report names every WebP page as not byte-recoverable, and the mechanism that states it is the one the
   per-page outcome vocabulary defines rather than a third decision site.
5. ZIP input behaviour and JXL output behaviour are unchanged, byte for byte.
6. `README.md` documents the WebP encoder for linux, mac and windows, and names it in the preflight when a
   WebP target is requested.
7. The released version installs and runs from a clean environment on all three platforms.

## Boundaries

The target page format and its encoder. Not geometry (epic-bounded-downscaling), not the input container
(epic-archive-containers), not the HTML reporting surface (epic-quality-audit).

## References

- parent — _bmad-output/initiative-cbx-jackal/initiative-cbx-jackal.md, section Requirements
- companion — _bmad-output/initiative-cbx-jackal/spec-cbz-jxl/spec-cbz-jxl.md, section Non-goals,
  "Reader compatibility" — contradicted by this epic and the section this epic's spec amendment rewrites
- companion — _bmad-output/initiative-cbx-jackal/change-bounded-page-downscaling/change-bounded-page-downscaling.md,
  section 4.1, as the model for how per-page reversibility is stated in the report
- constraint — `AGENTS.md`, the `bmad:context` block: losslessness is already decided in two places
  (`encode.is_lossless` and `report.py:152`); this epic must not add a fourth site
- touch point — `discover.py`, via `OUTPUT_SUFFIX` at `discover.py:55`, which carries the output suffix this
  epic parameterises

## Notes

- Open question: the destination name when WebP is the target, and when WebP is combined with a box. Waits
  on epic-bounded-downscaling's naming-and-flags contract.
- Open question: which of lossless or `--quality` governs a page that is both downscaled and re-encoded.
- Unknown: the WebP encoder to require. `cwebp` is absent here and ImageMagick 7.1.2 carries libwebp 1.5.0
  and reads and writes WebP. Measured: `-define webp:lossless=true` gave zero differing pixels against the
  source JPEG; `-quality 82` gave 187. Those byte counts came from a flat-colour image and say nothing
  about size on a real comic page.
- Concurrent edit: this epic and epic-archive-containers both write `discover.py` with no dependency between
  them. The edits are disjoint — this epic touches `OUTPUT_SUFFIX` at line 55, the container epic touches
  `ARCHIVE_SUFFIXES` at line 49 and `is_archive` at lines 73-82 — so they may run at the same time. Both
  are one-line-scale changes to a module of about thirty lines; if that stops being true at implementation
  time, one waits on the other rather than both proceeding.
- Decision: lossless by default with configurable quality, the same shape as jpg -> jxl. Details deferred to
  this epic's inception (maintainer, 2026-10-06).
