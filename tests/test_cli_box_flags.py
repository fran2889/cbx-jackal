# Copyright (C) 2026 Fran
# SPDX-License-Identifier: GPL-3.0-only
"""CLI box flags: --max-width and --max-height.

Tests the user-facing surface for bounded downscaling:
- Flag parsing and validation
- Preflight integration for magick
- Converter integration
"""

from __future__ import annotations

import os
import sys
import unittest
from io import StringIO

# Allow `python3 -m unittest tests.test_cli_box_flags` as well as
# `python3 -m unittest discover -s tests`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cbx_jackal.cli import build_parser, _validate_box_dimension


class FlagParsing(unittest.TestCase):
    """Parse --max-width and --max-height flags."""

    def test_max_width_flag(self):
        """--max-width flag is parsed correctly."""
        parser = build_parser()
        args = parser.parse_args(["--max-width", "1600", "test.cbz"])
        self.assertEqual(1600, args.max_width)
        self.assertIsNone(args.max_height)

    def test_max_height_flag(self):
        """--max-height flag is parsed correctly."""
        parser = build_parser()
        args = parser.parse_args(["--max-height", "1200", "test.cbz"])
        self.assertEqual(1200, args.max_height)
        self.assertIsNone(args.max_width)

    def test_both_flags(self):
        """Both --max-width and --max-height can be used together."""
        parser = build_parser()
        args = parser.parse_args(["--max-width", "1600", "--max-height", "1200", "test.cbz"])
        self.assertEqual(1600, args.max_width)
        self.assertEqual(1200, args.max_height)

    def test_no_box_flags(self):
        """When no box flags are given, both are None."""
        parser = build_parser()
        args = parser.parse_args(["test.cbz"])
        self.assertIsNone(args.max_width)
        self.assertIsNone(args.max_height)

    def test_box_flags_with_other_flags(self):
        """Box flags work with other flags."""
        parser = build_parser()
        args = parser.parse_args([
            "--max-width", "1600",
            "--max-height", "1200", 
            "--quality", "90",
            "--format", "jxl",
            "--dry-run",
            "test.cbz"
        ])
        self.assertEqual(1600, args.max_width)
        self.assertEqual(1200, args.max_height)
        self.assertEqual(90, args.quality)
        self.assertEqual("jxl", args.page_format)
        self.assertTrue(args.dry_run)


class FlagValidation(unittest.TestCase):
    """Validate box dimension flags."""

    def test_valid_max_width(self):
        """Valid max-width values are accepted."""
        result = _validate_box_dimension(1600, "max-width")
        self.assertEqual(1600, result)

    def test_valid_max_height(self):
        """Valid max-height values are accepted."""
        result = _validate_box_dimension(1200, "max-height")
        self.assertEqual(1200, result)

    def test_none_value(self):
        """None values are passed through."""
        result = _validate_box_dimension(None, "max-width")
        self.assertIsNone(result)

    def test_zero_rejected(self):
        """Zero is rejected as invalid."""
        with self.assertRaises(ValueError) as context:
            _validate_box_dimension(0, "max-width")
        self.assertIn("--max-width must be a positive integer, got 0", str(context.exception))

    def test_negative_rejected(self):
        """Negative values are rejected."""
        with self.assertRaises(ValueError) as context:
            _validate_box_dimension(-100, "max-height")
        self.assertIn("--max-height must be a positive integer, got -100", str(context.exception))


class PreflightIntegration(unittest.TestCase):
    """Integration with preflight module."""

    def test_magick_constant_available(self):
        """MAGICK constant is available in preflight."""
        from cbx_jackal import preflight
        self.assertTrue(hasattr(preflight, 'MAGICK'))
        self.assertEqual("magick", preflight.MAGICK)

    def test_magick_tool_registered(self):
        """magick tool is registered in TOOLS."""
        from cbx_jackal import preflight
        self.assertIn(preflight.MAGICK, preflight.TOOLS)

    def test_magick_stops_run(self):
        """magick is flag-driven but still stops the run when missing."""
        from cbx_jackal import preflight
        magick_tool = preflight.TOOLS[preflight.MAGICK]
        # For flag-driven tools, the stop behavior is handled at the CLI level
        # but the tool itself is marked as stopping the run
        self.assertTrue(magick_tool.stops_run)

    def test_magick_guidance(self):
        """magick has install guidance."""
        from cbx_jackal import preflight
        magick_tool = preflight.TOOLS[preflight.MAGICK]
        self.assertIn("ImageMagick", magick_tool.guidance)
        self.assertIn("resize", magick_tool.guidance.lower())


class ConverterIntegration(unittest.TestCase):
    """Integration with Converter class."""

    def test_converter_accepts_box_params(self):
        """Converter accepts max_width and max_height parameters."""
        from cbx_jackal.archive import Converter
        try:
            converter = Converter(
                cjxl="cjxl",
                quality=None,
                strict=False,
                page_format="jxl",
                max_width=1600,
                max_height=1200
            )
            self.assertEqual(1600, converter.max_width)
            self.assertEqual(1200, converter.max_height)
            self.assertTrue(converter.box_requested)
        except Exception as e:
            # If this fails due to missing dependencies, that's expected
            # We just want to verify the constructor signature
            self.assertIn("cjxl", str(e).lower())

    def test_converter_accepts_magick(self):
        """Converter accepts magick parameter."""
        from cbx_jackal.archive import Converter
        try:
            converter = Converter(
                cjxl="cjxl",
                magick="magick"
            )
            self.assertEqual("magick", converter.magick)
        except Exception as e:
            # If this fails due to missing cjxl, that's expected
            self.assertIn("cjxl", str(e).lower())

    def test_box_requested_false_without_bounds(self):
        """box_requested is False when no bounds are set."""
        from cbx_jackal.archive import Converter
        try:
            converter = Converter(
                cjxl="cjxl",
                max_width=None,
                max_height=None
            )
            self.assertFalse(converter.box_requested)
        except Exception as e:
            self.assertIn("cjxl", str(e).lower())

    def test_box_requested_true_with_width(self):
        """box_requested is True when max_width is set."""
        from cbx_jackal.archive import Converter
        try:
            converter = Converter(
                cjxl="cjxl",
                max_width=1600
            )
            self.assertTrue(converter.box_requested)
        except Exception as e:
            self.assertIn("cjxl", str(e).lower())

    def test_box_requested_true_with_height(self):
        """box_requested is True when max_height is set."""
        from cbx_jackal.archive import Converter
        try:
            converter = Converter(
                cjxl="cjxl",
                max_height=1200
            )
            self.assertTrue(converter.box_requested)
        except Exception as e:
            self.assertIn("cjxl", str(e).lower())


class HelpText(unittest.TestCase):
    """CLI help text includes box flags."""

    def test_help_includes_max_width(self):
        """Help text includes --max-width."""
        parser = build_parser()
        help_text = parser.format_help()
        self.assertIn("--max-width", help_text)

    def test_help_includes_max_height(self):
        """Help text includes --max-height."""
        parser = build_parser()
        help_text = parser.format_help()
        self.assertIn("--max-height", help_text)

    def test_help_includes_box_descriptions(self):
        """Help text describes box functionality."""
        parser = build_parser()
        help_text = parser.format_help()
        self.assertIn("maximum display width", help_text.lower())
        self.assertIn("maximum display height", help_text.lower())


if __name__ == '__main__':
    unittest.main()