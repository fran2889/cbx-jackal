---
title: 'Solid archives: entries byte-exact, and the cost'
type: 'feature'
ticket: '6'
created: '2026-10-08'
status: 'built'
baseline_revision: '4a2661c'
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

**Problem:** A solid archive is the case that decided the reader's design — extracting one member from a
single block decompresses the whole block — and no test converts one. Every end-to-end CB7 test so far builds
a plain archive, so the property the epic measured is asserted rather than proven.

**Approach:** Convert the solid fixture and assert its entries come out byte-exact, in the source's order and
count, with the untouched entry identical; and record the cost a solid source carries, which entry 9 then
documents for the owner.

## Verification

**Commands:**
- `python3 -m unittest discover -s tests` -- expected: `OK`, the pre-change count plus the new ones, zero
  failures, zero skips.
- `pyright` -- expected: no errors at the 3.9 floor `pyrightconfig.json` pins.

Confirm `cjxl`, `djxl`, `jxlinfo` and `7z` are on PATH first.

## Review Triage Log

Quick lens, 3 findings, pinned `review: 'quick'`. All three mutation-verified before a verdict, and all three
were right.

| # | Finding | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | The test never inspects the converted pages' bytes, so a read mixup passes | `medium` | `patch` | Confirmed: patching `SevenZipSource.read` to hand back `page001`'s bytes for `page002` left it green. The entry's verify says "every entry byte-exact" and the epic's Done-when says the entries "convert correctly", so the pages were the point and only the pass-through was checked. Now each page is asserted to reconstruct to its own source, as the sibling 7z test already does. |
| 2 | The test claims a solid source but would pass against a plain one | `false` | — | Disproved by running it: `7z`'s format is solid *by default*, so `solid=False` still yields `Solid = +` and there is no plain 7z archive to pass against. The lens's own mutation was a no-op. The premise assertion was still added, because a test about a solid source should say so. The same check did surface something real, fixed below: `build_7z`'s `solid` parameter never made anything solid, since `-ms=on` is redundant and only `-ms=off` disables it. |
| 3 | The `7z l -slt` header-skip comprehension is duplicated from another test | `low` | `patch` | Confirmed: two copies of "every `Path =` line except the archive's own". Moved to `sevenzip_entry_names` in the helpers, so the listing format lives in one place. |

No `intent_gap`, no `bad_plan`, no loopback.

## Implementation Notes

**Why oneshot:** one test method and a recorded fact — well under a hundred lines, no seam to prove, no
production code touched. The solid fixture already exists from entry 4.

**The cost, stated precisely so entry 9 can document it.** The output is always a freshly written ZIP, so a
converted book never preserves its source's internal container layout — a solid block is gone, and the same
is true of a deflated ZIP input. What is preserved is entry-level: each untouched entry's bytes are
identical, and order and count are the source's. The reason a solid source costs nothing extra to *read* is
that the reader stages one extraction rather than one per page; that is what would otherwise re-decompress
the block once per member.

</frozen-after-approval>
