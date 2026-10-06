<!-- bmad:context -->
<!-- Verified 2026-10-06 against 60cf685. Managed by bmad-project-context; edits inside this block are replaced on refresh. Keep anything you want preserved outside the markers. -->

## cbx-jackal

Transcodes a CBZ comic archive's JPEG pages to JPEG XL, losslessly and byte-reversibly, preserving entry order and passing everything else through untouched. Python 3.9+, standard library only; `cjxl` is an external tool that is never bundled. The contract (CAP-1..CAP-5) lives in `_bmad-output/initiative-cbx-jackal/`.

## Policy

- Work directly on `main`. No feature branches, no pull requests.
- Never add a runtime dependency to `pyproject.toml`; container handling is stdlib-only by design.
- Never re-encode an entry that is already `.jxl` — only `.jpg`/`.jpeg` transcode. Round-tripping strips the JPEG reconstruction data and silently destroys reversibility.
- Never write output in place; the destination is always `<name>.jxl.cbz`.

## Where things are

- Read the contract before changing behaviour: `_bmad-output/initiative-cbx-jackal/spec-cbz-jxl/`.
- cjxl argv: `cbx_jackal/encode.py`; classification, collision key, ZIP writing, atomic publish: `cbx_jackal/archive.py`.
- Exit codes: `README.md` and `tests/` are authoritative, not the spec. The spec narrows non-zero to "a JPEG entry failed"; the code also returns 1 for an unreadable archive and 2 for a usage or missing-cjxl error.

## Running and verifying

- `python3 -m unittest discover -s tests` — the whole suite; there is no test config in `pyproject.toml`.
- Confirm `cjxl`, `djxl` and `jxlinfo` are on PATH before trusting a green run. Without them the suite still reports OK: `Ran 29 tests ... OK (skipped=27)`, and 128 of 157 never execute.
- Running as root skips the unwritable-directory and unreadable-file error tests (`os.geteuid() != 0`), so they vanish silently in containers.

## Conventions that differ from defaults

- A lossy cjxl call needs `-q N` *and* `--lossless_jpeg=0`; `-q` alone exits 1 and writes nothing. The lossless path passes no flags at all.
- `ZIP_STORED` is hardcoded twice and the two sites must agree (`archive.py:153`, `archive.py:317`).
- Publish as temp file → `fsync` → `os.replace`, with the temp in the destination directory so the rename stays same-filesystem.
- The collision key is `unicodedata.normalize("NFC", name).casefold()` (`archive.py:120`).
- Commit subjects are Conventional Commits: a lowercase `type:` prefix, then the subject. The body carries the reasoning.

## Known pitfalls

- Keep `from __future__ import annotations` in every module. The pervasive `X | None` annotations are legal on the 3.9 floor only because of it.
- `Report.render(quality=...)` defaults to `None`, so a lossy archive rendered without it claims `lossless (JPEG bytes recoverable)`. Losslessness is decided twice — `encode.is_lossless` and `report.py:152`.
- Fixture bytes are load-bearing: `corrupt.jpg` must stay truncated, `page003.png` must stay a PNG, `sample.cbz` must keep 3 unsorted `.jpg` pages. `make_fixtures.py` needs ImageMagick and is not part of the test run; regenerating rewrites the inputs of ~40 tests.

<!-- /bmad:context -->