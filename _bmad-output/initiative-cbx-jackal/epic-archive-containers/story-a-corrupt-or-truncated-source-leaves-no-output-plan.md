---
title: 'A corrupt or truncated source leaves no output'
type: 'feature'
ticket: '7'
created: '2026-10-08'
status: 'built'
baseline_revision: '0108cee'
route: 'oneshot'
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

**Problem:** Entry 4.2 proved a `7z` failure becomes an `ArchiveError` with no output and no leaked staging
directory, but only for garbage bytes and a corrupted data region. A truncated archive — the shape a partial
download or a failed copy actually leaves — is untested, and nothing checks the CLI-level behaviour the epic
requires: that a truncated input does not stop a healthy one beside it.

**Approach:** Truncate the rich fixture, assert no output and a non-zero exit with no traceback, and assert a
healthy input in the same run still converts.

## Verification

**Commands:**
- `python3 -m unittest discover -s tests` -- expected: `OK`, the pre-change count plus the new ones, zero
  failures, zero skips.
- `pyright` -- expected: no errors at the 3.9 floor `pyrightconfig.json` pins.

Confirm `cjxl`, `djxl`, `jxlinfo` and `7z` are on PATH first.

## Review Triage Log

Quick lens, 3 findings, pinned `review: 'quick'`. All three mutation-verified and all three right — the first
version asserted less than its names claimed in every case.

| # | Finding | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | The carry-on test cannot detect a CLI that aborts on the first failure, because the healthy input is listed first | `medium` | `patch` | Confirmed: flipping `cli.py`'s `continue` to `break` left both tests green, because `good.cb7` was already converted before `bad.cb7` was opened. Reversing the order makes the mutation fail. The whole point of the test was that a truncated input does not stop a healthy one, so the order was the test. |
| 2 | `assertNoTempFiles` does not see the 7z reader's staging directory | `medium` | `patch` | Confirmed: it scans `self.tmp`, while `SevenZipSource` stages under the system temp with a `cbx-jackal-7z-` prefix. Making `close()` a no-op left both tests green; only 4.2's test caught it, via the `workdirs()` helper. The new tests now use that helper, so the leaked-staging-directory property is re-checked here too. |
| 3 | `assertNotEqual(0, code)` accepts any non-zero code where the entry requires exit 1 | `low` | `patch` | Confirmed: the verify says "exits 1" and the sibling method pins `cli.EXIT_FAILED`. A regression classifying a truncated source as an environment error would have satisfied the weaker assertion. |

No `intent_gap`, no `bad_plan`, no loopback.

## Implementation Notes

**Why oneshot:** two test methods, no production change. The reader already turns a `7z` failure into an
`ArchiveError` and the CLI already carries on per path — this entry proves both for the truncated shape.

Truncation fails at the listing, not the extraction: a `7z` archive carries its header at the end, so cutting
the file removes it. That is why it is a distinct case from 4.2's corrupted-data test, which lists fine and
fails at extraction.

</frozen-after-approval>
