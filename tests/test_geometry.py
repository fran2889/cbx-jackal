# Copyright (C) 2026 Fran
# SPDX-License-Identifier: GPL-3.0-only
"""Geometry, EXIF orientation, spread detection, and downscaling decisions.

Tests the display orientation logic that underpins bounded downscaling:
 EXIF orientation is honoured before any comparison, a recognised spread is
 exempt from the width rule but never split.

Fixture dimensions from make_fixtures.py:
- page_orient_1-8.jpg: 2000x3000 base, various orientations
- spread_exact_1.35.jpg: 2000x1481 (exactly 1.35:1)
- spread_above_1.35.jpg: 2000x1300 (~1.538:1)
- spread_below_1.35.jpg: 2000x1500 (~1.333:1)
- sideways_no_tag.jpg: dimensions vary, no EXIF orientation
- landscape_splash.jpg: dimensions vary, no EXIF orientation
"""

from __future__ import annotations

import os
import sys
import unittest

# Allow `python3 -m unittest tests.test_geometry` as well as
# `python3 -m unittest discover -s tests`.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cbx_jackal import geometry

from helpers import FIXTURES, read_bytes

# Test fixtures - we have EXIF orientation fixtures from Entry 2
# These are the page_orient_X.jpg files with specific EXIF orientations
ORIENT_1_JPEG = os.path.join(FIXTURES, "page_orient_1.jpg")  # Normal
ORIENT_2_JPEG = os.path.join(FIXTURES, "page_orient_2.jpg")  # Mirrored
ORIENT_3_JPEG = os.path.join(FIXTURES, "page_orient_3.jpg")  # Rotated 180
ORIENT_6_JPEG = os.path.join(FIXTURES, "page_orient_6.jpg")  # Rotated 90 CW
ORIENT_8_JPEG = os.path.join(FIXTURES, "page_orient_8.jpg")  # Rotated 270 CW

# Spread test fixtures from Entry 2
SPREAD_ABOVE_1_35 = os.path.join(FIXTURES, "spread_above_1.35.jpg")
SPREAD_EXACT_1_35 = os.path.join(FIXTURES, "spread_exact_1.35.jpg")
SPREAD_BELOW_1_35 = os.path.join(FIXTURES, "spread_below_1.35.jpg")

# Edge case fixtures
SIDEWAYS_NO_TAG = os.path.join(FIXTURES, "sideways_no_tag.jpg")
LANDSCAPE_SPLASH = os.path.join(FIXTURES, "landscape_splash.jpg")

# Regular fixtures for dimension tests
PAGE001_JPEG = os.path.join(FIXTURES, "page001.jpg")


class EXIFOrientationReading(unittest.TestCase):
    """Reading EXIF orientation tags from JPEG bytes."""

    def test_read_orientation_1_normal(self):
        """Orientation 1 = Normal (0°)."""
        bytes_data = read_bytes(ORIENT_1_JPEG)
        orientation = geometry.read_exif_orientation(bytes_data)
        self.assertEqual(1, orientation)

    def test_read_orientation_2_mirrored(self):
        """Orientation 2 = Mirrored (flip horizontal)."""
        bytes_data = read_bytes(ORIENT_2_JPEG)
        orientation = geometry.read_exif_orientation(bytes_data)
        self.assertEqual(2, orientation)

    def test_read_orientation_3_rotated_180(self):
        """Orientation 3 = Rotated 180°."""
        bytes_data = read_bytes(ORIENT_3_JPEG)
        orientation = geometry.read_exif_orientation(bytes_data)
        self.assertEqual(3, orientation)

    def test_read_orientation_6_rotated_90_cw(self):
        """Orientation 6 = Rotated 90° CW."""
        bytes_data = read_bytes(ORIENT_6_JPEG)
        orientation = geometry.read_exif_orientation(bytes_data)
        self.assertEqual(6, orientation)

    def test_read_orientation_8_rotated_270_cw(self):
        """Orientation 8 = Rotated 270° CW."""
        bytes_data = read_bytes(ORIENT_8_JPEG)
        orientation = geometry.read_exif_orientation(bytes_data)
        self.assertEqual(8, orientation)

    def test_read_orientation_no_tag_returns_none(self):
        """A JPEG without EXIF orientation returns None."""
        bytes_data = read_bytes(SIDEWAYS_NO_TAG)
        orientation = geometry.read_exif_orientation(bytes_data)
        self.assertIsNone(orientation)


class DisplayDimensionsCalculation(unittest.TestCase):
    """Display dimensions honouring EXIF orientation."""

    def test_normal_orientation_no_swap(self):
        """Orientation 1 (Normal) does not swap dimensions."""
        bytes_data = read_bytes(ORIENT_1_JPEG)
        # page_orient_1.jpg was created as 2000x3000 portrait
        display_dims = geometry.get_display_dimensions(bytes_data, 2000, 3000)
        self.assertEqual(2000, display_dims.width)
        self.assertEqual(3000, display_dims.height)

    def test_rotated_90_cw_swaps_dimensions(self):
        """Orientation 6 (Rotated 90° CW) swaps width and height."""
        bytes_data = read_bytes(ORIENT_6_JPEG)
        # page_orient_6.jpg was created as 2000x3000 but displays as 3000x2000
        display_dims = geometry.get_display_dimensions(bytes_data, 2000, 3000)
        self.assertEqual(3000, display_dims.width)
        self.assertEqual(2000, display_dims.height)

    def test_rotated_270_cw_swaps_dimensions(self):
        """Orientation 8 (Rotated 270° CW) swaps width and height."""
        bytes_data = read_bytes(ORIENT_8_JPEG)
        # page_orient_8.jpg was created as 2000x3000 but displays as 3000x2000
        display_dims = geometry.get_display_dimensions(bytes_data, 2000, 3000)
        self.assertEqual(3000, display_dims.width)
        self.assertEqual(2000, display_dims.height)

    def test_rotated_180_no_swap(self):
        """Orientation 3 (Rotated 180°) does not swap dimensions."""
        bytes_data = read_bytes(ORIENT_3_JPEG)
        # page_orient_3.jpg was created as 2000x3000, stays 2000x3000 when rotated 180
        display_dims = geometry.get_display_dimensions(bytes_data, 2000, 3000)
        self.assertEqual(2000, display_dims.width)
        self.assertEqual(3000, display_dims.height)

    def test_no_orientation_tag_no_swap(self):
        """No orientation tag means no swap."""
        bytes_data = read_bytes(SIDEWAYS_NO_TAG)
        display_dims = geometry.get_display_dimensions(bytes_data, 200, 100)
        self.assertEqual(200, display_dims.width)
        self.assertEqual(100, display_dims.height)

    def test_aspect_ratio_calculation(self):
        """DisplayDimensions.aspect_ratio returns width/height."""
        dims = geometry.DisplayDimensions(1600, 800)
        self.assertEqual(2.0, dims.aspect_ratio)


class SpreadDetection(unittest.TestCase):
    """Double-page spread detection via display aspect ratio."""

    def test_spread_above_1_35_threshold(self):
        """A spread with aspect ratio above 1.35:1 is detected."""
        # spread_above_1.35.jpg is 2000x1300, ratio = 2000/1300 ≈ 1.538 > 1.35
        bytes_data = read_bytes(SPREAD_ABOVE_1_35)
        is_spread = geometry.is_spread(2000, 1300)
        self.assertTrue(is_spread)

    def test_spread_exact_1_35_threshold(self):
        """A spread with aspect ratio exactly 1.35:1 is detected."""
        # spread_exact_1.35.jpg is 2000x1481, ratio = 2000/1481 ≈ 1.350
        bytes_data = read_bytes(SPREAD_EXACT_1_35)
        is_spread = geometry.is_spread(2000, 1481)
        self.assertTrue(is_spread)

    def test_spread_below_1_35_threshold(self):
        """A non-spread with aspect ratio below 1.35:1 is not detected."""
        # spread_below_1.35.jpg is 2000x1500, ratio = 2000/1500 ≈ 1.333 < 1.35
        bytes_data = read_bytes(SPREAD_BELOW_1_35)
        is_spread = geometry.is_spread(2000, 1500)
        self.assertFalse(is_spread)

    def test_spread_detection_direct(self):
        """Direct aspect ratio testing for spread detection."""
        # 1.35:1 exactly
        self.assertTrue(geometry.is_spread(1350, 1000))
        
        # Above 1.35:1
        self.assertTrue(geometry.is_spread(1400, 1000))  # 1.4:1
        self.assertTrue(geometry.is_spread(2480, 1500))  # ~1.65:1
        
        # Below 1.35:1
        self.assertFalse(geometry.is_spread(1300, 1000))  # 1.3:1
        self.assertFalse(geometry.is_spread(800, 600))   # ~1.33:1
        
        # Edge case: zero height
        self.assertFalse(geometry.is_spread(100, 0))


class DownscalingNeed(unittest.TestCase):
    """Determine whether a page needs downscaling."""

    def test_no_bounds_no_downscale(self):
        """With no bounds, no page is downscaled."""
        self.assertFalse(geometry.needs_downscale(3000, 2000, None, None))
        self.assertFalse(geometry.needs_downscale(800, 600, None, None))

    def test_fits_width_no_downscale(self):
        """A page that fits the width bound is not downscaled."""
        self.assertFalse(geometry.needs_downscale(1600, 2000, max_width=1600))
        self.assertFalse(geometry.needs_downscale(1200, 2000, max_width=1600))

    def test_exceeds_width_needs_downscale(self):
        """A page that exceeds the width bound needs downscaling."""
        self.assertTrue(geometry.needs_downscale(1800, 2000, max_width=1600))
        self.assertTrue(geometry.needs_downscale(2000, 1000, max_width=1600))

    def test_fits_height_no_downscale(self):
        """A page that fits the height bound is not downscaled."""
        self.assertFalse(geometry.needs_downscale(2000, 1600, max_height=1600))
        self.assertFalse(geometry.needs_downscale(2000, 1200, max_height=1600))

    def test_exceeds_height_needs_downscale(self):
        """A page that exceeds the height bound needs downscaling."""
        self.assertTrue(geometry.needs_downscale(2000, 1800, max_height=1600))
        self.assertTrue(geometry.needs_downscale(1000, 2000, max_height=1600))

    def test_fits_both_no_downscale(self):
        """A page that fits both bounds is not downscaled."""
        self.assertFalse(geometry.needs_downscale(1600, 1200, max_width=1600, max_height=1600))

    def test_exceeds_width_fits_height_needs_downscale(self):
        """A page that exceeds width but fits height needs downscaling."""
        self.assertTrue(geometry.needs_downscale(1800, 1200, max_width=1600, max_height=1600))

    def test_fits_width_exceeds_height_needs_downscale(self):
        """A page that fits width but exceeds height needs downscaling."""
        self.assertTrue(geometry.needs_downscale(1200, 1800, max_width=1600, max_height=1600))

    def test_exceeds_both_needs_downscale(self):
        """A page that exceeds both bounds needs downscaling."""
        self.assertTrue(geometry.needs_downscale(1800, 1800, max_width=1600, max_height=1600))

    def test_page_not_enlarged(self):
        """A page that already fits is not enlarged, even with bounds."""
        # This is the key property: no page is ever enlarged
        self.assertFalse(geometry.needs_downscale(800, 600, max_width=1600, max_height=1200))


class PageGeometryIntegration(unittest.TestCase):
    """Complete page geometry computation."""

    def test_page_geometry_normal(self):
        """Normal page geometry computation."""
        bytes_data = read_bytes(PAGE001_JPEG)
        # page001.jpg dimensions: 600x900 from make_fixtures.py
        width, height = 600, 900
        
        page_geom = geometry.compute_page_geometry(bytes_data, width, height, max_width=1600)
        assert page_geom is not None
        
        # Should have computed display dimensions
        self.assertEqual(width, page_geom.original_width)
        self.assertEqual(height, page_geom.original_height)
        self.assertEqual(width, page_geom.display_width)
        self.assertEqual(height, page_geom.display_height)
        # Should determine if it needs downscale (600x900 fits within 1600xanything)
        self.assertFalse(page_geom.needs_downscale)

    def test_page_geometry_with_orientation(self):
        """Page geometry with EXIF orientation."""
        bytes_data = read_bytes(ORIENT_6_JPEG)
        # page_orient_6.jpg: base 2000x3000, orientation 6 (rotated 90° CW)
        width, height = 2000, 3000
        
        page_geom = geometry.compute_page_geometry(bytes_data, width, height, max_width=1600)
        assert page_geom is not None
        
        # For orientation 6, display dimensions should be swapped
        # Original: 2000x3000, Display: 3000x2000
        self.assertEqual(2000, page_geom.original_width)
        self.assertEqual(3000, page_geom.original_height)
        self.assertEqual(3000, page_geom.display_width)
        self.assertEqual(2000, page_geom.display_height)
        self.assertEqual(6, page_geom.orientation)
        # With max_width=1600, 3000 > 1600 so needs downscale
        self.assertTrue(page_geom.needs_downscale)

    def test_page_geometry_spread_exemption(self):
        """Spread pages are exempt from width rule."""
        bytes_data = read_bytes(SPREAD_ABOVE_1_35)
        # spread_above_1.35.jpg: 2000x1300, ratio ≈ 1.538 > 1.35
        width, height = 2000, 1300
        
        # With a large max_width, a spread should still be detected as spread
        page_geom = geometry.compute_page_geometry(bytes_data, width, height, max_width=10000)
        assert page_geom is not None
        
        # Spread pages should be marked as spread
        self.assertTrue(page_geom.is_spread)
        # But with wide max_width, it doesn't need downscale
        self.assertFalse(page_geom.needs_downscale)


class ConstantsAndEdgeCases(unittest.TestCase):
    """Verify constants and edge cases."""

    def test_spread_threshold_constant(self):
        """Spread threshold is 1.35:1."""
        self.assertEqual(1.35, geometry.SPREAD_ASPECT_THRESHOLD)

    def test_orientation_map_coverage(self):
        """All valid orientations are mapped."""
        for orientation in range(1, 9):
            self.assertIn(orientation, geometry.ORIENTATION_MAP)

    def test_zero_height_handling(self):
        """Zero height is handled without division errors."""
        # These should not raise exceptions
        dims = geometry.DisplayDimensions(100, 0)
        self.assertEqual(float('inf'), dims.aspect_ratio)
        
        self.assertFalse(geometry.is_spread(100, 0))
        # With zero height and width > max_width, it technically needs downscale
        # This is a degenerate case that shouldn't happen in practice
        self.assertTrue(geometry.needs_downscale(100, 0, max_width=50))

    def test_empty_bytes_handling(self):
        """Empty bytes are handled gracefully."""
        orientation = geometry.read_exif_orientation(b'')
        self.assertIsNone(orientation)
        
        display_dims = geometry.get_display_dimensions(b'', 100, 200)
        self.assertEqual(100, display_dims.width)
        self.assertEqual(200, display_dims.height)


if __name__ == '__main__':
    unittest.main()