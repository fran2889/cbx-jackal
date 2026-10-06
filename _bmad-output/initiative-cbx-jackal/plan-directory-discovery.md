---
title: 'Convert a directory of archives'
type: 'feature'
ticket: ''
created: '2026-10-06'
status: 'in-progress'
baseline_revision: 'c8ae0471e1bdef4204e00096f7616e8d5cfdc625'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 1
context:
  - '{project-root}/_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/spec-cbz-jxl.md'
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** `cbx-jackal` takes explicit file paths only, so an owner with 300
archives must glob or loop by hand and cannot recurse into the subfolders a
library is organised into.

**Approach:** Accept anything in the existing `paths` positional — a file, a
directory, or a wildcard pattern — and expand it into the archives it names, with
opt-in recursion for directories. `paths` stays `nargs="+"`: several inputs, of
mixed kinds, in one run. The converter, the flags, and the exit-code contract are
untouched.

## Boundaries & Constraints

**Always:**
- Output stays `<name>.jxl.cbz` **beside the input**, including in a
  subdirectory — nothing hoisted or flattened. `book.zip` yields
  `book.jxl.cbz`, never `book.jxl.zip`: the suffix after `.jxl` is fixed.
- Preflight runs before any archive opens, so a missing `cjxl` over a 300-file
  scan is one message, not 300 failures.
- One bad archive or refused output must not abandon the batch — the existing
  per-path `continue` carries over. One report block per archive, no aggregate
  line, no new exit code.
- Order is **deterministic**: sort each directory's own entries, then descend
  depth-first, and sort pattern matches too — `glob` returns filesystem order,
  which is no more alphabetical than `os.scandir`'s. A global sort of the
  expanded list is not needed: output mirrors the input tree, so
  `lib/a/book.cbz` and `lib/b/book.cbz` resolve to distinct outputs, and the only
  collision a scan can produce is between two inputs in one directory.
- Expansion **deduplicates**: an archive reachable twice — named directly *and*
  reached by a directory or pattern that also contains it — is converted once,
  in the order first reached. Otherwise one archive gets two report blocks and,
  without `--force`, the duplicate's own output refuses and the run exits 2
  having converted everything.
- A pattern is expanded only when it carries glob metacharacters
  (`*`, `?`, `[`). A literal path is never glob-expanded, so an archive whose
  name really does contain `*` is still convertible.
- A pattern matching nothing is **not** an error. It takes the same path as an
  empty directory: one note naming the argument, exit `0`. An unquoted pattern
  is expanded by the shell into several paths before the tool sees it, so
  quoted-vs-unquoted is the user's choice and both behave.

**Never:** No parallelism, thread pool or progress bar — the spec forbids
page-level parallelism and `cjxl` already threads internally. No
`--delete-source`, no moving or renaming of inputs, no new dependency. `glob`
and `os.scandir` only.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Behavior | Error Handling |
|----------|--------------|-------------------|----------------|
| File path, unchanged | `cbx-jackal a.cbz` | identical to today | unchanged |
| Directory | `lib/` with `a.cbz`, `b.zip`, `notes.txt`, `sub/c.cbz` | root archives converted, `sub/` untouched | no error |
| Directory, `--recursive` | same tree | all three converted, output beside each input | no error |
| `.zip` input | `lib/b.zip` | `lib/b.jxl.cbz`, never `b.jxl.zip` | no error |
| Mixed list | `cbx-jackal lib/ c.cbz` | all three converted | no error |
| Several paths | `cbx-jackal a.cbz lib/ 'lib/x*.cbz'` | every archive once, in argument order | no error |
| Pattern, quoted | `'lib/name*.cbz'` | those archives, sorted | no error |
| Pattern, no match | `'lib/nope*.cbz'` | one note naming the pattern | `EXIT_OK` |
| Pattern mixed with a directory | `'lib/*.cbz' lib/sub` | every archive once, no duplicate blocks | no error |
| Literal path with `*` in the name | a file actually called `a*.cbz` | converted, not treated as a pattern | no error |
| Previous run's output | `lib/` with `a.cbz`, `a.jxl.cbz` | scan skips `a.jxl.cbz`; `a.cbz` refused | `EXIT_ENVIRONMENT`, as today for one file |
| One stem, two suffixes | `lib/` with `a.cbz`, `a.zip` | sorted, `a.cbz` wins, `a.zip` refused | `EXIT_ENVIRONMENT`, rest converted |
| No supported file | `lib/` of only `.txt` | one note naming the directory | `EXIT_OK` |
| Nonexistent path | `missing.cbz`, `missing_dir/` | `cannot read ...`, no output | `EXIT_FAILED`, as today |
| Symlink, dir or archive | `lib/series -> /elsewhere`, `lib/link.cbz -> a.cbz` | neither followed during a scan | no error |
| Unreadable subdirectory | `os.scandir` raises `OSError` | that subdirectory skipped | warning to stderr |

</frozen-after-approval>

## Code Map

- `cbx_jackal/discover.py` -- **new**. Sole owner of "which files does this
  argument name": `ARCHIVE_SUFFIXES`, `OUTPUT_SUFFIX`, `is_archive`,
  `has_magic`, `iter_directory`, `expand`.
- `cbx_jackal/cli.py` -- the `paths` positional (`metavar="CBZ|DIR|PATTERN"`), the
  per-path loop in `main`, the exit codes, `build_parser`, `EPILOG`. Expansion
  goes once, after the preflight, before the loop. Do **not** move the preflight:
  CAP-5 requires it before any archive opens.
- `cbx_jackal/archive.py` -- `destination_for` stays as is; `discover` sources
  `OUTPUT_SUFFIX` from a single owner rather than restating the `.jxl.cbz`
  literal, so the scan's skip and the converter's output name cannot drift apart.
- `cbx_jackal/report.py` -- **no changes**. One report per archive is the
  reporting unit; a batch reuses it as-is.
- `tests/test_archive.py` -- `CliSurface`, `MultiplePaths`, `build_zip()`. New
  classes `DirectoryDiscovery`, `RecursiveDiscovery`, `PatternDiscovery`, and
  shared helpers on the base case rather than copies per class.
- `README.md` -- `Usage` line, flag table, exit codes, pattern support.

## Tasks & Acceptance

**Execution:**
- [x] `cbx_jackal/discover.py` -- `ARCHIVE_SUFFIXES` (`.cbz`, `.zip`),
      `OUTPUT_SUFFIX` (`.jxl.cbz`, one owner), `is_archive`, `has_magic`,
      `iter_directory`, `expand` -- case-insensitive extension match, skip
      `OUTPUT_SUFFIX` names, `glob` only for arguments carrying metacharacters,
      `sorted()` on matches, `os.scandir` never `glob` for directories,
      `follow_symlinks=False` on `is_dir` and `is_file`, dedupe preserving first-
      reached order, warn on an `OSError` from one subdirectory, sort each
      directory's own entries, and report paths as typed rather than absolutised.
- [x] `cbx_jackal/cli.py` -- recursive flag, `discover.expand` after the preflight
      and before the loop, the no-match note, plus `metavar` and `EPILOG`.
- [x] `cbx_jackal/archive.py` -- single owner for the `.jxl.cbz` output suffix,
      so `destination_for` and the scan's skip read the same value.
- [x] `tests/test_archive.py` -- one method per matrix row, direct tests for
      `is_archive` / `has_magic` / the suffixes, a case-insensitivity test, a
      preflight-before-expansion test over a directory, the unreadable-named-
      directory branch, shared capture and set-up helpers on the base case, and
      the new flag in the parser-flag list.
- [x] `README.md` -- directory argument, recursive flag, pattern support, fixed
      `.jxl.cbz` output, the `.jxl.cbz` skip, sorted order, dedupe, and that an
      empty match set exits 0.

**Acceptance Criteria:**
- Given a directory of two archives and a text file, when passed without the
  recursive flag, then both archives gain a `<name>.jxl.cbz` beside them and the
  text file is untouched.
- Given a directory whose subdirectory holds an archive, when the flag is absent,
  then it is not converted and nothing is printed about it; with the flag
  present, its output lands there, not in the parent.
- Given a run whose output `a.jxl.cbz` sits beside its input `a.cbz`, when the
  directory is rescanned, then the output is not fed back in as an input, no
  `a.jxl.jxl.cbz` appears, and the run's exit code is the same one file would
  give — `EXIT_ENVIRONMENT` naming the existing output.
- Given a directory with no supported file, then the run exits 0 and names the
  directory once.
- Given a quoted pattern that matches nothing, then the run exits 0 with one note
  naming the pattern, the same as an empty directory.
- Given `cbx-jackal lib/ lib/a.cbz` or `'lib/*.cbz' lib`, then `a.cbz` is
  converted once, one report block, and the exit code reflects the conversions.
- Given a directory holding both `a.cbz` and `a.zip`, then one output is written
  — from `a.cbz`, which sorts first — the other is refused by name, and every
  other archive is still converted.
- Given `lib/a/book.cbz` and `lib/b/book.cbz`, when scanned recursively, then both
  are converted, each output beside its own input, and neither is refused.
- Given a directory whose archives were created in a deliberately unsorted order,
  when scanned twice, then both runs process them in the same order, which is not
  the order `os.scandir` returned.
- Given `cjxl` absent and a directory of ten archives, then the preflight message
  appears exactly once and no archive is opened.

## Implementation Notes

Implemented against the **amended** plan: the wildcard-pattern renegotiation in
the Plan Change Log plus the thirteen `patch` findings in the Review Triage Log.
Findings #1 (plan correction), #2 and #3 (rejected `false`) needed no code.
`report.py` is untouched, as the Code Map said.

- `cbx_jackal/discover.py`: `ARCHIVE_SUFFIXES = (".cbz", ".zip")`,
  `OUTPUT_SUFFIX = ".jxl.cbz"`, `GLOB_MAGIC`, `is_archive`, `has_magic`,
  `iter_pattern`, `iter_directory`, private `_walk`, `expand`. `archive.py`
  changed only to read `OUTPUT_SUFFIX` (#8); the `.jxl.cbz` literal now exists
  once in the tree. `OUTPUT_SUFFIX` stayed here rather than moving to
  `archive.py`, because the Code Map makes `discover.OUTPUT_SUFFIX` part of the
  new module's public surface; either direction gives the single owner the
  Tasks ask for.
- `cli.py`: `--recursive`/`-r`, `metavar` `CBZ|DIR|PATTERN`, an `EPILOG` that
  covers patterns and dedupe, and one call to `discover.expand` between the
  preflight and the converter loop. The loop itself is unchanged, so per-path
  error handling is inherited rather than reimplemented.
- **Patterns (#17).** `has_magic` gates `glob`, so a literal path is never
  globbed. `iter_pattern` sorts, filters on `is_archive` (this is what stops
  `'lib/*.cbz'` from feeding `a.jxl.cbz` back in and writing `a.jxl.jxl.cbz`) and
  on `os.path.isfile` (which drops a *directory* called `old.cbz`). It is
  deliberately non-recursive: `**` behaves as `*`, because `--recursive` is the
  one flag that descends and one flag must not mean two behaviours. No match is
  a note to stdout and exit 0, exactly like an empty directory.
- **Dedupe (#5).** Keyed on the path as written, first mention wins. `lib lib`,
  `lib lib/a.cbz` and `'lib/*.cbz' lib` each yield one report block per archive;
  before this the second pass refused the output the run had just written and
  downgraded a healthy batch to exit 2. The empty-directory note now keys off
  the scan being empty, not off the scan adding anything new, so a directory
  whose archives were all already reached is not reported as empty.
- **Paths as typed (#4).** `abspath` is gone from `_walk`; `os.scandir` is given
  the path as written, so `entry.path` inherits it. `destination_for` still
  absolutises the destination on its own.
- **Symlinks (#7).** Resolved toward the Design Notes: a symlink *found inside a
  scan* is skipped, a symlink *named on the command line* is followed. The code
  already did this; the module docstring and the README were what claimed
  otherwise, and both now say "during a scan". `test_a_named_symlinked_directory_is_followed`
  pins the named half, which previously had no test.
- **Dead code (#6)** removed: `os.path.isdir` already swallows `(OSError,
  ValueError)` and returns `False`, so the `try`/`except` around it could never
  fire. **Unused bindings (#9)** fixed by interpolating the exception into both
  walk warnings, matching `cli.py` and `archive.py`.
- **Fixture shape (#10).** `make_archive` is now a method on `ArchiveTestCase`
  with the join documented, so `make_archive(self.tmp, "c.cbz")` is a sibling
  file. The old call built a *directory* named `c.cbz` and passed the mixed-list
  row by accident. The row is now built as the matrix describes: `lib/` with
  `a.cbz` and `b.zip`, plus an explicit `c.cbz`, all three reported in order.
- **Shared helpers (#15).** `capture`, `make_dir`, `make_archive` and
  `report_sources` live on `ArchiveTestCase` in `tests/helpers.py`. The three
  verbatim `capture` copies and the two `setUp`s that only re-registered an
  `rmtree` the base class already runs are gone; the recursion test's inline
  `src -> dest` parser became `report_sources`, which is the same parse.
- Two calls the plan left open, both settled toward the existing error contract:
  the empty-match note goes to **stdout** for both an empty directory and an
  empty pattern, so it sits beside the report blocks rather than reading as a
  warning against exit 0; and an unreadable *named* directory is handed on to
  the converter, which reports `cannot read` for it exactly as it does for any
  path it cannot open (#13 now tests that branch). A directory the owner did not
  name — a subdirectory one level down — is warned about and skipped, which is
  what the matrix specifies.
- `uv.lock` is not present; the tooling run that produced one was done without
  `uv`, and it is in no manifest, so nothing to remove or commit.
- #16 was already satisfied: `plan-directory-discovery.md` ends with a newline in
  the revision reviewed here. `discover.py` did not, and now does, matching the
  rest of `cbx_jackal/`.
- **Verification.** `python3 -m unittest discover -s tests` → `Ran 214 tests ...
  OK`, zero skips (so the symlink and permission-dependent rows executed rather
  than being filtered out). `pyright` → `0 errors`. All four plan `Verification`
  commands behave as specified, including `'tests/fixtures/nope*.cbz'` → one
  note, exit 0, nothing written. Matrix audit: every row of the amended matrix,
  including the five pattern rows, has a covering test.
- **Mutation check.** Ten behaviours were mutated to confirm the tests bite
  rather than merely pass: removing either sort, removing dedupe, restoring
  `abspath`, dropping the `is_archive` or `isfile` filter from `iter_pattern`,
  forcing `has_magic` false, breaking case-insensitive matching, splitting
  `OUTPUT_SUFFIX` between the two modules, and moving `expand` above the
  preflight. All ten fail the suite. #6 is the exception and cannot be caught
  this way: it is a deletion of code no input can reach.
- Weak spot worth a reviewer's eye, unchanged from the first implementation: in
  `test_one_stem_two_suffixes_converts_one_and_refuses_the_other` the ordering
  assertion falls back to comparing against `len(out)` when the losing archive's
  report line is absent from stdout, which makes that branch close to trivially
  true. The refusal itself is asserted on stderr by path, so the row is still
  covered; only the ordering half is weakly pinned. The triage log records the
  mutation evidence that it is not vacuous.

## Plan Change Log

**Iteration 0, review finding 1 (matrix row "Previous run's output").** The Quick
lens found that rescanning a converted directory exits 2 with an
`already exists` refusal, while the matrix row's error column claimed *no error*.
Triggering finding: the divergence above, verified by probe. Amended: the row's
error column now reads `EXIT_ENVIRONMENT`, and the acceptance criterion now
demands the same exit code a single file would give — the row previously read
"only `a.cbz` is converted", which was also untrue, since `a.cbz` is refused. The
**code was already correct and was not changed**; the matrix column was the
defect. Known-bad state avoided: "fixing" the code to exit 0 would have made a
directory scan behave differently from a single-file invocation, and would have
quietly absorbed `--force`. Human ruling: rescan stays exit 2, identical for a
file and for that file inside a directory.

**Iteration 0, human renegotiation — wildcard patterns.** Glob support was
added to the frozen block, replacing the standing `Never: no glob or pattern
arguments`. Triggering finding: the human asked whether Python can expand
`dir1/name*.cbz` natively (it can — `glob`, stdlib, verified on this interpreter)
and ruled for it. Amended: `Approach` now covers file, directory, or pattern;
`paths` stays `nargs="+"`; determinism now covers `glob`'s filesystem order;
dedupe and the metacharacter rule became `Always`; five pattern rows were added
to the matrix; four acceptance criteria added; `glob` replaced `os.scandir` as an
allowed primitive in `Never`. Known-bad state avoided: the previous revision
forbade patterns outright, so keeping the ban would have shipped a CLI whose
behaviour contradicted its own shell. KEEP instructions for re-derivation:
`nargs="+"` must stay — the human considered restricting to a single input and
rejected it, because multiple paths are existing tested capability; a pattern
matching nothing must exit 0, not 2, the same as an empty directory; and
literal paths must never be glob-expanded.

## Review Triage Log

Quick lens (`review: quick`, iteration 0). Every claim below was verified against
the tree at `c8ae047` plus this diff, not taken on the lens's word.

| # | Finding | Verdict | Evidence |
|---|---|---|---|
| 1 | Matrix row "Previous run's output" says *no error*, but a rescan of a converted directory exits 2 with an `already exists` refusal | `medium` | Probed: `cbx-jackal rel/lib` twice → rc 0 then rc 2, stderr `a.jxl.cbz already exists; pass --force`. The scan *does* skip `a.jxl.cbz` (`is_archive`), but the surviving `a.cbz` then hits `Converter.convert`'s `OutputExistsError` (`archive.py:224`). Real user-visible surprise on the most natural second command, and it contradicts the matrix's own error column. |
| 2 | Ordering assertion in the one-stem-two-suffixes test is near-trivially true (`else len(out)`) | `false` | Mutated `sorted(...)` to `reverse=True`: the test errors, because `a.zip` then wins and `out.index("a.cbz -> ")` raises `ValueError`. The assertion does bite. It bites by way of an *absent* key rather than a comparison, which is fragile but not vacuous. |
| 3 | The "not the order `os.scandir` returned" clause is unasserted | `false` | Mutated away the sort entirely (`list(entries)`): `Ran 4 tests ... FAILED (failures=1)` on the expected-order list. The hardcoded expectation is order-bearing and catches removal of the sort on this filesystem. |
| 4 | `abspath` in `_walk` makes directory runs report absolute paths while file runs echo the typed path | `medium` | Probed: `cbx-jackal rel/lib/a.cbz` → `rel/lib/a.cbz -> /abs/...`; `cbx-jackal rel/lib` → `/abs/rel/lib/a.cbz -> /abs/...`. Contradicts the README example (`README.md:138`) and makes recursive reports noisier. `destination_for` already absolutises independently, so `abspath` buys nothing. |
| 5 | A directory named twice, or a directory plus a file inside it, converts the same archive twice | `medium` | Probed `cbx-jackal lib lib/a.cbz --force` → rc 0 with two identical report blocks. Without `--force` the second pass raises `OutputExistsError`, downgrading a healthy batch to exit 2. `expand` appends with no dedupe. Introduced by the scan: a hand-written path list could not produce this. |
| 6 | `try/except OSError` around `os.path.isdir` is unreachable | `low` | `inspect.getsource(os.path.isdir)` shows it already catches `(OSError, ValueError)` and returns `False`. Dead code implying a recovery path that does not exist. |
| 7 | README and the module docstring claim symlinks are never followed, but a symlinked directory *named on the command line* is scanned | `medium` | Probed `cbx-jackal lib/linkdir` with `lib/linkdir -> /abs/real` → rc 0, converted `/abs/real/d.cbz`, and wrote `d.jxl.cbz` beside the target, outside `lib`. `expand` decides with `os.path.isdir`, which follows links; only entries *inside* a scan use `follow_symlinks=False`. The docstring's "could loop forever" rationale does not cover the named case. No test. |
| 8 | `OUTPUT_SUFFIX` duplicates the `.jxl.cbz` literal in `archive.destination_for` | `medium` | `discover.py:40` and `archive.py:102` declare the same string independently. Harm is named: changing the output suffix would leave the scan skipping `.jxl.cbz` while the converter writes `.jxl.zip`, recreating the `a.jxl.jxl.cbz` the skip exists to prevent. The one guard test covers only the `.cbz` case. |
| 9 | `except OSError as exc:` binds `exc` and never uses it | `low` | `discover.py:81,84` interpolates `top`, not `exc`, so `Permission denied` is dropped. Every other handler in the codebase interpolates the exception (`cli.py:121`, `archive.py:232`). |
| 10 | `make_archive(self.path("c.cbz"), "c.cbz", …)` builds a *directory* named `c.cbz`, not a sibling file | `medium` | `make_archive` joins `name` onto `directory` (`tests/test_archive.py:447`), and `build_zip` makedirs the parent, so the fixture is `<tmp>/c.cbz/c.cbz`. The test passes, but the matrix row "`cbx-jackal lib/ c.cbz`, all three converted" — a directory beside a sibling archive — is covered only by accident, via a shape the scan never produces for an explicit argument. |
| 11 | Case-insensitive extension matching is documented and implemented but untested | `medium` | `discover.py:52` lowercases and `README.md:145` promises "any case"; every new test uses lowercase names. Probed working (`Alpha.CBZ`, `beta.ZIP` both convert), but a regression to case-sensitive comparison would silently drop every uppercase archive from every scan, with the suite green. |
| 12 | "Preflight runs before any archive opens" has no test for the directory case | `medium` | Probed with `PATH=/nonexistent-bin`: one `cjxl was not found on PATH` line, rc 2, no archive opened — correct, but `MissingDependency` passes a single *file*, so it holds wherever `expand` sits. Moving expansion above the preflight leaves all 188 tests green. |
| 13 | The `nested=True/False` split in `_walk` has no test on its `raise` path | `medium` | An unreadable *named* directory (`chmod 000`) is handed to the converter (`rc 1`, `cannot read … Permission denied`), which is the subtle branch of the new module; only the *nested* half is tested, and the nonexistent-path tests fail earlier, at `os.path.isdir`. |
| 14 | `is_archive`, `ARCHIVE_SUFFIXES`, `OUTPUT_SUFFIX` get no direct unit test | `medium` | Three of the six names the Code Map designates as `discover.py`'s public surface are reached only indirectly through `expand`; `iter_directory` by contrast is tested directly. |
| 15 | `capture` and `setUp` are duplicated across `DirectoryDiscovery` and `RecursiveDiscovery` | `low` | Three verbatim copies of the redirect-based capture helper (`tests/test_archive.py:1452`, `1616`, `1688`) and two identical `setUp`s whose `rmtree` cleanup already runs via `ArchiveTestCase.setUp` (`helpers.py:109`). Two copies of a helper drift; that is the named harm. |
| 16 | Plan file has no trailing newline | `low` | `\ No newline at end of file` on the new plan. Cosmetic, fixed alongside. |

**Routing.** #1 resolved as a **plan** correction — the code was right, the matrix
error column was wrong; see the Plan Change Log, and the human confirmed rescan
stays exit 2. #4, #5, #6, #7, #8, #9, #10, #11, #12, #13, #14, #15, #16 are
**patch** — each verified, each a direct correction or deletion with no new public
surface beyond the `--recursive` flag and pattern support the human approved. #2
and #3 are rejected as `false`, with the mutation evidence above. Glob support
(#17, raised by the human mid-review, not by the lens) re-enters through the
frozen block as a renegotiation, not as a patch.

| # | Finding | Verdict | Evidence |
|---|---|---|---|
| 17 | Wildcard patterns unsupported | `medium` | The human asked and ruled for it. `glob` expands `dir1/name*.cbz` natively and is stdlib, so it adds no dependency. Three real constraints surfaced while verifying: the shell expands unquoted patterns before the tool sees them, `glob` returns filesystem order needing `sorted()`, and `[]` for no match had to be distinguished from an empty directory — the human ruled it is the same case, exit 0. |

## Design Notes

`expand` returns a flat list of file paths and nothing else, so the CLI loop keeps
its shape and inherits the existing per-path error handling. The sort belongs in
`iter_directory` over each directory's own entries, not in `expand` over the
finished list: a whole-list sort interleaves the same files either way, differing
only in where the seam falls, and neither prevents a collision that mirroring the
output tree does not already prevent.

Three things `expand` decides per argument, in this order: is it a pattern, a
directory, or a literal. `glob` handles patterns and returns filesystem order, so
it needs the same `sorted()` as a scan. A literal path skips `glob` entirely —
globbing `a*.cbz` when a file is genuinely called that would convert a different
file than the user named.

Filtering by extension matters — otherwise a scan feeds `notes.txt` to `zipfile`
and an ordinary folder becomes a wall of `cannot read` failures.

Symlinks are skipped for files and directories *found inside a scan*, which is
where the loop hazard is. A symlink named directly on the command line is
followed, because the user named it; the README must say "during a scan" rather
than claim symlinks are never followed.

Dedup keys on the path as written, so `lib/a.cbz` named twice collapses but
`lib/./a.cbz` and `lib/a.cbz` do not — that is a caller mistake, and `normpath`
would change the reported path the user typed.

`abspath` is deliberately absent from the walk. The converter's
`destination_for` already absolutises the destination on its own, and echoing the
path as typed is what a single-file invocation has always done.

## Verification

**Commands:**
- `python3 -m unittest discover -s tests` -- expected: all pass, no skips
- `pyright` -- expected: no errors
- `python3 -m cbx_jackal.cli tests/fixtures --dry-run` -- expected: `sample.cbz`
  reported; the `.jpg`, `.png` and `.py` beside it ignored
- `python3 -m cbx_jackal.cli 'tests/fixtures/sample*.cbz' --dry-run` -- expected:
  `sample.cbz` reported; the `.jpg` files sharing the prefix ignored
- `python3 -m cbx_jackal.cli 'tests/fixtures/nope*.cbz'` -- expected: one note,
  exit 0, nothing written
