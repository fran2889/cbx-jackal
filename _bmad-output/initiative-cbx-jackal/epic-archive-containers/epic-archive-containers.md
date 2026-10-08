---
type: epic
title: "Read the archives comic collections actually arrive in"
parent: initiative-cbx-jackal
covers: ["R4"]
after: ["1.3", "1.5", "1.6"]
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
3. `7z` absent, with an input that needs it, names `7z` in the same message as any other missing tool
   rather than one message per tool, and refuses only the inputs that need it. Every other path in the run
   still converts and the run exits non-zero. A missing `7z` never stops a ZIP in the same run.
4. A solid archive's entries convert correctly, measured against a solid fixture — a member extracted from a
   single-block archive is byte-exact, but re-inserting one member re-deflates the whole stream, so this is
   stated as a known cost rather than left for a reader to discover.
5. ZIP input behaviour is unchanged, byte for byte.
6. `README.md` documents installing `7z` for linux, mac and windows.
7. The package installs into a clean virtual environment and its entry point runs, checked in the closing
   suite. (Amended 2026-10-08: this read "the released version installs and runs from a clean environment on
   all three platforms", which nothing here can verify — there is no CI and no release process. The
   three-platform release clause is dropped, as `epic-bounded-downscaling` dropped its identical one; the
   install itself is checkable, because the package has no dependencies and a clean virtualenv needs no
   network.)

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
- contract — _bmad-output/initiative-cbx-jackal/epic-bounded-downscaling/epic-bounded-downscaling.md,
  section Notes, the preflight ruling of 2026-10-08 that Done-when 3 now matches: `7z` is input-driven,
  decided by the recognised input suffix rather than by sniffing, and refuses only the inputs that need it

## Notes

- **Tracer bullet: entry 2, and the sequencing behind the breakdown** (2026-10-08, inception). Entry 2 is
  the thinnest path through every layer this epic touches: the reader and its registry, the scan's suffixes,
  a minimal input-driven `7z` check, the fixture builder, and contract 1.6's filesystem-effects clause. It
  ends at a converted CB7, which is the first thing worth demoing and the first thing that can teach the
  rest. Everything after it waits on a fixture entry 4 owns or on the reader entry 2 built, and three
  orderings are deliberate rather than incidental: entry 8 follows entry 7 because both change the reader's
  failure handling, entry 5 follows entry 4 because it extends the builder entry 4 owns, and entry 9 owns
  `README.md` alone so that entry 6 establishes the solid cost as behaviour and entry 9 documents it.
  RAR is deliberately not the tracer: `7z` cannot create it and no `rar` binary exists here, so its fixture
  is a committed binary and a `hitl` step, and the tracer must not be blocked on a person.
- Decision: Done-when 7 was amended on 2026-10-08, at inception, from a three-platform release check to a
  clean-virtualenv install. Nothing in this repository can verify a release — no CI, no release process — and
  the checkable half is real because the package has no dependencies.
- Decision: the reader is a **staged extraction** (2026-10-08, inception). One `7z x` into a temp directory the
  tool owns, the order taken from `7z l` before extraction, cleanup on every exit path per contract 1.6's
  clause. A solid archive settles it: extracting one member from a single-block archive decompresses the
  block, so per-member streaming is O(n²) over a 200-page solid book and staged extraction is O(n). The cost
  is temp disk, and it makes 1.6's symlink-and-device refusal clause load-bearing rather than theoretical.
- Decision: an **encrypted archive is refused with a message, and the run carries on** (2026-10-08,
  inception). One owner-facing line saying the archive is encrypted, exit 1, every other input still
  converting — the input-driven refusal 1.5 fixed for a missing `7z`, applied to a different unreadable
  cause. Pass-through is impossible: the output is rebuilt from entries that must be read. The reader must
  force a non-interactive failure, because `7z` otherwise prompts for a password and would hang an
  unattended run.
- Decision: **this epic implements the generalised preflight itself**, per contract 1.5, and entry 1.11 of
  `epic-bounded-downscaling` adds `magick` on top of a shape that then exists (2026-10-08, inception).
  `preflight.py`'s shape is nominally owned by the opening epic, but its code is entry 1.11's, deep in that
  epic's chain — waiting would serialise this epic behind entries 8 through 11. The contract is fixed, so
  the two edits are additive rather than competing.
- Decision: the preflight checks for **`7z` only** (2026-10-08, inception), matching Done-when 6 and the
  README. A system carrying only `7zz` or `7za` needs a `7z` symlink, which the README says in one line.
- Measured 2026-10-08, settling entry 5's `unknown`: **a RAR fixture cannot be produced in this repository,
  and hand-constructing one does not work.** `7z i` lists `Rar` and `Rar5` with no create flag, there is no
  `rar` binary, only read-only `unrar`, and no `.rar` exists on the system. A minimal stored-method RAR4
  written by hand — correct marker, main header, file header and CRCs — is accepted by `unrar` and listed
  with the right name and size, but **`7z` rejects every variant**, including with an end-of-archive block,
  both host-OS values, and the dictionary-size flag bits set. Since `7z` is the reader the tool uses, a
  hand-rolled encoder is not a fixture; it is a liability. So the fixture is a committed binary produced
  outside this repository by a real RAR writer, and producing it is the `hitl` step entry 5 already carries.
- Measured 2026-10-08: `7z` creates 7z, CB7, a solid 7z (`-ms=on`) and an encrypted 7z (`-p`) — but
  **cannot create RAR**, and no `rar` binary exists here, only read-only `unrar`. So the RAR fixture is a
  committed binary produced outside this repository, and making it is a `hitl` step. CB7, solid and
  encrypted fixtures are generated in-repo like the JPEG ones; RAR is the one fixture whose bytes cannot be
  regenerated by `make_fixtures.py`.
- Decision: the frontmatter gate was narrowed on 2026-10-08 from the whole of `epic-bounded-downscaling`
  to the three contracts it actually needs — `1.3` the naming rule, `1.5` the preflight shape, `1.6` the
  classification gate — matching what the initiative's declaration has said since inception. The whole-epic
  gate was the blunt pre-inception form, and left standing it would have blocked this epic's entries until
  downscaling's geometry and resize entries finished, serialising work the maintainer ruled order-free when
  the contract structure was accepted.
- Decision: Done-when 3 was amended on 2026-10-08 to stop promising an abort. It read "exits non-zero
  before any archive opens", which would have meant one missing `7z` refusing a whole library of CBZs.
  The preflight contract now carries two severities: `cjxl` and any box tool abort, because every run
  needs them; an input-driven tool refuses only the inputs that need it and the rest of the run converts.
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
