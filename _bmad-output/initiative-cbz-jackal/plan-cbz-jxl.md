---
title: 'CBZ to JXL transcoder CLI'
type: 'feature'
ticket: ''
created: '2026-10-05'
status: 'draft'
baseline_revision: 'ff7843a3612f09eadbff0e3953fc6e0f01b110ce'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: ''
review_source: ''
lenses_ran: []
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/conventions.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Comic owners re-encode the same JPEG pages repeatedly and their storage grows, because
existing tools either re-encode lossily or leave the bytes alone. JPEG XL lossless transcoding can shrink
pages 19–48% with no quality loss *and* keep the source JPEG byte-recoverable, but nothing exposes that as
a safe, order-preserving one-command operation.

**Approach:** A Python CLI that walks a CBZ's entries in stored order, transcodes JPEG pages to JXL via
`cjxl`, copies every other entry through byte-for-byte, and writes the result atomically to
`<name>.jxl.cbz`.

## Boundaries & Constraints

**Always:** lossless by default with no flag; stored entry order verbatim, never sorted or renumbered;
output is always a new file, never in-place; write to temp then `os.replace`; `ZIP_STORED` only; exit
non-zero if and only if a JPEG failed to convert; no Python imaging libraries (Pillow stays out);
`cjxl` is never bundled, and ImageMagick's `magick` is a second external tool required only when a
box is requested.

**Never:** bundle libjxl or ImageMagick; modify or delete the input archive; drop a failed page (copy it
through instead); re-encode an existing `.jxl` (that destroys the reconstruction data); decode pixels in
Python (reading a `SOF0` header and an APP1 orientation tag is not decoding); split a double-page
spread; enlarge, rotate or crop a page.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | 200-page CBZ of valid `.jpg` | `<name>.jxl.cbz`, 200 entries in order, ≥19% smaller, exit 0 | none |
| Lossless guarantee | any valid `.jpg` page | `djxl` on the output reproduces the source JPEG byte-for-byte | hash mismatch ⇒ classify not-converted |
| Metadata passthrough | `ComicInfo.xml`, `readme.txt`, `__MACOSX/`, nested dirs | copied byte-identical at original position, name unchanged | none; does not affect exit code |
| Corrupt page | truncated / garbage `.jpg` | original bytes copied through under its **original** name; archive still complete | one line + summary; exit non-zero |
| Already-JXL page | existing `.jxl` entry | copied verbatim, never re-encoded | none |
| Ordering | any archive | output entry order identical to input; no natural sort | never “fix” pre-existing bad order |
| Lossy mode | `--quality 90` | smaller than lossless; mode stated in output | must pass `--lossless_jpeg=0` or cjxl exits 1 |
| Missing dependency | `cjxl` not on PATH | exit non-zero **before** opening any archive, naming the tool + docs | no stack trace |
| Output exists | `<name>.jxl.cbz` present | refuse without `--force` | exit non-zero, input untouched |
| Unreadable archive | zip that cannot be read | no output file written at all | exit non-zero |
| Bounded downscale | `--max-width 1600` on a 2480x3508 page | page becomes 1600x2260, one entry, source recoverable only as the intermediate | none |
| Already fits | `--max-width 1600` on an 800x1200 page | untouched by the resize path; source JPEG byte-for-byte recoverable | none |
| Never enlarged | `--max-width 4000` on an 800x1200 page | still 800x1200 | none |
| Rotated page | 600x300 tagged orientation 6, `--max-width 1600` | box judged against display 300x600, so the width limit does not apply to the height | none |
| Spread | 2480x1500, `--max-width 1600` | `--max-height` applies, `--max-width` does not; stays one entry | named in the report |
| Downscale failure | `magick` non-zero on one page | original bytes copied through under original name; archive complete | one line + non-zero exit |
| Missing second tool | `magick` absent, a box requested | exit non-zero before any archive opens, naming `magick` | no stack trace |
| No box requested | `magick` absent, no box given | runs normally; `magick` is never checked | none |

</frozen-after-approval>

## Code Map

- `_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/spec-cbz-jxl.md` — CAP-1..CAP-5, constraints, non-goals. Source of truth.
- `_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/conventions.md` — exact `cjxl`/`djxl` invocations, the `--lossless_jpeg=0` trap, effort/parallelism numbers, per-platform install docs requirement. Do not re-derive these; they were measured.
- `_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/entry-transformations.md` — per-entry decision matrix and the three reporting classes.
- `cbx_jackal/` — new. No existing source; nothing to reuse or avoid changing.
- Tests use stdlib `unittest`, not pytest, so the project keeps zero third-party dependencies in line with the no-imaging-libraries constraint.

## Tasks & Acceptance

**Execution:**
- [ ] `pyproject.toml` — metadata + `cbx-jackal` console script, **no runtime dependencies** — makes the entry point installable while keeping the dependency set empty
- [ ] `cbx_jackal/__init__.py` — version constant only
- [ ] `cbx_jackal/preflight.py` — `shutil.which("cjxl")` check returning a platform-neutral message pointing at README docs — CAP-5
- [ ] `cbx_jackal/encode.py` — invoke `cjxl`: bare for lossless; `-q N --lossless_jpeg=0` for lossy; capture stderr verbatim; temp output path per page — the trap in `conventions.md` is the whole reason this file exists
- [ ] `cbx_jackal/archive.py` — iterate entries in stored order, classify by extension, transcode or copy, write `ZIP_STORED` to a temp file, `fsync`, `os.replace` — CAP-3 and CAP-4
- [ ] `cbx_jackal/report.py` — three classes (converted / passed through / **not converted**), per-failure lines with `cjxl` stderr, summary counts — conflating classes 2 and 3 breaks the exit-code contract
- [ ] `cbx_jackal/cli.py` — argparse: `paths`, `--quality`, `--strict`, `--dry-run`, `--force`; exit codes; always clean up temps
- [ ] `tests/test_archive.py` — unit-test every row of the I/O matrix with synthetic zips; assert byte-identity of pass-through entries, order preservation, and that no output exists after a failed run
- [ ] `tests/test_encode.py` — assert the lossless path passes no `-q`, and that `--quality N` passes **both** `-q N` and `--lossless_jpeg=0`
- [ ] `README.md` — `cjxl` install paths for linux (distro `libjxl-tools`), mac (Homebrew `libjxl`), windows (libjxl release on PATH) — CAP-5 requires docs cover all three

**Acceptance Criteria:**
- Given a CBZ of N JPEG pages, when converted, then the output holds exactly N entries in the input's stored order with no page renumbered or dropped
- Given any successfully converted page, when `djxl` reconstructs it, then it is byte-identical to the source JPEG (CAP-1)
- Given a corrupt page, when the run completes, then the archive still contains every entry, the corrupt page is present under its original name, and the exit code is non-zero (CAP-4, CAP-3)
- Given any run that fails, when the process exits, then no output file exists at any path
- Given `cjxl` absent from PATH, when invoked, then it exits non-zero before opening the archive and mentions the tool (CAP-5)
- Given `--dry-run`, when invoked, then nothing is written and the plan plus size figures are reported
- Given a page that already fits the box, when converted, then it is byte-identically recoverable from the output (CAP-1 intact for that page)
- Given an oversized page tagged with a non-trivial EXIF orientation, when the box is applied, then the comparison uses the display dimensions, so `--max-width` is never applied to a page's height
- Given a spread over the box, when converted, then `--max-width` is not applied, `--max-height` still is, and the entry count is unchanged
- Given any run with a box requested, when `magick` is absent, then the run exits non-zero before opening an archive and names `magick` (CAP-5)

## Implementation Notes

## Plan Change Log

## Review Triage Log

## Design Notes

The single non-obvious mechanic is the cjxl invocation matrix. libjxl defaults to lossless-transcoding
for JPEG input, so a bare call is already lossless:

```bash
cjxl in.jpg out.jxl                        # lossless, reversible
cjxl -q 90            in.jpg out.jxl       # FAILS, exit 1
cjxl -q 90 --lossless_jpeg=0 in.jpg out.jxl   # lossy, irreversible
```

Only the lossless form embeds JPEG bitstream reconstruction data. That is why reversibility is exclusive
to lossless, and why re-encoding an existing `.jxl` must be avoided — it would silently strip it.

Ordering is a correctness property, not cosmetics. Because nothing is renumbered, a page that fails and
is copied through stays at its original index, so the book gets a hole rather than a misnumbering.

## Verification

**Commands:**
- `python3 -m unittest discover -s tests -v` -- expected: all pass
- `python3 -m cbx_jackal.cli tests/fixtures/sample.cbz` -- expected: writes `sample.jxl.cbz`, exit 0
- `djxl` round-trip over each output page -- expected: SHA-256 matches the source JPEG
- `python3 -m cbx_jackal.cli missing.cbz` with `cjxl` off PATH -- expected: non-zero exit, message names `cjxl`, no traceback