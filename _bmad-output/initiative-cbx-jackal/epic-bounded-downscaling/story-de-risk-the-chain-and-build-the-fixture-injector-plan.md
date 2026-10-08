---
title: 'De-risk the chain and build the fixture injector'
type: 'spike'
ticket: '1'
created: '2026-10-08'
status: in_progress
baseline_revision: ''
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: []
context: ['{project-root}/cbx_jackal/archive.py', '{project-root}/cbx_jackal/encode.py']
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** The ImageMagick build in use cannot write EXIF orientation tags (`-set exif:Orientation` produces no APP1 segment), yet the downscaling epic requires fixtures with all eight orientation values to prove the geometry and spread logic. Entry 1 de-risks this by building a byte-level EXIF APP1 injector that can add orientation to any JPEG, then proving the full chain: orientation injection → magick resize → cjxl encode → djxl decode.

**Approach:** Create `tests/fixtures/exif_injector.py` with a function `inject_orientation(jpeg_bytes: bytes, orientation: int) -> bytes` that inserts or updates the EXIF APP1 marker with the specified orientation value, preserving all other data. Then create a test script that: (1) generates a synthetic oversized JPEG, (2) injects orientation 6, (3) passes it through a modified Converter call that invokes magick for resize, (4) verifies ImageMagick reads the orientation from both input and output.

## Boundaries & Constraints

**Always:**
- The injector works on raw JPEG bytes, not files
- The injector handles JPEGs that already have EXIF (updates) or don't (inserts)
- The injector preserves all existing APP segments that are not EXIF
- The chain test uses the existing `Converter` class, called directly (not via CLI)
- The test passes the box dimensions programmatically to the Converter

**Never:**
- Do not use PIL/Pillow or any Python imaging library (project constraint)
- Do not modify the existing `Converter` or `encode` modules for this spike
- Do not add external dependencies
- Do not commit the test script to the main codebase (it is a spike artifact)

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Inject orientation into plain JPEG | 1000x1500 JPEG, no EXIF | APP1 segment with orientation=6 added | None |
| Inject orientation into JPEG with EXIF | 1000x1500 JPEG, existing EXIF | EXIF orientation field updated to 6 | None |
| Inject orientation 1 | Any JPEG | APP1 segment with orientation=1 (normal) | None |
| Inject orientation 8 | Any JPEG | APP1 segment with orientation=8 (rotated 90° CCW) | None |
| Chain test: orientation 6 | 2480x3508 JPEG (portrait), orient=6 | Resized to 1600x2260, orient=6 preserved | magick reads orient=6 from output |
| Chain test: no magick | Same as above | Clean failure with clear message | Exit non-zero |

## Code Map

- `tests/fixtures/exif_injector.py` — **new**. `inject_orientation(jpeg_bytes, orientation)` and helper functions for EXIF APP1 segment construction.
- `tests/fixtures/test_exif_injector.py` — **new**. Unit tests for the injector over all eight orientation values.
- `tests/fixtures/spike_chain_test.py` — **new**. Script that exercises the full chain and prints PASS/FAIL.
- `cbx_jackal/geometry.py` — **stub for this spike only**. Temporary module with `get_display_dimensions(bytes) -> (width, height)` and `needs_downscale(width, height, max_width, max_height) -> bool` to pass to Converter. **Not committed; spike artifact.**

</frozen-after-approval>

## Tasks & Acceptance

**Execution:**

### Phase 1: EXIF Injector
- [ ] Research JPEG APP1 segment structure and EXIF format
- [ ] Implement `inject_orientation()` in `tests/fixtures/exif_injector.py`
- [ ] Implement EXIF APP1 segment construction with orientation field
- [ ] Handle both insertion and update cases
- [ ] Write unit tests for all eight orientation values (1-8)
- [ ] Verify injector output with `jxlinfo` or `exiftool` (if available)

### Phase 2: Chain Test
- [ ] Create `spike_chain_test.py` that:
  - [ ] Generates a synthetic 2480x3508 JPEG (use existing ImageMagick if it works, or find another way)
  - [ ] Injects orientation 6 (rotated 90° CW)
  - [ ] Calls `Converter` directly with a modified `_process` that resizes via magick
  - [ ] Verifies the output page is downscaled
  - [ ] Verifies ImageMagick reads orientation 6 from the output
- [ ] Run the test with `cjxl`, `magick` on PATH
- [ ] Document the result

**Acceptance Criteria:**
- `inject_orientation()` correctly adds/updates EXIF orientation in raw JPEG bytes for all values 1-8
- A synthetic oversized JPEG with injected orientation 6 passes through a direct `Converter` call and produces a downscaled output
- `magick identify -format %[exif:Orientation] input.jpg` returns the injected orientation value
- The same command on the downscaled JXL output returns the same orientation (proving the PNG intermediate preserves it via ImageMagick)
- No external dependencies added
- No changes to existing production code (`cbx_jackal/`)

## Design Notes

### EXIF APP1 Segment Structure

A JPEG APP1 segment carrying EXIF has this structure:
```
FF D8                  # SOI (Start of Image)
FF E1 xx xx            # APP1 marker (0xFFE1) + 2-byte length (includes marker)
45 78 69 66 00 00     # "Exif\0\0" identifier
[EXIF data in TIFF format]
```

The EXIF data is a TIFF IFD (Image File Directory) with specific tags. The orientation tag is:
- Tag ID: 0x0112 (274 decimal)
- Tag Type: SHORT (2 bytes)
- Count: 1
- Value: 1-8 (the orientation value)

For simplicity, we can construct a minimal EXIF block with just the orientation tag.

### Minimal EXIF Construction

A minimal EXIF block for orientation only:
1. TIFF header: byte order (II or MM), version (42), offset to IFD0
2. IFD0: single entry for orientation tag
3. Tag data: the orientation value

Byte order: Use `II` (little-endian, Intel)
- `49 49 2A 00` — II, version 42
- `08 00 00 00` — offset to IFD0 (8 bytes from start of TIFF header)
- `01 00` — 1 entry in IFD0
- `01 12 00 03 00 00 00 01` — Tag 0x0112, type SHORT (3), count 1, value offset
- `XX XX 00 00` — The orientation value (2 bytes, little-endian), followed by 2 bytes padding

### Orientation Values

EXIF orientation values:
1. Normal (0°)
2. Mirrored (flip horizontal)
3. Rotated 180°
4. Mirrored and rotated 180°
5. Mirrored and rotated 270° CW (or 90° CCW)
6. Rotated 90° CW (or 270° CCW)
7. Mirrored and rotated 90° CW
8. Rotated 270° CW (or 90° CCW)

### Chain Test Implementation

The spike can use a temporary `_downscale_process()` function that:
1. Checks if the entry is a JPEG
2. Uses ImageMagick to resize (with `-auto-orient` to apply the EXIF rotation)
3. Passes the resized PNG to `cjxl`
4. Returns the encoded JXL bytes

This is thrown away after the spike proves the chain works.

## Verification

**Commands:**
- `python3 tests/fixtures/test_exif_injector.py` — expected: all orientation tests pass
- `python3 tests/fixtures/spike_chain_test.py` — expected: PASS, with downscaled dimensions and orientation preserved
- `python3 -m unittest discover -s tests` — expected: unchanged from baseline (no production code modified)
- `pyright` — expected: no errors

**Tools required:**
- `magick` (ImageMagick 7) for resize and orientation reading
- `cjxl`, `djxl` from libjxl-tools
- Optionally `jxlinfo` or `exiftool` for EXIF verification
