---
type: story
title: "Refactor sweep"
id: 10
epic: epic-archive-containers
initative: initiative-cbx-jackal
covers: ["R4"]
after: [2, 3, 4, 5, 6, 7, 8, 9]
hitl: false
risk: low
status: in-progress
---

# Refactor Sweep

## Done When

The suite and pyright are still green at the 3.9 floor, and each cleanup is traceable to a finding recorded during this epic.

## Cleanup Items Addressed

### 1. SEVENZIP constant consolidation (from entry 4 finding)
- **Finding**: `archive.py` carried a third copy of `SEVENZIP = "7z"` while `preflight.py` and `helpers.py` use `preflight.SEVENZIP`
- **Fix**: 
  - Added `from . import preflight` to archive.py imports
  - Removed local `SEVENZIP = "7z"` definition from archive.py
  - Updated `shutil.which(SEVENZIP)` → `shutil.which(preflight.SEVENZIP)`
  - Updated error message to use `preflight.SEVENZIP`
- **Note**: `SEVENZIP_WORKDIR_PREFIX` remains as a separate constant (prefix naming only)

### 2. Dead function removal (from entry 3 finding)
- **Finding**: `missing_tool_message` and `check` functions are dead in production; kept only for existing test suite
- **Fix**:
  - Removed `missing_tool_message` from preflight.py
  - Removed `check` from preflight.py
  - Updated `MissingDependency` test class in test_archive.py to use new API:
    - `missing_tool_message()` → `missing_message([TOOLS[TOOL]])`
    - `check()` → `find_tool()`
    - Renamed tests to reflect new function names

## Verification

- ✅ `python3 -m py_compile cbx_jackal/archive.py` — passes
- ✅ `python3 -m py_compile cbx_jackal/preflight.py` — passes  
- ✅ `python3 -m py_compile tests/test_archive.py` — passes
- ⏳ `python3 -m unittest tests.test_archive.MissingDependency` — requires cjxl on PATH
- ⏳ `pyright` — requires Python 3.9+

## Changes Made

1. **cbx_jackal/archive.py**: 
   - Added import: `from . import preflight`
   - Removed: `SEVENZIP = "7z"`
   - Updated: `shutil.which(preflight.SEVENZIP)` and error messages

2. **cbx_jackal/preflight.py**:
   - Removed: `missing_tool_message()` function (38 lines)
   - Removed: `check()` function

3. **tests/test_archive.py**:
   - Updated `MissingDependency` class to use new preflight API
   - 6 tests updated to use `missing_message()` and `find_tool()`

## Notes

All cleanup items traced to specific findings recorded in entry 3 and entry 4 plan files. No additional refactoring beyond what was explicitly deferred.
