---
title: 'CBZ to JXL transcoder CLI'
type: 'feature'
ticket: ''
created: '2026-10-05'
status: 'built'
baseline_revision: 'ff7843a3612f09eadbff0e3953fc6e0f01b110ce'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context:
  - '{project-root}/_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/conventions.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Comic owners re-encode the same JPEG pages repeatedly and their storage grows, because
existing tools either re-encode lossily or leave the bytes alone. JPEG XL lossless transcoding can shrink
pages 19-48% with no quality loss *and* keep the source JPEG byte-recoverable, but nothing exposes that as
a safe, order-preserving one-command operation.

**Approach:** A Python CLI that walks a CBZ's entries in stored order, transcodes JPEG pages to JXL via
`cjxl`, copies every other entry through byte-for-byte, and writes the result atomically to
`<name>.jxl.cbz`.

## Boundaries & Constraints

**Always:** lossless by default with no flag; stored entry order verbatim, never sorted or renumbered;
output is always a new file, never in-place; write to temp then `os.replace`; `ZIP_STORED` only; exit
non-zero if and only if a JPEG failed to convert; no Python imaging libraries; `cjxl` is the only
external tool and is never bundled.

**Never:** bundle libjxl; modify or delete the input archive; drop a failed page (copy it through
instead); re-encode an existing `.jxl` (that destroys the reconstruction data); parse pixels in Python.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Happy path | 200-page CBZ of valid `.jpg` | `<name>.jxl.cbz`, 200 entries in order, >=19% smaller, exit 0 | none |
| Lossless guarantee | any valid `.jpg` page | `djxl` on the output reproduces the source JPEG byte-for-byte | hash mismatch => classify not-converted |
| Metadata passthrough | `ComicInfo.xml`, `readme.txt`, `__MACOSX/`, nested dirs | copied byte-identical at original position, name unchanged | none; does not affect exit code |
| Corrupt page | truncated / garbage `.jpg` | original bytes copied through under its **original** name; archive still complete | one line + summary; exit non-zero |
| Already-JXL page | existing `.jxl` entry | copied verbatim, never re-encoded | none |
| Ordering | any archive | output entry order identical to input; no natural sort | never "fix" pre-existing bad order |
| Lossy mode | `--quality 90` | smaller than lossless; mode stated in output | must pass `--lossless_jpeg=0` or cjxl exits 1 |
| Missing dependency | `cjxl` not on PATH | exit non-zero **before** opening any archive, naming the tool + docs | no stack trace |
| Output exists | `<name>.jxl.cbz` present | refuse without `--force` | exit non-zero, input untouched |
| Unreadable archive | zip that cannot be read | no output file written at all | exit non-zero |

</frozen-after-approval>

## Code Map

- `_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/spec-cbz-jxl.md` -- CAP-1..CAP-5, constraints, non-goals. Source of truth.
- `_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/conventions.md` -- exact `cjxl`/`djxl` invocations, the `--lossless_jpeg=0` trap, effort/parallelism numbers, per-platform install docs requirement. Do not re-derive these; they were measured.
- `_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/entry-transformations.md` -- per-entry decision matrix and the three reporting classes.
- `cbx_jackal/` -- new. No existing source; nothing to reuse or avoid changing.
- Tests use stdlib `unittest`, not pytest, so the project keeps zero third-party dependencies in line with the no-imaging-libraries constraint.

## Tasks & Acceptance

**Execution:**
- [ ] `pyproject.toml` -- metadata + `cbx-jackal` console script, **no runtime dependencies** -- makes the entry point installable while keeping the dependency set empty
- [ ] `cbx_jackal/__init__.py` -- version constant only
- [ ] `cbx_jackal/preflight.py` -- `shutil.which("cjxl")` check returning a platform-neutral message pointing at README docs -- CAP-5
- [ ] `cbx_jackal/encode.py` -- invoke `cjxl`: bare for lossless; `-q N --lossless_jpeg=0` for lossy; capture stderr verbatim; temp output path per page -- the trap in `conventions.md` is the whole reason this file exists
- [ ] `cbx_jackal/archive.py` -- iterate entries in stored order, classify by extension, transcode or copy, write `ZIP_STORED` to a temp file, `fsync`, `os.replace` -- CAP-3 and CAP-4
- [ ] `cbx_jackal/report.py` -- three classes (converted / passed through / **not converted**), per-failure lines with `cjxl` stderr, summary counts -- conflating classes 2 and 3 breaks the exit-code contract
- [ ] `cbx_jackal/cli.py` -- argparse: `paths`, `--quality`, `--strict`, `--dry-run`, `--force`; exit codes; always clean up temps
- [ ] `tests/test_archive.py` -- unit-test every row of the I/O matrix with synthetic zips; assert byte-identity of pass-through entries, order preservation, and that no output exists after a failed run
- [ ] `tests/test_encode.py` -- assert the lossless path passes no `-q`, and that `--quality N` passes **both** `-q N` and `--lossless_jpeg=0`
- [ ] `README.md` -- `cjxl` install paths for linux (distro `libjxl-tools`), mac (Homebrew `libjxl`), windows (libjxl release on PATH) -- CAP-5 requires docs cover all three

**Acceptance Criteria:**
- Given a CBZ of N JPEG pages, when converted, then the output holds exactly N entries in the input's stored order with no page renumbered or dropped
- Given any successfully converted page, when `djxl` reconstructs it, then it is byte-identical to the source JPEG (CAP-1)
- Given a corrupt page, when the run completes, then the archive still contains every entry, the corrupt page is present under its original name, and the exit code is non-zero (CAP-4, CAP-3)
- Given any run that fails, when the process exits, then no output file exists at any path
- Given `cjxl` absent from PATH, when invoked, then it exits non-zero before opening the archive and mentions the tool (CAP-5)
- Given `--dry-run`, when invoked, then nothing is written and the plan plus size figures are reported

## Implementation Notes

## Plan Change Log

## Review Triage Log

| Finding | Verdict | Evidence | Route |
|---|---|---|---|
| Output-name collision silently destroys a converted page and exits 0 | high | `classify` derives `output_name` from the stem alone, so `page001.jpg` and an existing `page001.jxl` both map to `page001.jxl`. Reproduced: output holds two `page001.jxl` members, name-addressed read returns only the pre-existing one, the converted page is unreachable, run reports `1/2 converted` and exits 0. Violates CAP-3 (nothing lost). | patch |
| Reported size figures do not describe the published archive | high | `report.size_line` sums `EntryOutcome.source_size/output_size`, which are per-entry payload bytes and exclude ZIP framing and the source's own compression. Reproduced on a deflated source: tool reports `43.1% smaller`, published archive is `5.5% smaller`. Can overstate savings or mask a regression. | patch |
| Aborted runs discard the report, so failed pages are never named | medium | `convert()` populates `report.failures` then raises `ArchiveError`; `main()` prints only `str(exc)`, so `report.render` is never reached. Under `--strict` the owner cannot learn which pages failed, which is the mode where they most need to. Violates CAP-4's "one line per failed page". | patch |
| `RuntimeError` / `NotImplementedError` from `ZipFile.open` escape as tracebacks | medium | `convert()` catches only `(BadZipFile, OSError)` (archive.py:172) and `main()` only `OutputExistsError`/`ArchiveError` (cli.py:120-124). An encrypted member or an unsupported compression method reaches the top level and prints a traceback. | patch |
| `--dry-run` validates only pages, so it can report success for an archive the real run refuses | medium | `_process_dry_run` early-returns on `not plan.transcode` using `info.file_size` and never calls `_read_entry`, unlike `_process` (archive.py:266). A bad-CRC pass-through yields `rc=0` in dry-run and `rc=1` on the real run. | patch |
| Temp archive file handle is never closed; fsync flushes a GC-released buffer | medium | `_open_temp` (archive.py:227-240) discards the `NamedTemporaryFile` handle and returns only path and `ZipFile`. `ZipFile.close()` does not close a passed-in handle, so the descriptor and buffer are released by refcount teardown; `_publish` then fsyncs a buffer the function never flushed. Weakens the CAP-4 atomicity guarantee. | patch |
| Output-exists refusal aborts the remaining paths | medium | `except OutputExistsError: return EXIT_ENVIRONMENT` (cli.py:119-121) returns from `main`, while `except ArchiveError` continues. With `one.cbz` already converted and `two.cbz` fresh, only the first is reported and `two.jxl.cbz` is never created, silently. | patch |
| `test_lossy_output_does_not_differ_in_pixels` can pass without comparing anything | medium | `try: assertPixelsIdentical(...) except AssertionError: return` also swallows the helper's internal assertions on the `cjxl`/`djxl` subprocess return codes, so a failing subprocess inside the helper passes the test vacuously. | patch |
| `conventions.md` contradicts itself on pass-through compression | low | Line 87 says write every entry `ZIP_STORED`; line 88 says preserve the source's compression type for pass-through entries. The plan's frozen `Always` clause and the spec constraint both say STORED only, and the code follows them, so line 88 is the stray line. | patch |
| `helpers.contents()` collapses duplicate names, hiding collisions | low | Keys by `info.filename`, and `ZipFile.read` returns the last member for a repeated name, so a stem-collision archive looks correct. This is why the high finding above escaped the suite; no test builds one. | patch |
| `test_destination_is_a_new_file_beside_the_input` asserts the same case twice | low | archive.py:227-230 and 232-235 are byte-identical `destination_for("/x/book.cbz")` assertions; the second case is never exercised. | patch |
| Unreadable-archive test lacks a root guard | low | `_make_unreadable` chmods to `0o000` without a `geteuid() != 0` skip, unlike the adjacent unwritable-directory test. Fails as root, which is the default in most container images. | patch |
| Dead `EntryOutcome.saved` and unreachable `encode.run(timeout=)` branch | low | `saved` is never read; `archive.py` calls `encode.run` without `timeout`, so the `TimeoutExpired` branch cannot fire. Harm named: a pathological page could hang a batch run with no timeout, because the only guard for it is unreachable. | patch |
| Duplicated import blocks in `test_archive.py` / `test_encode.py`, stray blank line in `helpers.py` | low | `os` imported twice in each file, with a `sys.path` insert between stdlib and project imports; `helpers.py` has a double blank line. Cosmetic. | patch |
| Plan AC "no output file exists when a run fails" contradicts the frozen matrix | false | The frozen matrix row for a corrupt page requires the opposite — archive complete, failed page copied through, exit non-zero — and that is the human-owned decision from the forge. The code implements the matrix. The looseness is in the AC's wording, and fixing that would mean editing the frozen block, which is not actionable here. | reject |

## Design Notes

The single non-obvious mechanic is the cjxl invocation matrix. libjxl defaults to lossless-transcoding
for JPEG input, so a bare call is already lossless:

```bash
cjxl in.jpg out.jxl                             # lossless, reversible
cjxl -q 90 in.jpg out.jxl                        # FAILS, exit 1
cjxl -q 90 --lossless_jpeg=0 in.jpg out.jxl      # lossy, irreversible
```

Only the lossless form embeds JPEG bitstream reconstruction data. That is why reversibility is exclusive
to lossless, and why re-encoding an existing `.jxl` must be avoided -- it would silently strip it.

Ordering is a correctness property, not cosmetics. Because nothing is renumbered, a page that fails and
is copied through stays at its original index, so the book gets a hole rather than a misnumbering.

## Verification

**Commands:**
- `python3 -m unittest discover -s tests -v` -- expected: all pass
- `python3 -m cbx_jackal.cli tests/fixtures/sample.cbz` -- expected: writes `sample.jxl.cbz`, exit 0
- `djxl` round-trip over each output page -- expected: SHA-256 matches the source JPEG
- `python3 -m cbx_jackal.cli missing.cbz` with `cjxl` off PATH -- expected: non-zero exit, message names `cjxl`, no traceback
