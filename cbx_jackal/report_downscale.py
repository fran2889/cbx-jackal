# Copyright (C) 2026 Fran
# SPDX-License-Identifier: GPL-3.0-only
"""Extended reporting for downscaled and spread-exempt pages.

This module extends the base reporting with downscaling and spread information
that Contract 1.4 specifies. Downscaled and spread-exempt are not classes -- they
remain `converted` in the exit-code contract -- but they are reported with
additional detail in the output.

Entry 10 carries the per-page reporting implementation per the clause map:
"8 the orientation and spread rules; 9 the invocation; 10 the per-page reporting".

Recoverability vocabulary from Contract 1.4:
- `source`: djxl reproduces the source JPEG byte-for-byte
- `pixels`: exact pixels survive, the source JPEG file does not
- `intermediate`: recoverable as the intermediate only (unreachable: djxl
  reproduces the intermediate exactly, which is the `pixels` wording above)
- `none`: lossy; nothing recovers the page
"""

from dataclasses import dataclass, field
from typing import Literal

# Recoverability values per Contract 1.4
SOURCE = "source"  # djxl reproduces the source JPEG byte-for-byte
PIXELS = "pixels"  # exact pixels survive, the source JPEG file does not
INTERMEDIATE = "intermediate"  # recoverable as the intermediate only (unreachable)
NONE = "none"  # lossy; nothing recovers the page

# Valid recoverability values
RecoverabilityValue = Literal["source", "pixels", "intermediate", "none"]


@dataclass(frozen=True)
class DownscaledInfo:
    """Additional information for a downscaled page."""
    original_width: int
    original_height: int
    target_width: int
    target_height: int


@dataclass(frozen=True)
class SpreadInfo:
    """Additional information for a spread-exempt page."""
    display_width: int
    display_height: int


@dataclass
class ExtendedEntryOutcome:
    """Extended entry outcome with downscaling and spread information.
    
    This extends the base EntryOutcome with optional fields for per-page
    reporting of downscaled and spread-exempt pages.
    """
    name: str
    classification: str
    #: Populated only for `NOT_CONVERTED`: the one-line cjxl diagnostic.
    reason: str | None = None
    source_size: int = 0
    output_size: int = 0
    #: Downscaling information, if the page was downscaled.
    downscaled: DownscaledInfo | None = None
    #: Spread information, if the page is a spread-exempt.
    spread: SpreadInfo | None = None
    #: Recoverability value for this page: source, pixels, intermediate, or none.
    recoverability: RecoverabilityValue | None = None

    @property
    def failed(self) -> bool:
        from .report import NOT_CONVERTED
        return self.classification == NOT_CONVERTED

    def format_per_page_line(self) -> str | None:
        """Format the per-page report line for this outcome.
        
        Returns the per-page line for downscaled or spread-exempt pages,
        or None for regular pages.
        """
        if self.downscaled is not None:
            if self.recoverability == PIXELS:
                return (f"{self.name}: downscaled {self.downscaled.original_width}x{self.downscaled.original_height} -> "
                        f"{self.downscaled.target_width}x{self.downscaled.target_height}, "
                        f"pixels recoverable, source JPEG not")
            elif self.recoverability == INTERMEDIATE:
                return (f"{self.name}: downscaled {self.downscaled.original_width}x{self.downscaled.original_height} -> "
                        f"{self.downscaled.target_width}x{self.downscaled.target_height}, "
                        f"recoverable as the intermediate only")
            elif self.recoverability == SOURCE:
                return (f"{self.name}: downscaled {self.downscaled.original_width}x{self.downscaled.original_height} -> "
                        f"{self.downscaled.target_width}x{self.downscaled.target_height}, "
                        f"source recoverable")
            else:
                # Default for downscaled without specific recoverability
                return (f"{self.name}: downscaled {self.downscaled.original_width}x{self.downscaled.original_height} -> "
                        f"{self.downscaled.target_width}x{self.downscaled.target_height}")
        
        elif self.spread is not None:
            return f"{self.name}: spread kept at {self.spread.display_width}x{self.spread.display_height}, exempt from the width rule"
        
        return None


@dataclass
class DownscaleReport:
    """Tracks downscaling statistics across a run."""
    
    downscaled_count: int = 0
    spread_count: int = 0
    
    # Counts by recoverability value for downscaled pages
    pixels_count: int = 0
    intermediate_count: int = 0
    source_count: int = 0
    
    def add_downscaled(self, recoverability: RecoverabilityValue) -> None:
        """Record a downscaled page with its recoverability."""
        self.downscaled_count += 1
        if recoverability == PIXELS:
            self.pixels_count += 1
        elif recoverability == INTERMEDIATE:
            self.intermediate_count += 1
        elif recoverability == SOURCE:
            self.source_count += 1
    
    def add_spread(self) -> None:
        """Record a spread-exempt page."""
        self.spread_count += 1
    
    @property
    def has_downscaled(self) -> bool:
        """Whether any pages were downscaled."""
        return self.downscaled_count > 0
    
    @property
    def has_spreads(self) -> bool:
        """Whether any pages were spread-exempt."""
        return self.spread_count > 0
    
    def format_mode_suffix(self) -> str | None:
        """Format the mode line suffix for downscaling information.
        
        Returns the suffix for the mode line, or None if no downscaling occurred.
        """
        if not self.has_downscaled:
            return None
        
        # A downscaled page always reports "pixels": djxl reproduces the
        # intermediate exactly, but the source JPEG is not what it hands back.
        # "intermediate" is unreachable for the same reason as with any
        # intermediate that decodes losslessly.
        if self.pixels_count > 0:
            return f", {self.downscaled_count} of {self.downscaled_count + self.spread_count} pages downscaled (pixels recoverable, source JPEG not)"
        elif self.intermediate_count > 0:
            return f", {self.downscaled_count} of {self.downscaled_count + self.spread_count} pages downscaled (recoverable as the intermediate only)"
        else:
            return f", {self.downscaled_count} of {self.downscaled_count + self.spread_count} pages downscaled"


class DownscaleReportBuilder:
    """Helper to build downscaling report information from a run."""
    
    def __init__(self):
        self.report = DownscaleReport()
    
    def add_entry(self, outcome: ExtendedEntryOutcome) -> None:
        """Add an entry outcome to the report statistics."""
        if outcome.downscaled is not None and outcome.recoverability is not None:
            self.report.add_downscaled(outcome.recoverability)
        elif outcome.spread is not None:
            self.report.add_spread()
    
    def get_report(self) -> DownscaleReport:
        """Get the final report."""
        return self.report


def create_extended_outcome(
    name: str,
    classification: str,
    reason: str | None = None,
    source_size: int = 0,
    output_size: int = 0,
    downscaled: DownscaledInfo | None = None,
    spread: SpreadInfo | None = None,
    recoverability: RecoverabilityValue | None = None
) -> ExtendedEntryOutcome:
    """Factory function to create an ExtendedEntryOutcome."""
    return ExtendedEntryOutcome(
        name=name,
        classification=classification,
        reason=reason,
        source_size=source_size,
        output_size=output_size,
        downscaled=downscaled,
        spread=spread,
        recoverability=recoverability
    )


def format_run_level_mode(
    quality: int | None,
    downscale_report: DownscaleReport | None = None,
    downscaled: bool = False,
) -> str:
    """Format the run-level mode line with optional downscaling information.
    
    A downscaled page is lossy whatever `quality` says. The resample discards
    pixels and the intermediate is itself a re-encode, so the source JPEG is
    already gone before `cjxl` is called; `cjxl` preserving the intermediate
    losslessly does not undo that. Claiming losslessness here would promise
    recovery of a JPEG that no longer exists.
    
    Args:
        quality: The quality value from CLI (None for lossless)
        downscale_report: Optional downscaling statistics
        downscaled: True when any page in this run was downscaled
    
    Returns:
        The formatted mode line.
    """
    if quality is not None and quality < 100:
        mode = f"lossy, quality {quality} (JPEG bytes NOT recoverable)"
    elif downscaled or (downscale_report is not None and downscale_report.has_downscaled):
        mode = "lossy (downscaled; JPEG bytes NOT recoverable)"
    else:
        mode = "lossless (JPEG bytes recoverable with djxl)"
    
    # Add downscaling suffix if present
    suffix = downscale_report.format_mode_suffix() if downscale_report else None
    if suffix:
        mode += suffix
    
    return f"mode: {mode}"


def format_per_page_lines(outcomes: list[ExtendedEntryOutcome]) -> list[str]:
    """Format per-page report lines for downscaled and spread-exempt pages.
    
    Regular converted and pass-through pages have no per-page line.
    
    Args:
        outcomes: List of extended entry outcomes
    
    Returns:
        List of formatted per-page lines
    """
    lines = []
    for outcome in outcomes:
        line = outcome.format_per_page_line()
        if line:
            lines.append(line)
    return lines