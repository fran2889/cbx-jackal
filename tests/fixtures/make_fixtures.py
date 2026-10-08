"""Regenerate the binary fixtures. Run from tests/fixtures/.

The page JPEGs and the PNG are produced with ImageMagick; the truncated JPEG is
cut from a real page so `cjxl` rejects it exactly as it rejects a genuinely
damaged archive member. The fixture archives are built here too, so the bytes
are reproducible rather than being whatever happened to be committed.

For Entry 2 of the bounded-downscaling epic, this script now also generates:
- All eight EXIF orientation values (page_orient_1.jpg through page_orient_8.jpg)
- Spread test fixtures (spread_exact_1.35.jpg, spread_above_1.35.jpg, spread_below_1.35.jpg)
- Edge case fixtures (landscape_splash.jpg, sideways_no_tag.jpg)

Requires ImageMagick 7+ on PATH.

    magick -size 600x900 ... -quality 88 page001.jpg
    python3 make_fixtures.py
"""

import os
import struct
import subprocess
import sys
import tempfile
import zipfile
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))

#: An archive with three pages plus metadata, in a deliberately unsorted order
#: so order-preservation is actually exercised rather than incidentally.
SAMPLE_ENTRIES = [
    ("ComicInfo.xml", None),
    ("readme.txt", None),
    ("page002.jpg", "page002.jpg"),
    ("page001.jpg", "page001.jpg"),
    ("page003.jpg", "page003.jpg"),
]

COMIC_INFO = (
    b'<?xml version="1.0" encoding="UTF-8"?>\n'
    b'<ComicInfo xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
    b"  <Title>Fixture Book</Title>\n"
    b"  <Series>Fixture</Series>\n"
    b"  <Number>1</Number>\n"
    b"  <Pages Count=\"3\"/>\n"
    b"</ComicInfo>\n"
)
README = b"Sample fixture for cbx-jackal.\nNot a page.\n"

# ============================================================================
# EXIF Orientation Fixtures (Entry 2)
# ============================================================================

# Base size for orientation fixtures: 2000x3000 (portrait)
# With different orientations, the display dimensions change
ORIENTATION_FIXTURES = [
    # (filename, width, height, orientation)
    ("page_orient_1.jpg", 2000, 3000, 1),  # Normal
    ("page_orient_2.jpg", 2000, 3000, 2),  # Mirrored
    ("page_orient_3.jpg", 2000, 3000, 3),  # Rotated 180°
    ("page_orient_4.jpg", 2000, 3000, 4),  # Mirrored and rotated 180°
    ("page_orient_5.jpg", 2000, 3000, 5),  # Mirrored and rotated 270° CW
    ("page_orient_6.jpg", 2000, 3000, 6),  # Rotated 90° CW (display: 3000x2000)
    ("page_orient_7.jpg", 2000, 3000, 7),  # Mirrored and rotated 90° CW
    ("page_orient_8.jpg", 2000, 3000, 8),  # Rotated 270° CW
]

# ============================================================================
# Spread Test Fixtures (Entry 2)
# ============================================================================

# Spread detection threshold: 1.35:1
# 1.35:1 = 4/3 ≈ 1.333... but the spec says 1.35
# Actually, 1.35:1 means width/height = 1.35

# Exact 1.35:1: width/height = 1.35, so height = width / 1.35
# For width=2000: height = 2000 / 1.35 ≈ 1481.48, use 1481
SPREAD_EXACT_WIDTH = 2000
SPREAD_EXACT_HEIGHT = 1481  # 2000/1481 ≈ 1.350...

# Above 1.35:1: width/height > 1.35, so height < width/1.35
# For width=2000: use height=1300, ratio = 2000/1300 ≈ 1.538
SPREAD_ABOVE_WIDTH = 2000
SPREAD_ABOVE_HEIGHT = 1300

# Below 1.35:1: width/height < 1.35, so height > width/1.35
# For width=2000: use height=1500, ratio = 2000/1500 ≈ 1.333
SPREAD_BELOW_WIDTH = 2000
SPREAD_BELOW_HEIGHT = 1500

SPREAD_FIXTURES = [
    # (filename, width, height, orientation)
    ("spread_exact_1.35.jpg", SPREAD_EXACT_WIDTH, SPREAD_EXACT_HEIGHT, 1),
    ("spread_above_1.35.jpg", SPREAD_ABOVE_WIDTH, SPREAD_ABOVE_HEIGHT, 1),
    ("spread_below_1.35.jpg", SPREAD_BELOW_WIDTH, SPREAD_BELOW_HEIGHT, 1),
]

# ============================================================================
# Edge Case Fixtures (Entry 2)
# ============================================================================

EDGE_CASE_FIXTURES = [
    # (filename, width, height, orientation)
    ("landscape_splash.jpg", 3000, 1000, 1),  # Wide page, misread as spread
    ("sideways_no_tag.jpg", 2000, 3000, None),  # No EXIF, portrait scanned sideways
]


def _check_magick_available() -> bool:
    """Check if ImageMagick is available."""
    return subprocess.run(
        ["magick", "-version"],
        capture_output=True,
        timeout=5,
    ).returncode == 0


def _create_jpeg(width: int, height: int, color: str = "white", quality: int = 88) -> bytes:
    """Create a JPEG image using ImageMagick.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        color: Background color
        quality: JPEG quality (1-100)
    
    Returns:
        Raw JPEG bytes
    """
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        temp_path = f.name
    
    try:
        result = subprocess.run(
            [
                "magick",
                "-size", f"{width}x{height}",
                f"xc:{color}",
                "-quality", str(quality),
                temp_path,
            ],
            capture_output=True,
            timeout=10,
        )
        
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to create JPEG {width}x{height}: {result.stderr.decode()}"
            )
        
        with open(temp_path, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def _inject_orientation(jpeg_bytes: bytes, orientation: int) -> bytes:
    """Inject EXIF orientation into JPEG bytes.
    
    Args:
        jpeg_bytes: Raw JPEG bytes
        orientation: EXIF orientation value (1-8)
    
    Returns:
        JPEG bytes with orientation injected
    """
    # Import here to avoid dependency issues if exif_injector is missing
    from exif_injector import inject_orientation
    return inject_orientation(jpeg_bytes, orientation)


def _create_oriented_jpeg(width: int, height: int, orientation: Optional[int], color: str = "white") -> bytes:
    """Create a JPEG with optional EXIF orientation.
    
    Args:
        width: Image width in pixels
        height: Image height in pixels
        orientation: EXIF orientation value (1-8) or None for no EXIF
        color: Background color
    
    Returns:
        Raw JPEG bytes
    """
    jpeg_bytes = _create_jpeg(width, height, color)
    
    if orientation is not None:
        jpeg_bytes = _inject_orientation(jpeg_bytes, orientation)
    
    return jpeg_bytes


def _create_sideways_no_tag_jpeg(width: int, height: int) -> bytes:
    """Create a JPEG with no EXIF APP1 segment at all.
    
    This is tricky because ImageMagick might add some EXIF.
    We'll create it with ImageMagick and then strip any APP1 segments.
    """
    jpeg_bytes = _create_jpeg(width, height, "white")
    
    # Strip any APP1 segments (EXIF)
    # Find and remove all APP1 (0xFFE1) segments
    import struct
    
    SOI = 0xFFD8
    APP1 = 0xFFE1
    
    if len(jpeg_bytes) < 2 or struct.unpack(">H", jpeg_bytes[0:2])[0] != SOI:
        return jpeg_bytes
    
    result = bytearray(jpeg_bytes[:2])  # Keep SOI
    pos = 2
    
    while pos < len(jpeg_bytes) - 4:
        marker = struct.unpack(">H", jpeg_bytes[pos:pos+2])[0]
        
        if marker & 0xFF00 != 0xFF00:
            # Not a segment marker
            result.append(jpeg_bytes[pos])
            pos += 1
            continue
        
        if pos + 4 > len(jpeg_bytes):
            break
        
        segment_length = struct.unpack(">H", jpeg_bytes[pos+2:pos+4])[0]
        
        if marker == APP1:
            # Skip this APP1 segment entirely
            pos += 2 + segment_length
        else:
            # Keep this segment
            result.extend(jpeg_bytes[pos:pos+2+segment_length])
            pos += 2 + segment_length
    
    # Append any remaining bytes
    if pos < len(jpeg_bytes):
        result.extend(jpeg_bytes[pos:])
    
    return bytes(result)


def generate_orientation_fixtures() -> list[tuple[str, bytes]]:
    """Generate all orientation fixtures.
    
    Returns:
        List of (filename, bytes) tuples
    """
    fixtures = []
    for filename, width, height, orientation in ORIENTATION_FIXTURES:
        jpeg_bytes = _create_oriented_jpeg(width, height, orientation, "white")
        fixtures.append((filename, jpeg_bytes))
    return fixtures


def generate_spread_fixtures() -> list[tuple[str, bytes]]:
    """Generate all spread test fixtures.
    
    Returns:
        List of (filename, bytes) tuples
    """
    fixtures = []
    for filename, width, height, orientation in SPREAD_FIXTURES:
        jpeg_bytes = _create_oriented_jpeg(width, height, orientation, "lightgray")
        fixtures.append((filename, jpeg_bytes))
    return fixtures


def generate_edge_case_fixtures() -> list[tuple[str, bytes]]:
    """Generate edge case fixtures.
    
    Returns:
        List of (filename, bytes) tuples
    """
    fixtures = []
    for filename, width, height, orientation in EDGE_CASE_FIXTURES:
        if orientation is None:
            jpeg_bytes = _create_sideways_no_tag_jpeg(width, height)
        else:
            jpeg_bytes = _create_oriented_jpeg(width, height, orientation, "darkgray")
        fixtures.append((filename, jpeg_bytes))
    return fixtures


def write_fixtures() -> None:
    """Write all fixtures to disk."""
    # Check if ImageMagick is available
    if not _check_magick_available():
        print("ERROR: ImageMagick (magick) not found on PATH", file=sys.stderr)
        print("Fixtures cannot be generated without ImageMagick", file=sys.stderr)
        sys.exit(1)
    
    # Generate and write orientation fixtures
    print("Generating orientation fixtures...")
    for filename, jpeg_bytes in generate_orientation_fixtures():
        path = os.path.join(HERE, filename)
        with open(path, "wb") as f:
            f.write(jpeg_bytes)
        print(f"  wrote {filename}")
    
    # Generate and write spread fixtures
    print("Generating spread fixtures...")
    for filename, jpeg_bytes in generate_spread_fixtures():
        path = os.path.join(HERE, filename)
        with open(path, "wb") as f:
            f.write(jpeg_bytes)
        print(f"  wrote {filename}")
    
    # Generate and write edge case fixtures
    print("Generating edge case fixtures...")
    for filename, jpeg_bytes in generate_edge_case_fixtures():
        path = os.path.join(HERE, filename)
        with open(path, "wb") as f:
            f.write(jpeg_bytes)
        print(f"  wrote {filename}")


def main() -> None:
    # Write individual fixture files
    write_fixtures()
    
    # Build sample.cbz (original functionality)
    with zipfile.ZipFile(os.path.join(HERE, "sample.cbz"), "w") as archive:
        for name, source in SAMPLE_ENTRIES:
            if source is None:
                data = COMIC_INFO if name.endswith(".xml") else README
            else:
                # Check if source file exists (from fixtures generation)
                source_path = os.path.join(HERE, source)
                if os.path.exists(source_path):
                    with open(source_path, "rb") as handle:
                        data = handle.read()
                else:
                    # Fall back to placeholder
                    data = b""
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, data)
    print("wrote sample.cbz")


if __name__ == "__main__":
    main()
