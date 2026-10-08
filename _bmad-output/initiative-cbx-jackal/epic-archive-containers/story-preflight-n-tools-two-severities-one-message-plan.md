---
title: 'Preflight: N tools, two severities, one message'
type: 'feature'
ticket: '3'
created: '2026-10-08'
status: 'built'
baseline_revision: '927c658'
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

**Problem:** Entry 2's check stops the whole run when `7z` is absent, so a library holding one CB7 beside
forty CBZs converts nothing. Contract 1.5 fixed the shape it should have: N tools, each with a severity, one
message naming every missing tool rather than one per tool, and an input-driven tool refusing only the inputs
that need it.

**Approach:** Replace the two ad-hoc check functions with one tool registry — each tool carrying its name,
its install guidance and whether its absence stops the run or only skips inputs — plus a single message
builder. Then stage the checks: the stop-tools before expansion, the input-driven tools after it.

## Boundaries & Constraints

**Always:** One message names every missing tool, each with its own guidance and whether it stops the run or
skips inputs, in severity order. `cjxl` stays checked before expansion; input-driven tools after it, because
only the expanded set knows they are needed. An input-driven absence refuses only the inputs that need it,
converts the rest, and exits 2.

**Never:** `magick` is not added here — entry 1.11 of `epic-bounded-downscaling` adds it. The reader, the
seam, `classify` and the naming rule are untouched. No tool is bundled, and the existing platform guidance
lines are kept verbatim.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| `cjxl` absent | any input | nothing opened | one message naming `cjxl`, exit 2 |
| `7z` absent, a CB7 beside a CBZ | the CBZ converts, the CB7 is refused | one message naming `7z`, exit 2 |
| `7z` absent, only CBZs | no `7z` check runs at all | none; exit 0 |
| both absent | any input | nothing opened | one message naming `cjxl`; the run stops before expansion, so `7z` is not yet known to be needed |
| all present | any input | unchanged from today | none |

</frozen-after-approval>

## Code Map

- `cbx_jackal/preflight.py` — the whole entry lives here plus the call sites. `TOOL`/`SEVENZIP` at `:7-11`,
  the two message templates at `:13-42`, `missing_tool_message:45`, `check:55`, `check_sevenzip:67`. The two
  check functions and the duplicated template are what this replaces.
- `cbx_jackal/cli.py:161-180` — the two check sites: `cjxl` before `discover.expand`, the `7z` check after
  it, and the loop that follows. The `requires_sevenzip` import at `:13`.
- `cbx_jackal/archive.py` — `requires_sevenzip` reads the suffix off `SOURCE_READERS`, so a tool's input
  need is derived from the registry rather than a second suffix list. Untouched here.
- `tests/test_archive.py` — `MissingDependency` and `SevenZipPreflight` hold today's coverage; both are the
  model for the matrix rows.

## Tasks & Acceptance

**Execution:**
- [ ] `cbx_jackal/preflight.py` -- one `Tool` record (name, guidance, and whether its absence stops the run)
  and a `TOOLS` registry; `missing(names)` returning the absent ones and `missing_message(tools)` building
  the single message -- a header naming every missing tool, then each one's guidance and its severity, in
  severity order. Keep both platform-guidance texts verbatim.
- [ ] `cbx_jackal/cli.py` -- stage the checks through the registry: stop-tools before `discover.expand`,
  input-driven tools after it, one message each time. An input-driven absence refuses only the inputs that
  need it, one line each, converts the rest, and exits 2.
- [ ] `tests/test_archive.py` -- the matrix: a CB7 beside a CBZ with `7z` absent converts the CBZ and refuses
  the CB7; an all-CBZ list never checks `7z`; `cjxl` absent still names `cjxl` alone.

**Acceptance Criteria:**
- Given `7z` absent and a CB7 beside a CBZ, when the run starts, then the CBZ converts, the CB7 is refused
  with one line, one message names `7z`, and the exit code is 2.
- Given `7z` absent and only CBZs, when the run starts, then it converts normally and exits 0, having never
  looked for `7z`.
- Given `cjxl` absent, when the run starts, then nothing is opened, one message names `cjxl`, and the exit
  code is 2.
- Given the whole suite, when it runs with all four tools on PATH, then it reports OK with no test edited.

## Implementation Notes

Implemented by a coding subagent, judged against the diff, and the review's findings re-verified by running
them rather than reading them.

**One finding was disproved by running the builder.** The review held that the boolean `stops_run` could not
express contract 1.5's three-level severity order, so entry 1.11 could not reuse the message builder. It can:
the sort is stable, so it groups by severity and preserves registry order within a group, and with `magick`
registered the header reads `cjxl, magick, 7z` — exactly the contract's order. The plan's claim that 1.11
reuses the builder unchanged holds.

**The one real divergence is deferred, not hidden.** A run missing both `cjxl` and `7z` names only `cjxl`,
because the run stops before expansion. The plan's frozen matrix and Design Notes specify it, and the fix is
a staging change belonging to entry 1.11 — a flag-driven check can run after expansion, since nothing about a
flag needs the scan. Recorded in `deferred-work.md` with its evidence.

**Two functions survive that this entry's task said it replaces.** `check` and `missing_tool_message` are now
dead in production — the CLI stages through `missing` and `missing_message` — but six existing test methods
call them, and the plan's acceptance criterion forbids editing tests. Their docstrings were corrected to say
exactly that, rather than the "single-tool call sites" the first pass claimed. Removing them and updating
those tests is entry 10's sweep.

Two smaller corrections: the message header no longer calls an input-driven tool "required" while the block
beneath it says otherwise, and `SevenZipPreflight`'s class docstring no longer claims a `.cb7` is refused
before anything is opened when its own member asserts a CBZ beside it converts.

Final state: 243 tests OK with all four tools on PATH, zero skips, `pyright` clean at the 3.9 floor. Baseline
was 240.

## Plan Change Log

## Review Triage Log

Quick lens, 5 findings, pinned `review: 'quick'`. One was disproved by running the builder.

| # | Finding | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | The shared header calls every missing tool "required", contradicting the input-driven block beneath it | `low` | `patch` | Confirmed: `missing_message` prints `missing required tools: cjxl, magick, 7z` and then, for `7z`, "needed only by some inputs". Contract 1.5 has each tool state its own severity; the header must not pre-empt it. |
| 2 | `missing_tool_message` and `check` are dead in production and their docstring misstates why they were kept | `low` | `patch` | Confirmed: no `cbx_jackal/` module calls either; only `tests/test_archive.py` does. The docstring claims "single-tool call sites" that do not exist. Kept because the plan's AC forbids editing tests; the docstring is corrected to say so, and the sweep (entry 10) is the home for removing them. |
| 3 | The two-stage design cannot name `cjxl` and `7z` together when both are absent | `medium` | `defer` | Real, and the plan's own frozen matrix row and Design Notes already specify and record it: the run stops before expansion, so `7z`'s need is unknowable. The fix is a staging or contract change owned by entry 1.11, which is the entry that must reconcile 1.5's "names every missing tool" with its own placement of a flag-driven check before expansion. |
| 4 | The boolean `stops_run` cannot express contract 1.5's three-level severity order, so 1.11 cannot reuse the builder | `false` | — | Disproved by running it: with `magick` registered, `missing_message` orders `cjxl, magick, 7z` — exactly 1.5's order — because the sort is stable, grouping by severity and preserving registry order within a group. The builder is reused unchanged. |
| 5 | `SevenZipPreflight`'s class docstring is falsified by its own new member | `low` | `patch` | Confirmed: the docstring says a `.cb7` is "refused before anything is opened" while `test_a_cb7_beside_a_cbz_converts_the_cbz_and_refuses_the_cb7` asserts the CBZ converts. Direct correction. |

No `intent_gap` and no `bad_plan`: finding 3's divergence is inside the frozen matrix by design, and its fix
belongs to another entry. No loopback; `review_loop_iteration` stays 0.

## Design Notes

The registry carries the severity, not the requirement source. A tool is "stop" or "skip"; whether it is
required by a flag or by an input is a fact about the caller, and only the caller knows it. That keeps
`preflight.py` free of both the CLI's flags and the reader registry, and it is what lets entry 1.11 add
`magick` by registering it and calling the same builder.

Recorded, not resolved here: contract 1.5 asserts that a run missing both `magick` and `7z` names both in one
message, while also placing `magick` before expansion and `7z` after — and one message across two stages is
not possible. Entry 1.11 owns the reconciliation, and the likely answer is that a flag-driven check belongs
after expansion too, since nothing about a flag needs the scan to have run. This entry leaves both the
registry and the staging explicit so that decision is a call site, not a rewrite.

## Verification

**Commands:**
- `python3 -m unittest discover -s tests` -- expected: `OK`, the pre-change count plus the new ones, zero
  failures, zero skips.
- `pyright` -- expected: no errors at the 3.9 floor `pyrightconfig.json` pins.

Confirm `cjxl`, `djxl`, `jxlinfo` and `7z` are on PATH first: without them the suite still reports OK while
most of it skips.
