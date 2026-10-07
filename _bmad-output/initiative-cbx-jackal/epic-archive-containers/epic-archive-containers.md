---
type: epic
title: "Read the archives comic collections actually arrive in"
parent: initiative-cbx-jackal
covers: ["R4"]
after: ["epic-bounded-downscaling"]
assignee: ""
risk: high
---

# Read the archives comic collections actually arrive in

## Description

An owner whose library is RAR, CB7 or 7Z converts it without unpacking it by hand. Read-only on the
container side: `7z` reads all three by content rather than extension, and output stays CBZ, so no
proprietary archiver writer is ever required.

## Outcome

An owner whose collection is not already CBZ can run the same command they run today; entry order, entry
count and entry bytes are preserved exactly as the ZIP path preserves them.

## Requirements

- **R4** — RAR, CB7 and 7Z read as input containers, with output always CBZ. (parent initiative,
  Requirements; origin: owner, 2026-10-06)

## Done when

1. A book in RAR, CB7 or 7Z converts to `<name>.jxl.cbz` with entry order and entry count identical to the
   source, and every non-converted entry byte-identical.
2. A corrupt or unreadable source archive leaves no output at all and exits non-zero, exactly as the ZIP
   path behaves today.
3. `7z` absent, with an input that needs it, exits non-zero before any archive opens, naming `7z` in the
   same message as any other missing tool rather than one message per tool.
4. A solid archive's entries convert correctly, measured against a solid fixture — a member extracted from a
   single-block archive is byte-exact, but re-inserting one member re-deflates the whole stream, so this is
   stated as a known cost rather than left for a reader to discover.
5. ZIP input behaviour is unchanged, byte for byte.
6. `README.md` documents installing `7z` for linux, mac and windows.
7. The released version installs and runs from a clean environment on all three platforms.

## Boundaries

The input container and the external reader for it. Output stays CBZ and the atomic-publish path in
`archive.py` is reused unchanged. Not the target page format (epic-webp-target), geometry
(epic-bounded-downscaling), or the HTML reporting surface (epic-quality-audit).

## References

- parent — _bmad-output/initiative-cbx-jackal/initiative-cbx-jackal.md, section Requirements
- companion — _bmad-output/initiative-cbx-jackal/spec-cbz-jxl/spec-cbz-jxl.md, section Constraints, "ZIP
  entries are STORED, never deflated" and the page-order constraint — both contradicted by this epic and
  the section this epic's spec amendment rewrites
- companion — _bmad-output/initiative-cbx-jackal/spec-cbz-jxl/conventions.md, section Container, for the
  temp-then-`fsync`-then-`os.replace` pattern this epic reuses for a non-ZIP source
- constraint — `AGENTS.md`, the `bmad:context` block: fixtures are load-bearing, and `ZIP_STORED` is
  hardcoded twice at `archive.py:161` and `archive.py:325` and the two sites must agree
- touch point — `discover.py`, via `ARCHIVE_SUFFIXES` at `discover.py:49` and `is_archive` at
  `discover.py:73-82`, without which `book.rar` is never fed to the converter

## Notes

- Measured: `7z` reads rar, cb7 and 7z by content rather than extension; extraction is byte-exact; `7z l`
  on a broken archive returns rc 2, so the failure oracle keeps the shape `cjxl` already has.
- Known cost: re-inserting one member into a solid block re-deflates the whole stream, so pages that were
  never touched get recompressed and the source's internal container layout is not preserved. Entry-level
  byte fidelity holds; layout fidelity does not.
- Touch point: the classification gate in `archive.py:66-95` is shared with epic-bounded-downscaling — both
  rewrite it. This epic waits on that epic's gate contract rather than merging.
- Concurrent edit: this epic and epic-webp-target both write `discover.py` with no dependency between them.
  The edits are disjoint — this epic touches `ARCHIVE_SUFFIXES` at line 49 and `is_archive` at lines 73-82,
  the WebP epic touches `OUTPUT_SUFFIX` at line 55 — so they may run at the same time.
- Open question: `7z` is needed to read and Python `zipfile` to write, so the converter must hold two open
  representations of the same book at once. Whether that is a reader protocol or a staged extraction is a
  design decision for this epic's inception.
- Unknown: whether password-protected RAR or 7Z archives should get an owner-facing message or be skipped
  silently. Not decided here.
