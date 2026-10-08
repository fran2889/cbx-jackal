# External tool conventions

`cjxl` is required on every run; a container archiver is required only when a run has a non-ZIP input.
Everything measured below is libjxl 0.11.1; the spec's Assumptions section carries the risk that this
generalises.

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

**PNG input is the other lossy-by-default case.** The `lossless_jpeg` default only covers JPEG input, so
`cjxl in.png out.jxl` encodes *lossily*: measured 195,790 wrong pixels — 19.2% — on a saturated synthetic
page. PNG input therefore always needs `-q 100`, which measured zero wrong pixels. "The lossless invocation
passes no flags" is a statement about JPEG input and nothing else.

**`-quality` on PNG is a compression knob, never a fidelity one.** Measured on ImageMagick 7.1.2-18 at every
value including 30: it changed the output's byte size and never its pixels. 90 and 100 produced identical
bytes.

## Resizing

`cjxl` cannot resize. Verified against libjxl 0.11.1's full expert option list (`cjxl -v -v -v -v
--help`): no `--resize`, no size argument, nothing that scales the output grid. A page that must be
smaller goes through ImageMagick first, then takes the existing lossless path unchanged:

```bash
magick <in.jpg> -auto-orient -resize '<W>x<H>>' -quality 100 <mid.png>   # W,H computed in Python
cjxl -q 100 <mid.png> <out.jxl>                                    # -q 100 mandatory for PNG
```

Three flags are load-bearing:

- `-resize '<W>x<H>>'` — the trailing `>` is the downsize guard: verified that `2400x3200>` against a
  400x600 page leaves it 400x600. `<W>x<H>` are supplied by Python, already aspect-correct, so `magick`
  has no fit decision left to make.
- `-auto-orient` — bakes the EXIF orientation into the pixels before geometry is measured, so the
  intermediate is upright and its EXIF tag cannot double-rotate it.
- the intermediate's own encoding — for PNG, `-quality 100` is mandatory: `cjxl` with no flags on a PNG
  intermediate lost 195,790 pixels on the 2026-10-08 re-measurement, so the lossless invocation on this path
  is `cjxl -q 100`.

Geometry is decided in Python from the `SOF0` frame header and the APP1 orientation tag. Neither
requires decoding a pixel, so the stdlib-only constraint holds. Letting `magick` pick the box instead
would be a bug: it measures coded dimensions, which is how a 600x300 page tagged orientation 6 ends up
fitted against its height.

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
`JPEG bitstream reconstruction data available`, which was the cheap way to assert reversibility is present.

**That check is no longer sufficient.** Under CAP-6 a downscaled page carries reconstruction data too, and
`djxl` on it reproduces the intermediate rather than the source — measured, the reconstructed file is
byte-identical to the intermediate and differs from the source. To audit a page, hash `djxl`'s output
against that page's *source bytes* and let the comparison decide. The presence of reconstruction data
proves a generation exists, never which one.

Reversibility exists **only** in lossless mode. Any `-q N` below 100 drops the reconstruction data and
permanently adds a generation of loss. Never re-encode an existing `.jxl` — that is the one way to
silently destroy reconstruction data.

Note the terminology: libjxl calls this *lossless transcoding*, not lossless JPEG. Borrow the upstream word.
JPEG cannot be restored from decoded pixels alone — two JPEGs differing only by an inserted 22-byte comment
marker decode to identical pixels — so the reconstruction data carried in the container is what makes it
possible, and it is present only in this mode.

## Effort and concurrency

Do not expose an effort flag. Measured at A4/300dpi on **JPEG input**:

| Effort | Flat comic page | Detail-heavy page |
|---|---|---|
| 3 | 0.08 s, 45,360 B | 0.15 s, 1,925,691 B |
| **7 (default)** | **0.08 s, 45,359 B** | **0.16 s, 1,925,695 B** |
| 9 | 0.91 s, 38,909 B | 3.88 s, 1,915,004 B |

On JPEG input effort 7 is free relative to effort 3, and effort 9 costs 10–25× the time for under 4% size.

**That free-lunch finding is specific to JPEG input and does not carry.** Lossless transcoding of a JPEG is a
bitstream copy, so there is little for effort to spend. PNG input is modular lossless *encoding*, and effort
bites:

| Effort on PNG input | `.jxl` bytes | Time | Wrong pixels |
|---|---|---|---|
| 3 | 1,999 | 230 ms | 0 |
| 5 | 1,298 | 689 ms | 0 |
| **7 (default)** | **1,298** | **961 ms** | **0** |
| 9 | 1,343 | 2,375 ms | 0 |

Effort 7 costs roughly 4× effort 3 here, and produces output byte-identical to effort 5. The default is still
the right one — one synthetic page is no basis for tuning against real comic art — but the earlier claim that
effort is free is corrected to name JPEG input specifically, and anyone revisiting it on a PNG path should
re-measure rather than assume.

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

- ZIP is read with Python `zipfile` in stored order; RAR, CB7 and 7Z are read with an external archiver, in
  that archiver's own listing order. Never sort or renumber either.
- Write every entry with `ZIP_STORED`, because the output is always a ZIP. JXL is already entropy-coded —
  deflate measured under 1% gain and costs real CPU on every page.
- The input's own compression is not preserved. Re-inserting one member of a solid archive recompresses the
  whole block, so untouched pages are recomputed and the source's internal layout is lost. Entry-level byte
  fidelity still holds — a member extracted from a single-block archive is byte-exact — but layout fidelity
  does not.
- Build to a temp file in the destination directory, `fsync`, then `os.replace` onto
  `<name>.jxl.cbz`. `os.replace` is atomic within a filesystem; this is what guarantees CAP-4.
- Clean up both the zip temp file and each per-page `.jxl` temp file on every exit path, including failure.

## Preflight

Check with `shutil.which`, in two severities.

| Severity | Example | Checked | On absence |
|---|---|---|---|
| every run needs it | `cjxl` | before any archive opens | exit non-zero, the run stops |
| only some inputs need it | a container archiver | after the input set is expanded | exit non-zero, only those inputs skipped |

The second severity is decided by the recognised input suffix, never by sniffing the file's magic bytes: that
would mean reading the file before knowing the tools are present. By-content detection belongs to the
archiver at open time, where it belongs. A file whose suffix says ZIP and whose bytes are not is an
unreadable archive, which is the answer it already gets.

One message names every missing tool whatever the count, in severity order, and each says whether it stops
the run or skips inputs. The message must not be a stack trace.

A dry run needs exactly what a real run would, because it encodes every page to report real size figures
rather than estimates.

When a box is requested, check `magick` the same way and in the same breath; CAP-5 exists so an owner
learns what is missing before a 200-page run, not eighty pages into one. `magick` is not checked when no
box is requested, so a plain transcode still needs nothing but libjxl. Require the `magick` name rather
than `convert`: an ImageMagick 6 host has no `magick` and should receive the install message instead of
silently taking a different code path. Check both together and report both together, so an owner missing
everything is told everything in one message rather than one run per missing tool.

Platform-specific install instructions belong in **documentation, not CLI output**, and must cover all
three supported platforms:

| Platform | Notes for the docs |
|---|---|
| linux | `libjxl-tools` provides `cjxl`; `imagemagick` provides `magick`; a `p7zip-full` or equivalent for the archiver |
| mac | Homebrew formulas `libjxl` and `imagemagick`; `p7zip` for the archiver |
| windows | libjxl release build on PATH, or a package manager; ImageMagick from imagemagick.org; 7-Zip for the archiver |

The `cjxl` rows are required by CAP-5. The `magick` rows are required by CAP-6 and are only consulted
when a box is requested.

Keep the CLI message platform-neutral so it does not go stale per platform.