---
title: 'Fixtures: the full set'
type: 'feature'
ticket: '2'
created: '2026-10-08'
status: done
baseline_revision: ''
route: 'full'
route_source: 'auto'
risk: 'low'
review: 'quick'
review_source: 'pinned'
lenses_ran: []
context: ['{project-root}/tests/fixtures/exif_injector.py']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The geometry and report entries need a comprehensive set of test fixtures to prove their behavior: all eight EXIF orientation values, spreads at various aspect ratios, edge cases for the spread detection, and pages with/without EXIF tags. The ImageMagick build in use cannot write EXIF orientation tags, so Entry 1 built an injector. Entry 2 uses it to generate all fixtures.

**Approach:** Extend `tests/fixtures/make_fixtures.py` to generate all required fixtures using ImageMagick for base image creation and `exif_injector.inject_orientation` for orientation tagging. Ensure byte-stability by writing deterministic generation code.

## Boundaries & Constraints

**Always:**
- Fixtures are generated, not hand-crafted binary blobs
- Running `python3 make_fixtures.py` twice produces byte-identical output
- All eight orientation values are represented
- Spread boundaries are exactly at 1.35:1
- Fixtures use consistent sizes that make the geometry decisions clear
- The `sideways_no_tag.jpg` has no EXIF APP1 segment at all

**Never:**
- Do not use PIL/Pillow or any Python imaging library
- Do not add external dependencies beyond ImageMagick (which is already required)
- Do not check generated fixtures into git (they are generated artifacts)
- Do not modify existing fixtures (`sample.cbz`, `page001.jpg`, etc.)

## I/O & Edge-Case Matrix

| Fixture | Size | Orientation | Spread Exempt? | Notes |
|--------|------|-------------|---------------|-------|
| page_orient_1.jpg | 2000x3000 | 1 (normal) | No | Portrait |
| page_orient_2.jpg | 2000x3000 | 2 (mirrored) | No | Portrait |
| page_orient_3.jpg | 2000x3000 | 3 (180°) | No | Portrait |
| page_orient_4.jpg | 2000x3000 | 4 (mirror+180°) | No | Portrait |
| page_orient_5.jpg | 2000x3000 | 5 (mirror+270°CW) | No | Portrait |
| page_orient_6.jpg | 2000x3000 | 6 (90°CW) | No | **Display: 3000x2000** |
| page_orient_7.jpg | 2000x3000 | 7 (mirror+90°CW) | No | Portrait |
| page_orient_8.jpg | 2000x3000 | 8 (270°CW) | No | Portrait |
| spread_exact_1.35.jpg | 2000x1481 | 1 | **Yes** | 2000/1481 = 1.35:1 exactly |
| spread_above_1.35.jpg | 2000x1300 | 1 | **Yes** | 2000/1300 ≈ 1.54 > 1.35 |
| spread_below_1.35.jpg | 2000x1500 | 1 | No | 2000/1500 ≈ 1.33 < 1.35 |
| landscape_splash.jpg | 3000x1000 | 1 | No | Wide, misread as spread |
| sideways_no_tag.jpg | 2000x3000 | None | No | Portrait, no EXIF |

## Code Map

- `tests/fixtures/make_fixtures.py` — **extended**. Add fixture generation functions:
  - `_create_base_jpeg(width, height, color)` — create a plain JPEG
  - `_inject_orientation(path, orientation)` — inject orientation using exif_injector
  - `generate_orientation_fixtures()` — all 8 orientation values
  - `generate_spread_fixtures()` — exact, above, below 1.35:1
  - `generate_edge_case_fixtures()` — landscape splash, sideways no tag
  - `main()` — extended to call all generators

## Tasks & Acceptance

**Execution:**
- [ ] Extend `make_fixtures.py` with fixture generation functions
- [ ] Add all orientation fixtures (page_orient_1.jpg through page_orient_8.jpg)
- [ ] Add spread fixtures (spread_exact_1.35.jpg, spread_above_1.35.jpg, spread_below_1.35.jpg)
- [ ] Add edge case fixtures (landscape_splash.jpg, sideways_no_tag.jpg)
- [ ] Verify byte-stability: run make_fixtures.py twice, compare outputs
- [ ] Verify ImageMagick reads correct orientation for all orientation fixtures
- [ ] Add all fixtures to a new test archive for geometry tests

**Acceptance Criteria:**
- `python3 tests/fixtures/make_fixtures.py` runs successfully and generates all new fixtures
- Running the script a second time produces byte-identical fixtures
- `magick identify -format %wx%h` returns expected dimensions for each fixture
- `magick identify -format %[exif:Orientation]` returns correct orientation for orientation fixtures
- `magick identify -format %[exif:Orientation]` returns empty for sideways_no_tag.jpg
- The existing `sample.cbz` and its fixtures remain unchanged
- With `cjxl`, `djxl`, `jxlinfo`, and `magick` on PATH, the full test suite reports zero skips

## Design Notes

**Fixture Sizes:**
- Orientation fixtures: 2000x3000 base, orientation applied
- Spread exact: 2000x1481 (2000/1481 = 1.35 exactly)
- Spread above: 2000x1300 (2000/1300 ≈ 1.538)
- Spread below: 2000x1500 (2000/1500 ≈ 1.333)
- Landscape splash: 3000x1000 (3.0:1)
- Sideways no tag: 2000x3000 (no EXIF)

**Spread Detection:**
The spread test compares the display aspect ratio against 1.35:1. Display aspect ratio is:
- For images with EXIF orientation: width/height after applying the rotation
- For images without EXIF: width/height as-is

Orientation 6 (90° CW) swaps width and height, so 2000x3000 becomes 3000x2000 in display terms, with aspect ratio 1.5:1, which is > 1.35:1 and should be exempt.

**Byte Stability:**
All fixtures are generated with deterministic parameters. ImageMagick's output may vary slightly between versions, so we:
1. Generate the base JPEG with fixed parameters
2. Strip any timestamps/metadata that might vary
3. Use the same color values and compression settings

**sideways_no_tag.jpg:**
This fixture must have NO EXIF at all. It represents a page that was scanned sideways but has no orientation metadata. The geometry code should detect this based on pixel dimensions alone, treating it as landscape.

## Verification

**Commands:**
- `python3 tests/fixtures/make_fixtures.py` — expected: all fixtures generated
- `md5sum tests/fixtures/*.jpg` — run twice, expected: identical checksums
- `magick identify -format '%f: %wx%h (orientation: %[exif:Orientation])\n' tests/fixtures/page_orient_*.jpg` — expected: correct dimensions and orientations
- `magick identify -format '%f: %wx%h\n' tests/fixtures/spread_*.jpg` — expected: correct dimensions
- `python3 -m unittest discover -s tests -v` — expected: all tests pass, zero skips

## Notes

- The `_bmad-output` and `tests/fixtures` directories are in `.gitignore`, so generated fixtures won't be committed accidentally
- For CI/testing, the fixtures need to be generated as part of the test setup
- The make_fixtures.py script should be idempotent: safe to run multiple times

</frozen-after-approval>

## Plan Change Log

## Review Triage Log

## Design Notes
