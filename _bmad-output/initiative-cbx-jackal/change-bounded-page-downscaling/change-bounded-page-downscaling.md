---
id: CHANGE-bounded-page-downscaling
type: change
title: Bounded page downscaling
initiative: cbx-jackal
created: 2026-10-06
status: approved
scope: moderate
approved: 2026-10-06
routed_to:
  - bmad-spec
  - human (frozen block in plan-cbz-jxl.md)
  - bmad-build
reads:
  - ../spec-cbz-jxl/spec-cbz-jxl.md
  - ../spec-cbz-jxl/conventions.md
  - ../spec-cbz-jxl/entry-transformations.md
  - ../plan-cbz-jxl.md
  - ../plan-directory-discovery.md
  - '{project-root}/AGENTS.md'
---

> **This document changes nothing on its own.** It proposes edits; you apply them through the owning skills
> (`bmad-spec` for the spec and its companions, and a human decision for the frozen block in
> `plan-cbz-jxl.md`). Implementation follows through `bmad-build`.

# Sprint Change Proposal — bounded page downscaling

## 1. Issue Summary

**Problem.** `cbx-jackal` transcodes JPEG pages losslessly and byte-reversibly, and is forbidden by its own
contract from touching a single pixel. Owners whose pages are larger than their screen or their reader can
handle have no way to bound them with this tool. The owner of cbx-jackal has asked for `--max-width` and
`--max-height`, with three specific refinements: downsize only, EXIF orientation honoured when deciding
which limit applies to which axis, and double-page spreads recognised but never split.

**How it surfaced.** Requested directly by the owner against a built spec, after the transcoder shipped
(`plan-cbz-jxl.md`, `status: built`).

**Category.** A new requirement from the owner — gated by a technical limitation discovered while assessing
it. `cjxl` 0.11.1 cannot resize.

**Evidence.** All measured on libjxl 0.11.1 and ImageMagick 7 in the development sandbox.

| # | Finding | How it was established |
|---|---|---|
| E1 | `cjxl` 0.11.1 has **no resize option in any form** | Full expert option list, `cjxl -v -v -v -v --help` |
| E2 | Coded dimensions readable with **stdlib only, no pixel decode** | `SOF0` frame header parsed from raw bytes: `(600, 300)` |
| E3 | EXIF orientation readable with **stdlib only, no pixel decode** | APP1 → TIFF IFD0 tag `0x0112`, both endians: `value 6`. `jxlinfo` confirms `cjxl` carries it (`Orientation: 6 (90 degrees clockwise)`) and `djxl` restores it byte-identically |
| E4 | `magick -auto-orient -resize '800x1000>'` implements the requested semantics | `800x1200 → 667x1000` |
| E5 | After a downscale, `djxl` recovers the **intermediate**, not the source — *and `jxlinfo` still reports `reconstruction data available`* | SHA-256 of the reconstruction matched the intermediate, differed from the source |
| E6 | Recognising a spread without splitting it keeps the entry count unchanged | Classification ran clean on a 1200x600 fixture |

Live classification against a box of 800x1000, using only header bytes. **The spread rule was
re-measured after the tree check found that it contradicted CAP-6** — the first pass implemented a
display-only test while the approved text said "coded or display". The ruling is display-only at 1.35:1:

```
fixture      coded       o   display    ratio  spread
spread.jpg   1200x600    1   1200x600   2.00   True    a true 2:1 spread
p.jpg        1700x2400   1   1700x2400  1.41   False   a single page, portrait
rot.jpg      2400x1700   1   2400x1700  1.41   True    a single page scanned sideways, NO tag -> exempt
rot6.jpg     2400x1700   6   1700x2400  1.41   False   the same page, tagged -> width applies
o6.jpg       600x300     6   300x600    2.00   False   orientation reaches the width rule
small.jpg    400x600     1   400x600    1.50   False   already fits

`rot6.jpg` is the case that proves the orientation rule: the same page untagged is exempt, tagged is not.
`rot.jpg` is the accepted false positive — untagged and sideways, it is indistinguishable from a spread.
```

Cost: `magick` resize ≈ **0.24 s** per A4/300dpi page, against ≈ **0.26 s** for `cjxl` on the result. A
downscaled page costs roughly twice a transcoded one; pages inside the box are unaffected. The `>` suffix
is confirmed downsize-only — `2400x3200>` against a 400x600 page leaves it 400x600.

## 2. Impact Analysis

### Contract conflicts

| Artifact | Location | Conflict |
|---|---|---|
| Spec | CAP-1 success | "`djxl` reproduces the source JPEG byte-for-byte" fails for every downscaled page (E5) |
| Spec | Non-goals `:84` | "no resize" — the feature is explicitly excluded |
| Spec | Non-goals `:78` | "Pixel dimensions survive conversion" becomes false |
| Spec | Constraint `:59` | "`cjxl` is the single external tool" — impossible (E1) |
| Spec | Success signal | Silent about oversized pages |
| Spec | Assumptions | Silent on ImageMagick and on the heuristic's validation state |
| Companions | `entry-transformations.md` | No row for a box; the three reporting classes cannot express "downscaled" |
| Companions | `conventions.md` | `jxlinfo` documented as "the cheap way to assert reversibility" — a false positive under CAP-6 |
| Plan | `plan-cbz-jxl.md` **frozen block** | "no Python imaging libraries; `cjxl` is the only external tool" and "parse pixels in Python" |

### What survives untouched

- **The stdlib-only constraint.** ImageMagick is an external process, not a Python library. Pillow stays
  forbidden. E2 and E3 confirm the orientation and dimension work is header parsing, not decoding.
- **CAP-3.** No splitting means no renumbering and no entry count change, so `ComicInfo.xml`'s
  `<Pages Count>` stays correct without being rewritten.
- **CAP-4.** A failed downscale is classified as a failed conversion: original name, original position,
  own report line, non-zero exit, archive still complete.
- **The exit-code contract.** No new exit code, no new reporting class. Downscaling is a flag on
  `converted`, so `not converted` keeps exactly one meaning.
- **Non-goals on reader compatibility and long-term archival preservation.** A downscaled page is less
  archival than a lossless one, which was already the honest position.

### Absent

No PRD, no architecture document, no UX document, no epic file, **no ticket tree**. Analysis rests on the
spec, its companions, the two plans, and `AGENTS.md`.

### Sequencing risk — resolved

`plan-directory-discovery.md` was flagged as `status: in-progress` while owning `cli.py`. Re-verified on
2026-10-06: it is complete, shipped as `24844b8`, and now reads `built`. Its claims were checked against
the tree — 214 tests, OK, zero skips; `pyright` clean; all four verification probes behaving as specified,
with every external tool confirmed on PATH. **No collision remains, and slice 4 may proceed.**

## 3. Recommended Approach

**Option 1 — Direct Adjustment.** Effort **Medium**, risk **Medium**.

The transcoder is not wrong and nothing in it needs reverting. CAP-6 is additive: a new geometry module
that decides *whether* and *to what*, one more external tool consulted conditionally, one more flag on an
existing class. Every existing behaviour survives verbatim when no box is requested, which is the
zero-regression property that makes this cheap.

Rejected:

- **Option 2, Rollback.** Reverting costs the entire transcoder to solve nothing; no existing code is
  wrong because resize is wanted.
- **Option 3, MVP reduction.** The owner chose full scope. The report-only `--check-size WxH` variant
  remains available later as a cheap complement — it would answer how many books actually need this,
  and costs neither a second tool nor a spec change.

**Risks accepted, and why.**

| Risk | Why accepted |
|---|---|
| A 1.35:1 spread test misreads landscape splash art as a spread, leaving it over the width limit | One splash page slightly too wide beats crushing every spread in the book. Every exempt page is named in the report |
| A page scanned sideways with **no** orientation tag reads as a spread and escapes the width limit | Genuinely indistinguishable from a spread by dimensions alone. Naming it in the report is the honest answer; guessing would be worse |
| The heuristic is unvalidated against a real library | Stated in the spec's Assumptions. The first real book is its test |
| `magick` becomes a second thing owners must install | It is checked only when a box is requested, and both tools are reported in one message |

## 4. Detailed Change Proposals

All eight were approved individually. Rationale for each is recorded in the conversation; the edits follow.

### 4.1 Spec — CAP-1 becomes conditional

**File:** `spec-cbz-jxl/spec-cbz-jxl.md` § Capabilities

OLD:
```
- **CAP-1 — Lossless page conversion by default**
  - **intent:** An owner can convert a comic archive's JPEG pages to JXL without any quality loss, without
    asking for lossless and without supplying a flag.
  - **success:** For every converted page, decoding the output `.jxl` yields pixels identical to decoding
    the source `.jpg` (zero differing pixels), and `djxl` reproduces the source JPEG byte-for-byte.
```

NEW:
```
- **CAP-1 — Lossless page conversion by default**
  - **intent:** An owner can convert a comic archive's JPEG pages to JXL without any quality loss, without
    asking for lossless and without supplying a flag.
  - **success:** For every converted page that was **not** downscaled, decoding the output `.jxl` yields
    pixels identical to decoding the source `.jpg` (zero differing pixels), and `djxl` reproduces the source
    JPEG byte-for-byte. A downscaled page keeps reconstruction data, and `djxl` reproduces **the downscaled
    intermediate** byte-for-byte — never the source. The report states which of the two happened per page;
    an owner is never told "recoverable" without being told recoverable *from what*.
```

### 4.2 Spec — the new capability

**File:** `spec-cbz-jxl/spec-cbz-jxl.md` § Capabilities, after CAP-5

NEW:
```
- **CAP-6 — Bounded downscaling of oversized pages**
  - **intent:** An owner with books whose pages are larger than their screen or reader can handle
    shrinks them to a box, without paying for it on pages that already fit and without the tool
    guessing wrong about spreads.
  - **success:** Given `--max-width W` and/or `--max-height H`, a JPEG page whose **display** box
    already fits is transcoded exactly as it is today — losslessly, with its source JPEG byte-for-byte
    recoverable. A page that does not fit is downscaled to the largest box that fits, and its report
    line says so. A page is never enlarged, never cropped, never rotated on disk, and never split
    into two entries; the entry count is unchanged, so `<Pages Count>` stays correct untouched.

  **The box is measured in display orientation.** EXIF orientation is read from the JPEG's APP1
  segment and applied before any comparison, so `--max-width` is never compared against a page's
  height: a 600×300 page tagged orientation 6 displays as 300×600, and a `--max-width 800` is judged
  against 300.

  **A recognised spread is exempt from the width rule only.** A page is treated as a double-page
  spread when its **display** aspect ratio reaches 1.35:1. For a recognised spread, `--max-width` is not
  applied — the spread is left at its natural double width rather than crushed to a single page's width —
  while `--max-height` still applies as usual. Spreads are **recognised, never split**: one entry stays
  one entry, so page order and page count are untouched.

  The test is on **display** orientation, never on the coded grid. That is deliberate: a page stored
  sideways with an orientation tag displays portrait and is correctly *not* exempt, so the width rule
  reaches it and is judged against its display width. The alternative — testing the coded aspect too —
  made every such page exempt, which defeated the orientation rule it was meant to sit beside, and the
  tree check caught the two clauses contradicting each other on the same fixture.

  **The exemption is heuristic and says so.** 1.35:1 is set because a genuine two-page spread of
  ~1.4:1 pages measures about 1.43:1, so a higher bar misses most real spreads and crushes them. The cost
  runs the other way: full-page landscape art at 1.35:1 or beyond reads as a spread and escapes the width
  limit, and so does a page scanned sideways that carries no orientation tag at all — which is genuinely
  indistinguishable from a spread by dimensions alone. Every exempt page is named in the report, so the
  owner sees exactly which pages the exemption covered and can judge the rule against their own library.
```

### 4.3 Spec — non-goals

**File:** `spec-cbz-jxl/spec-cbz-jxl.md` § Non-goals

OLD `:78`:
```
- **DPI preservation.** Pixel dimensions survive conversion; physical density does not, and is knowingly
  dropped rather than reconstructed.
```
NEW:
```
- **DPI preservation.** Physical density is dropped rather than reconstructed, and under CAP-6 an
  oversized page's pixel dimensions are changed too. Both are knowing trades: a downscaled page cannot
  keep its source pixel grid, because not keeping it is the whole point of asking for it.
```

OLD `:84`:
```
- Any image manipulation: no resize, rotate, upscale, re-encoding of non-JPEG pages, or ComicInfo.xml
  rewriting. The entry count never changes, so `<Pages Count>` stays correct untouched.
```
NEW:
```
- Image manipulation beyond CAP-6's bounded downscale: no rotate, no crop, no colour change, no
  re-encoding of non-JPEG pages, no ComicInfo.xml rewriting. A spread is recognised, never split, so
  the entry count never changes and `<Pages Count>` stays correct untouched.
```

### 4.4 Spec — constraints

**File:** `spec-cbz-jxl/spec-cbz-jxl.md` § Constraints

OLD `:58`:
```
- No Python imaging libraries. Container handling is Python standard library only.
```
NEW:
```
- No Python imaging libraries. Container handling is Python standard library only. CAP-6 does not weaken
  this. Reading a page's coded dimensions and its EXIF orientation is marker parsing over bytes already
  in hand — a `SOF0` frame header and an APP1 TIFF tag — with no pixel decoded. The resampling itself is
  done by an external process. Pillow remains forbidden.
```

OLD `:59`:
```
- `cjxl` is the single external tool, and is never bundled into the distribution — two libjxl copies on one
  Linux host fight over global decoder handler registration, and the wrong one can win silently.
```
NEW:
```
- `cjxl` is never bundled into the distribution — two libjxl copies on one Linux host fight over global
  decoder handler registration, and the wrong one can win silently.
- CAP-6 adds a second external tool, ImageMagick's `magick`, which is likewise never bundled. libjxl
  0.11.1's `cjxl` has **no resize option in any form** — not in the basic help, not in the full expert
  option list — so no arrangement of `cjxl` flags can shrink a page and the work must go to another
  process. `magick` is required **only** when a box is requested: a run with neither `--max-width` nor
  `--max-height` needs nothing but `cjxl`, and CAP-5's preflight demands the second tool only when it
  will actually be used.
```

OLD `:69`:
```
- The exit code is non-zero if and only if a JPEG entry failed to convert. Non-JPEG pass-throughs are
  normal and must never make a healthy run look failed.
```
NEW:
```
- The exit code is non-zero if and only if a JPEG entry failed to convert. Non-JPEG pass-throughs are
  normal and must never make a healthy run look failed. A page that could not be downscaled is a page
  that failed to convert: it is copied through under its original name, reported on its own line, and
  drives the non-zero exit exactly as a `cjxl` failure already does.
```

### 4.5 Spec — success signal and assumptions

**File:** `spec-cbz-jxl/spec-cbz-jxl.md` § Success signal

OLD `:89`:
```
A 200-page comic converts in one command to an archive at least 19% smaller whose JPEG pages remain
byte-identically recoverable, with zero entries lost, added or reordered — and a run containing a corrupt
page leaves either a complete archive or none at all, never a partial one.
```
NEW:
```
A 200-page comic converts in one command to an archive at least 19% smaller whose JPEG pages remain
byte-identically recoverable, with zero entries lost, added or reordered — and a run containing a corrupt
page leaves either a complete archive or none at all, never a partial one. Given a box, a book of mixed
page sizes converts to a book in which every page fits the box, every page that already fit is still
byte-identically recoverable, and the entry count and order are exactly what they were — no spread split,
no page cropped, no page enlarged, no page rotated.
```

**File:** same § Assumptions — appended:
```
- ImageMagick 7's `magick` is on the owner's PATH and its `-auto-orient` and `-resize 'WxH>'` behave as
  measured here: downsize-only, aspect preserved. The `magick` name is required deliberately, so an
  ImageMagick 6 host that offers only `convert` gets the honest preflight message rather than a
  different code path. Resize measured ~0.24 s per A4/300dpi page against ~0.26 s for `cjxl` on the
  result, so a downscaled page costs roughly twice a transcoded one; pages inside the box are unaffected.
- The spread heuristic — 1.35:1, tested on **display** aspect only — was reasoned, then re-derived after a
  review found it contradicting CAP-6's orientation clause. It has not been validated against a real comic
  library, and the first book run with `--max-width` is its test.
```

**File:** same § Assumptions `:100` — amended:
```
- `cjxl` is on the owner's PATH, or discoverable once the preflight message points them at the documentation.
  When a box is requested, `magick` is on PATH on the same terms.
```

### 4.6 Companion — entry transformations

**File:** `spec-cbz-jxl/entry-transformations.md`

Table row 1 OLD:
```
| `.jpg` / `.jpeg` (any case), converts cleanly | Transcode | same basename, `.jxl` | Lossless unless `--quality < 100`. |
```
NEW — four rows:
```
| `.jpg` / `.jpeg` (any case), fits the box, or no box was requested | Transcode | same basename, `.jxl` | Lossless unless `--quality < 100`; source JPEG byte-for-byte recoverable. |
| `.jpg` / `.jpeg`, over the box, recognised as a spread | Downscale by `--max-height` only | same basename, `.jxl` | `--max-width` deliberately not applied. One entry stays one entry. |
| `.jpg` / `.jpeg`, over the box, not a spread | Downscale to fit | same basename, `.jxl` | Largest box that fits, aspect preserved, never enlarged. |
| `.jpg` / `.jpeg`, downscale attempted and failed | Copy verbatim, unchanged | **original name kept** | Reported as a failure; drives non-zero exit. Not dropped. |
```

Consequences, appended after `:26`:
```
- **Reversibility is per page, and a downscaled page is a weaker guarantee.** A downscaled page keeps its
  reconstruction data, so `djxl` still recovers *something* byte-for-byte — the downscaled intermediate,
  not the source. A book in which every page was downscaled is not a CAP-1 book, and the report must not
  let it look like one. `jxlinfo` reporting `reconstruction data available` proves nothing on its own: it
  is true of a downscaled page too.
```

Reporting table, amended:
```
| converted | JPEG page successfully transcoded, downscaled or not | no |
```
plus two summary numbers and the exemption list:
```
194/200 converted (6 downscaled, 1 exempt as a spread), 3 passed through, 0 not converted
page014.jpg: cjxl exited 1 (truncated JPEG)
page042.jpg: 2480x1500 exceeds 1600x2400, left at full width as a recognised spread
```

### 4.7 Companion — external tool conventions

**File:** `spec-cbz-jxl/conventions.md`

NEW section after the `-q` trap paragraph at `:26`:
```
## Resizing

`cjxl` cannot resize. Verified against libjxl 0.11.1's full expert option list (`cjxl -v -v -v -v
--help`): no `--resize`, no size argument, nothing that scales the output grid. A page that must be
smaller goes through ImageMagick first, then takes the existing lossless path unchanged:

```bash
magick <in.jpg> -auto-orient -resize '<W>x<H>>' -quality 92 <mid.jpg>   # W,H computed in Python
cjxl <mid.jpg> <out.jxl>                                                # bare, as always
```

Three flags are load-bearing:

- `-resize '<W>x<H>>'` — the trailing `>` is the downsize guard: verified that `2400x3200>` against a
  400x600 page leaves it 400x600. `<W>x<H>` are supplied by Python, already aspect-correct, so `magick`
  has no fit decision left to make.
- `-auto-orient` — bakes the EXIF orientation into the pixels before geometry is measured, so the
  intermediate is upright and its EXIF tag cannot double-rotate it.
- the intermediate's own encoding — **open, not settled here.** This draft names `-quality 92`, which was
  chosen and not measured. Measured since, on a synthetic comic page: JPEG q92 discards 8.9% of the
  page's pixels, JPEG q100 discards 3.6%, and a PNG intermediate with `cjxl -q 100` discards none while
  producing a *smaller* archive than JPEG q100. The choice is deferred to the implementation entry, which
  carries the evidence and the consequences; a lossless intermediate forces `cjxl -q 100` on that path,
  because its default for PNG input is lossy, and `djxl` then returns a PNG rather than a JPEG.

Geometry is decided in Python from the `SOF0` frame header and the APP1 orientation tag. Neither
requires decoding a pixel, so the stdlib-only constraint holds. Letting `magick` pick the box instead
would be a bug: it measures coded dimensions, which is how a 600x300 page tagged orientation 6 ends up
fitted against its height.
```

`:41` OLD:
```
Verified byte-identical to the source (size and SHA-256 both match). `jxlinfo` reports
`JPEG bitstream reconstruction data available`, which is the cheap way to assert reversibility is present.
```
NEW:
```
Verified byte-identical to the source (size and SHA-256 both match). `jxlinfo` reports
`JPEG bitstream reconstruction data available`, which was the cheap way to assert reversibility is present.

**That check is no longer sufficient.** Under CAP-6 a downscaled page carries reconstruction data too, and
`djxl` on it reproduces the intermediate rather than the source — measured, the reconstructed file is
byte-identical to the intermediate and differs from the source. To audit a page, hash `djxl`'s output
against that page's *source bytes* and let the comparison decide. The presence of reconstruction data
proves a generation exists, never which one.
```

Preflight `:94`, appended:
```
When a box is requested, check `magick` the same way and in the same breath; CAP-5 exists so an owner
learns what is missing before a 200-page run, not eighty pages into one. `magick` is not checked when no
box is requested, so a plain transcode still needs nothing but libjxl. Require the `magick` name rather
than `convert`: an ImageMagick 6 host has no `magick` and should receive the install message instead of
silently taking a different code path. Check both together and report both together, so an owner missing
everything is told everything in one message rather than one run per missing tool.
```

Install table `:98` OLD:
```
| linux | distro package (`libjxl-tools`), which provides `cjxl` |
| mac | Homebrew formula (`libjxl`) |
| windows | libjxl release build on PATH, or a package manager |
```
NEW:
```
| linux | `libjxl-tools` provides `cjxl`; `imagemagick` provides `magick` |
| mac | Homebrew formulas `libjxl` and `imagemagick` |
| windows | libjxl release build on PATH, or a package manager; ImageMagick from imagemagick.org |

The `cjxl` rows are required by CAP-5. The `magick` rows are required by CAP-6 and are only consulted
when a box is requested.
```

### 4.8 Plan — frozen block renegotiation

**File:** `plan-cbz-jxl.md`, inside `<frozen-after-approval reason="human-owned intent — do not modify
unless human renegotiates">`. **This block is human-owned; the approval of this proposal is the
renegotiation.**

`:34` OLD:
```
output is always a new file, never in-place; write to temp then `os.replace`; `ZIP_STORED` only; exit
non-zero if and only if a JPEG failed to convert; no Python imaging libraries; `cjxl` is the only
external tool and is never bundled.
```
NEW:
```
output is always a new file, never in-place; write to temp then `os.replace`; `ZIP_STORED` only; exit
non-zero if and only if a JPEG failed to convert; no Python imaging libraries (Pillow stays out);
`cjxl` is never bundled, and ImageMagick's `magick` is a second external tool required only when a
box is requested.
```

`:39` OLD:
```
**Never:** bundle libjxl; modify or delete the input archive; drop a failed page (copy it through
instead); re-encode an existing `.jxl` (that destroys the reconstruction data); parse pixels in Python.
```
NEW:
```
**Never:** bundle libjxl or ImageMagick; modify or delete the input archive; drop a failed page (copy it
through instead); re-encode an existing `.jxl` (that destroys the reconstruction data); decode pixels in
Python (reading a `SOF0` header and an APP1 orientation tag is not decoding); split a double-page
spread; enlarge, rotate or crop a page.
```

I/O matrix rows appended:
```
| Bounded downscale | `--max-width 1600` on a 2480x3508 page | page becomes 1600x2260, one entry, source recoverable only as the intermediate | none |
| Already fits | `--max-width 1600` on an 800x1200 page | untouched by the resize path; source JPEG byte-for-byte recoverable | none |
| Never enlarged | `--max-width 4000` on an 800x1200 page | still 800x1200 | none |
| Rotated page | 600x300 tagged orientation 6, `--max-width 1600` | box judged against display 300x600, so the width limit does not apply to the height | none |
| Spread | 2480x1500, `--max-width 1600` | `--max-height` applies, `--max-width` does not; stays one entry | named in the report |
| Downscale failure | `magick` non-zero on one page | original bytes copied through under original name; archive complete | one line + non-zero exit |
| Missing second tool | `magick` absent, a box requested | exit non-zero before any archive opens, naming `magick` | no stack trace |
| No box requested | `magick` absent, no box given | runs normally; `magick` is never checked | none |
```

Acceptance criteria appended:
```
- Given a page that already fits the box, when converted, then it is byte-identically recoverable from the
  output (CAP-1 intact for that page)
- Given an oversized page tagged with a non-trivial EXIF orientation, when the box is applied, then the
  comparison uses the display dimensions, so `--max-width` is never applied to a page's height
- Given a spread over the box, when converted, then `--max-width` is not applied, `--max-height` still is,
  and the entry count is unchanged
- Given any run with a box requested, when `magick` is absent, then the run exits non-zero before opening
  an archive and names `magick` (CAP-5)
```

## 5. Implementation Handoff

**Scope classification: Moderate.** No fundamental replan — the contract change is drafted above and the
transcoder needs no rework — but the work must be sequenced around an in-progress plan, and the artifacts
need applying through their owning skills before code moves.

### Apply the artifacts first

1. `bmad-spec` — sections 4.1 to 4.5 against `spec-cbz-jxl.md`.
2. `bmad-spec` — sections 4.6 and 4.7 against the two companions.
3. **You, by hand** — section 4.8, the frozen block. No skill owns it.
4. `bmad-project-context` — after the code lands, so `AGENTS.md` records the new invariant rather than
   the superseded one. Do not hand-edit the `bmad:context` block; that skill replaces it wholesale on
   refresh. The rules it should end up carrying: never use `jxlinfo`'s reconstruction line as proof of
   source recovery; `magick` is checked only when a box is requested; geometry is decided in Python, never
   delegated to `magick`.

### Then implement

No ticket tree exists. Per `bmad-ticket`'s own guidance, a project without one keeps unplanned work as
free-text intent, so this lands as a **loose `bmad-build` plan**, `plan-bounded-downscaling.md`, matching
the project's two existing loose plans. Setting up a ticket tree for one capability is not worth the
scaffolding; if you expect several more capabilities, say so and `bmad-ticket` can set up the store and
this becomes ticket `1.1`.

Suggested slicing, in dependency order:

| Slice | Content | Touches |
|---|---|---|
| 1 | Geometry module: `SOF0` dimensions, APP1 orientation, display box, spread test, target box | new `cbx_jackal/geometry.py` |
| 2 | `magick` invocation, mirroring `encode.run`'s temp-pair discipline and exit-code oracle | new `cbx_jackal/resize.py` |
| 3 | Wire into `Converter`, `EntryOutcome.downscaled`, summary counts, exemption lines | `archive.py`, `report.py` |
| 4 | `--max-width` / `--max-height`, conditional second preflight, `EPILOG` | `cli.py`, `preflight.py` |
| 5 | Fixtures needing hand-built EXIF APP1 segments — ImageMagick in this sandbox will not *write* an orientation tag (`magick -set exif:Orientation 6` produced no APP1 at all), so orientation fixtures must be injected byte-wise, as they were for this proposal | `tests/`, `make_fixtures.py` |
| 6 | `README.md` install docs: two tools, three platforms | `README.md` |

**Two findings the implementation must not rediscover.** The `magick`-writes-EXIF gap in slice 5 is real
and will otherwise be met as a confused fixture; and `AGENTS.md` already records that losslessness is
decided twice (`encode.is_lossless` and `report.py:152`) — a third axis makes that a three-way split, so
fold the box into the existing decision rather than adding a fourth site.

**Sequencing.** Clear. `plan-directory-discovery.md` was the only collision on `cli.py` and is now
`built` and shipped, so all six slices can run without waiting on anything.

### Success criteria

- Every acceptance criterion in section 4.8 passes, with `cjxl`, `djxl`, `jxlinfo` and `magick` all on PATH.
- With no box requested, the full existing suite passes **unchanged** — the zero-regression property is
  the point, and a test that had to be edited to accommodate CAP-6 is a finding.
- A page inside the box is still byte-identically recoverable.
- An oversized orientation-6 page is fitted against its display width.
- A spread over the box keeps its width and loses no entry.
- `magick` absent with a box requested exits 2 before any archive opens, naming `magick`.
- `pyright` clean at the 3.9 floor.
