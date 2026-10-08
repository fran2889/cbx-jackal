---
id: 5
type: story
title: "Contract: preflight shape for N external tools"
parent: epic-bounded-downscaling
covers: [R1]
after: []
hitl: true
risk: low
---

# Contract: preflight shape for N external tools

## Description

cjxl always; each further tool conditional on the flags that need it; one message listing everything missing rather than one message per tool. Must also rule whether a dry run with a box requires magick, since a dry run really invokes the toolchain. Records the ruling in this epic's envelope.

## Acceptance Criteria

Verify: The shape is written down, including the exit code, the single-message rule, and whether presence is decided by flag presence or by what the run will actually touch.

## References

- parent — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md
- contract — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md, section Notes, the ruling of 2026-10-08. Two severities: `cjxl` is unconditional, `magick` is flag-driven and both abort; `7z` is input-driven, decided by the recognised input suffix, and refuses only the inputs that need it. One message names every missing tool, and a dry run needs exactly what the real run would.
- amendment — _bmad-output/initiative-cbx-jackal/epic-archive-containers/epic-archive-containers.md, Done-when 3, amended 2026-10-08 to match this ruling.
