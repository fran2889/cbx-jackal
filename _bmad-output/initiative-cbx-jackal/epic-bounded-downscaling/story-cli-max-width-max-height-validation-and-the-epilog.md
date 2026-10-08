---
id: 11
type: story
title: "CLI: --max-width, --max-height, validation and the epilog"
parent: epic-bounded-downscaling
covers: [R1]
after: [0, 0a, 3, 5, 10]
hitl: false
risk: medium
---

# CLI: --max-width, --max-height, validation and the epilog

## Description

The two flags with the validation entry 3 fixed and the conditional preflight entry 5 fixed, reaching the report entry 10 made able to state a downscale. The epilog covers the box, the intermediate, and which tool each run needs.

## Acceptance Criteria

Verify: cbx-jackal --max-width 1600 on a book downsizes the oversized pages; with magick absent and a box requested it exits 2 before any archive opens, naming magick, in one message; with magick absent and no box it runs normally and never checks for it; and with no box at all the run is byte-for-byte the run it is today.

## References

- parent — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md
