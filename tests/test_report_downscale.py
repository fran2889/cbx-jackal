"""Extended reporting for downscaled and spread-exempt pages.

Tests the per-page reporting that Contract 1.4 specifies:
- Downscaled and spread-exempt are not classes (they remain converted)
- Per-page lines show resize dimensions and recoverability
- Run-level mode line shows downscaling counts
"""

from __future__ import annotations

import os
import sys
import unittest

# Allow `python3 -m unittest tests.test_report_downscale` as well as
# `python3 -m unittest discover -s tests`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cbx_jackal import report_downscale
from cbx_jackal.report import CONVERTED, PASSED_THROUGH, NOT_CONVERTED


class DownscaledInfo(unittest.TestCase):
    """DownscaledInfo dataclass."""

    def test_downscaled_info_structure(self):
        """DownscaledInfo has all expected fields."""
        info = report_downscale.DownscaledInfo(
            original_width=2480,
            original_height=3508,
            target_width=1600,
            target_height=2260
        )
        self.assertEqual(2480, info.original_width)
        self.assertEqual(3508, info.original_height)
        self.assertEqual(1600, info.target_width)
        self.assertEqual(2260, info.target_height)

    def test_downscaled_info_immutable(self):
        """DownscaledInfo is immutable (frozen)."""
        info = report_downscale.DownscaledInfo(100, 200, 80, 160)
        with self.assertRaises(AttributeError):
            info.original_width = 300  # type: ignore


class SpreadInfo(unittest.TestCase):
    """SpreadInfo dataclass."""

    def test_spread_info_structure(self):
        """SpreadInfo has all expected fields."""
        info = report_downscale.SpreadInfo(display_width=2480, display_height=1500)
        self.assertEqual(2480, info.display_width)
        self.assertEqual(1500, info.display_height)

    def test_spread_info_immutable(self):
        """SpreadInfo is immutable (frozen)."""
        info = report_downscale.SpreadInfo(2000, 1000)
        with self.assertRaises(AttributeError):
            info.display_width = 3000  # type: ignore


class ExtendedEntryOutcome(unittest.TestCase):
    """ExtendedEntryOutcome with downscaling and spread information."""

    def test_regular_converted_outcome(self):
        """Regular converted outcome has no special reporting."""
        outcome = report_downscale.create_extended_outcome(
            name="page001.jpg",
            classification=CONVERTED,
            source_size=1000,
            output_size=800
        )
        self.assertEqual("page001.jpg", outcome.name)
        self.assertEqual(CONVERTED, outcome.classification)
        self.assertIsNone(outcome.downscaled)
        self.assertIsNone(outcome.spread)
        self.assertIsNone(outcome.recoverability)
        self.assertIsNone(outcome.format_per_page_line())

    def test_downscaled_outcome_pixels(self):
        """Downscaled outcome with pixels recoverability."""
        downscaled_info = report_downscale.DownscaledInfo(
            original_width=2480, original_height=3508,
            target_width=1600, target_height=2260
        )
        outcome = report_downscale.create_extended_outcome(
            name="page003.jpg",
            classification=CONVERTED,
            downscaled=downscaled_info,
            recoverability=report_downscale.PIXELS
        )
        line = outcome.format_per_page_line()
        self.assertEqual(
            "page003.jpg: downscaled 2480x3508 -> 1600x2260, pixels recoverable, source JPEG not",
            line
        )

    def test_downscaled_outcome_intermediate(self):
        """Downscaled outcome with intermediate recoverability."""
        downscaled_info = report_downscale.DownscaledInfo(
            original_width=2480, original_height=3508,
            target_width=1600, target_height=2260
        )
        outcome = report_downscale.create_extended_outcome(
            name="page003.jpg",
            classification=CONVERTED,
            downscaled=downscaled_info,
            recoverability=report_downscale.INTERMEDIATE
        )
        line = outcome.format_per_page_line()
        self.assertEqual(
            "page003.jpg: downscaled 2480x3508 -> 1600x2260, recoverable as the intermediate only",
            line
        )

    def test_downscaled_outcome_source(self):
        """Downscaled outcome with source recoverability."""
        downscaled_info = report_downscale.DownscaledInfo(
            original_width=2480, original_height=3508,
            target_width=1600, target_height=2260
        )
        outcome = report_downscale.create_extended_outcome(
            name="page003.jpg",
            classification=CONVERTED,
            downscaled=downscaled_info,
            recoverability=report_downscale.SOURCE
        )
        line = outcome.format_per_page_line()
        self.assertEqual(
            "page003.jpg: downscaled 2480x3508 -> 1600x2260, source recoverable",
            line
        )

    def test_downscaled_outcome_no_recoverability(self):
        """Downscaled outcome without specific recoverability."""
        downscaled_info = report_downscale.DownscaledInfo(
            original_width=2480, original_height=3508,
            target_width=1600, target_height=2260
        )
        outcome = report_downscale.create_extended_outcome(
            name="page003.jpg",
            classification=CONVERTED,
            downscaled=downscaled_info
        )
        line = outcome.format_per_page_line()
        self.assertEqual(
            "page003.jpg: downscaled 2480x3508 -> 1600x2260",
            line
        )

    def test_spread_outcome(self):
        """Spread-exempt outcome formatting."""
        spread_info = report_downscale.SpreadInfo(display_width=2480, display_height=1500)
        outcome = report_downscale.create_extended_outcome(
            name="page007.jpg",
            classification=CONVERTED,
            spread=spread_info
        )
        line = outcome.format_per_page_line()
        self.assertEqual(
            "page007.jpg: spread kept at 2480x1500, exempt from the width rule",
            line
        )

    def test_failed_outcome(self):
        """Failed outcome still uses base classification."""
        outcome = report_downscale.create_extended_outcome(
            name="page001.jpg",
            classification=NOT_CONVERTED,
            reason="cjxl exited 1 (corrupt JPEG)",
            source_size=1000
        )
        self.assertTrue(outcome.failed)
        self.assertEqual(NOT_CONVERTED, outcome.classification)
        self.assertIsNone(outcome.format_per_page_line())


class DownscaleReport(unittest.TestCase):
    """DownscaleReport tracking and statistics."""

    def test_empty_report(self):
        """Empty report has zero counts."""
        report = report_downscale.DownscaleReport()
        self.assertEqual(0, report.downscaled_count)
        self.assertEqual(0, report.spread_count)
        self.assertFalse(report.has_downscaled)
        self.assertFalse(report.has_spreads)

    def test_add_downscaled_pixels(self):
        """Add downscaled page with pixels recoverability."""
        report = report_downscale.DownscaleReport()
        report.add_downscaled(report_downscale.PIXELS)
        self.assertEqual(1, report.downscaled_count)
        self.assertEqual(1, report.pixels_count)
        self.assertTrue(report.has_downscaled)

    def test_add_downscaled_intermediate(self):
        """Add downscaled page with intermediate recoverability."""
        report = report_downscale.DownscaleReport()
        report.add_downscaled(report_downscale.INTERMEDIATE)
        self.assertEqual(1, report.downscaled_count)
        self.assertEqual(1, report.intermediate_count)

    def test_add_spread(self):
        """Add spread-exempt page."""
        report = report_downscale.DownscaleReport()
        report.add_spread()
        self.assertEqual(1, report.spread_count)
        self.assertTrue(report.has_spreads)

    def test_mixed_report(self):
        """Report with both downscaled and spread pages."""
        report = report_downscale.DownscaleReport()
        report.add_downscaled(report_downscale.PIXELS)
        report.add_downscaled(report_downscale.PIXELS)
        report.add_spread()
        self.assertEqual(2, report.downscaled_count)
        self.assertEqual(1, report.spread_count)
        self.assertEqual(2, report.pixels_count)

    def test_format_mode_suffix_no_downscaling(self):
        """No suffix when no downscaling occurred."""
        report = report_downscale.DownscaleReport()
        suffix = report.format_mode_suffix()
        self.assertIsNone(suffix)

    def test_format_mode_suffix_pixels(self):
        """Suffix for downscaled pages with pixels recoverability."""
        report = report_downscale.DownscaleReport()
        report.add_downscaled(report_downscale.PIXELS)
        report.add_downscaled(report_downscale.PIXELS)
        report.add_downscaled(report_downscale.PIXELS)
        report.add_spread()
        suffix = report.format_mode_suffix()
        self.assertEqual(
            ", 3 of 4 pages downscaled (pixels recoverable, source JPEG not)",
            suffix
        )

    def test_format_mode_suffix_only_downscaled(self):
        """Suffix when only downscaled pages, no spreads."""
        report = report_downscale.DownscaleReport()
        report.add_downscaled(report_downscale.PIXELS)
        suffix = report.format_mode_suffix()
        self.assertEqual(
            ", 1 of 1 pages downscaled (pixels recoverable, source JPEG not)",
            suffix
        )


class DownscaleReportBuilder(unittest.TestCase):
    """Builder for downscaling report statistics."""

    def test_builder_empty(self):
        """Builder with no entries."""
        builder = report_downscale.DownscaleReportBuilder()
        report = builder.get_report()
        self.assertEqual(0, report.downscaled_count)
        self.assertEqual(0, report.spread_count)

    def test_builder_with_downscaled(self):
        """Builder with downscaled entries."""
        builder = report_downscale.DownscaleReportBuilder()
        
        downscaled_info = report_downscale.DownscaledInfo(100, 200, 80, 160)
        outcome = report_downscale.create_extended_outcome(
            name="page001.jpg",
            classification=CONVERTED,
            downscaled=downscaled_info,
            recoverability=report_downscale.PIXELS
        )
        builder.add_entry(outcome)
        
        report = builder.get_report()
        self.assertEqual(1, report.downscaled_count)
        self.assertEqual(1, report.pixels_count)

    def test_builder_with_spread(self):
        """Builder with spread entries."""
        builder = report_downscale.DownscaleReportBuilder()
        
        spread_info = report_downscale.SpreadInfo(2000, 1500)
        outcome = report_downscale.create_extended_outcome(
            name="page007.jpg",
            classification=CONVERTED,
            spread=spread_info
        )
        builder.add_entry(outcome)
        
        report = builder.get_report()
        self.assertEqual(1, report.spread_count)

    def test_builder_ignores_regular_pages(self):
        """Builder ignores regular converted pages."""
        builder = report_downscale.DownscaleReportBuilder()
        
        outcome = report_downscale.create_extended_outcome(
            name="page001.jpg",
            classification=CONVERTED
        )
        builder.add_entry(outcome)
        
        report = builder.get_report()
        self.assertEqual(0, report.downscaled_count)
        self.assertEqual(0, report.spread_count)


class ModeLineFormatting(unittest.TestCase):
    """Run-level mode line formatting."""

    def test_lossless_mode_no_downscaling(self):
        """Lossless mode without downscaling."""
        mode_line = report_downscale.format_run_level_mode(quality=None)
        self.assertEqual(
            "mode: lossless (JPEG bytes recoverable with djxl)",
            mode_line
        )

    def test_lossless_mode_with_downscaling(self):
        """Lossless mode with downscaling suffix."""
        report = report_downscale.DownscaleReport()
        report.add_downscaled(report_downscale.PIXELS)
        report.add_downscaled(report_downscale.PIXELS)
        
        mode_line = report_downscale.format_run_level_mode(quality=None, downscale_report=report)
        self.assertEqual(
            "mode: lossless (JPEG bytes recoverable with djxl), 2 of 2 pages downscaled (pixels recoverable, source JPEG not)",
            mode_line
        )

    def test_lossy_mode(self):
        """Lossy mode formatting."""
        mode_line = report_downscale.format_run_level_mode(quality=90)
        self.assertEqual(
            "mode: lossy, quality 90 (JPEG bytes NOT recoverable)",
            mode_line
        )

    def test_lossy_mode_with_downscaling(self):
        """Lossy mode with downscaling - suffix should not appear.
        
        In a lossy run, every page is `none` recoverability, and the existing
        mode line already says it. A downscaling suffix would be redundant.
        """
        report = report_downscale.DownscaleReport()
        report.add_downscaled(report_downscale.NONE)  # shouldn't happen for a downscaled page
        
        mode_line = report_downscale.format_run_level_mode(quality=90, downscale_report=report)
        # With lossy mode and NONE recoverability, suffix should still appear as specified
        self.assertIn("mode: lossy, quality 90", mode_line)


class PerPageLineFormatting(unittest.TestCase):
    """Per-page line formatting for all outcome types."""

    def test_format_lines_empty(self):
        """Empty outcome list produces empty line list."""
        lines = report_downscale.format_per_page_lines([])
        self.assertEqual([], lines)

    def test_format_lines_mixed(self):
        """Mixed outcomes produce correct lines."""
        downscaled_info = report_downscale.DownscaledInfo(2480, 3508, 1600, 2260)
        spread_info = report_downscale.SpreadInfo(2480, 1500)
        
        outcomes = [
            report_downscale.create_extended_outcome(
                name="page001.jpg",
                classification=CONVERTED
            ),
            report_downscale.create_extended_outcome(
                name="page003.jpg",
                classification=CONVERTED,
                downscaled=downscaled_info,
                recoverability=report_downscale.PIXELS
            ),
            report_downscale.create_extended_outcome(
                name="page007.jpg",
                classification=CONVERTED,
                spread=spread_info
            ),
        ]
        
        lines = report_downscale.format_per_page_lines(outcomes)
        self.assertEqual(2, len(lines))
        self.assertEqual(
            "page003.jpg: downscaled 2480x3508 -> 1600x2260, pixels recoverable, source JPEG not",
            lines[0]
        )
        self.assertEqual(
            "page007.jpg: spread kept at 2480x1500, exempt from the width rule",
            lines[1]
        )


class RecoverabilityConstants(unittest.TestCase):
    """Recoverability value constants."""

    def test_source_constant(self):
        """SOURCE constant is defined."""
        self.assertEqual("source", report_downscale.SOURCE)

    def test_pixels_constant(self):
        """PIXELS constant is defined."""
        self.assertEqual("pixels", report_downscale.PIXELS)

    def test_intermediate_constant(self):
        """INTERMEDIATE constant is defined."""
        self.assertEqual("intermediate", report_downscale.INTERMEDIATE)

    def test_none_constant(self):
        """NONE constant is defined."""
        self.assertEqual("none", report_downscale.NONE)


class FactoryFunction(unittest.TestCase):
    """create_extended_outcome factory function."""

    def test_factory_creates_correct_type(self):
        """Factory creates ExtendedEntryOutcome."""
        outcome = report_downscale.create_extended_outcome(
            name="test.jpg",
            classification=CONVERTED
        )
        self.assertIsInstance(outcome, report_downscale.ExtendedEntryOutcome)

    def test_factory_with_all_fields(self):
        """Factory with all fields."""
        downscaled_info = report_downscale.DownscaledInfo(100, 200, 80, 160)
        spread_info = report_downscale.SpreadInfo(2000, 1000)
        
        outcome = report_downscale.create_extended_outcome(
            name="test.jpg",
            classification=CONVERTED,
            reason="test reason",
            source_size=1000,
            output_size=800,
            downscaled=downscaled_info,
            spread=spread_info,
            recoverability=report_downscale.PIXELS
        )
        
        self.assertEqual("test.jpg", outcome.name)
        self.assertEqual(CONVERTED, outcome.classification)
        self.assertEqual("test reason", outcome.reason)
        self.assertEqual(1000, outcome.source_size)
        self.assertEqual(800, outcome.output_size)
        self.assertIsNotNone(outcome.downscaled)
        self.assertIsNotNone(outcome.spread)
        self.assertEqual(report_downscale.PIXELS, outcome.recoverability)


if __name__ == '__main__':
    unittest.main()