---
title: 'Read a CB7 or 7Z and convert it end to end'
type: 'feature'
ticket: '2'
created: '2026-10-08'
status: done
baseline_revision: '5ff1c179d1f72fd5dbdc1b4ac639082fe9279dd3'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The source seam exists (contract 1.6) but only ZIP has a reader behind it, so a CB7 or 7Z cannot
be converted at all — and every later entry of this epic waits on the reader this one builds or the fixtures
entry 4 owns.

**Approach:** The tracer bullet. Add a staged-extraction reader behind the seam, register the two suffixes
`7z` reads, add a minimal input-driven `7z` preflight, and convert one CB7 end to end — the thinnest path
through every layer this epic touches.

## Boundaries & Constraints

**Always:** Entry order is `7z l -slt`'s, supplied, never walked. Extraction goes to a temp directory the tool
owns and is removed on every exit path, success or failure. A source holding a link or device entry is refused
rather than materialised. The preflight answers before any archive is opened. ZIP behaviour is unchanged byte
for byte.

**Never:** RAR is not registered here (entry 5). Encryption and solid-specific behaviour are not handled here
beyond what falls out (entries 6 and 8). `classify`, the naming rule and the ZIP reader are untouched. No
reader fallback and no sniffing. `7z` is never bundled.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| CB7 end to end | a page, `ComicInfo.xml`, a nested file | converts; entries in the listing's order; page is `.jxl`; rest byte-identical | none |
| 7z absent | a `.cb7` in the list | nothing opened | exit 2, one message naming `7z` |
| Link entry | a source holding a symlink | no output written | refused, naming the entry; never materialised |
| Read failure mid-run | a source that fails to extract | no output written | `ArchiveError`; no temp directory survives |
| ZIP input | any `.cbz` | byte-identical to today | none |

</frozen-after-approval>

## Code Map

- `cbx_jackal/archive.py` — the seam this plugs into: `EntrySource` (Protocol), `ZipSource`,
  `SOURCE_READERS`, `open_source`, `EntryTemplate`, `DEFAULT_ENTRY_TEMPLATE`, around `:165-300`. The new
  reader is a sibling of `ZipSource`; nothing above the seam changes.
- `cbx_jackal/discover.py:49` — `ARCHIVE_SUFFIXES = (".cbz", ".zip")`; the scan and the pattern matcher both
  read it.
- `cbx_jackal/preflight.py:6` — `TOOL = "cjxl"`, and the one-tool message at `:8`. This entry adds only the
  `7z` name and a minimal input-driven check; entry 3 generalises the shape.
- `cbx_jackal/cli.py:165` — `preflight.check(TOOL)` runs *before* `discover.expand` at `:172`. The `7z` check
  must run *after* expand, because the expanded set is the only thing that knows an input needs it.
- `tests/helpers.py:39` — `build_zip` is the model for the new `build_7z`; `ArchiveTestCase:91` gates a class
  on `cjxl` via `requires_cjxl`, which is the pattern for gating on `7z`.
- `tests/test_archive.py:791` — `SourceSeam` is where the stub's tests live; the reader's tests belong beside
  them.

## Tasks & Acceptance

**Execution:**
- [ ] `cbx_jackal/archive.py` -- add `SevenZipSource`: `7z l -slt` for the ordered names and each entry's
  `Modified`/`Attributes`, a refusal for any entry whose `Attributes` mark it a link or device, `7z x -y` into
  a temp directory the tool owns, `read` from that directory, and `close` that removes it -- and register
  `.cb7` and `.7z` in `SOURCE_READERS`. The reader resolves `7z` itself so the registry stays
  `Callable[[str], EntrySource]`.
- [ ] `cbx_jackal/discover.py` -- add `.cb7` and `.7z` to `ARCHIVE_SUFFIXES` so a scan or a pattern feeds
  them to the converter.
- [ ] `cbx_jackal/preflight.py` and `cbx_jackal/cli.py` -- a minimal input-driven `7z` check: needed only
  when an expanded input's suffix has no ZIP reader, checked after `discover.expand` and before any archive
  opens, exit 2 naming `7z`.
- [ ] `tests/helpers.py` -- `build_7z(path, entries, *, solid=False, password=None, symlink=None)` shelling
  out to `7z`, and a gate so a class needing it skips cleanly without `7z` on PATH.
- [ ] `tests/test_archive.py` -- the matrix: the CB7 end-to-end order/count/bytes assertion, the absent-`7z`
  refusal, the link-entry refusal, and no temp directory surviving a failed run.

**Acceptance Criteria:**
- Given a CB7 holding a page, a `ComicInfo.xml` and a nested file, when it converts, then the output's
  entries are in the listing's order, the page is `.jxl`, and every other entry is byte-identical.
- Given `7z` absent and a `.cb7` in the list, when the run starts, then nothing is opened, the message names
  `7z`, and the exit code is 2.
- Given a source holding a symlink entry, when it is converted, then no output is written and the refusal
  names the entry.
- Given the whole suite, when it runs with `cjxl`, `djxl`, `jxlinfo` and `7z` on PATH, then it reports OK
  with no test edited by this change.

## Implementation Notes

Implemented by a coding subagent, then judged against the diff and re-verified by running each mutation.

**Two plan-internal contradictions, both mine.** `Boundaries` says ZIP behaviour is unchanged and the AC says
no test was edited, but the Execution task requires adding `.cb7`/`.7z` to `ARCHIVE_SUFFIXES` — which
necessarily invalidates `test_archive_suffixes_are_cbz_and_zip`, a literal assertion of that tuple. The
specific task won, as in entry 1.16; that one test and its class docstring are the only pre-existing lines
touched. Separately, the plan told the reader to carry `Modified` into the template without saying anything
about ZIP's representable range, which the review then caught as a crash.

**The review found two real defects, both reproduced before a verdict.** A timestamp outside 1980–2107
escapes as a raw traceback: `zipfile.ZipInfo` raises below 1980 and overflows its struct above 2107, and
neither `convert`'s handlers nor `cli.main` catch it — a reachable crash, since `7z` stores the 1970 epoch
for a file with no usable mtime. `_stored_info` now clamps an unrepresentable stamp to the documented
default, which is what a source with no timestamp gets anyway, and that covers every reader rather than
this one. And an explicit directory entry, listed as `Path = emptydir` with `Attributes = D drwxr-xr-x`,
reached the gate without a trailing slash, so `classify` wrote a zero-byte file where the ZIP path keeps a
directory; the reader restores the slash.

**One finding was rejected as a finding.** The AC "no test was edited" is unmet as a fact, but its only fix
is to reword the plan's own criterion, which the rules reject — recorded above instead.

The review's other four: a dead README pointer (softened; the section is entry 9's), the exit-code and
container docs this entry falsified (patched in `cli.py` and README — the install section and the
solid/encrypted behaviour stay entry 9's), and the matrix's "fails to extract" row being covered only at the
listing stage, which now has its own test built from a data-corrupted archive where `7z l` succeeds and
`7z x` fails.

Final state: 240 tests OK with `cjxl`, `djxl`, `jxlinfo` and `7z` on PATH, zero skips, `pyright` clean at the
3.9 floor. Baseline was 230.

## Plan Change Log

## Review Triage Log

Quick lens, 7 findings, pinned `review: 'quick'`. The three serious ones were reproduced independently before
a verdict — a reviewer's reproduction is a claim, not proof.

| # | Finding | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | A source timestamp outside ZIP's range crashes with an uncaught traceback (pre-1980 `ValueError`, post-2107 `struct.error`) | `high` | `patch` | Reproduced both. `touch -d 1970` then `7z a` stores `1970-01-02`, the reader passes it through, and `zipfile.ZipInfo` raises at construction; `(2200,...)` survives construction and raises `struct.error` at `writestr`. `convert` catches only `ArchiveError`/`BadZipFile`/`OSError`, so it escapes `cli.main` as a traceback, breaking CAP-5 and the exit-code contract. Reachable on any archive with an old or wrong mtime, which is common. |
| 2 | An explicit directory entry is written as a zero-byte file, so structure is not preserved | `medium` | `patch` | Reproduced: an empty dir lists as `Path = emptydir` with `Attributes = D drwxr-xr-x` — no trailing slash — so `classify` sees a plain name and writes a zero-byte *file*. The ZIP path preserves directories, and `test_directory_entries_survive` pins it. |
| 3 | The missing-`7z` message points at a README section that does not exist | `low` | `patch` | `preflight.py` says "README.md -> Installing 7z"; README has only `Installing cjxl`. One dead pointer, fixed by softening it — the section itself is entry 9's to write. |
| 4 | The exit-code and container docs were not updated for this entry's behaviour | `medium` | `patch` | `cli.py`'s epilog still defines code 2 as "missing cjxl" and its metavar is `CBZ|DIR|PATTERN`; README still says "no runtime dependencies at all", "stored order", and "unreadable from the ZIP". AGENTS.md makes README authoritative, and this entry falsified each line. The install section and the solid/encrypted behaviour stay entry 9's. |
| 5 | Acceptance criterion "no test edited" is unmet | `false` | — | True as a fact — the suffix pin `test_archive_suffixes_are_cbz_and_zip` had to change, because adding `.cb7`/`.7z` to `ARCHIVE_SUFFIXES` invalidates a literal assertion of that tuple. But its fix is to reword the plan's own criterion, which the rules reject as a finding. Recorded in Implementation Notes instead; same plan-internal contradiction as entry 1.16. |
| 6 | The "fails to extract" matrix row is covered at the wrong stage | `medium` | `patch` | The named test writes garbage, which fails at `7z l` (listing), not `7z x` (extraction). The lens verified the extraction path separately, so the code is right and the coverage is partial — the row says "fails to extract" and nothing fails at extraction. |

Groups 1 and 2 are code defects this change introduced; 3, 4 and 6 are this change's own consequences. No
`intent_gap`, no `bad_plan`, so no loopback; `review_loop_iteration` stays 0.

## Design Notes

`7z l -slt` sorts by name, so a 7z's source order *is* its listing order; the reader supplies that and nothing
walks the extracted tree. The archive itself appears as the first `Path =` block and is skipped.

The output template is built from `Modified` and `Attributes` rather than returning `None`. The listing
carries both, and contract 1.6 says a reader that can supply real values does — the mode string maps to
`external_attr` as `mode << 16`, which is what `ZipSource` carries through for a ZIP. Returning the default
instead would be a silent quality gap against the ZIP path.

The refusal is of the whole source, not of the one entry: extraction is all-or-nothing into a single tree, so
there is no way to skip a link and still serve the rest from it. The tracer proves that with a fixture built
by `7z a -snl`, and the test guards on being able to create a symlink at all, since Windows needs a privilege
for it.

## Verification

**Commands:**
- `python3 -m unittest discover -s tests` -- expected: `OK`, the pre-change count plus the new ones, zero
  failures, zero skips.
- `pyright` -- expected: no errors at the 3.9 floor `pyrightconfig.json` pins.

Confirm `cjxl`, `djxl`, `jxlinfo` **and `7z`** are on PATH first: without them the suite still reports OK
while most of it skips.
