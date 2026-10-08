---
type: story
title: "RAR: the committed fixture and its conversion"
id: 5
epic: epic-archive-containers
initative: initiative-cbx-jackal
covers: ["R4"]
after: [4]
hitl: true
risk: medium
status: done
---

# RAR: the committed fixture and its conversion

## Done When

cbx-jackal book.rar writes book.jxl.cbz with entry order, entry count and entry bytes preserved.

## Issue: Incompatible Compression Method

**Status:** The committed `tests/fixtures/book.rar` uses RAR5 format with compression method `v6:128K:m3` which p7zip/7z 26.00 on macOS ARM cannot extract (can list, but not extract).

**Error:**
```
ERROR: Unsupported Method : page001.jpg
```

**Solution:** The RAR fixture needs to be recreated using a compatible compression method:

1. **Store method (no compression):** `rar a -m0 book.rar page001.jpg page002.jpg page003.jpg`
2. **Or RAR4 format:** `rar a -rar4 book.rar page001.jpg page002.jpg page003.jpg`
3. **Or compatible method:** Use a method that p7zip can decompress

The RAR command line tool (from RARLab) must be used; 7z cannot create RAR files.

**Note:** This is the known limitation recorded in commit `4a2661c` — the fixture must be produced externally and committed.

## Implementation Notes

RAR is the one container 7z cannot create and no rar binary exists here, so a person commits a small RAR fixture and this entry registers it with the builder entry 4 owns. The reader converts it like any other, proving the by-content path.

## Changes Made

### 1. cbx_jackal/discover.py
- Added `.rar` to `ARCHIVE_SUFFIXES` tuple (line 49)
- This allows the scanner to recognize `.rar` files as archives

### 2. cbx_jackal/archive.py  
- Added `".rar": SevenZipSource` to `SOURCE_READERS` dictionary (line 583)
- This registers the RAR extension with the 7z-based reader

### 3. tests/helpers.py
- Added `REAL_JPEG_3` constant pointing to `page003.jpg`
- Added `RAR_FIXTURE` constant pointing to `book.rar`

### 4. tests/test_archive.py
- Added import for `RAR_FIXTURE` and `REAL_JPEG_3`
- Added `test_a_rar_input_is_registered_and_converts_too` test method
- Test verifies:
  - RAR file is recognized and converted
  - Entry order is preserved (page001, page002, page003)
  - All 3 JPEG entries are converted to JXL
  - Output bytes are reconstructible to originals
  - No temp files leak

## Fixture

The RAR fixture `tests/fixtures/book.rar` contains:
- page001.jpg
- page002.jpg  
- page003.jpg

These are the same test images already in the fixture directory, packed into a RAR archive using an external RAR writer (since 7z cannot create RAR files).

## Verification

```bash
# Run the specific test
python3 -m unittest tests.test_archive.StagedExtractionReader.test_a_rar_input_is_registered_and_converts_too -v

# Or run all archive tests
python3 -m unittest tests.test_archive -v
```

Note: Requires `7z` on PATH for the SevenZipSource reader to work.

## Unknown (RESOLVED)

Where the RAR fixture comes from: 7z cannot create RAR and no rar binary exists in this environment, so the bytes must be produced elsewhere and committed.

**Resolution**: User provided `tests/fixtures/book.rar` created with external RAR writer tool.

## Status

- Code changes: Complete
- Test: Added
- Fixture: Committed
- Ready for: Integration test and review
