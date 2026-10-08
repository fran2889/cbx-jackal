# cbx-jackal

Transcode a CBZ comic archive's JPEG pages to JPEG XL — **losslessly, and with
the original JPEG still byte-for-byte recoverable** — while preserving entry
order and passing through everything else untouched.

```
$ cbx-jackal book.cbz
book.cbz -> book.jxl.cbz
mode: lossless (JPEG bytes recoverable with djxl)
199/200 converted, 1 passed through, 0 not converted
```

Measured on real scanned pages, JPEG pages shrink **19–48%** with zero quality
loss, and `djxl` reproduces the source file exactly:

```
$ djxl page001.jxl recovered.jpg
JPEG XL decoder v0.11.1
Reconstructed to JPEG.
$ sha256sum page001.jpg recovered.jpg
505661c8...  page001.jpg
505661c8...  recovered.jpg
```

## Why this is worth doing

Every tool available for shrinking a comic archive either re-encodes lossily or
leaves the bytes alone. JPEG XL's *lossless transcoding* mode is the first
generation of encoders that gives you smaller **and** lossless **and**
reversible at the same time. That combination is what makes re-encoding worth
doing at all — and it is what nothing exposed as a safe, order-preserving,
one-command operation until now.

Two properties do the work:

- **Lossless by default, with no flag.** libjxl defaults to lossless-transcoding
  for JPEG input, so a bare `cjxl in.jpg out.jxl` is already reversible.
- **Reversibility rides in the container.** libjxl embeds *JPEG bitstream
  reconstruction data*, so `djxl` recovers the original file. This is not the
  same as lossless pixels: JPEG cannot be restored from decoded pixels alone —
  two JPEGs differing only by an inserted 22-byte comment marker decode to
  identical pixels. Only the lossless mode carries the data needed to undo that,
  and only the lossless mode keeps it.

## Installing cjxl

`cjxl` is the single external dependency. It is **never bundled**: two libjxl
copies on one Linux host fight over global decoder handler registration, and the
wrong one can win silently.

### Linux

Your distribution's `libjxl` tools package provides `cjxl`:

```bash
# Debian, Ubuntu
sudo apt install libjxl-tools

# Fedora
sudo dnf install libjxl-tools

# Arch
sudo pacman -S libjxl-tools
```

### macOS

```bash
brew install libjxl
```

Then put Homebrew's `bin` on your `PATH` if it is not already:
`export PATH="$(brew --prefix)/bin:$PATH"`.

### Windows

Download a release build from the
[libjxl releases page](https://github.com/libjxl/libjxl/releases) and put the
extracted `cjxl.exe`, `djxl.exe` and `jxlinfo.exe` on your `PATH`. Alternatively
use whichever package manager you already have — scoop, winget, chocolatey — if
it ships libjxl under a name you can confirm with `cjxl --version` afterwards.

### Verify

```bash
cjxl --version   # JPEG XL encoder v0.11.1
djxl --version
```

## Installing 7z

A CB7, 7Z, or RAR input also needs the `7z` command from 7-Zip / p7zip.
`7z` is **never bundled**: a system binary is used, and nothing here installs it
for you.

`7z` must be available as `7z`, not `7zz` or `7za`. Systems that ship only
`7zz` (some Linux distributions) or `7za` (the "AES" variant) need a `7z`
symlink or alias pointing to it, because the tool checks for `7z` by that name.

### Linux

Your distribution's p7zip package provides `7z`:

```bash
# Debian, Ubuntu
sudo apt install p7zip-full

# Fedora
sudo dnf install p7zip

# Arch
sudo pacman -S p7zip
```

### macOS

```bash
brew install p7zip
```

Then put Homebrew's `bin` on your `PATH` if it is not already:
`export PATH="$(brew --prefix)/opt/p7zip/bin:$PATH"`.

### Windows

Download 7-Zip from the [7-Zip website](https://www.7-zip.org/) and put
`7z.exe` on your `PATH`. Alternatively use whichever package manager you
already have — scoop, winget, chocolatey — if it ships 7-Zip under a name you
can confirm with `7z` afterwards.

### Verify

```bash
7z --help
```

cbx-jackal checks for `cjxl` **before opening any archive**, so a missing
dependency is reported up front rather than discovered 150 pages into a run:

```
$ cbx-jackal book.cbz
cbx-jackal: missing tools: cjxl

cjxl was not found on PATH.
...
```

## Install

Python 3.9 or newer. No Python dependencies at all — container handling is the
standard library, with no Python imaging libraries. A CB7, 7Z, or RAR input
also needs the `7z` command (see [Installing 7z](#installing-7z) above).

```bash
pip install .
```

Or run it without installing:

```bash
python3 -m cbx_jackal.cli book.cbz
```

## Usage

```
cbx-jackal CBZ|DIR|PATTERN [CBZ|DIR|PATTERN ...] [--recursive] [--quality N] [--format FMT] [--strict] [--dry-run] [--force]
```

| Flag | Meaning |
|---|---|
| `--recursive`, `-r` | Descend into subdirectories when a path is a directory. |
| `--quality N` | Encode lossy at quality 1–100 instead of losslessly. Surrenders byte-for-byte JPEG recovery. 100 and above is lossless. |
| `--format FMT` | Page format of the output; legal values: `jxl`. The output is named `<input>.<format>.cbz` either way, and the container never varies with the input. Default: `jxl`. |
| `--strict` | Write nothing at all if any page fails to convert, instead of copying the failed page through and completing the archive. |
| `--dry-run` | Report the plan and the real size figures without writing anything. |
| `--force` | Overwrite an existing `<name>.<format>.cbz`. |

Output is always a **new file** `<input>.<format>.cbz` beside the input, where
`<format>` is what `--format` names. Never in-place, never without `--force`.
The input archive is never modified.

### Converting a whole directory, or a pattern

Point the tool at a folder instead of globbing by hand:

```
$ cbx-jackal ~/comics/2024
~/comics/2024/issue-01.cbz -> ~/comics/2024/issue-01.jxl.cbz
mode: lossless (JPEG bytes recoverable with djxl)
24/24 converted, 1 passed through, 0 not converted
```

A wildcard pattern works too. **Quote it**, so the shell hands it over whole
instead of expanding it first — an unquoted `lib/*.cbz` arrives as a list of
files, which converts just the same, but the tool cannot then tell you the
pattern matched nothing:

```
$ cbx-jackal "$HOME/comics/2024/issue-0*.cbz"
```

Quoting stops the shell from expanding `*`, but it also stops it expanding `~`,
so use `$HOME` (or an absolute path) rather than `~/comics/...` inside a quoted
pattern.

| | Behaviour |
|---|---|
| **Scanned** | `.cbz`, `.zip`, `.cb7`, `.7z`, `.rar`, any case. Nothing else — `notes.txt` beside the books is ignored, not reported as unreadable. |
| **Not descended into** | Subdirectories, unless `--recursive` is given. A pattern is never recursive: `**` behaves as `*`. |
| **Where output lands** | Beside each input, mirroring the tree. `lib/a/book.cbz` → `lib/a/book.jxl.cbz`; nothing is hoisted or flattened. |
| **Output name** | Always `<stem>.<format>.cbz`, where `<format>` is what `--format` names. `book.zip` yields `book.jxl.cbz`, never `book.jxl.zip`. |
| **Already converted** | `<stem>.<format>.cbz` files, for every declared format, are skipped, so rescanning a directory does not produce `a.jxl.jxl.cbz`. |
| **Symlinks** | Not followed when *found by a scan*. A symlink you name yourself is followed, because you named it. |
| **Order** | Sorted, each directory's own entries, depth-first, and pattern matches sorted too. Two runs over the same tree process the same archives in the same order. |
| **Named twice** | Converted once. `cbx-jackal lib lib/a.cbz` gives one report block, in the order first reached. |
| **Nothing matched** | One note naming the directory or pattern, exit code `0`. |

Paths are reported exactly as you typed them, not absolutised.

A subdirectory that cannot be read is skipped with a warning and the rest of
the tree is still converted. The converter, the exit-code contract, and one
report block per archive are all unchanged — a scan is just a longer list of
paths, so a bad archive in the middle still does not abandon the batch.

### Exit codes

| Code | Meaning |
|---|---|
| `0` | Every JPEG page converted. Pass-through entries never affect this. |
| `1` | At least one JPEG page failed to convert, or an archive was unreadable. |
| `2` | Usage error, a missing tool (`cjxl` always, `7z` when an input needs it), or the output already exists without `--force`. |

## Container-specific behaviour

| Container | Behaviour |
|---|---|
| **CBZ, ZIP** | Standard library only. No external tools. |
| **CB7, 7Z, RAR** | Uses `7z` for reading; output is always CBZ. |
| **Solid archives (7Z, CB7)** | Every entry is stored byte-exact, but the internal container layout is **not preserved** — re-inserting one member re-deflates the whole block. |
| **Encrypted archives** | Refused with a message naming the archive as encrypted; exit code 1; **every other input in the run still converts**. |

## What happens to each entry

Every entry gets exactly one outcome, in the source's **stored order**.
Nothing is sorted, renumbered, or repaired.

| Entry | Action | Output name |
|---|---|---|
| `.jpg` / `.jpeg`, any case, converts cleanly | transcode | `<stem>.jxl` |
| `.jpg` / `.jpeg` that `cjxl` rejects | copied verbatim, **not dropped** | **original name kept** |
| Extension says `.jpg`, content is another image format | transcode (`cjxl` sniffs content) | `<stem>.jxl` |
| Already `.jxl` | copied verbatim, **never re-encoded** | unchanged |
| `ComicInfo.xml`, `readme.txt`, any non-image | copied verbatim | unchanged |
| `__MACOSX/` and resource-fork junk | copied verbatim | unchanged |
| Nested folders | copied verbatim, structure preserved | unchanged |
| Anything unreadable from the source | abort that input, leave no output | — |

Three reporting classes, because conflating the second and third would make a
healthy run look broken:

| Class | Meaning | Affects exit code |
|---|---|---|
| converted | JPEG page successfully transcoded | no |
| passed through | non-JPEG entry, or one deliberately not transcoded | no |
| **not converted** | a JPEG entry left as-is because `cjxl` failed | **yes** |

```
199/200 converted, 1 passed through, 1 not converted
page014.jpg: Error while decoding the JPEG image. It may be corrupt (e.g. truncated) ...
```

### Design decisions worth stating

- **A failed page leaves a hole, never a misnumbering.** Because nothing is
  renumbered, a page that fails and is copied through stays at its original index
  under its original name. The book gets a visible hole instead of a book whose
  page 15 is suddenly the old page 16.
- **An existing `.jxl` is never re-encoded.** Round-tripping it through the
  transcoder strips the JPEG bitstream reconstruction data — the one way to
  silently destroy reversibility.
- **`ComicInfo.xml` is never rewritten.** The entry count never changes, so
  `<Pages Count>` stays correct untouched.
- **Everything is written `ZIP_STORED`.** JXL is already entropy-coded, so deflate
  measured under 1% gain while costing real CPU on every page.
- **Output is atomic.** Built to a temp file in the destination directory,
  `fsync`'d, then `os.replace`d. A failed run leaves no output file, never a
  partial one.

## The one trap worth knowing about

libjxl sets `lossless_jpeg=1` by default for JPEG input, so passing only a
quality flag fails outright:

```bash
cjxl in.jpg out.jxl                          # lossless, reversible
cjxl -q 90            in.jpg out.jxl         # exit 1, no output
cjxl -q 90 --lossless_jpeg=0 in.jpg out.jxl  # lossy, irreversible
```

```
Must not set quality below 100 in combination with --lossless_jpeg=1,
which is set by default.
```

Every lossy invocation must pass `--lossless_jpeg=0` as well. cbx-jackal does
this for you, which is why `--quality 90` works at all.

## Tests

Stdlib `unittest`, no third-party packages — the same zero-dependency stance the
project takes at runtime. `djxl` round-trip assertions are skipped if `djxl` is
absent; everything else skips if `cjxl` is absent.

```bash
python3 -m unittest discover -s tests -v
```

Types are checked with [pyright](https://github.com/microsoft/pyright), pinned to
the declared 3.9 floor in `pyrightconfig.json` rather than whatever interpreter
you happen to run:

```bash
pyright
```

It is a development tool and is not a project dependency — nothing here installs
it for you.

## Commit messages

[Conventional Commits](https://www.conventionalcommits.org/): a lowercase type,
then the subject. The body carries the reasoning, and it should — the history is
where the *why* of this codebase lives.

```
fix: treat output-name collisions the way readers resolve them

Compare via NFC normalisation plus casefold, matching how ZIP readers on
macOS and Windows resolve member names.
```

Types: `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `perf`, `build`, `ci`,
`style`, `revert` — plus `feature` and `bugfix`, which is what `bmad-build` emits
from a plan's `type` frontmatter. A scope is optional: `feat(cli): add --dry-run`.

### Enabling the check

Commit subjects are enforced by `.githooks/commit-msg`. Point Git at it once per
clone:

```bash
git config core.hooksPath .githooks
```

That setting is **local Git config, so it cannot be committed** — a fresh clone
gets the hook file but no enforcement until you run the line above. The test
`tests/test_commit_hook.py` fails if the setting is missing, so the gap announces
itself rather than passing quietly.

Merge commits, `Revert`, and `fixup!`/`squash!` lines are exempt, as the
Conventional Commits spec intends. `--no-verify` bypasses the hook for a single
commit.

## Requirements and non-goals

- **Reader compatibility.** Output is JXL-only and will not display in most comic
  readers. Chosen knowingly after weighing the sidecar alternative, and made
  acceptable by byte-level reversibility.
- **Long-term archival preservation.** JXL decoder support outside a few
  libraries is too thin to recommend as a retention format. This tool's case is
  per-user size and reversibility, not durability over decades.
- **DPI preservation.** Pixel dimensions survive; physical density does not, and
  is knowingly dropped.
- **No image manipulation.** No resize, rotate, upscale, re-encoding of
  non-JPEG pages, or `ComicInfo.xml` rewriting.
- **No page-order repair.** Readers own the sort. This tool never silently
  reorders a book.

## License

MIT
