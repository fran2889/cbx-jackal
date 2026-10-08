---
id: 3
type: story
title: "Contract: destination naming and the flag namespace"
parent: epic-bounded-downscaling
covers: [R1]
after: []
hitl: true
risk: low
---

# Contract: destination naming and the flag namespace

## Description

Fixes the destination name across formats, geometry and input containers, and where --format, --max-width, --max-height and --quality live and which apply where. --max-width and --max-height are combinable, per CAP-6's and/or; this entry must say so explicitly rather than leave mutual exclusion open. Records the ruling in this epic's envelope, not in the spec.

## Acceptance Criteria

Verify: The rules are written down and a reader can name the output of any combination of format, box and input container without asking.

## References

- parent — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md
- contract — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md, section Notes, the ruling of 2026-10-08. The destination is `<stem>.<format>.cbz`, the box never appears in the name, the two box flags are combinable, and `--quality` keeps one meaning across every format.
