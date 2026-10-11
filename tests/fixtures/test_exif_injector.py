"""Unit tests for the EXIF orientation injector."""

import os
import tempfile
import unittest

from exif_injector import inject_orientation, get_orientation


# Try to use ImageMagick to verify, but don't require it
try:
    import subprocess
    
    def read_orientation_with_magick(path: str) -> int | None:
        """Use ImageMagick to read EXIF orientation."""
        try:
            result = subprocess.run(
                ["magick", "identify", "-format", "%[exif:Orientation]", path],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        except (subprocess.TimeoutExpired, OSError, ValueError):
            pass
        return None
    
    MAGICK_AVAILABLE = True
except (ImportError, OSError):
    MAGICK_AVAILABLE = False


class TestEXIFInjector(unittest.TestCase):
    """Test cases for the EXIF orientation injector."""

    def setUp(self) -> None:
        """Create a test JPEG without EXIF."""
        # Create a minimal JPEG for testing
        # This is a tiny valid JPEG (1x1 pixel, grayscale)
        # SOI + APP0 (JFIF) + DQT + DHT + SOS + image data + EOI
        self.plain_jpeg = bytes.fromhex(
            "FFD8 FFE0 0010 4A46 4946 0001 0101 0000 0100 0100 0000"
            "FFDB 0043 0003 0202 0202 0203 0303 0403 0405 0805 0504"
            "0606 0707 0708 0A08 080A 0C0A 0C0C 0D0B 0B0D 0E0D 0E0F"
            "100F 1010 1110 1112 1312 1313 1301 1415 1411 1416 1715"
            "1711 1817 1718 1918 1914 1A1A 1A1B 1B1B 1B1A FFDA 000C"
            "0301 0002 1103 1100 3F00 DD32 E290 9D0C 0E48 ABB6 FFD9"
        )
        
    def test_inject_orientation_1(self) -> None:
        """Test injecting orientation 1 (normal)."""
        result = inject_orientation(self.plain_jpeg, 1)
        orientation = get_orientation(result)
        self.assertEqual(orientation, 1)

    def test_inject_orientation_6(self) -> None:
        """Test injecting orientation 6 (rotated 90° CW)."""
        result = inject_orientation(self.plain_jpeg, 6)
        orientation = get_orientation(result)
        self.assertEqual(orientation, 6)

    def test_inject_orientation_8(self) -> None:
        """Test injecting orientation 8 (rotated 90° CCW)."""
        result = inject_orientation(self.plain_jpeg, 8)
        orientation = get_orientation(result)
        self.assertEqual(orientation, 8)

    def test_all_orientations(self) -> None:
        """Test injecting all eight orientation values."""
        for orientation in range(1, 9):
            with self.subTest(orientation=orientation):
                result = inject_orientation(self.plain_jpeg, orientation)
                read_back = get_orientation(result)
                self.assertEqual(read_back, orientation, 
                               f"Orientation {orientation} not preserved")

    def test_replace_existing_orientation(self) -> None:
        """Test replacing an existing orientation tag."""
        # Inject orientation 6 first
        with_6 = inject_orientation(self.plain_jpeg, 6)
        self.assertEqual(get_orientation(with_6), 6)
        
        # Replace with orientation 3
        with_3 = inject_orientation(with_6, 3)
        self.assertEqual(get_orientation(with_3), 3)

    def test_invalid_orientation(self) -> None:
        """Test that invalid orientation values raise ValueError."""
        with self.assertRaises(ValueError):
            inject_orientation(self.plain_jpeg, 0)
        
        with self.assertRaises(ValueError):
            inject_orientation(self.plain_jpeg, 9)
        
        with self.assertRaises(ValueError):
            inject_orientation(self.plain_jpeg, 100)

    def test_invalid_jpeg(self) -> None:
        """Test that invalid JPEG bytes raise ValueError."""
        with self.assertRaises(ValueError):
            inject_orientation(b"not a jpeg", 1)
        
        with self.assertRaises(ValueError):
            inject_orientation(b"", 1)
        
        with self.assertRaises(ValueError):
            inject_orientation(b"\xFF\xD7", 1)  # Not SOI

    def test_get_orientation_no_exif(self) -> None:
        """Test getting orientation from JPEG without EXIF."""
        orientation = get_orientation(self.plain_jpeg)
        self.assertIsNone(orientation)

    def test_preserves_original_data(self) -> None:
        """Test that non-EXIF data is preserved."""
        original = self.plain_jpeg
        modified = inject_orientation(original, 1)
        
        # Find SOI and EOI positions
        soi_pos = original.find(b"\xFF\xD8")
        eoi_pos = original.find(b"\xFF\xD9")
        
        self.assertEqual(modified[:2], original[:2])  # SOI preserved
        self.assertEqual(modified[-2:], original[-2:])  # EOI preserved
        
        # The original data should appear in the modified version
        # (except for the inserted APP1 segment)
        # This is a basic sanity check

    def test_idempotent_replace(self) -> None:
        """Test that replacing orientation multiple times works."""
        jpeg = self.plain_jpeg
        for orientation in [1, 2, 3, 4, 5, 6, 7, 8, 1]:
            jpeg = inject_orientation(jpeg, orientation)
            self.assertEqual(get_orientation(jpeg), orientation)


@unittest.skipUnless(MAGICK_AVAILABLE, "ImageMagick not available")
class TestEXIFInjectorWithMagick(unittest.TestCase):
    """Test cases that use ImageMagick for verification."""

    def setUp(self) -> None:
        """Create a test JPEG using ImageMagick."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            self.temp_path = f.name
        
        try:
            subprocess.run(
                ["magick", "-size", "100x100", "xc:white", self.temp_path],
                capture_output=True,
                timeout=5,
                check=True,
            )
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, OSError):
            # Clean up if we created the file
            try:
                os.unlink(self.temp_path)
            except OSError:
                pass
            self.temp_path = None

    def tearDown(self) -> None:
        """Clean up test files."""
        if self.temp_path and os.path.exists(self.temp_path):
            try:
                os.unlink(self.temp_path)
            except OSError:
                pass

    def test_magick_reads_injected_orientation(self) -> None:
        """Test that ImageMagick can read the injected orientation."""
        if not self.temp_path:
            self.skipTest("Could not create test JPEG")
        
        with open(self.temp_path, "rb") as f:
            original_bytes = f.read()
        
        # Inject orientation 6
        oriented_bytes = inject_orientation(original_bytes, 6)
        
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(oriented_bytes)
            oriented_path = f.name
        
        try:
            # Check with our function
            self.assertEqual(get_orientation(oriented_bytes), 6)
            
            # Check with ImageMagick
            magick_orientation = read_orientation_with_magick(oriented_path)
            self.assertEqual(magick_orientation, 6)
        finally:
            if os.path.exists(oriented_path):
                os.unlink(oriented_path)


if __name__ == "__main__":
    unittest.main()
