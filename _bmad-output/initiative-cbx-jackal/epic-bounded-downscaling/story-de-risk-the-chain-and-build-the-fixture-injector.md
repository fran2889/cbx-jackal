---
id: 1
type: spike
title: "De-risk the chain and build the fixture injector"
parent: epic-bounded-downscaling
covers: []
after: [0, "0a"]
hitl: false
risk: medium
---

# De-risk the chain and build the fixture injector

## Description

Proves byte-injected orientation bytes to a downscaled page in a published archive, through the existing Converter with the box passed programmatically. Keeps the EXIF APP1 injector, because the ImageMagick build in use cannot write an orientation tag and every later fixture needs it; throws away the rest of the chain.

## Acceptance Criteria

A synthetic book with one oversized tagged page converts via Converter called directly, that page downscaled against its display width, and the injector writes a tag ImageMagick then reads back.

## Implementation Notes

This is a **spike** rather than a story. The risk this epic carries is technical feasibility, not integration. Entry 1 re-proves the chain (magick → cjxl → djxl) on the real fixture path and, more usefully, settles that the EXIF injector works, which every later fixture depends on.

The injector must:
1. Take a raw JPEG byte sequence
2. Inject an EXIF APP1 segment with a specified orientation value
3. Preserve all other JPEG data unchanged
4. Work for all eight EXIF orientation values (1-8)

The chain test must:
1. Create a synthetic oversized JPEG page
2. Inject an EXIF orientation tag (e.g., orientation 6 = rotated 90° CW)
3. Pass the page through the Converter with downscaling enabled
4. Verify the downscaled page has correct dimensions relative to display orientation
5. Verify ImageMagick can read the injected orientation from both the original and downscaled page

## Key Decisions

- The intermediate format for downscaling is PNG (decided 2026-10-08)
- `cjxl` must be invoked with `-q 100` on PNG intermediates to ensure pixel-perfect encoding
- ImageMagick's `-quality` flag is fidelity-neutral on this path, confirmed at 100
- `cjxl` effort stays at default (7) on the PNG path

## References

- parent — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md
- decision — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md, section Notes, the decision of 2026-10-08: intermediate is PNG, encoded at cjxl -q 100
- contract — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md, section Notes, entry 4's vocabulary: every downscaled page is `pixels` (exact pixels survive, source JPEG not recoverable)
