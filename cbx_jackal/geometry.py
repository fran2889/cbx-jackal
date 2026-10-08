"""Display geometry and EXIF orientation handling for comic page analysis.

This module provides the geometric reasoning that underpins bounded downscaling:
 EXIF orientation is honoured before any comparison, a recognised spread is exempt
from the width rule but never split, and every decision is made on display aspect
ratio only.

Spread threshold: 1.35:1 on display aspect only, as reasoned in the epic notes.
A genuine spread of ~1.4:1 pages measures about 1.43:1, and a page scanned sideways
with no orientation tag is indistinguishable from one.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import NamedTuple

# JPEG markers
APP1 = 0xFFE1  # Application Segment 1 (where EXIF lives)

# EXIF identifier: "Exif\x00\x00"
EXIF_IDENTIFIER = b"Exif\x00\x00"

# TIFF byte orders
LITTLE_ENDIAN = b"II"  # Little-endian (Intel)
BIG_ENDIAN = b"MM"    # Big-endian (Motorola)

# TIFF version constant
TIFF_VERSION = 42

# EXIF orientation tag values and their meaning
# Maps orientation value to (swap_width_height, mirror_horizontal, mirror_vertical)
ORIENTATION_MAP = {
    1: (False, False, False),  # Normal
    2: (False, True, False),   # Mirrored (flip horizontal)
    3: (True, False, False),   # Rotated 180°
    4: (True, True, False),    # Mirrored and rotated 180°
    5: (True, True, True),     # Mirrored and rotated 270° CW (or 90° CCW)
    6: (True, False, True),     # Rotated 90° CW (or 270° CCW)
    7: (True, True, True),     # Mirrored and rotated 90° CW
    8: (True, False, True),     # Rotated 270° CW (or 90° CCW)
}

# Spread detection threshold: 1.35:1 ratio
SPREAD_ASPECT_THRESHOLD = 1.35

# JPEG frame header markers
SOF0 = 0xFFC0  # Start of Frame 0 - Baseline DCT
SOF2 = 0xFFC2  # Start of Frame 2 - Progressive DCT
SOF1 = 0xFFC1  # Start of Frame 1 - Extended sequential DCT
SOF3 = 0xFFC3  # Start of Frame 3 - Lossless (sequential)

# Valid SOF markers for dimension extraction
SOF_MARKERS = (SOF0, SOF1, SOF2, SOF3)


def _read_jpeg_dimensions_from_sof(jpeg_bytes: bytes) -> tuple[int, int] | None:
    """Extract width and height from a JPEG SOF (Start of Frame) segment.
    
    Scans the JPEG bytes for SOF0-SOF3 markers and reads the height and width
    from the frame header. Returns (width, height) or None if no valid SOF found.
    """
    if len(jpeg_bytes) < 4:
        return None
    
    # JPEG files start with SOI (0xFFD8)
    if jpeg_bytes[:2] != b'\xff\xd8':
        return None
    
    offset = 2
    while offset + 4 <= len(jpeg_bytes):
        # Each segment starts with 0xFF followed by a marker byte
        if jpeg_bytes[offset] != 0xFF:
            # Not a marker, skip to next byte
            offset += 1
            continue
        
        marker = jpeg_bytes[offset+1]
        
        # Check if this is a Start of Frame marker
        if marker in (0xC0, 0xC1, 0xC2, 0xC3):
            # Found SOF marker - skip marker (2 bytes) and read length (2 bytes)
            if offset + 4 > len(jpeg_bytes):
                return None
                
            # Read segment length (includes the length field itself)
            segment_length = struct.unpack('>H', jpeg_bytes[offset+2:offset+4])[0]
            
            # SOF segment structure: marker(2) + length(2) + precision(1) + height(2) + width(2) + components(N)
            # We need at least 7 more bytes: precision + height + width + components count
            if offset + 2 + segment_length > len(jpeg_bytes):
                return None
            
            data_start = offset + 4  # Skip marker and length
            
            # precision byte (1 byte) - we don't need this
            # height is next 2 bytes
            height_start = data_start + 1
            if height_start + 2 > len(jpeg_bytes):
                return None
                
            height = struct.unpack('>H', jpeg_bytes[height_start:height_start+2])[0]
            
            # width is next 2 bytes after height
            width_start = height_start + 2
            if width_start + 2 > len(jpeg_bytes):
                return None
                
            width = struct.unpack('>H', jpeg_bytes[width_start:width_start+2])[0]
            
            return width, height
        
        # Not an SOF marker - skip this segment
        if offset + 4 > len(jpeg_bytes):
            break
            
        # Read segment length to skip to next segment
        segment_length = struct.unpack('>H', jpeg_bytes[offset+2:offset+4])[0]
        
        if segment_length < 2:
            offset += 2
        else:
            offset += 2 + segment_length
    
    return None


def get_jpeg_dimensions(jpeg_bytes: bytes) -> tuple[int, int] | None:
    """Extract width and height from JPEG bytes.
    
    Returns (width, height) tuple or None if dimensions cannot be extracted.
    This function scans the JPEG for SOF (Start of Frame) markers and extracts
    the encoded dimensions from the frame header.
    """
    return _read_jpeg_dimensions_from_sof(jpeg_bytes)


class DisplayDimensions(NamedTuple):
    """Width and height in display orientation, after EXIF orientation is honoured."""
    width: int
    height: int

    @property
    def aspect_ratio(self) -> float:
        """Width divided by height in display orientation."""
        return self.width / self.height if self.height != 0 else float('inf')


@dataclass(frozen=True)
class PageGeometry:
    """Complete geometric description of a page."""
    original_width: int
    original_height: int
    display_width: int
    display_height: int
    orientation: int | None = None
    is_spread: bool = False
    needs_downscale: bool = False

    @property
    def display_aspect_ratio(self) -> float:
        """Display aspect ratio (width / height)."""
        return self.display_width / self.display_height if self.display_height != 0 else float('inf')


def _read_uint16(data: bytes, offset: int, is_big_endian: bool) -> int:
    """Read a 16-bit unsigned integer from bytes at offset."""
    if is_big_endian:
        return struct.unpack('>H', data[offset:offset+2])[0]
    else:
        return struct.unpack('<H', data[offset:offset+2])[0]


def _read_uint32(data: bytes, offset: int, is_big_endian: bool) -> int:
    """Read a 32-bit unsigned integer from bytes at offset."""
    if is_big_endian:
        return struct.unpack('>I', data[offset:offset+4])[0]
    else:
        return struct.unpack('<I', data[offset:offset+4])[0]


def _find_app1_segment(jpeg_bytes: bytes) -> bytes | None:
    """Find the APP1 segment containing EXIF data in JPEG bytes.
    
    Returns the APP1 segment data (without the marker and length) or None.
    """
    if len(jpeg_bytes) < 4:
        return None
    
    # JPEG files start with SOI (0xFFD8)
    if jpeg_bytes[:2] != b'\xff\xd8':
        return None
    
    offset = 2
    while offset + 4 <= len(jpeg_bytes):
        # Each segment starts with 0xFF followed by a marker byte
        if jpeg_bytes[offset:offset+2] != b'\xff\xe1':
            # Skip to next marker
            marker_high = jpeg_bytes[offset]
            if marker_high != 0xFF:
                return None
            marker = jpeg_bytes[offset+1]
            # Skip variable-length segments
            if 0xD0 <= marker <= 0xD7:  # RST markers
                offset += 2
                continue
            elif 0xD9 == marker:  # EOI
                break
            elif 0xDA == marker:  # SOS - start of scan
                break
            # For other markers, skip based on length field
            if offset + 4 <= len(jpeg_bytes):
                segment_length = struct.unpack('>H', jpeg_bytes[offset+2:offset+4])[0]
                if segment_length >= 2:
                    offset += 2 + segment_length
                else:
                    offset += 2
            else:
                break
            continue
        
        # Found APP1 segment
        if offset + 4 > len(jpeg_bytes):
            return None
        
        segment_length = struct.unpack('>H', jpeg_bytes[offset+2:offset+4])[0]
        if segment_length < 2:
            return None
            
        segment_start = offset + 4
        segment_end = segment_start + (segment_length - 2)
        
        if segment_end > len(jpeg_bytes):
            return None
            
        return jpeg_bytes[segment_start:segment_end]
    
    return None


def _parse_exif_orientation(app1_data: bytes) -> int | None:
    """Parse EXIF orientation tag from APP1 segment data.
    
    The APP1 segment contains: EXIF identifier (6 bytes) + TIFF header (8 bytes) + IFD data
    The TIFF header: byte order (2) + version (2) + IFD offset (4)
    The IFD offset is relative to the start of the TIFF header (byte 6 in APP1 data).
    
    Returns the orientation value (1-8) or None if not found or not parseable.
    """
    if len(app1_data) < 14:
        return None
    
    # Check for EXIF identifier
    if app1_data[:6] != EXIF_IDENTIFIER:
        return None
    
    # Byte order at offset 6
    byte_order = app1_data[6:8]
    is_big_endian = byte_order == BIG_ENDIAN
    
    # TIFF version at offset 8 (should be 42)
    tiff_version = _read_uint16(app1_data, 8, is_big_endian)
    if tiff_version != TIFF_VERSION:
        return None
    
    # Offset to first IFD at offset 10 (4 bytes)
    # This offset is relative to the start of the TIFF header (byte 6)
    ifd_offset_from_tiff_start = _read_uint32(app1_data, 10, is_big_endian)
    
    # Calculate absolute offset in APP1 data: TIFF header starts at byte 6
    ifd_offset = 6 + ifd_offset_from_tiff_start
    
    # Sanity check on IFD offset
    if ifd_offset < 8 or ifd_offset >= len(app1_data):
        return None
    
    # Read IFD entry count at the IFD offset (2 bytes)
    if ifd_offset + 2 > len(app1_data):
        return None
    
    entry_count = _read_uint16(app1_data, ifd_offset, is_big_endian)
    
    # Each IFD entry is 12 bytes
    entry_offset = ifd_offset + 2
    
    for i in range(entry_count):
        entry_start = entry_offset + i * 12
        if entry_start + 12 > len(app1_data):
            break
        
        # Read tag (2 bytes), type (2 bytes), count (4 bytes), value/offset (4 bytes)
        tag = _read_uint16(app1_data, entry_start, is_big_endian)
        entry_type = _read_uint16(app1_data, entry_start + 2, is_big_endian)
        count = _read_uint32(app1_data, entry_start + 4, is_big_endian)
        value_offset = _read_uint32(app1_data, entry_start + 8, is_big_endian)
        
        # EXIF orientation tag is 0x0112 (274 in decimal)
        if tag == 0x0112:
            # Orientation is a SHORT (type 3) with count 1
            if entry_type == 3 and count == 1:
                # Value fits in 4 bytes (inline for count=1)
                orientation = value_offset
                if 1 <= orientation <= 8:
                    return orientation
            elif entry_type == 3 and count > 1:
                # Value is at offset, read first value
                if value_offset + 2 <= len(app1_data):
                    orientation = _read_uint16(app1_data, value_offset, is_big_endian)
                    if 1 <= orientation <= 8:
                        return orientation
    
    return None


def read_exif_orientation(jpeg_bytes: bytes) -> int | None:
    """Read EXIF orientation tag from JPEG bytes.
    
    Returns the orientation value (1-8) or None if not found or not parseable.
    The ImageMagick build in use cannot write EXIF orientation tags, so this
    byte-level parsing is the only reliable way.
    """
    app1_data = _find_app1_segment(jpeg_bytes)
    if app1_data is None:
        return None
    
    return _parse_exif_orientation(app1_data)


def get_display_dimensions(jpeg_bytes: bytes, original_width: int, original_height: int) -> DisplayDimensions:
    """Get the width and height in display orientation, honouring EXIF rotation.
    
    EXIF orientation is honoured before any comparison: an oversized page tagged
    with a non-trivial EXIF orientation is fitted against its display width, so
    `--max-width` is never compared against a page's height.
    
    Args:
        jpeg_bytes: The raw JPEG bytes to check for EXIF orientation.
        original_width: The pixel width from the JPEG header or metadata.
        original_height: The pixel height from the JPEG header or metadata.
    
    Returns:
        DisplayDimensions with width and height in display orientation.
        For orientation values that swap dimensions (5, 6, 7, 8), the
        display dimensions are swapped.
    """
    orientation = read_exif_orientation(jpeg_bytes)
    
    if orientation is None or orientation == 1:
        # No orientation tag or normal orientation
        return DisplayDimensions(original_width, original_height)
    
    # Check if this orientation swaps width and height
    swap_dimensions = orientation in (5, 6, 7, 8)
    
    if swap_dimensions:
        return DisplayDimensions(original_height, original_width)
    else:
        return DisplayDimensions(original_width, original_height)


def is_spread(display_width: int, display_height: int) -> bool:
    """Determine if a page is a double-page spread based on display aspect ratio.
    
    A double-page spread is recognised by its display aspect ratio and exempt from
    the width rule but never split. The threshold is 1.35:1 on display aspect only.
    
    Args:
        display_width: Width in display orientation.
        display_height: Height in display orientation.
    
    Returns:
        True if the page is considered a spread.
    """
    if display_height == 0:
        return False
    
    aspect_ratio = display_width / display_height
    return aspect_ratio >= SPREAD_ASPECT_THRESHOLD


def needs_downscale(
    display_width: int, 
    display_height: int, 
    max_width: int | None = None, 
    max_height: int | None = None
) -> bool:
    """Determine if a page needs downscaling to fit the given bounds.
    
    Given both max_width and max_height, the page must fit both axes, and a page
    is not enlarged either way. With only one bound, the page must fit that
    dimension. With neither bound, no page is downscaled.
    
    Args:
        display_width: Width in display orientation.
        display_height: Height in display orientation.
        max_width: Maximum allowed width, or None for no width limit.
        max_height: Maximum allowed height, or None for no height limit.
    
    Returns:
        True if the page needs downscaling to fit the given bounds.
    """
    if max_width is None and max_height is None:
        return False
    
    # A page is not enlarged, so if it already fits, no downscale
    fits_width = max_width is None or display_width <= max_width
    fits_height = max_height is None or display_height <= max_height
    
    return not (fits_width and fits_height)


def compute_page_geometry(
    jpeg_bytes: bytes, 
    original_width: int | None = None, 
    original_height: int | None = None,
    max_width: int | None = None, 
    max_height: int | None = None
) -> PageGeometry | None:
    """Compute complete geometric description of a page.
    
    Combines JPEG dimension extraction, EXIF orientation reading, display dimension calculation,
    spread detection, and downscaling need into one call.
    
    Args:
        jpeg_bytes: The raw JPEG bytes.
        original_width: Original pixel width (optional, will be extracted from JPEG if None).
        original_height: Original pixel height (optional, will be extracted from JPEG if None).
        max_width: Maximum allowed width for downscale check.
        max_height: Maximum allowed height for downscale check.
    
    Returns:
        PageGeometry with all computed values, or None if dimensions cannot be extracted.
    """
    # Extract dimensions if not provided
    if original_width is None or original_height is None:
        jpeg_dims = get_jpeg_dimensions(jpeg_bytes)
        if jpeg_dims is None:
            return None
        if original_width is None:
            original_width = jpeg_dims[0]
        if original_height is None:
            original_height = jpeg_dims[1]
    
    display_dims = get_display_dimensions(jpeg_bytes, original_width, original_height)
    orientation = read_exif_orientation(jpeg_bytes)
    is_spread_flag = is_spread(display_dims.width, display_dims.height)
    needs_downscale_flag = needs_downscale(
        display_dims.width, display_dims.height, max_width, max_height
    )
    
    return PageGeometry(
        original_width=original_width,
        original_height=original_height,
        display_width=display_dims.width,
        display_height=display_dims.height,
        orientation=orientation,
        is_spread=is_spread_flag,
        needs_downscale=needs_downscale_flag
    )