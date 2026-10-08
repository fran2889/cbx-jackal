---
id: 1
type: story
title: "Spec: the container model, amended for RAR, CB7 and 7Z inputs"
parent: epic-archive-containers
covers: [R4]
after: [1.5]
hitl: false
risk: low
---

# Spec: the container model, amended for RAR, CB7 and 7Z inputs

## Description

Amends spec-cbz-jxl and both companions so the contract stops forbidding what this epic builds. The spec's Constraints say container handling is Python standard library only, that cjxl is the single external tool, and that page order is the source ZIP's stored order; all three contradict reading RAR, CB7 and 7Z. Reading those is an external-tool step because no standard-library module reads them, while writing stays zipfile, so the output is always ZIP and no proprietary writer is ever needed. CAP-5's success and the assumptions are amended to the preflight shape entry 1.5 fixed: tools carry a severity, and one that only some inputs need refuses only those inputs rather than the whole run. The heading, which names CBZ as the input, is corrected. This amends the text CAP-6 leaves behind rather than the spec as it stands today, so it carries entry 1.7's edit forward instead of reverting it. It does not touch the output name, which is R2's amendment and which entry 1.3 already rules on.

## Acceptance Criteria

Verify: The spec no longer contradicts this epic: reading a non-ZIP container is named as an external-tool step, page order is the source container's rather than the source ZIP's, the STORED rule is stated about output rather than about input, and CAP-5 states both severities including the carry-on behaviour entry 1.5 fixed. CAP-1 through CAP-4 are untouched and CAP-5's success is extended rather than replaced, so every existing success test still passes. The external-tool constraint is generalised to N tools rather than narrowed back to cjxl alone, leaving entry 1.7 free to apply CAP-6 on top, and a reader can tell from the spec alone which tools a given run needs.

## References

- parent — _bmad-output/initiative-cbx-jackal/epic-archive-containers/epic-archive-containers.md
