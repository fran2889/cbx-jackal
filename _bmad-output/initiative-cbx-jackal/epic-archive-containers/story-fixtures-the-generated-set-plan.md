---
title: 'Fixtures: the generated set'
type: 'feature'
ticket: '4'
created: '2026-10-08'
status: 'built'
baseline_revision: '4bc0655'
route: 'oneshot'
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

**Problem:** `build_7z` is not byte-stable: `7z` embeds the staged files' modification times, which differ on
every run, so a fixture cannot be regenerated identically and any test that pins or hashes one is flaky. The
solid, corrupt and encrypted entries also each build their own fixture ad hoc rather than consuming a named
set.

**Approach:** Pin the staged files' timestamps so the builder is deterministic, and give the fixtures the
later entries consume one home in `tests/helpers.py`.

## Verification

**Commands:**
- `python3 -m unittest discover -s tests` -- expected: `OK`, the pre-change count plus the new ones, zero
  failures, zero skips.
- `pyright` -- expected: no errors at the 3.9 floor `pyrightconfig.json` pins.

Confirm `cjxl`, `djxl`, `jxlinfo` and `7z` are on PATH first.

## Review Triage Log

Quick lens, 5 findings, pinned `review: 'quick'`. F1 was reproduced before its verdict.

| # | Finding | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | `build_7z` updates an existing archive instead of replacing it, so a reused path holds more than `entries` | `medium` | `patch` | Reproduced: building `x.cb7` with `a.txt` then again with `b.txt` lists both. `7z a` merges, and `build_zip` in the same file opens with `"w"`, so the two builders disagreed. Developer harm is silent — a fixture is not what the caller asked for. Fixed by removing the path first. |
| 2 | The solid byte-stability case ran against an archive polluted by the previous iteration | `medium` | `patch` | Same root cause as 1: the loop reused `first.cb7`, so `solid_cb7`'s entries were added to `rich_cb7`'s. Fixed by 1, and the test now reuses a path safely because the builder replaces. |
| 3 | `rich_cb7` and its test claimed every classification but hold neither a directory entry nor a bare `._` file | `low` | `patch` | Confirmed: the listing is `ComicInfo.xml`, `__MACOSX/._page001.jpg`, `extras/note.txt`, `page001.jpg`, so the `__MACOSX` branch is hit, not the bare-`._` one, and no directory entry is staged. The fixture is fine for what the later entries consume; the *name* overclaimed. Renamed to what it asserts. |
| 4 | The diff folded in ticket 3's plan `status` flip | `false` | — | Not a defect: it is the effect of `tickets.py mark 4.3 done`, which writes the plan. Committed separately from this change rather than bundled, so the history stays legible. |
| 5 | `build_7z` and `sevenzip_listing` hardcode `"7z"` while `preflight.SEVENZIP` is the declared source | `low` | `patch` | Confirmed: two literals against a constant the class gate already reads, which is the drift AGENTS.md names for `ZIP_STORED`. Both now read `preflight.SEVENZIP`. `archive.py` carries a third copy from entry 4.2; recorded in `deferred-work.md` for entry 10's sweep. |

No `intent_gap`, no `bad_plan`, no loopback.

## Implementation Notes

**Why oneshot:** roughly seventy lines across two files — a pinned timestamp, a few named builders, and the
byte-stability assertions. One session plans and finishes it, and there is no cross-layer seam to prove.

**The plan's own verify was over-broad, and the test found it.** It required every fixture to be byte-stable,
but an encrypted `7z` cannot be: AES picks a random salt per archive, so two encrypted fixtures built from
identical input differ by design. The encrypted fixture's test now pins that non-determinism and asserts the
property it exists for instead, rather than leaving the next reader to rediscover it. The generated fixtures
that *can* be stable — plain, rich and solid — are asserted stable, which is what the pinned stamp buys.

</frozen-after-approval>
