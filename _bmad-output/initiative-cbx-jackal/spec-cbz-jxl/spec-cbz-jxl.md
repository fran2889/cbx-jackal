---
id: SPEC-cbz-jxl
companions:
  - conventions.md
  - entry-transformations.md
sources:
  - ../forge-cbz-jxl/forge-cbz-jxl.md
  - ../forge-cbz-jxl/forge-report.html
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# cbx-jackal — CBZ to JXL page transcoder

## Why

An opportunity to capture, on a pain that is already expensive. Owners of comic archives keep re-encoding
the same JPEG pages and their storage keeps growing, because every tool available to them either re-encodes
lossily or leaves the bytes alone. JPEG XL's lossless transcoding mode changed that: it re-encodes a JPEG
page 19–48% smaller **with no quality loss**, and because libjxl embeds JPEG bitstream reconstruction data
in that mode, the original JPEG stays byte-for-byte recoverable. That combination — smaller *and* lossless
*and* reversible — was not available before this generation of encoders, and it is what makes re-encoding
worth doing at all. Affected: anyone holding a large scanned or downloaded comic library. Affected now,
because the capability exists and nothing exposes it as a safe, order-preserving, one-command operation.

## Capabilities

- **CAP-1 — Lossless page conversion by default**
  - **intent:** An owner can convert a comic archive's JPEG pages to JXL without any quality loss, without
    asking for lossless and without supplying a flag.
  - **success:** For every converted page, decoding the output `.jxl` yields pixels identical to decoding
    the source `.jpg` (zero differing pixels), and `djxl` reproduces the source JPEG byte-for-byte.

- **CAP-2 — Deliberate lossy quality control**
  - **intent:** An owner who wants smaller files can trade quality on purpose rather than by accident.
  - **success:** `--quality N` below 100 yields `.jxl` pages smaller than lossless output and smaller than
    the source, and the run states the mode so the owner knows reversibility has been surrendered.

- **CAP-3 — Byte-faithful pass-through of everything else**
  - **intent:** Nothing an owner did not ask to convert is ever altered, reordered or lost.
  - **success:** Output entry count and order match the input exactly, every non-converted entry is
    byte-identical to its source, and no page is renumbered or dropped — including when a page fails to
    convert.

- **CAP-4 — Failure never yields a partial book**
  - **intent:** An owner is never left holding a truncated archive that looks valid.
  - **success:** When any page fails to convert, either no output file exists at all, or it exists complete
    with every entry present; the exit code is non-zero and one line per failed page is reported.

- **CAP-5 — Honest prerequisites**
  - **intent:** An owner can start the tool and learn precisely what is missing instead of meeting a
    mysterious failure partway through a 200-page run.
  - **success:** With `cjxl` absent, the tool exits non-zero before reading any archive, names the missing
    tool, and points at the documentation covering linux, mac and windows install paths.

## Constraints

- No Python imaging libraries. Container handling is Python standard library only.
- `cjxl` is the single external tool, and is never bundled into the distribution — two libjxl copies on one
  Linux host fight over global decoder handler registration, and the wrong one can win silently.
- Page order is the source ZIP's stored entry order, verbatim. No natural sort, no renumbering, no repair
  of archives whose ordering is already wrong. Readers own the sort; the tool never silently reorders a
  book.
- Output is always a new file `<name>.jxl.cbz` beside the input. Never in-place; never overwrite without an
  explicit force.
- Output is atomic: build to a temp file in the destination directory, then rename. A failed run leaves no
  output file, never a partial one.
- ZIP entries are STORED, never deflated.
- The exit code is non-zero if and only if a JPEG entry failed to convert. Non-JPEG pass-throughs are
  normal and must never make a healthy run look failed.

## Non-goals

- **Reader compatibility.** Output is JXL-only and will not display in most comic readers. Chosen knowingly
  after weighing the sidecar alternative, and made acceptable by byte-level reversibility.
- **Long-term archival preservation.** JXL decoder support outside a few libraries is too thin to recommend
  as a retention format. This tool's case is per-user size and reversibility, not durability over decades.
- **DPI preservation.** Pixel dimensions survive conversion; physical density does not, and is knowingly
  dropped rather than reconstructed.
- **A `--verify` mode.** Deliberately deferred out of v1, not overlooked. Losslessness stays auditable after
  the fact by reconstructing with `djxl`, and the guarantee rests on trusting libjxl plus the `cjxl` exit code.
- Bundled or standalone binaries.
- Repairing page order in archives that already have broken ordering.
- Any image manipulation: no resize, rotate, upscale, re-encoding of non-JPEG pages, or ComicInfo.xml
  rewriting. The entry count never changes, so `<Pages Count>` stays correct untouched.

## Success signal

A 200-page comic converts in one command to an archive at least 19% smaller whose JPEG pages remain
byte-identically recoverable, with zero entries lost, added or reordered — and a run containing a corrupt
page leaves either a complete archive or none at all, never a partial one.

## Assumptions

- libjxl 0.11.1 behaviour generalises to the versions owners will have: implicit lossless-transcoding for
  JPEG input, `-q 100` meaning mathematically lossless, and embedded reconstruction data. Verified on this
  version only.
- Python 3's `zipfile` suffices — it reads stored entry order reliably and writes STORED entries, including
  ZIP64 for large archives.
- `cjxl` is on the owner's PATH, or discoverable once the preflight message points them at the documentation.