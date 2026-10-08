---
id: 6
type: story
title: "Contract: the classification gate, with a stub"
parent: epic-bounded-downscaling
covers: [R1]
after: [3, 16]
hitl: true
risk: medium
---

# Contract: the classification gate, with a stub

## Description

The interface at archive.py:66-95 that separates a raw page from an archive entry, extended so a source that is not a ZIP can be represented, with a stub epic-archive-containers can fill. Implements the naming rule entry 3 fixed, which entry 16 makes readable from a flag. Records the ruling in this epic's envelope.

## Acceptance Criteria

Verify: The interface is written down and the stub classifies a page, a resource fork, a directory and a source whose container it does not recognise, without naming any real archiver.

## Boundaries

- `classify` keeps deciding from the name alone. The extension is a seam below the gate, not a change to it,
  and making it content-aware is not an improvement — the name-only property is what makes CAP-3's
  pass-through guarantee hold.
- No reader is chosen here. Reader protocol against staged extraction is `epic-archive-containers`' call at
  its inception. The interface is identical either way, so deciding it now would be a guess about cost.
- The stub names no real archiver, and falls back to no other reader: a source that does not match its
  declared suffix is an unreadable archive, exit 1, the answer it gets today.

## References

- parent — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md
- contract — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md, section Notes, the ruling of 2026-10-08. A source offers entry names in supplied order, the bytes of one named entry, and an optional per-entry output template. The template's default is documented rather than required, so a reader that cannot supply metadata degrades instead of becoming unreadable.
- constraint — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md, section Notes, the preflight ruling of 2026-10-08. A reader is chosen by the recognised input suffix with no fallback, and by-content detection belongs to the reader at open time.
- contract — _bmad-output/initiative-cbx-jackal/epic-archive-containers/epic-archive-containers.md, section References, the preflight contract it already cites. That epic may add to this seam's contract; it may not relax the clause bounding a reader's filesystem effects to regular files in a directory the tool owns.
