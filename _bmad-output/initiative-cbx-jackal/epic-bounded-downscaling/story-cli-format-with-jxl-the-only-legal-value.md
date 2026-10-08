---
id: 16
type: story
title: "CLI: --format, with jxl the only legal value"
parent: epic-bounded-downscaling
covers: [R1]
after: [3]
hitl: false
risk: low
---

# CLI: --format, with jxl the only legal value

## Description

Implements the format segment of the naming rule entry 3 fixed, so entry 6 has a format to read. The flag is accepted and validated, jxl is the default and the only value that converts today, and an unknown value is a usage error rather than a silent fallback. Webp arrives with epic-webp-target, which finds the flag and the naming rule already in place. Folds the rescan skip from one constant to every <stem>.<format>.cbz, so the segment the name needs is read from one place.

## Acceptance Criteria

Verify: cbx-jackal --format jxl on a book writes book.jxl.cbz, byte for byte the run without the flag; --format webp exits 2 with a usage message naming webp as unsupported, before any archive opens; rescanning a directory already holding book.jxl.cbz skips it rather than producing book.jxl.jxl.cbz; and no existing test was edited to accommodate this entry.

## Boundaries

- `classify` is not touched here. It builds the name of an entry *inside* the archive, which is a different
  name from the archive's own, and with `jxl` the only legal value an entry name does not change. Entry 6
  owns that gate and reads the format then; two entries in one function would put the naming rule's two
  halves in the wrong order.
- The format is threaded as a defaulted value, never a required one. `--format jxl` has to be byte-for-byte
  the run without the flag, which a required parameter cannot be.
- The output suffix is split, not duplicated: the `.cbz` container part stays constant and the format segment
  gains its own declaration, both read by the write path and by the scan's skip. `destination_for`'s warning
  about those two drifting is load-bearing and survives the split verbatim — it is the reason the skip and
  the write name share one declaration, and the `a.jxl.jxl.cbz` it prevents is exactly what the rescan clause
  of the verify tests.

## References

- parent — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md
- contract — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md, section Notes, the naming ruling of 2026-10-08. The destination is `<stem>.<format>.cbz`, and the rescan skip has to cover every format rather than one constant.
