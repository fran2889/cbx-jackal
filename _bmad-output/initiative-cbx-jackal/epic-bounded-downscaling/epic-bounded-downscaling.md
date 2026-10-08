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
- **Contract `1.4`, the per-page outcome vocabulary (2026-10-08).** Settled by the maintainer and recorded
  here rather than in the spec, as that entry directs.

  **Downscaled and spread-exempt are not classes.** The three classes stay three, because they are an
  exit-code contract and `not converted` is the only one that drives a non-zero exit. A downscaled page is
  still `converted`; what changed is its reversibility. A spread-exempt page is also still `converted`, still
  source-recoverable, and differs in nothing but that it is named — so it is a report line, not a state.

  **One page's reversibility takes one of four values**, named for what the owner gets back rather than for
  how it happened:

  | value | meaning |
  |---|---|
  | `source` | `djxl` reproduces the source JPEG byte-for-byte |
  | `pixels` | exact pixels survive, the source JPEG file does not |
  | `intermediate` | `djxl` returns a stand-in that is itself lossy against the source |
  | `none` | lossy; nothing recovers the page |

  Four rather than three because the lossless-intermediate case is a genuinely stronger guarantee than the
  JPEG-intermediate one, and one pair of words cannot honestly carry both. Which values are *reachable*
  depends on entry 9's undecided intermediate — a lossless intermediate makes `pixels` the value for every
  downscaled page and `intermediate` unreachable, a JPEG one does the reverse — so the vocabulary is fixed
  at this shape deliberately: whichever way entry 9 rules, no wording changes.

  **Exact per-page wording**, one line each, dimensions being the display box on both sides because that is
  what the box rule compared and what the output contains:

  ```
  page003.jpg: downscaled 2480x3508 -> 1600x2260, pixels recoverable, source JPEG not
  page003.jpg: downscaled 2480x3508 -> 1600x2260, recoverable as the intermediate only
  page007.jpg: spread kept at 2480x1500, exempt from the width rule
  ```

  **Exact run-level mode line**, three cases. The first two are byte-identical to today, because a run that
  downscaled nothing must be byte-for-byte the run it is:

  ```
  mode: lossless (JPEG bytes recoverable with djxl)
  mode: lossy, quality 90 (JPEG bytes NOT recoverable)
  mode: lossless, 3 of 15 pages downscaled (pixels recoverable, source JPEG not)
  mode: lossless, 3 of 15 pages downscaled (recoverable as the intermediate only)
  ```

  The breakdown appears only when the mode is lossless and at least one page was downscaled. In a lossy run
  every page is `none`, so the existing parenthetical already says it and a breakdown would be arithmetic.
  Counts are over converted pages, so they reconcile with the summary line beneath. The clause carries the
  *value name*, not a count per value, because within a run every downscaled page shares one value and the
  arithmetic would be redundant — what the owner needs is which of the two weaker guarantees they have.

  **Reversibility is claimed in exactly one place, and it is not `is_lossless`.** `encode.is_lossless` keeps
  answering only "what argv do I build", which is a legitimate separate question: a run with a box and no
  `--quality` is lossless in argv and not byte-recoverable at the same time. The report is the only layer
  that sees both the flags and every outcome, so it alone states what can be recovered, and it derives that
  from the outcomes plus the box — never from a defaulted argument. `render()`'s `quality=None` default must
  never reach a losslessness claim, which is the way today's two decision sites came to disagree.
- **Contract `1.5`, the preflight shape for N external tools (2026-10-08).** Settled by the maintainer and
  recorded here rather than in the spec, as that entry directs.

  **Tools carry one of two severities, and the difference is what the run would lose without them.**
  `cjxl` is unconditional — every book needs it. `magick` is flag-driven: required only when a box is
  requested, and known before any file is touched. `7z` is input-driven: required only when an expanded
  input is a recognised non-ZIP container, and known only after expansion.

  | severity | tool | when it is needed | when it is checked | missing means |
  |---|---|---|---|---|
  | unconditional | `cjxl` | always | before path expansion | exit 2, nothing runs |
  | flag-driven | `magick` | only when `--max-width` or `--max-height` is given | before path expansion | exit 2, nothing runs |
  | input-driven | `7z` | only when an expanded input is a recognised non-ZIP container | after path expansion | exit 2 overall, only the inputs needing it are refused |

  **The input-driven case carries on rather than aborting.** A missing `7z` must not stop the ZIPs in the
  same run: every other path is still work the owner asked for, and the tool already refuses one path and
  continues rather than abandoning the list. CAP-5's "before any archive opens" is a real protection for
  the two severities that abort — a tool every run needs, discovered partway through a 200-page run — and
  a much weaker one for a tool only some inputs need, because a RAR is not more of the same work, it is
  different work. This amends `epic-archive-containers`' Done-when 3, which had promised an abort.

  **One message, whatever the count, and severity stated per tool.** The header names every missing tool;
  each block then carries its own install guidance and says whether it stops the run or only skips the
  inputs that need it. Blocks run in severity order — unconditional, then flag-driven, then input-driven —
  so the tool that cannot be worked around is named first. A run missing both `magick` and `7z` therefore
  names both in one message, before the owner fixes either and re-runs to learn of the other.

  **An input-driven tool is decided by the recognised input suffix, never by sniffing.** By-content
  detection stays `7z`'s own job at open time, which is where the measurement put it. Sniffing in the
  preflight would mean reading the file before knowing the tools are present, which is the situation CAP-5
  exists to prevent. A file whose suffix says ZIP and whose bytes are not is an unreadable archive, exit
  1 — the same answer it gives today.

  **A dry run needs exactly the tools the real run would.** It encodes every page so the report can state
  real size figures rather than estimates, so it is a real run that discards its output; `magick` is
  required with a box and `7z` with a RAR under `--dry-run` exactly as without it.

  **Exit 2 for any missing tool**, whether the run then aborts or carries on, alongside a refused path for
  the same reason.

  **The preflight covers the tools the converter runs, not the tools the suite runs.** `djxl` and
  `jxlinfo` verify output; the converter never shells out to them, so neither is ever preflighted.
- **Shared setup:** the EXIF injector is on entry 1, the first entry that needs it, and entry 2 extends it.
- **Decision: the intermediate is a PNG, and the downscale path encodes it at `cjxl -q 100` (2026-10-08).**
  Settled by the maintainer, closing the open question this epic had deferred to entry 9. Evidence below,
  re-measured independently on 2026-10-08 against libjxl 0.11.1 and ImageMagick 7.1.2-18.

  | intermediate | pixels wrong | final `.jxl` | s/page | 200-page book |
  |---|---|---|---|---|
  | JPEG q92 | 364,021 — 8.9% | 26,837 | 0.047 | 9s |
  | JPEG q100 | 145,218 — 3.6% | 41,286 | 0.047 | 10s |
  | **PNG + `cjxl -q 100`** | **0** | 27,784 | 0.29 | 58s |

  Measured 2026-10-06 on a 1700x2400 synthetic comic page — hard line art, flat colour, text — comparing the
  final `.jxl` against the intermediate's own pixels. PPM and PAM measured identically to PNG on fidelity and
  output size; PNG wins on intermediate disk size (79 KB against 12 MB, transient either way). JPEG q100 is
  dominated: 54% more archive size than q92 *and* it still discards 3.6% of the page.

  **Why PNG rather than the cheaper routes.** An owner who asks for a box has already surrendered
  byte-recoverability for that page; they have not agreed to a second lossy generation on top of the resize.
  JPEG q92 silently corrupts 8.9% of a downscaled page's pixels, on hard line art, in the one route where the
  owner cannot check afterwards because the intermediate is discarded either way. PNG costs 3.5% archive size
  against q92 and is 33% *smaller* than q100. The price is 6.2× the time.

  **Re-verified, and the `-q 100` mandate is stronger than first recorded.** `cjxl` with no flags on a PNG
  intermediate lost **195,790 pixels (19.2%)** on a saturated synthetic page, against the 4.9% this epic had
  recorded on lighter content. `-q 100` lost zero. So the mandate holds and the default is worse than
  believed; `build_command` needs its second branch, and the "the lossless path passes no flags at all"
  convention holds only for JPEG input.

  **`magick`'s own `-quality` is not a decision on this path.** Measured fidelity-neutral at every value
  tested, `-quality 30` included: it changed the intermediate's byte size and never its pixels. `-quality 100`
  is the confirmed value because it is the least room for doubt and costs nothing — 90 and 100 produced
  identical bytes.

  **`cjxl` effort stays at the default on this path.** Measured on PNG input, effort is *not* free as it is
  on JPEG input, where lossless transcoding is a bitstream copy:

  | `cjxl -e N` on a PNG intermediate | `.jxl` bytes | ms | wrong pixels |
  |---|---|---|---|
  | 3 | 1,999 | 230 | 0 |
  | 5 | 1,298 | 689 | 0 |
  | 7 (default) | 1,298 | 961 | 0 |
  | 9 | 1,343 | 2,375 | 0 |

  Effort 7 costs about 4× effort 3 for byte-identical output to effort 5. The default is kept — no new flag,
  and a single easy synthetic page is no basis for tuning against real comic art. `conventions.md`'s
  "effort 7 is free relative to effort 3" is narrowed to the JPEG route, where it was measured.

  **What this settles downstream.** In entry 4's vocabulary every downscaled page is `pixels` and
  `intermediate` is unreachable, so that value stands in the contract with no live instance — deliberately,
  so that a later switch of intermediate needs no wording change. `--quality` applies to the `.jxl` encode
  only and never to the intermediate, so `--quality 90 --max-width 1600` has one answer: a lossy run, every
  page `none`.
- **Source conflict: the change proposal's CAP-1 amendment, its conventions reversal, and its `jxlinfo`
  reversal all assume the JPEG intermediate.** All three claim a downscaled page *keeps* reconstruction data
  and that `djxl` reproduces *the intermediate* byte-for-byte — the proposal's section 4.1 success text, the
  reversal appended to `conventions.md` after `:26`, and the reversal appended to the `jxlinfo` paragraph at
  `:405`, plus the section 4.8 table row "source recoverable only as the intermediate". With a PNG
  intermediate there is no reconstruction data at all: `djxl` returns a PNG and `jxlinfo` reports none. The
  proposal flagged this choice as "open, not settled here" at `:384` and then assumed the JPEG answer
  anyway. The proposals' *caution* survives unchanged — a downscaled book must not be allowed to look like a
  CAP-1 book, and reconstruction data never proved which generation was present — but its stated mechanism
  is now wrong, and under PNG the absence of reconstruction data is a cleaner signal rather than a weaker
  one. Entry 1.7 carries the correction into the spec; the approved text is not edited here.

- **Entry count: 15,** at the top of the range and above the typical eight to twelve, because this is one
  lane with one owner and five entries are decisions rather than code. Offered for a split if wanted; a
  split is defensible along the decision/code seam that entries 3 to 7 already form.
- **Clause map.** Every entry covers R1, which the change proposal details as CAP-6 in three parts. Entry 3
  and 6 carry the box contract; 8 the orientation and spread rules; 9 the invocation; 10 the per-page
  reporting; 11 the user-facing surface; 7 writes all of it into the spec; 15 verifies it end to end.
