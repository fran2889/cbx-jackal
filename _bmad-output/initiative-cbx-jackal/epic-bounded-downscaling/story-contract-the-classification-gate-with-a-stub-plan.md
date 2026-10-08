---
title: 'Contract: the classification gate, with a stub'
type: 'feature'
ticket: '6'
created: '2026-10-08'
status: done
baseline_revision: 'd003a7f0dae79fc47e23c291d003340bc4dafbe1'
route: 'full'
route_source: 'auto'
risk: 'medium'
review: 'quick'
review_source: 'pinned'
lenses_ran: ['quick']
review_loop_iteration: 0
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** Entry 6's ruling fixed the source seam's contract, but nothing implements it: the pipeline is
coupled to `zipfile` in six places — the open, the enumeration, the names handed to the gate, the per-entry
pairing, the byte read, and `_stored_info`'s metadata copy — so a source that is not a ZIP cannot be
represented, and `epic-archive-containers` has nothing to fill.

**Approach:** Introduce the seam exactly as ruled — entry names in supplied order, the bytes of one named
entry, an optional per-entry output template — implement `ZipSource` over today's `zipfile` behaviour
byte-for-byte, dispatch by recognised suffix with no fallback, and prove the seam with a stub that names no
real archiver.

## Boundaries & Constraints

**Always:** ZIP input behaviour is unchanged byte-for-byte: the existing suite passes unedited, including
`MetadataPassthrough` and `ContainerContract`. Entry order is supplied by the source, never inferred from a
filesystem walk. The output template is optional with one documented, deterministic default. An unrecognised
container is an `ArchiveError` naming the path — refused before any output, exit 1, the answer it gets today.

**Never:** No real archiver is named, registered, or shelled out to — that is `epic-archive-containers`'
work, and this change exists so that epic has a seam to fill. `classify` does not change. No reader fallback
and no sniffing, per the preflight contract. `discover.py` is not touched: `ARCHIVE_SUFFIXES` gains
`.rar`/`.cb7`/`.7z` in the container epic, not here — the stub registers under a fake suffix in tests only.
No exit-code changes.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|----------|--------------|---------------------------|----------------|
| Stub end-to-end | a `.stub` book: a real JPEG page, `__MACOSX/._page` fork, `extras/` dir, `ComicInfo.xml` | converts through the seam; entry order and count identical; page transcoded, rest passed through | none |
| Unrecognised container | a path whose suffix is not registered | `ArchiveError` naming the path, no output written, exit 1 | refused before any output |
| ZIP through the seam | `sample.cbz` | byte-identical behaviour to today, metadata carried | none |
| Template absent | stub supplies none | entry written with the documented default, deterministic across runs | none |
| Template present | ZIP source | `date_time` and attrs carried exactly as today | none |
| Read failure | stub entry whose read raises | `ArchiveError` naming that entry | aborts the run, no output — as `_read_entry` does today |

</frozen-after-approval>

## Code Map

- `cbx_jackal/archive.py` — where the whole change lives. `classify:66` stays untouched. The six coupling
  sites to rewire: the open at `convert:255`, `_entries:175`, `build_plan:137`, the pairing loop at
  `convert:272`, `_read_entry:180`, `_stored_info:164` (copies `date_time`, `external_attr`,
  `internal_attr`, `create_system`, `comment` from the source `ZipInfo`). `_process:369` takes
  `(info, plan, source, target, report)`.
- `tests/test_archive.py` — the stub's home. `ContainerContract:649` and `MetadataPassthrough:257` are the
  ZIP-behaviour guards this change must not disturb. `RecordingConverter` at `:888` is the established
  precedent for a test subclass. Style: `Converter(self.cjxl)` from `ArchiveTestCase`, `build_zip` from
  `tests/helpers.py:39`.
- `tests/helpers.py` — `build_zip` pins timestamps to `(2026,1,1,0,0,0)`, which is what makes a
  metadata-preservation assertion stable.

## Tasks & Acceptance

**Execution:**
- [ ] `cbx_jackal/archive.py` -- the seam: an `EntrySource` protocol offering `names_in_order()`,
  `read(name)`, `template_for(name)` returning an `EntryTemplate` or `None`, and `close()`; a
  `ZipSource` implementing it over `zipfile` so every current behaviour is preserved byte-for-byte; a
  `SOURCE_READERS` registry keyed by recognised suffix with `open_source(path)` dispatching on it — the
  extension point the container epic fills by registering a reader, and the reason the stub can prove the
  seam without naming an archiver.
- [ ] `cbx_jackal/archive.py` -- rewire `convert`, `_process`, `_read_entry` and `_stored_info` through the
  seam so no `zipfile.ZipInfo` or `zipfile.ZipFile` crosses `Converter`'s boundary; the documented default
  template as one deterministic constant.
- [ ] `tests/test_archive.py` -- a stub source under a fake suffix, registered in tests only: end-to-end
  through `Converter` over the four entry kinds the verify names; the unrecognised-container refusal; the
  absent-template default; and an order-supplied assertion that would fail if anything sorted or walked.

**Acceptance Criteria:**
- Given a stub book holding a page, a resource fork, a directory and a `ComicInfo.xml`, when it converts,
  then all four classifications are today's and the output's entry order and count match the source's.
- Given a path whose suffix no reader claims, when it is converted, then an `ArchiveError` names the path,
  nothing is written, and the exit code is 1.
- Given any ZIP input, when it converts through the seam, then the existing 225 tests pass unedited and the
  output is byte-identical to today's.
- Given a source offering no template, when an entry is written, then it carries the documented default and
  the same value on every run.

## Implementation Notes

The implementation subagent path was dead this session — two dispatches returned empty — so the plan was
implemented directly, which step-03 sanctions when no subagent is available. Every claim below was verified
by running it, not read off a report.

**`writestr` stamps `0o600 << 16` on a fresh entry, and the first version of the default-template test
asserted the wrong thing.** The template's `external_attr = 0` came back as 25165824, and the investigation
that followed settled the real rule: a nonzero attribute is preserved through `_stored_info` — which is why
the ZIP path's attribute copying matters — and `0` means "nothing to carry", so zipfile stamps its own
documented `?rw-------` mode, the same one every entry zipfile itself creates gets. The test now pins that
observable, deterministic outcome instead of the number 0.

**A mutation check caught the no-fallback contract unpinned.** With a silent `ZipSource` fallback installed
in `open_source`, all five seam tests passed: the refusal test fed garbage bytes, so "refused because no
reader" was indistinguishable from "refused because ZipSource could not read it". The fixed test feeds the
`.dat` file a perfectly valid ZIP's bytes — the refusal is by suffix, never content, so a fallback that
opens it anyway fails the test with "ArchiveError not raised". That is the contract's sharpest statement.

The Quick lens found one thing: a comment on the open-failure re-raise that was false on both its claims.
The report does exist when `open_source` raises, and attaching it is inert on that path — the message is
what names the input. The re-raise was kept (the pre-change code attached the same empty report there) and
the comment now says what is true.

Final state: 230 tests OK with `cjxl`, `djxl` and `jxlinfo` on PATH, zero skips, `pyright` clean at the 3.9
floor. Baseline was 225.

## Plan Change Log

## Review Triage Log

Quick lens, 1 finding, pinned `review: 'quick'`. Verified before its verdict; the lens had already
checked it against the pre-change code and the CPython source, and the verification agreed.

| # | Finding | Verdict | Route | Evidence |
|---|---|---|---|---|
| 1 | The comment on the open-failure re-raise is false on both its claims (`archive.py:367-368`) | `low` | `patch` | Confirmed: the `Report` is built at `:356`, nine lines before the call, so "raises before any report exists" is wrong — what is true is that the `ArchiveError` carries none (`report` defaults to `None`). And the CLI renders a report only when it has outcomes (`cli.py:191-198`), which this one never does, so the attachment is inert and the *message* is what names the input. The re-raise itself is behaviour-preserving — the pre-change code attached the same empty report here — so the defect is the comment, not the code. |

`low` kept rather than rejected: the fix is a direct correction of a comment on load-bearing error handling, and
a false explanation of why code exists is exactly what misleads the next maintainer. No `intent_gap`, no
`bad_plan`, so no loopback; `review_loop_iteration` stays 0.

## Design Notes

The registry is the extension point, not a base class. `epic-archive-containers` adds its reader by
registering under `.rar`/`.cb7`/`.7z` in one line, and the stub does the same under a fake suffix in tests —
which is what lets the seam be proven end-to-end without naming any real archiver, exactly as the verify
demands.

`EntryTemplate` is a plain dataclass with the five fields `_stored_info` already copies. The default
constant is deterministic on purpose: `zipfile.ZipInfo`'s own default is `time.localtime()`, which would
make outputs differ run to run and break `DryRunParity`-style comparisons for non-ZIP sources.

The stub needs no filesystem — names and bytes in memory — which is also the cheapest proof the
regular-files-only clause holds: a registry entry that needs no disk cannot violate it.

## Verification

**Commands:**
- `python3 -m unittest discover -s tests` -- expected: `OK`, the pre-change count plus the new ones, zero
  failures, zero skips.
- `pyright` -- expected: no errors at the 3.9 floor `pyrightconfig.json` pins.

Confirm `cjxl`, `djxl` and `jxlinfo` are on PATH before trusting the count: without them the suite still
reports OK while most of it skips.
