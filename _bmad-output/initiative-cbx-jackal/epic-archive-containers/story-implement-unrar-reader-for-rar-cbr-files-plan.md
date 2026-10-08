---
title: 'Implement unrar reader for RAR/CBR files'
type: 'feature'
ticket: '12'
created: '2026-10-08'
status: done
baseline_revision: 'unknown'
route: 'full'
route_source: 'auto'
risk: 'medium'
---

# Plan: Implement unrar reader for RAR/CBR files

## Implementation Steps

1. **Fix UnrarSource parsing**: Update `_parse_unrar_listing()` to handle actual unrar `l` command output format
2. **Test UnrarSource**: Verify with existing `tests/fixtures/book.rar`
3. **Update Entry 5**: Modify RAR fixture conversion to use the new unrar reader
4. **Update Entry 3**: Verify preflight checks work for both unrar and 7z
5. **Add test cases**: Create test coverage for unrar functionality
6. **Update README**: Add unrar installation instructions

## Current Status

- Code structure added for UnrarSource
- Preflight system updated for unrar
- CLI tool checking updated for unrar
- Needs: Parsing logic fix, integration testing, test coverage

## Verification Plan

- [ ] `cbx-jackal tests/fixtures/book.rar` produces `tests/fixtures/book.jxl.cbz`
- [ ] Entry order and count preserved
- [ ] Non-converted entries byte-identical
- [ ] Missing unrar produces clear error message
- [ ] CB7/7Z still work with 7z
- [ ] All existing tests pass

## Dependencies

- Requires unrar binary on PATH
- Requires existing RAR fixture at `tests/fixtures/book.rar`

## Notes

Unrar command format differs from 7z:
- Listing: `unrar l archive.rar` (vs `7z l -slt archive.cb7`)
- Extraction: `unrar x archive.rar output_dir/` (vs `7z x -y -ooutput_dir archive.cb7`)
- Output format is simpler table vs complex key=value blocks