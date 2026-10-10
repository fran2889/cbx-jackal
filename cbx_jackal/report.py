# Copyright (C) 2026 Fran
# SPDX-License-Identifier: GPL-3.0-only
"""Per-entry outcome classification and reporting.

Three classes, not two. Conflating the second and third would make a healthy
run look broken, and the exit-code contract depends on the distinction:

| Class          | Meaning                                             | Exit code |
|----------------|-----------------------------------------------------|-----------|
| converted      | JPEG page successfully transcoded                   | no        |
| passed through | non-JPEG entry, or one not deliberately transcoded  | no        |
| not converted  | JPEG entry left as-is because `cjxl` failed         | **yes**   |

Pass-throughs are normal. ComicInfo.xml, readme.txt, resource forks and nested
directories all pass through on every healthy run, so counting them as failures
would mean no archive ever converted successfully.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .report_downscale import ExtendedEntryOutcome

CONVERTED = "converted"
PASSED_THROUGH = "passed through"
NOT_CONVERTED = "not converted"


@dataclass
class EntryOutcome:
    """What happened to one archive entry."""

    name: str
    classification: str
    #: Populated only for `NOT_CONVERTED`: the one-line cjxl diagnostic.
    reason: str | None = None
    source_size: int = 0
    output_size: int = 0

    @property
    def failed(self) -> bool:
        return self.classification == NOT_CONVERTED


@dataclass
class Report:
    """Accumulates outcomes and renders the per-failure lines plus summary."""

    source: str
    destination: str
    outcomes: list[EntryOutcome] = field(default_factory=list)
    #: Populated when the run aborted before or during archive writing.
    abort_reason: str | None = None
    #: Size of the source archive on disk. Set by the caller.
    source_size_bytes: int | None = None
    #: Size of the published archive on disk. None until it is published, and
    #: None for good on a dry run or an abort.
    output_size_bytes: int | None = None
    #: Extended outcomes for downscaling and spread reporting (for entry 12-14 integration)
    _extended_outcomes: list = field(default_factory=list)

    def add(self, outcome: EntryOutcome) -> EntryOutcome:
        self.outcomes.append(outcome)
        return outcome

    def count(self, classification: str) -> int:
        return sum(1 for o in self.outcomes if o.classification == classification)

    @property
    def converted(self) -> int:
        return self.count(CONVERTED)

    @property
    def passed_through(self) -> int:
        return self.count(PASSED_THROUGH)

    @property
    def not_converted(self) -> int:
        return self.count(NOT_CONVERTED)

    @property
    def total(self) -> int:
        return len(self.outcomes)

    @property
    def failures(self) -> list[EntryOutcome]:
        return [o for o in self.outcomes if o.failed]

    @property
    def ok(self) -> bool:
        """True when no JPEG entry failed to convert.

        The exit code is non-zero if and only if a JPEG entry failed to convert,
        so an abort is also a failure.
        """
        return not self.failures and self.abort_reason is None

    @property
    def source_bytes(self) -> int:
        return sum(o.source_size for o in self.outcomes)

    @property
    def output_bytes(self) -> int:
        return sum(o.output_size for o in self.outcomes)

    def summary(self) -> str:
        return (
            f"{self.converted}/{self.total} converted, "
            f"{self.passed_through} passed through, "
            f"{self.not_converted} not converted"
        )

    def failure_lines(self) -> list[str]:
        lines = []
        for outcome in self.failures:
            reason = outcome.reason or "cjxl failed"
            lines.append(f"{outcome.name}: {reason}")
        if self.abort_reason:
            lines.append(f"aborted: {self.abort_reason}")
        return lines

    @staticmethod
    def _percentage(before: int, after: int) -> str:
        if before <= 0:
            return f"{after} bytes"
        change = (before - after) / before * 100.0
        direction = "smaller" if change >= 0 else "larger"
        return f"{before} -> {after} bytes ({abs(change):.1f}% {direction})"

    def size_line(self) -> str | None:
        """Describe the archives as they exist on disk, not as payload sums.

        Entry payload bytes are not the file's size: ZIP framing, the central
        directory, and whatever compression the *source* used all sit outside
        them. Summing payloads could claim a 43% saving on a deflated archive
        whose published file was 5% smaller, or hide an archive that grew. So the
        published figure is `os.path.getsize` of the file actually written, and
        the fallback for a dry run -- where no file exists -- says so rather than
        quietly passing an estimate off as a measurement.
        """
        if self.source_size_bytes is None:
            return None

        if self.output_size_bytes is not None:
            return self._percentage(self.source_size_bytes, self.output_size_bytes)

        if self.total == 0:
            return f"{self.source_size_bytes} bytes in"

        before, after = self.source_bytes, self.output_bytes
        line = self._percentage(before, after)
        return f"{line} (entry data only; no archive written)"

    def render(self, quality: int | None = None, dry_run: bool = False) -> str:
        """Full human-facing report: mode, per-failure lines, summary, sizes."""
        from .report_downscale import format_per_page_lines, format_run_level_mode
        
        lines = [f"{self.source} -> {self.destination}"]
        
        # Use extended mode formatting if we have downscaling/spread info
        if self._extended_outcomes:
            # Lossy if any page was actually resized, whatever --quality said.
            downscaled = any(o.downscaled is not None for o in self._extended_outcomes)
            mode_line = format_run_level_mode(quality, downscaled=downscaled)
        else:
            if quality is None or quality >= 100:
                mode = "lossless (JPEG bytes recoverable with djxl)"
            else:
                mode = f"lossy, quality {quality} (JPEG bytes NOT recoverable)"
            mode_line = f"mode: {mode}{' [dry run, nothing written]' if dry_run else ''}"
        
        lines.append(mode_line)
        lines.extend(self.failure_lines())
        
        # Add per-page lines for downscaled and spread pages
        if self._extended_outcomes:
            from .report_downscale import format_per_page_lines
            per_page_lines = format_per_page_lines(self._extended_outcomes)
            lines.extend(per_page_lines)
        
        lines.append(self.summary())
        size_line = self.size_line()
        if size_line:
            lines.append(size_line)
        return "\n".join(lines)
