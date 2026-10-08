---
id: 0
type: story
title: "Core CBZ to JXL transcoder"
parent: epic-bounded-downscaling
after: []
hitl: false
risk: medium
---

# Core CBZ to JXL transcoder

## Description

Foundational feature: CBZ to JXL transcoder CLI that walks a CBZ's entries in stored order, transcodes JPEG pages to JXL via cjxl, copies every other entry byte-for-byte, and writes the result atomically to <name>.jxl.cbz.

## Acceptance Criteria

Verify: python3 -m unittest discover -s tests -v passes; cbx-jackal sample.cbz produces sample.jxl.cbz; djxl round-trip reproduces source JPEG bytes.

## References

- parent — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md
