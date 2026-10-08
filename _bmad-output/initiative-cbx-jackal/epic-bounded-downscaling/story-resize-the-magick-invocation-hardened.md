---
id: 9
type: story
title: "Resize: the magick invocation hardened"
parent: epic-bounded-downscaling
covers: [R1]
after: [8]
hitl: false
risk: medium
---

# Resize: the magick invocation hardened

## Description

Carries the spike's invocation to the full contract: the trailing > as an explicit downsize guard, -auto-orient, -quality with the confirmed value, the target box supplied by entry 8 so magick has no fit decision left to make, temp file discipline and cleanup on every exit path matching encode.run, and magick's non-zero exit as the not-converted oracle per entry 4's vocabulary. Creates cbx_jackal/resize.py.

## Acceptance Criteria

Verify: A magick failure on one page leaves that page copied through under its original name with its own report line and a non-zero exit, no temp file survives any exit path, and the intermediate is encoded at the confirmed quality with the confirmed interaction against run-level --quality.

## References

- parent — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md
- contract — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md, section Notes, the decision of 2026-10-08. The intermediate is a PNG, encoded at `cjxl -q 100` with effort left at the default. `magick`'s own `-quality` is fidelity-neutral at every value measured and is confirmed as 100. The `-q 100` is mandatory: `cjxl` with no flags on a PNG intermediate lost 195,790 pixels on the 2026-10-08 re-measurement, so `build_command` needs a second branch and "the lossless path passes no flags at all" holds only for JPEG input.
- contract — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md, section Notes, entry 4's vocabulary of 2026-10-08. Every downscaled page is `pixels`: exact pixels survive, the source JPEG file does not.
- conflict — _bmad-output/initiative-cbx-jackal/change-bounded-page-downscaling/change-bounded-page-downscaling.md, sections 4.1, the conventions reversal, the `jxlinfo` reversal and the 4.8 table all assume the JPEG intermediate and say a downscaled page keeps reconstruction data. With a PNG intermediate there is none. Entry 1.7 carries the correction into the spec.

## Notes

- Settled 2026-10-08: the intermediate is a PNG, and this entry's `unknown` is closed. Every downscaled page
  is `pixels` in entry 4's vocabulary, so `djxl` returns a PNG and `jxlinfo` reports no JPEG reconstruction
  data. The guarantee is stronger and different rather than weaker: exact pixels, source JPEG not recoverable.
- Cost accepted: a downscaled 200-page book goes from about 9s to about 58s, and only pages actually
  downscaled pay it. `cjxl` effort stays at the default on this path — measured there, effort is not free the
  way it is on JPEG input, but a single synthetic page is no basis for tuning against real comic art.

