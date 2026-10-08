---
title: 'CLI: --format, with jxl the only legal value'
type: 'feature'
ticket: '16'
created: '2026-10-08'
status: done
baseline_revision: '9942a5c842753bff58b53ccc3aa8e2710bd5f730'
route: 'full'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Entry 3 fixed the destination as `<stem>.<format>.cbz`, but nothing reads a format:
`discover.OUTPUT_SUFFIX` is a literal and `is_archive` skips exactly one suffix, so there is no way to
implement that rule, and no format for entry 6's classification gate to read.

**Approach:** Add `--format` to the CLI with `jxl` the only legal value today, thread it to where the
archive name is built, and split the output suffix into a constant container part plus a declared set of
page formats — keeping `OUTPUT_SUFFIX` derived at today's value so no existing test changes.
## Boundaries & Constraints

**Always:** An output is named `<stem>.<format>.cbz`, and the container never varies with the input. The
scan's skip and the write name read one declaration so they cannot drift. The default path stays
byte-for-byte the run it is today, and `--format jxl` equals no flag.

**Never:** Do not touch `classify` — it builds the name of an entry *inside* the archive, a different name,
and entry 6 owns that gate. Do not add `webp` as a value or stub an encoder for it. Do not edit any existing
test or helper. Do not change `ARCHIVE_SUFFIXES`, the atomic publish, or anything in `archive.py` beyond the
output name.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Default run | `book.cbz`, no flag | `book.jxl.cbz`, byte-for-byte as today | none |
| Explicit default | `book.cbz --format jxl` | `book.jxl.cbz`, identical to no flag | none |
| Unsupported value | `book.cbz --format webp` | nothing written | exit 2, message naming `webp` as unsupported, before the preflight |
| Rescan | directory holds `book.jxl.cbz` | skipped, no `book.jxl.jxl.cbz` | none |
| Zip input | `book.zip --format jxl` | `book.jxl.cbz`, never `book.jxl.zip` | none |

</frozen-after-approval>

## Code Map

- `cbx_jackal/discover.py` — the suffix declarations, and where the split happens: `ARCHIVE_SUFFIXES:49`,
  `OUTPUT_SUFFIX:55`, `is_archive:73`.
- `cbx_jackal/archive.py` — `destination_for:98` builds the archive name and already documents *why* the
  write path and the scan must share one declaration. `Converter.__init__:209`; `convert:228` calls it.
- `cbx_jackal/cli.py` — `build_parser:43` adds the flag. `_validate_quality:106` is the pattern to mirror:
  it raises `ValueError`, which `main` turns into `parser.error:120`, and that runs *before* the preflight
  at `:125`, so a bad flag exits 2 with no tool on PATH. `Converter(...)` is built at `:135`; `EPILOG:23`
  states the output name twice.
- `tests/test_archive.py` — all CLI coverage lives here; there is no `test_cli.py`. Style is
  `cli.main([...])` returning an int, or `self.capture([...])` → `(code, out, err)` (`tests/helpers.py:140`).
  `test_parser_exposes_every_documented_flag:832` lists the flags. `ArchiveSuffixes` at `:1480` holds the
  drift guards, including the case-variant and dotted-stem names at `:1503`.
- `tests/helpers.py:163` — `report_sources` filters on `discover.OUTPUT_SUFFIX`; ~20 tests depend on it.
- `tests/test_archive.py:1484` — asserts the literal `".jxl.cbz"`.

Both last two are **do not change**.

## Tasks & Acceptance

**Execution:**
- [ ] `cbx_jackal/discover.py` -- declare `CONTAINER_SUFFIX = ".cbz"`, `PAGE_FORMATS = ("jxl",)` and
  `DEFAULT_FORMAT`; add `output_suffix(page_format=DEFAULT_FORMAT)` and `is_output_name(name)`; redefine
  `OUTPUT_SUFFIX = output_suffix()` at the same `".jxl.cbz"` value. One declaration then feeds both the write
  name and the scan skip, so the drift guard at `:1508` keeps passing unedited.
- [ ] `cbx_jackal/archive.py` -- give `destination_for` a defaulted `page_format` parameter built from
  `CONTAINER_SUFFIX`, and give `Converter.__init__` a trailing `page_format: str = DEFAULT_FORMAT` passed to
  it. Appending a defaulted parameter keeps all ~78 existing `Converter(self.cjxl)` call sites valid.
- [ ] `cbx_jackal/cli.py` -- add `--format` with `dest="page_format"`, mirror `_validate_quality` as
  `_validate_format` rejecting anything outside `PAGE_FORMATS`, thread the result into `Converter`, and add
  `--format` to the documented-flag test's tuple.
- [ ] `cbx_jackal/cli.py` -- correct the two help sentences stating the output name as a literal
  `<input>.jxl.cbz`, so the help does not contradict the flag. Entry 11 owns the epilog for the box flags;
  these lines are disjoint from it.
- [ ] `tests/test_archive.py` -- cover the matrix.

**Acceptance Criteria:**
- Given a book and `--format jxl`, when it converts, then the output is byte-identical to the run without
  the flag.
- Given a book and `--format webp`, when the run starts, then nothing is written, the exit code is 2, and
  the message names `webp` as unsupported.
- Given a directory already holding `book.jxl.cbz`, when it is rescanned, then that book is skipped and no
  `book.jxl.jxl.cbz` appears.
- Given `cjxl`, `djxl` and `jxlinfo` on PATH, when the whole suite runs, then it reports OK and no test was
  edited by this change.

## Implementation Notes

Implementation ran as two passes: the plan's five Execution bullets, then the six `patch` groups from the Quick
lens. A coding subagent did both; every claim was re-verified from the diff and by re-running the mutations
rather than taken from its reports.

**The plan contradicted itself on one line, and the specific bullet won.** `Boundaries & Constraints` says
never edit an existing test; the `cbx_jackal/cli.py` Execution bullet says to add `--format` to the
documented-flag test's tuple. `git diff -U0` confirms exactly one removed line in `tests/` — that tuple — so
"no existing test was edited" is true of every other line, not literally true. The review re-raised this and
was right to; the contradiction was the plan's, not the implementer's.

**Two findings were false, and running the mutation is what settled them.** The lens reported that deleting the
threading left the suite green; it did not — but the two failures were `test_commit_hook` and a leaked-temp
check, both artifacts of its scratch copy lacking `.githooks`, so the *claim* survived while its *evidence*
did not. And it reported that the derived `OUTPUT_SUFFIX` silently disarms 14 call sites: changing
`DEFAULT_FORMAT` to `webp` produces 6 failures and 53 errors, `test_output_suffix_is_fixed_at_jxl_cbz` among
them. That one is loudly refuted, not silently armed.

**The undeclared-format guard lives in the suffix builder, not in the CLI.** `_validate_format` was the only
membership check and sat in the wrong layer — the invariant is about the name, not the flag. Putting it in
`output_suffix` covers `destination_for` and `is_output_name` together and needs no new parameter, and it
closes the traversal case for free: a path separator is simply not in `PAGE_FORMATS`.

**`--format JXL` now normalises to `jxl` rather than merely being accepted.** Returning the declared spelling
rather than the typed one means the output is `book.jxl.cbz`, not `book.JXL.CBZ` — the case-insensitive skip
would have covered the latter, but writing a name in a spelling the tool never declares is not worth allowing.

Final state: 225 tests OK with `cjxl`, `djxl` and `jxlinfo` on PATH, zero skips, `pyright` clean at the 3.9
floor. Baseline was 214.

## Plan Change Log

## Review Triage Log

Quick lens, 13 findings, pinned `review: 'quick'`. Every claim verified independently before a verdict;
the reviewer's own severities were disregarded. Two were disproved by running the mutation myself.

| # | Finding | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | No test distinguishes a threaded `--format` from an ignored one (with F10) | `medium` | `patch` | Reproduced: with `page_format=page_format` removed from the `Converter(...)` call, all four format tests still pass. The reviewer's stated evidence (176 tests OK) was wrong — a scratch copy without `.githooks` — but the claim survives. |
| 2 | `page_format` reaches the name builder unvalidated; `webp` re-ingests to `book.webp.webp.cbz`; traversal via the same parameter (F2) | `medium` | `patch` | Reproduced exactly: `destination_for(book, "webp")` → `book.webp.cbz`, `is_archive` True, rescan → `book.webp.webp.cbz`. Traversal: `destination_for("/lib/book.cbz", "../../etc/evil")` → `/lib/book.../../etc/evil.cbz`. Unreachable through the CLI, but entry 6 is the next caller. |
| 3 | `README.md` still states the name as a literal in five places (F3) | `medium` | `patch` | Confirmed at `README.md:118, 127, 129, 161, 162`. Entry 1.3's ruling says README is "amended by the epic that changes it", and this is that epic. `AGENTS.md:19` makes README authoritative. |
| 4 | `Converter.convert` and the `destination_for` drift example still say `<name>.jxl.cbz` (F4) | `low` | `patch` | `archive.py:237` and `archive.py:104-105`. Direct correction. |
| 5 | `discover.py` module docstring still states the skip rule as `.jxl.cbz` (F5) | `low` | `patch` | `discover.py:21-22`, contradicting the `is_archive` docstring the same diff updated. Direct correction. |
| 6 | `_validate_format` rejects `JXL` while matching is case-insensitive elsewhere; message interpolates raw input (F7, F8) | `low` | `patch` | Confirmed: `--format JXL` → `unsupported --format JXL`; `--format ""` → `unsupported --format ;`. One function, one fix. |
| 7 | Nothing records that `--format` does not change the written bytes (F6) | `false` | — | The premise is disproved by the reviewer's own citation: `archive.py:212-214` records exactly that, in `Converter`'s docstring. The test comment is scoped to *skipping* and says so. Help is accurate for the only legal value. |
| 8 | `report_sources` on the derived `OUTPUT_SUFFIX` silently disarms 14 call sites (F9) | `false` | — | Disproved by running it: changing `DEFAULT_FORMAT` to `webp` yields **6 failures and 53 errors**, with `test_output_suffix_is_fixed_at_jxl_cbz` failing loudly. The loudest possible outcome, not a silent one. |
| 9 | `AGENTS.md:13` misdescribes the destination (F11) | `medium` | `defer` | True, but the `bmad:context` block is never hand-edited and entry 13 of this epic refreshes it. A fix editing an agent-context file routes to `defer` by rule. |

Findings 12 and 13 were the reviewer's own verification notes (suite green with all three tools present, pyright
clean, exactly one removed test line). Not defects; both plan gates confirmed.

Groups 1–6 share the change as cause and route to `patch`. No `intent_gap`, no `bad_plan`, so no loopback and
`review_loop_iteration` stays 0.

## Design Notes

`OUTPUT_SUFFIX` survives as a *derived* constant rather than being replaced. Its value stays `".jxl.cbz"`, so
the literal assertion at `test_archive.py:1485` and the ~20 tests reaching it through `helpers.report_sources`
keep passing — which is what makes "no existing test was edited" true rather than aspirational. New code
should prefer `is_output_name`: a reader that reaches for `OUTPUT_SUFFIX` silently stops covering WebP the day
that format lands.

`is_output_name` matches the declared format set rather than "any dotted word before `.cbz`", so a `.cbz` this
tool did not produce and cannot name is still offered for conversion rather than silently skipped.

Recorded, not fixed, since editing a helper is forbidden here: `helpers.report_sources` matching
`OUTPUT_SUFFIX` would return an empty list rather than fail if `DEFAULT_FORMAT` ever changed.

## Verification

**Commands:**
- `python3 -m unittest discover -s tests` -- expected: `OK`, zero failures, the pre-change test count plus
  the new ones.
- `pyright` -- expected: no errors, at the 3.9 floor `pyrightconfig.json` pins.

`.venv` here is Python 3.14, so run the suite with the system `python3`. Confirm `cjxl`, `djxl` and
`jxlinfo` are on PATH first: without them the suite still reports OK while most of it skips.
