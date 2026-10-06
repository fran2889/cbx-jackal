# External tool conventions

`cjxl` is the only external dependency. Everything below was measured against **libjxl 0.11.1**; the
Assumptions section of the spec carries the risk that this generalises.

## Invocation

```bash
# lossless (default mode) — no quality flag at all
cjxl <in.jpg> <out.jxl>

# explicit lossless, silences the notice
cjxl --lossless_jpeg=1 <in.jpg> <out.jxl>

# lossy — the second flag is MANDATORY
cjxl -q <N> --lossless_jpeg=0 <in.jpg> <out.jxl>
```

**The trap.** For JPEG input libjxl sets `lossless_jpeg=1` by default. Passing only `-q N` for any
`N < 100` fails outright:

```
Must not set quality below 100 in combination with --lossless_jpeg=1, which is set by default.
```

Every lossy invocation must also pass `--lossless_jpeg=0`. Without it every lossy run fails.

## Lossless transcoding and reversibility

libjxl's default for JPEG input is **lossless transcoding**, announced as:

```
Note: Implicit-default for JPEG is lossless-transcoding.
```

In this mode the JXL embeds **JPEG bitstream reconstruction data**, so `djxl` recovers the original file:

```bash
djxl <in.jxl> <out.jpg>     # -> "Reconstructed to JPEG."
```

Verified byte-identical to the source (size and SHA-256 both match). `jxlinfo` reports
`JPEG bitstream reconstruction data available`, which is the cheap way to assert reversibility is present.

Reversibility exists **only** in lossless mode. Any `-q N` below 100 drops the reconstruction data and
permanently adds a generation of loss. Never re-encode an existing `.jxl` — that is the one way to
silently destroy reconstruction data.

Note the terminology: libjxl calls this *lossless transcoding*, not lossless JPEG. Borrow the upstream word.
JPEG cannot be restored from decoded pixels alone — two JPEGs differing only by an inserted 22-byte comment
marker decode to identical pixels — so the reconstruction data carried in the container is what makes it
possible, and it is present only in this mode.

## Effort and concurrency

Do not expose an effort flag. Measured at A4/300dpi:

| Effort | Flat comic page | Detail-heavy page |
|---|---|---|
| 3 | 0.08 s, 45,360 B | 0.15 s, 1,925,691 B |
| **7 (default)** | **0.08 s, 45,359 B** | **0.16 s, 1,925,695 B** |
| 9 | 0.91 s, 38,909 B | 3.88 s, 1,915,004 B |

Effort 7 is free relative to effort 3. Effort 9 costs 10–25× the time for under 4% size. Leave the default.

**No page-level parallelism.** At 0.08–0.16 s per page a 200-page book finishes in 16–32 s serially, and
`cjxl` already threads internally. A process pool would add a subsystem for no measurable gain.

## Corruption detection

`cjxl` is a reliable oracle: it exits **1 and writes no output** for truncated and garbage JPEGs, so there
is no silent padding to guard against.

```
truncated JPEG -> exit 1, no output file
garbage bytes  -> exit 1, no output file
misnamed PNG   -> exit 0, converts correctly (content sniffing)
```

Therefore a non-zero exit from `cjxl` is sufficient to classify an entry as not-converted. No separate JPEG
validity check is needed.

## Container

- Read entries with Python `zipfile` in stored order; never sort or renumber.
- Write every entry with `ZIP_STORED`. JXL is already entropy-coded — deflate measured under 1% gain and
  costs real CPU on every page.
- Build to a temp file in the destination directory, `fsync`, then `os.replace` onto
  `<name>.jxl.cbz`. `os.replace` is atomic within a filesystem; this is what guarantees CAP-4.
- Clean up both the zip temp file and each per-page `.jxl` temp file on every exit path, including failure.

## Preflight

Check for `cjxl` with `shutil.which` before opening any archive. On absence: exit non-zero naming the missing
tool and pointing at the documentation, per CAP-5. The message must not be a stack trace.

Platform-specific libjxl install instructions belong in **documentation, not CLI output**, and must cover all
three supported platforms:

| Platform | Notes for the docs |
|---|---|
| linux | distro package (`libjxl-tools`), which provides `cjxl` |
| mac | Homebrew formula (`libjxl`) |
| windows | libjxl release build on PATH, or a package manager |

Keep the CLI message platform-neutral so it does not go stale per platform.