---
type: epic
title: "Pages that fit the box stay untouched"
parent: initiative-cbx-jackal
covers: ["R1"]
assignee: ""
risk: medium
---

# Pages that fit the box stay untouched

## Description

An owner bounds their library's page dimensions with a flag pair, and pays nothing on the pages that
already fit. The box is measured in display orientation, a double-page spread is recognised and exempt from
the width rule but never split, and a downscaled page is reported as recoverable only from the intermediate.
Detailed as CAP-6 in the approved change proposal, sections 4.1 to 4.8, which this epic applies to the
spec as its first entry.

## Outcome

An owner can run one command over a library and know that every page fits their reader, that nothing was
enlarged or cut, and exactly which pages lost byte-recoverability; CAP-6's success criteria are the measure.

## Requirements

- **R1** — Bounded downscaling of oversized pages, with EXIF orientation honoured before any comparison and
  a recognised spread exempt from the width rule but never split. (parent initiative, Requirements; detailed
  as CAP-6 in the change proposal section 4.2.) Children of this epic cite `R1`; `CAP-6` is a cross-reference
  to spec text that does not exist until this epic's first entry applies the change proposal.

## Contracts this epic hands to the other three

This is the opening epic, so it owns every decision more than one epic must adopt. Each is its own entry in
this epic's breakdown, and each waiter names it in its `after`.

| Contract | Settles | Consumed by |
|---|---|---|
| Naming and flags | the destination name across formats and geometry, and where `--format`, `--max-width`, `--max-height` and `--quality` live and which apply where | epic-webp-target, epic-archive-containers |
| Outcome vocabulary | the per-page states including downscaled and spread-exempt, and the rule that `not converted` keeps exactly one meaning and reversibility is stated per page | epic-webp-target, epic-quality-audit |
| Preflight shape for N tools | `cjxl` always; each further tool conditional on the flags that need it; one message listing everything missing | epic-webp-target, epic-archive-containers |
| Classification gate | the interface at `archive.py:66-95` that separates a raw page from an archive entry, with a stub for a non-ZIP source | epic-archive-containers |

## Done when

1. Every acceptance criterion in the change proposal's section 4.8 passes with `cjxl`, `djxl`, `jxlinfo`
   and `magick` all on PATH.
2. With no box requested, the existing suite passes unchanged — a test edited to accommodate this epic is a
   finding, not a fix.
3. A page inside the box is still byte-identically recoverable from the output.
4. An oversized page tagged with a non-trivial EXIF orientation is fitted against its display width, so
   `--max-width` is never compared against a page's height.
5. A spread over the box keeps its full width, loses no entry, and is named in the report.
6. `magick` absent with a box requested exits non-zero before any archive opens, naming `magick`.
7. `README.md` documents installing both `cjxl` and `magick` for linux, mac and windows, and a reader on
   each platform can install both from it alone and know which a given run needs.
8. `pyright` reports no errors at the 3.9 floor the change proposal pins.
9. The spec carries CAP-1's per-page wording, CAP-6, the amended non-goals, the amended constraints, the
   amended success signal and the amended assumptions, as change proposal sections 4.1 to 4.5 draft them.

## Boundaries

The per-page geometry decision, the one extra external tool it needs, and the four contracts listed above
that the other three epics wait on. Not the output format (epic-webp-target), not the input container
(epic-archive-containers), not the HTML reporting surface (epic-quality-audit).

## References

- parent — _bmad-output/initiative-cbx-jackal/initiative-cbx-jackal.md, section Requirements
- change — _bmad-output/initiative-cbx-jackal/change-bounded-page-downscaling/change-bounded-page-downscaling.md,
  sections 4.1 to 4.8 for the spec edits this epic applies, and section 5 for its slice table and success
  criteria including the `pyright` check
- companion — _bmad-output/initiative-cbx-jackal/spec-cbz-jxl/conventions.md, sections Invocation,
  Lossless transcoding and reversibility, Preflight (the Resizing section this epic adds)
- companion — _bmad-output/initiative-cbx-jackal/spec-cbz-jxl/entry-transformations.md (the table rows and
  reporting classes this epic adds to)
- constraint — _bmad-output/initiative-cbx-jackal/spec-cbz-jxl/spec-cbz-jxl.md, section Constraints: no
  Python imaging libraries, `cjxl` never bundled, exit non-zero if and only if a JPEG entry failed
- constraint — `AGENTS.md`, the `bmad:context` block, refreshed by `bmad-project-context` after this lands

## Notes

- Unknown: whether the 1.35:1 spread threshold, tested on display aspect only, holds against a real comic
  library. It is reasoned, not measured. A genuine spread of ~1.4:1 pages measures about 1.43:1, and a page
  scanned sideways with no orientation tag is indistinguishable from one.
- Touch point: `discover.py`, via `OUTPUT_SUFFIX` at `discover.py:55`, which this epic's naming contract and
  epic-webp-target both depend on.
- Touch point: `tests/fixtures/make_fixtures.py`. EXIF-orientation fixtures cannot be written by the
  ImageMagick build in use — `-set exif:Orientation` produces no APP1 segment — so they must be injected
  byte-wise. This is a finding the implementation must not rediscover.
- Decision: this is the opening epic, so the extension-surface contracts the other three epics must adopt
  live here rather than in an architecture spine (2026-10-06).
- Decision: Done-when 7 was amended on close-out. It previously also required "the released version
  installs and runs from a clean environment on all three platforms". This repository has no CI
  configuration and no release process, so that clause was not checkable here and no entry could own it;
  the first half, which is, is what the check now says (2026-10-06).
- **Tracer bullet: entry 1, and it is a spike rather than a story.** The risk this epic carries is
  technical feasibility, not integration, and that risk was already measured once during the change
  proposal — `magick` hands a downscaled page to `cjxl` and `djxl` recovers the intermediate. Entry 1
  re-proves it on the real fixture path and, more usefully, settles that the EXIF injector works, which
  every later fixture depends on and which the ImageMagick build cannot do for itself. The layers' own
  connection is proven by entry 1's direct `Converter` call; the first end-to-end user-visible run is
  entry 11. A thinner story that crossed every layer would have had to implement the naming, vocabulary,
  preflight and gate contracts first, which is the whole of entries 3 to 6.
- **Contracts handed over:** entries 3, 4, 5 and 6. Their ids are stable and are what epic-webp-target,
  epic-quality-audit and epic-archive-containers name as providers at their inception — `1.3` naming and
  flags, `1.4` the outcome vocabulary, `1.5` the preflight shape, `1.6` the classification gate.
- **Contract `1.3`, the naming and flags ruling (2026-10-08).** Settled by the maintainer and recorded here
  rather than in the spec, as that entry directs. Two rules and one table.

  **The destination is `<stem>.<format>.cbz`.** `<stem>` is the input's basename with its own suffix
  removed and nothing else changed. `<format>` is whatever `--format` names, `jxl` by default. `.cbz` is
  constant: it is the output container whatever the input container was, so a RAR, CB7 or 7Z input is
  indistinguishable from a CBZ one once converted. **The box never appears in the name.**
  `--max-width` and `--max-height` are a knob on the result, not part of its identity, and that is what
  keeps the rescan-skip rule exact rather than width-dependent.

  | input | flags | output |
  |---|---|---|
  | `book.cbz` | none | `book.jxl.cbz` |
  | `book.zip` | none | `book.jxl.cbz` |
  | `book.rar` | none | `book.jxl.cbz` |
  | `book.cb7` | none | `book.jxl.cbz` |
  | `book.cbz` | `--max-width 1600` | `book.jxl.cbz` |
  | `book.cbz` | `--max-width 1600 --max-height 2000` | `book.jxl.cbz` |
  | `book.cbz` | `--format webp` | `book.webp.cbz` |
  | `book.cbz` | `--format webp --quality 90 --max-width 1600` | `book.webp.cbz` |

  **The flag namespace.** `--format` names the target page format, `jxl` by default. `--max-width` and
  `--max-height` are combinable and/or, never mutually exclusive: given both, the page must fit both
  axes, and a page is not enlarged either way. `--quality` keeps one meaning across every format —
  absent is lossless, present is lossy at that quality, range 1-100 throughout — and applies to the
  target format's encode and never to a resize intermediate, so `--quality 90 --max-width 1600` has
  exactly one answer. All three are per run and apply to every path in it; none varies by path. Whether
  the intermediate is lossless or JPEG is entry 9's open decision and changes none of this surface.

  **Known cost: two inputs, one name.** `book.cbz` and `book.rar` in one scan both want `book.jxl.cbz`.
  Pre-existing — `book.cbz` and `book.zip` already collide today — but R4 makes it routine rather than
  incidental. Accepted: the second path refuses on the existing output-exists error and `--force` decides.
  Neither a suffix segment nor an outright refusal is the tool's business to invent, and a name that
  varied with the input container would contradict the constant `.cbz` above.

  **Owed downstream.** `is_archive` must skip every `<stem>.<format>.cbz` and not one constant, so the
  rescan rule survives `--format webp`; that needs the format segment in its own constant beside today's.
  `spec-cbz-jxl.md:64`, `conventions.md:89` and `README.md` each state the name as a literal
  `<name>.jxl.cbz` and each is amended by the epic that changes it.

  **Ownership gap this ruling opens: nothing yet owns the `--format` flag.** Entry 6 implements the naming
  rule and so must read a format from somewhere, but entry 6 is a contract entry with no CLI work in it and
  entry 11 adds only the two box flags. The flag needs a home before entry 6 starts, and the honest one is
  entry 11 or a new entry alongside it: `--format` accepted, `jxl` the only legal value, `webp` arriving
  with epic-webp-target. Left unowned it would be settled twice, once by the rule and once by the CLI.
- **Shared setup:** the EXIF injector is on entry 1, the first entry that needs it, and entry 2 extends it.
- **Open decision, deferred to entry 9: the intermediate's format and quality.** Measured 2026-10-06 on a
  1700x2400 synthetic comic page — hard line art, flat colour, text — decoding the source with one decoder
  and comparing the final `.jxl` against it. Not a decision taken; the evidence for whoever settles it.

  | intermediate | pixels wrong | final `.jxl` | s/page | 200-page book |
  |---|---|---|---|---|
  | JPEG q92 (the change proposal's draft value) | 364,021 — 8.9% | 26,837 | 0.047 | 9s |
  | JPEG q100 | 145,218 — 3.6% | 41,286 | 0.047 | 10s |
  | PNG + `cjxl -q 100` | **0** | **27,784** | 0.29 | 58s |

  PPM and PAM measured identically to PNG on fidelity and output size; PNG is the pick on intermediate
  disk size (79 KB against 12 MB, transient either way). The 6× cost is modular lossless encoding, not
  input parsing. JPEG q100 is dominated: it pays 54% more archive size than q92 *and* still discards
  3.6% of the page, while the PNG route is lossless and 33% smaller than it.

  **Three consequences a lossless intermediate would force**, all of which are decisions, not parameters:
  1. `cjxl` defaults to *lossy* on PNG input — measured 198,397 wrong pixels, 4.9%, with no flags. So
     `-q 100` becomes mandatory on this path, which breaks the convention `encode.py`'s docstring exists to
     explain ("the lossless path passes no flags at all") and needs a second branch in `build_command`.
  2. `djxl` returns a PNG, not a JPEG, and `jxlinfo` reports no JPEG reconstruction data. The guarantee
     becomes *stronger but different*: pixels exactly preserved, the original JPEG file not.
  3. It settles the run-level interaction for free — with a lossless intermediate, `--quality` applies to
     the JXL encode only and never to the intermediate, so `--quality 90 --max-width 1600` has one answer.

  The cost is real: a downscaled 200-page book goes from about 9s to about 58s, roughly doubling the
  figure `conventions.md` currently states, though only for pages actually downscaled.
- **Entry count: 15,** at the top of the range and above the typical eight to twelve, because this is one
  lane with one owner and five entries are decisions rather than code. Offered for a split if wanted; a
  split is defensible along the decision/code seam that entries 3 to 7 already form.
- **Clause map.** Every entry covers R1, which the change proposal details as CAP-6 in three parts. Entry 3
  and 6 carry the box contract; 8 the orientation and spread rules; 9 the invocation; 10 the per-page
  reporting; 11 the user-facing surface; 7 writes all of it into the spec; 15 verifies it end to end.
