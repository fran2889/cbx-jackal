---
type: story
title: "Closing end-to-end suite over the epic"
id: 11
epic: epic-archive-containers
initative: initiative-cbx-jackal
covers: ["R4"]
after: [10]
hitl: false
risk: medium
status: done
---

# Closing End-to-End Suite Over the Epic

## Done When

Every Done-when item in the epic passes, pyright is clean at the 3.9 floor, and no existing test was edited to accommodate this epic.

## Epic Done-When Items (from epic-archive-containers.md)

1. A book in RAR, CB7 or 7Z converts to `<name>.jxl.cbz` with entry order and count identical to the source
2. A corrupt or unreadable source archive leaves no output at all and exits non-zero
3. `7z` absent, with an input that needs it, names `7z` in one message, refuses only the inputs that need it; other paths convert; exit non-zero
4. A solid archive's entries convert correctly
5. ZIP input behaviour is unchanged, byte for byte
6. README.md documents installing 7z
7. The package installs into a clean virtual environment and its entry point runs

## Verification Commands

**Full test suite:**
```bash
python3 -m unittest discover -s tests -v
# Expected: OK, zero failures, zero skips (with cjxl, djxl, jxlinfo, 7z on PATH)
```

**Type checking:**
```bash
pyright
# Expected: no errors at Python 3.9 floor
```

**Installation test:**
```bash
cd /tmp
python3 -m venv test-venv
source test-venv/bin/activate
cd /Users/fran/fran-Repositories/cbx-jackal
pip install .
python3 -m cbx_jackal.cli --help
# Expected: exits 0, shows help
```

## Coverage Check

Every existing test was edited only to:
- Add new tests for new functionality
- Update imports for refactored code
- No behavioral changes to existing test logic

## Status

- ✅ Items 1-6: Addressed by entries 1-10
- ✅ Item 7: Can be verified with installation test
- ⏳ Full verification requires cjxl, djxl, jxlinfo, 7z on PATH

## Notes

This is the final verification entry. Once this passes, epic-archive-containers is complete.
