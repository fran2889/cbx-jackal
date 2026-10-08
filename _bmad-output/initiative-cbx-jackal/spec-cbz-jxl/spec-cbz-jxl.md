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

# cbx-jackal — comic archive page transcoder

## Why

An opportunity to capture, on a pain that is already expensive. Owners of comic archives keep re-encoding the
same JPEG pages and their storage keeps growing, because every tool available to them either re-encodes
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
  - **success:** With a tool the run needs absent, the tool exits non-zero, names every missing tool in a
    single message, points at the documentation covering linux, mac and windows, and states whether the run
    stops or only skips the inputs that need it. A tool every run needs stops the run before any archive is
    opened; one only some inputs need converts the rest of the list and skips those inputs.

- **CAP-7 — Read the containers collections actually arrive in**
  - **intent:** An owner whose library is RAR, CB7 or 7Z converts it without unpacking it by hand first.
  - **success:** A book in RAR, CB7 or 7Z converts to a CBZ whose entry order, entry count and entry bytes
    match the source exactly. A corrupt or unreadable source leaves no output at all and exits non-zero. A
    run whose only non-CBZ inputs need an absent archiver still converts every other input and exits
    non-zero.

## Constraints

- No Python imaging libraries. Reading and writing ZIP is Python standard library only, via `zipfile`.
  Reading RAR, CB7 and 7Z is an external archiver step, because no standard-library module reads them.
- The output container is always CBZ and is always written by `zipfile`, whatever the input container was.
  No proprietary archiver writer is therefore ever required, and a converted book is indistinguishable from
  one that arrived as a CBZ.
- No external tool is ever bundled into the distribution. `cjxl` is required on every run; every other tool
  is required only by CAP-5's severities. Two libjxl copies on one Linux host fight over global decoder
  handler registration and the wrong one can win silently, which is why nothing is vendored.
- Page order is the source container's stored entry order, verbatim: the `zipfile` order for ZIP, the
  external archiver's listing order for RAR, CB7 and 7Z. No natural sort, no renumbering, no repair of
  archives whose ordering is already wrong. Readers own the sort; the tool never silently reorders a book.
- Output is always a new file `<name>.jxl.cbz` beside the input. Never in-place; never overwrite without an
  explicit force.
- Output is atomic: build to a temp file in the destination directory, then rename. A failed run leaves no
  output file, never a partial one.
- Entries in the output are STORED, never deflated, because the output is always a ZIP. The input's own
  compression is not preserved: re-inserting one member of a solid archive recompresses the whole block, so
  entry-level byte fidelity holds while the source's internal container layout does not.
- The exit code is non-zero when a JPEG entry failed to convert, when a source could not be read, and when a
  tool the run needed was absent or an existing output was refused. Non-JPEG pass-throughs are normal and
  must never make a healthy run look failed. One refused path does not abandon the rest of the list.

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
byte-identically recoverable, with zero entries lost, added or reordered — whether it arrived as a CBZ, a
ZIP, a RAR, a CB7 or a 7Z — and a run containing a corrupt page leaves either a complete archive or none at
all, never a partial one.

## Assumptions

- libjxl 0.11.1 behaviour generalises to the versions owners will have: implicit lossless-transcoding for
  JPEG input, `-q 100` meaning mathematically lossless, and embedded reconstruction data. Verified on this
  version only.
- Python 3's `zipfile` suffices for the output container and for reading ZIP: it reads stored entry order
  reliably and writes STORED entries, including ZIP64 for large archives. It does not read RAR, CB7 or 7Z,
  and nothing in the standard library does.
- External tools are expected on PATH, or discoverable once the preflight names them and points at the
  documentation. No vendored copy of any of them.

## Open Questions

- Encrypted or password-protected archives are unaddressed. Should such an input be refused with an
  owner-facing message naming the password, skipped the way a missing tool is skipped, or passed through
  untouched? RAR and 7Z both support encryption and comic collections containing it are common, so the tool
  will meet them.
