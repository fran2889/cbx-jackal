---
title: 'An encrypted archive is refused by name, and the run carries on'
type: 'feature'
ticket: '8'
created: '2026-10-08'
status: 'in-progress'
baseline_revision: '85fa949'
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

**Problem:** An encrypted CB7 or 7Z is already refused without hanging — the reader runs `7z` with stdin
closed — but the owner is told "Break signaled", which names nothing. The epic's decision is that an
encrypted input is refused with a line saying so, exit 1, and every other input still converting.

**Approach:** `7z l -slt` already marks an encrypted entry `Encrypted = +`, so the reader can refuse before
it tries to extract, with a message that names the archive as encrypted.

## Verification

**Commands:**
- `python3 -m unittest discover -s tests` -- expected: `OK`, the pre-change count plus the new ones, zero
  failures, zero skips.
- `pyright` -- expected: no errors at the 3.9 floor `pyrightconfig.json` pins.

Confirm `cjxl`, `djxl`, `jxlinfo` and `7z` are on PATH first.

## Implementation Notes

**Why oneshot:** the reader gains one check and one field, plus tests — no seam, no new interface, well under
a hundred lines. The non-interactive failure and the per-path carry-on already exist; this entry makes the
refusal say what happened.

The detection belongs in the listing step, before extraction, because extraction is where `7z` emits the
unhelpful "Break signaled" — the listing succeeds and already carries the fact.

The "never waits for input" property is structural: the reader passes `stdin=DEVNULL` to every `7z` call. The
test proves it by running the CLI as a subprocess with a live stdin pipe that is never written, so a reader
that let `7z` prompt would block until the timeout rather than return.

</frozen-after-approval>
