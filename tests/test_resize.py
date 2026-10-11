# Copyright (C) 2026 Fran
# SPDX-License-Identifier: GPL-3.0-only
"""Resize functionality with ImageMagick.

Tests the downscaling invocation: target dimension calculation, magick
command construction, and temp file discipline.
"""

import os
import shutil
import sys
import tempfile
import unittest

# Allow `python3 -m unittest tests.test_resize` as well as
# `python3 -m unittest discover -s tests`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cbx_jackal import geometry, resize

from helpers import FIXTURES, read_bytes

# Test fixtures
PAGE001_JPEG = os.path.join(FIXTURES, "page001.jpg")
ORIENT_6_JPEG = os.path.join(FIXTURES, "page_orient_6.jpg")


class TargetDimensionCalculation(unittest.TestCase):
    """Compute target dimensions for downscaling."""

    def test_no_bounds_no_resize(self):
        """With no bounds, no resize is performed."""
        target_w, target_h = resize.compute_target_dimensions(2000, 3000, None, None)
        self.assertEqual(2000, target_w)
        self.assertEqual(3000, target_h)

    def test_fits_width_no_resize(self):
        """Page fits within width bound, no resize needed."""
        target_w, target_h = resize.compute_target_dimensions(1600, 2000, max_width=1600)
        self.assertEqual(1600, target_w)
        self.assertEqual(2000, target_h)

    def test_fits_height_no_resize(self):
        """Page fits within height bound, no resize needed."""
        target_w, target_h = resize.compute_target_dimensions(2000, 1600, max_height=1600)
        self.assertEqual(2000, target_w)
        self.assertEqual(1600, target_h)

    def test_fits_both_no_resize(self):
        """Page fits within both bounds, no resize needed."""
        target_w, target_h = resize.compute_target_dimensions(1600, 1200, max_width=1600, max_height=1600)
        self.assertEqual(1600, target_w)
        self.assertEqual(1200, target_h)

    def test_exceeds_width_only(self):
        """Page exceeds width bound only, scale to fit width."""
        target_w, target_h = resize.compute_target_dimensions(2000, 3000, max_width=1600)
        self.assertEqual(1600, target_w)
        # Height should be scaled proportionally: 1600/2000 * 3000 = 2400
        self.assertEqual(2400, target_h)

    def test_exceeds_height_only(self):
        """Page exceeds height bound only, scale to fit height."""
        target_w, target_h = resize.compute_target_dimensions(2000, 3000, max_height=1600)
        # Width should be scaled proportionally: 1600/3000 * 2000 ≈ 1066.67 -> 1066
        self.assertEqual(1066, target_w)
        self.assertEqual(1600, target_h)

    def test_exceeds_both_width_more_constraining(self):
        """Page exceeds both bounds, width is more constraining."""
        # 2000x3000 with max 1600x2000
        # width ratio: 1600/2000 = 0.8
        # height ratio: 2000/3000 ≈ 0.667
        # min ratio is 0.667, so scale by height constraint
        target_w, target_h = resize.compute_target_dimensions(2000, 3000, max_width=1600, max_height=2000)
        self.assertEqual(1333, target_w)  # 2000 * (2000/3000) ≈ 1333.33
        self.assertEqual(2000, target_h)

    def test_exceeds_both_height_more_constraining(self):
        """Page exceeds both bounds, height is more constraining."""
        # 2000x3000 with max 2400x1600
        # width ratio: 2400/2000 = 1.2 (but capped at 1.0, no enlargement)
        # height ratio: 1600/3000 ≈ 0.533
        # min ratio is 0.533, so scale by height constraint
        target_w, target_h = resize.compute_target_dimensions(2000, 3000, max_width=2400, max_height=1600)
        self.assertEqual(1066, target_w)  # 2000 * (1600/3000) ≈ 1066.67 -> 1066
        self.assertEqual(1600, target_h)

    def test_never_enlarges(self):
        """Page is never enlarged beyond its original dimensions."""
        # Small page with large bounds should not be enlarged
        target_w, target_h = resize.compute_target_dimensions(800, 600, max_width=1600, max_height=1200)
        self.assertEqual(800, target_w)
        self.assertEqual(600, target_h)

    def test_minimum_dimensions(self):
        """Target dimensions are at least 1 pixel."""
        target_w, target_h = resize.compute_target_dimensions(100, 100, max_width=1, max_height=1)
        self.assertEqual(1, target_w)
        self.assertEqual(1, target_h)

    def test_zero_original_dimensions(self):
        """Zero original dimensions are handled without errors."""
        target_w, target_h = resize.compute_target_dimensions(0, 100, max_width=100)
        self.assertEqual(0, target_w)
        self.assertEqual(100, target_h)

        target_w, target_h = resize.compute_target_dimensions(100, 0, max_height=100)
        self.assertEqual(100, target_w)
        self.assertEqual(0, target_h)


class CommandBuilding(unittest.TestCase):
    """Build magick commands for resizing."""

    def test_command_structure(self):
        """magick command includes all required flags."""
        command = resize._build_command("magick", "input.jpg", "output.jpg", 1600, 2000)
        self.assertEqual("magick", command[0])
        self.assertEqual("input.jpg", command[1])
        self.assertIn("-auto-orient", command)
        self.assertIn("-quality", command)
        self.assertIn(resize.MAGICK_QUALITY, command)
        self.assertIn("1600x2000>", command)
        self.assertIn("jpg:output.jpg", command)

    def test_downsize_guard(self):
        """Trailing > prevents enlargement."""
        command = resize._build_command("magick", "input.jpg", "output.jpg", 1600, 2000)
        # Should contain the downsize guard
        self.assertTrue(any("1600x2000>" in arg for arg in command))
        self.assertFalse(any("1600x2000" == arg and ">" not in arg for arg in command))

    def test_jpeg_format(self):
        """Output format is JPEG."""
        command = resize._build_command("magick", "input.jpg", "output.jpg", 1600, 2000)
        self.assertTrue(any("jpg:" in arg for arg in command))


class ResizeResultStructures(unittest.TestCase):
    """ResizeResult dataclass and its properties."""

    def test_resize_result_structure(self):
        """ResizeResult has all expected fields."""
        result = resize.ResizeResult(
            ok=True,
            data=b"test",
            error=None,
            original_width=100,
            original_height=200,
            display_width=100,
            display_height=200,
            target_width=80,
            target_height=160
        )
        self.assertTrue(result.ok)
        self.assertEqual(b"test", result.data)
        self.assertIsNone(result.error)
        self.assertEqual(100, result.original_width)
        self.assertEqual(200, result.original_height)
        self.assertEqual(100, result.display_width)
        self.assertEqual(200, result.display_height)
        self.assertEqual(80, result.target_width)
        self.assertEqual(160, result.target_height)
        self.assertEqual(4, result.size)

    def test_resize_result_size_empty(self):
        """Size is 0 for empty data."""
        result = resize.ResizeResult(ok=True, data=b"")
        self.assertEqual(0, result.size)

    def test_resize_result_size_none(self):
        """Size is 0 for None data."""
        result = resize.ResizeResult(ok=False, data=None)
        self.assertEqual(0, result.size)


class IntegrationWithGeometry(unittest.TestCase):
    """Integration between resize and geometry modules."""

    def test_orientation_handling(self):
        """Display dimensions from geometry are used for resize calculation."""
        bytes_data = read_bytes(ORIENT_6_JPEG)
        original_width, original_height = 2000, 3000
        
        # Get display dimensions (should be swapped for orientation 6)
        display_dims = geometry.get_display_dimensions(bytes_data, original_width, original_height)
        self.assertEqual(3000, display_dims.width)
        self.assertEqual(2000, display_dims.height)
        
        # Compute target dimensions based on display dimensions
        target_w, target_h = resize.compute_target_dimensions(
            display_dims.width, display_dims.height, max_width=1600
        )
        self.assertEqual(1600, target_w)
        self.assertEqual(1066, target_h)  # 1600 * (2000/3000) ≈ 1066.67 -> 1066

    def test_normal_orientation(self):
        """Normal orientation uses original dimensions."""
        bytes_data = read_bytes(PAGE001_JPEG)
        # page001.jpg is 600x900
        original_width, original_height = 600, 900
        
        display_dims = geometry.get_display_dimensions(bytes_data, original_width, original_height)
        self.assertEqual(600, display_dims.width)
        self.assertEqual(900, display_dims.height)
        
        # With max_width=1600, no resize needed
        target_w, target_h = resize.compute_target_dimensions(
            display_dims.width, display_dims.height, max_width=1600
        )
        self.assertEqual(600, target_w)
        self.assertEqual(900, target_h)


class ErrorHandling(unittest.TestCase):
    """Error handling and edge cases."""

    def test_failure_description(self):
        """Failure messages include exit code and last stderr line."""
        description = resize._describe_failure("error message\nmore details\n", 1)
        self.assertIn("magick exited 1", description)
        self.assertIn("more details", description)

    def test_failure_description_no_stderr(self):
        """Failure messages handle empty stderr."""
        description = resize._describe_failure("", 2)
        self.assertIn("magick exited 2", description)
        self.assertIn("no diagnostic output", description)


class Constants(unittest.TestCase):
    """Verify constants and configuration."""

    def test_tool_constant(self):
        """Tool is magick."""
        self.assertEqual("magick", resize.TOOL)

    def test_intermediate_format(self):
        """Intermediate format is JPEG, so cjxl can transcode it losslessly."""
        self.assertEqual(".jpg", resize.INTERMEDIATE_FORMAT)

    def test_magick_quality(self):
        """magick quality is 90, the last value before the size cliff."""
        self.assertEqual("90", resize.MAGICK_QUALITY)

    def test_real_invocation_produces_a_jpeg(self):
        """magick runs and writes a real JPEG, under its own steam.

        This is the regression that a JPEG intermediate invites: the staged
        source and the intermediate would share `.jpg`, so reusing the same
        stem makes magick read and write the same path.
        """
        magick = shutil.which("magick")
        if magick is None:
            self.skipTest("magick is not on PATH")
        result = resize.resize_page(
            magick,
            read_bytes(PAGE001_JPEG),
            600,
            900,
            max_width=300,
            max_height=300,
        )
        self.assertTrue(result.ok, result.error)
        data = result.data
        self.assertIsNotNone(data)
        assert data is not None
        self.assertTrue(data.startswith(b"\xff\xd8\xff"))
        self.assertEqual(200, result.target_width)
        self.assertEqual(300, result.target_height)

    def test_explicit_quality_reaches_magick(self):
        """A caller's --quality lands on the intermediate, the only lossy step."""
        command = resize._build_command(
            "magick", "in.jpg", "out.jpg", 1600, 2000, quality="99"
        )
        self.assertEqual("99", command[command.index("-quality") + 1])

    def test_quality_falls_back_to_the_measured_default(self):
        """No --quality still uses MAGICK_QUALITY."""
        command = resize._build_command("magick", "in.jpg", "out.jpg", 1600, 2000)
        self.assertEqual(
            resize.MAGICK_QUALITY, command[command.index("-quality") + 1]
        )

    def test_quality_actually_changes_the_intermediate(self):
        """The plumb-through is real, not a parameter nobody reads."""
        magick = shutil.which("magick")
        if magick is None:
            self.skipTest("magick is not on PATH")
        source = read_bytes(PAGE001_JPEG)
        low = resize.resize_page(magick, source, 600, 900, max_width=200, quality=20)
        high = resize.resize_page(magick, source, 600, 900, max_width=200, quality=95)
        self.assertTrue(low.ok, low.error)
        self.assertTrue(high.ok, high.error)
        low_data, high_data = low.data, high.data
        self.assertIsNotNone(low_data)
        self.assertIsNotNone(high_data)
        assert low_data is not None and high_data is not None
        self.assertLess(len(low_data), len(high_data))


if __name__ == '__main__':
    unittest.main()