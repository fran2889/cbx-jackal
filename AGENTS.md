<!-- bmad:context -->
<!-- Verified 2026-10-09 against HEAD. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## cbx-jackal

Transcodes a CBZ comic archive's JPEG pages to JPEG XL, losslessly and byte-reversibly, preserving entry order and passing everything else through untouched. Python 3.9+, standard library only; `cjxl` and `magick` (when --max-width/--max-height is requested) are external tools that are never bundled. The contract (CAP-1..CAP-6) lives in `_bmad-output/initiative-cbx-jackal/`.

## Policy

- Work directly on `main`. No feature branches, no pull requests.
- Never add a runtime dependency to `pyproject.toml`; container handling is stdlib-only by design.
- Never re-encode an entry that is already `.jxl` — only `.jpg`/`.jpeg` transcode. Round-tripping strips the JPEG reconstruction data and silently destroys reversibility.
- Never write output in place; the destination is always `<name>.jxl.cbz`.

## Where things are

- Read the contract before changing behaviour: `_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/`.
- cjxl argv: `cbx_jackal/encode.py`; classification, collision key, ZIP writing, atomic publish: `cbx_jackal/archive.py`; geometry and box decisions: `cbx_jackal/geometry.py`.
- Exit codes: `README.md` and `tests/` are authoritative, not the spec. The spec narrows non-zero to "a JPEG entry failed"; the code also returns 1 for an unreadable archive and 2 for a usage or missing-tool error. `magick` is checked only when a box is requested.

## Running and verifying

- `python3 -m unittest discover -s tests` — the whole suite; there is no test config in `pyproject.toml`.
- Type-check with `pyright`, which `pyrightconfig.json` pins to the 3.9 floor. It is a dev tool, not installed by the project.
- Confirm `cjxl`, `djxl` and `jxlinfo` are on PATH before trusting a green run. Without them the suite still reports OK: `Ran 29 tests ... OK (skipped=27)`, and 128 of 157 never execute.
- Running as root skips the unwritable-directory and unreadable-file error tests (`os.geteuid() != 0`), so they vanish silently in containers.

## Conventions that differ from defaults

- A lossy cjxl call needs `--quality=N` *and* `--lossless_jpeg=0`; `--quality=N` alone exits 1 and writes nothing. The lossless path passes only `--lossless_jpeg=1`.
- `ZIP_STORED` is hardcoded twice and the two sites must agree (`archive.py:153`, `archive.py:317`).
- Publish as temp file → `fsync` → `os.replace`, with the temp in the destination directory so the rename stays same-filesystem.
- The collision key is `unicodedata.normalize("NFC", name).casefold()` (`archive.py:120`).
- Commit subjects are Conventional Commits: a lowercase `type:` prefix, then the subject. The body carries the reasoning.

## Known pitfalls

- Keep `from __future__ import annotations` in every module. The pervasive `X | None` annotations are legal on the 3.9 floor only because of it.
- `Report.render(quality=...)` defaults to `None`, so a lossy archive rendered without it claims `lossless (JPEG bytes recoverable)`. Losslessness is **not** a simple flag: a downscaled page keeps reconstruction data too, and `djxl` reproduces the intermediate rather than the source. The report states per page which is which; `jxlinfo`'s reconstruction line is **not** proof of source recovery.
- Geometry is decided in Python from `SOF0` frame headers and EXIF orientation tags — never delegated to `magick`, which would measure coded dimensions and misfit rotated pages.
- Fixture bytes are load-bearing: `corrupt.jpg` must stay truncated, `page003.png` must stay a PNG, `sample.cbz` must keep 3 unsorted `.jpg` pages. `make_fixtures.py` needs ImageMagick and is not part of the test run; regenerating rewrites the inputs of ~40 tests.

<!-- /bmad:context -->