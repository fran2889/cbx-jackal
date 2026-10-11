"""EXIF orientation injector for JPEG images.

This module provides byte-level injection of EXIF orientation tags into JPEG
images. The ImageMagick build in use cannot write EXIF orientation tags
(`-set exif:Orientation` produces no APP1 segment), so we inject them directly
into the JPEG byte stream.

EXIF orientation values:
  1 = Normal (0°)
  2 = Mirrored (flip horizontal)
  3 = Rotated 180°
  4 = Mirrored and rotated 180°
  5 = Mirrored and rotated 270° CW (or 90° CCW)
  6 = Rotated 90° CW (or 270° CCW)
  7 = Mirrored and rotated 90° CW
  8 = Rotated 270° CW (or 90° CCW)

Usage:
    with open("input.jpg", "rb") as f:
        jpeg_bytes = f.read()
    oriented_bytes = inject_orientation(jpeg_bytes, 6)
    with open("output.jpg", "wb") as f:
        f.write(oriented_bytes)
"""

import struct

# JPEG markers
SOI = 0xFFD8  # Start of Image
APP0 = 0xFFE0  # Application Segment 0 (JFIF)
APP1 = 0xFFE1  # Application Segment 1
APP2 = 0xFFE2  # Application Segment 2
# ... up to APP15 = 0xFFEF

# EXIF identifier: "Exif\x00\x00"
EXIF_IDENTIFIER = b"Exif\x00\x00"

# TIFF byte orders
TIITLE_ENDIAN = b"II"  # Little-endian (Intel)
MM_BIG_ENDIAN = b"MM"  # Big-endian (Motorola)

# TIFF version
TIFF_VERSION = 42


def _build_minimal_exif_tiff(orientation: int) -> bytes:
    """Build a minimal TIFF IFD with just the orientation tag.
    
    Returns only the TIFF portion (without EXIF identifier).
    Uses little-endian (II) byte order.
    
    Structure:
    - TIFF header (8 bytes): byte order + version + IFD offset
    - Number of entries (2 bytes): 1
    - IFD entry (12 bytes): tag + type + count + value
    - Next IFD offset (4 bytes): 0
    """
    if not 1 <= orientation <= 8:
        raise ValueError(f"Orientation must be 1-8, got {orientation}")
    
    # TIFF header
    # Byte order: II (little-endian)
    # Version: 42
    # IFD offset: 8 (the IFD starts at byte 8, which is where we put num_entries)
    tiff_header = TIITLE_ENDIAN + struct.pack("<H", TIFF_VERSION) + struct.pack("<I", 8)
    
    # IFD starts at byte 8
    # First 2 bytes: number of entries = 1
    num_entries = struct.pack("<H", 1)
    
    # IFD entry for orientation tag (0x0112)
    # Each IFD entry is 12 bytes:
    # Tag (2), Type (2), Count (4), Value/Offset (4)
    tag = struct.pack("<H", 0x0112)  # Orientation tag
    tag_type = struct.pack("<H", 3)  # SHORT = 3
    tag_count = struct.pack("<I", 1)  # Count = 1
    
    # For SHORT with count=1, the value goes in the last 4 bytes (inline)
    # We pack the orientation as 2 bytes and pad with 2 zero bytes
    value_bytes = struct.pack("<H", orientation) + b"\x00\x00"
    
    ifd_entry = tag + tag_type + tag_count + value_bytes
    
    # Next IFD offset: 0 (no next IFD)
    next_ifd = struct.pack("<I", 0)
    
    # Total: TIFF header + num_entries + IFD entry + next IFD
    return tiff_header + num_entries + ifd_entry + next_ifd


def _find_exif_app1_segment(jpeg_bytes: bytes) -> int | None:
    """Find the position of an existing EXIF APP1 segment.
    
    Returns the start index of the APP1 marker (0xFFE1), or None if not found.
    """
    if len(jpeg_bytes) < 4:
        return None
    
    if struct.unpack(">H", jpeg_bytes[0:2])[0] != SOI:
        return None
    
    pos = 2  # Start after SOI
    while pos < len(jpeg_bytes) - 4:
        # Read marker (2 bytes, big-endian)
        marker = struct.unpack(">H", jpeg_bytes[pos:pos+2])[0]
        
        # Check for end of image
        if marker == 0xFFDA:  # SOS (Start of Scan)
            break
        elif marker == 0xFFD9:  # EOI (End of Image)
            break
        elif marker & 0xFF00 == 0xFF00:  # Any segment marker
            if pos + 4 > len(jpeg_bytes):
                break
            segment_length = struct.unpack(">H", jpeg_bytes[pos+2:pos+4])[0]
            
            if marker == APP1:
                # Check if this is an EXIF segment
                data_start = pos + 4
                data_end = pos + 2 + segment_length
                if data_end > len(jpeg_bytes):
                    data_end = len(jpeg_bytes)
                
                segment_data = jpeg_bytes[data_start:data_end]
                if segment_data.startswith(EXIF_IDENTIFIER):
                    return pos
            
            # Skip to next segment
            pos += 2 + segment_length
        else:
            pos += 1
    
    return None


def _find_insertion_point(jpeg_bytes: bytes) -> int:
    """Find the best insertion point for an APP1 segment.
    
    The best place is after all other APPn segments (APP0, APP1, etc.)
    but before any non-APPn segments. If there are no APPn segments,
    insert right after SOI.
    
    Returns the insertion position (after SOI, or after the last APPn segment).
    """
    if len(jpeg_bytes) < 2:
        return 2
    
    if struct.unpack(">H", jpeg_bytes[0:2])[0] != SOI:
        return 2
    
    last_appn_end = 2  # Default: right after SOI
    pos = 2
    
    while pos < len(jpeg_bytes) - 4:
        marker = struct.unpack(">H", jpeg_bytes[pos:pos+2])[0]
        
        if marker == 0xFFDA or marker == 0xFFD9:
            # SOS or EOI - we've reached image data
            break
        elif marker & 0xFF00 == 0xFF00:  # Any segment marker
            if pos + 4 > len(jpeg_bytes):
                break
            segment_length = struct.unpack(">H", jpeg_bytes[pos+2:pos+4])[0]
            
            # Check if this is an APPn segment (APP0 to APP15: 0xFFE0 to 0xFFEF)
            if 0xFFE0 <= marker <= 0xFFEF:
                last_appn_end = pos + 2 + segment_length
            
            # Skip to next segment
            pos += 2 + segment_length
        else:
            pos += 1
    
    return last_appn_end


def inject_orientation(jpeg_bytes: bytes, orientation: int) -> bytes:
    """Inject EXIF orientation tag into a JPEG byte sequence.
    
    If the JPEG already has an EXIF APP1 segment, it is replaced.
    Otherwise, a new APP1 segment is inserted at the appropriate position.
    
    Args:
        jpeg_bytes: The raw JPEG bytes
        orientation: The EXIF orientation value (1-8)
    
    Returns:
        The JPEG bytes with EXIF orientation injected
    """
    if not 1 <= orientation <= 8:
        raise ValueError(f"Orientation must be 1-8, got {orientation}")
    
    if len(jpeg_bytes) < 2:
        raise ValueError("Invalid JPEG: too short")
    
    # Verify SOI
    if struct.unpack(">H", jpeg_bytes[0:2])[0] != SOI:
        raise ValueError("Invalid JPEG: missing SOI marker")
    
    # Build EXIF TIFF data
    tiff_data = _build_minimal_exif_tiff(orientation)
    
    # APP1 segment: marker (2) + length (2) + EXIF identifier + TIFF data
    # Length field: size of (EXIF identifier + TIFF data)
    exif_payload = EXIF_IDENTIFIER + tiff_data
    app1_length = len(exif_payload)
    
    # APP1 segment structure: FFE1 + [2-byte length] + payload
    # The length in the APP1 marker is the size of the payload (not including the marker itself)
    app1_segment = struct.pack(">H", APP1) + struct.pack(">H", app1_length) + exif_payload
    
    # Check if there's an existing EXIF APP1 segment
    existing_pos = _find_exif_app1_segment(jpeg_bytes)
    
    if existing_pos is not None:
        # Find the end of the existing segment
        existing_length = struct.unpack(">H", jpeg_bytes[existing_pos+2:existing_pos+4])[0]
        existing_end = existing_pos + 2 + existing_length
        
        # Replace the existing APP1 segment
        new_jpeg = (
            jpeg_bytes[:existing_pos] + 
            app1_segment + 
            jpeg_bytes[existing_end:]
        )
        return new_jpeg
    else:
        # Find the best insertion point
        insert_pos = _find_insertion_point(jpeg_bytes)
        
        # Insert the APP1 segment
        new_jpeg = (
            jpeg_bytes[:insert_pos] + 
            app1_segment + 
            jpeg_bytes[insert_pos:]
        )
        return new_jpeg


def _parse_exif_orientation(exif_payload: bytes) -> int | None:
    """Parse orientation from EXIF payload (after EXIF_IDENTIFIER).
    
    The payload starts with the TIFF header.
    """
    if len(exif_payload) < 8:
        return None
    
    # Check for EXIF identifier at the start
    if not exif_payload.startswith(EXIF_IDENTIFIER):
        # Might be the TIFF data directly
        tiff_data = exif_payload
    else:
        tiff_data = exif_payload[len(EXIF_IDENTIFIER):]
    
    if len(tiff_data) < 8:
        return None
    
    # Parse TIFF header
    byte_order = tiff_data[0:2]
    
    if byte_order == TIITLE_ENDIAN:
        endian = "<"
    elif byte_order == MM_BIG_ENDIAN:
        endian = ">"
    else:
        return None
    
    # Check TIFF version (should be 42)
    version = struct.unpack(endian + "H", tiff_data[2:4])[0]
    if version != TIFF_VERSION:
        return None
    
    # Get offset to IFD0
    ifd_offset = struct.unpack(endian + "I", tiff_data[4:8])[0]
    
    # Check if offset is valid
    if ifd_offset < 8 or ifd_offset >= len(tiff_data):
        return None
    
    # Read IFD0
    ifd_pos = ifd_offset
    
    # Number of entries in IFD0 (2 bytes)
    if ifd_pos + 2 > len(tiff_data):
        return None
    num_entries = struct.unpack(endian + "H", tiff_data[ifd_pos:ifd_pos+2])[0]
    
    # Each IFD entry is 12 bytes
    for i in range(num_entries):
        entry_pos = ifd_pos + 2 + i * 12
        if entry_pos + 12 > len(tiff_data):
            break
        
        # Parse IFD entry
        tag = struct.unpack(endian + "H", tiff_data[entry_pos:entry_pos+2])[0]
        tag_type = struct.unpack(endian + "H", tiff_data[entry_pos+2:entry_pos+4])[0]
        count = struct.unpack(endian + "I", tiff_data[entry_pos+4:entry_pos+8])[0]
        value_offset_bytes = tiff_data[entry_pos+8:entry_pos+12]
        
        if tag == 0x0112:  # Orientation tag
            if tag_type == 3 and count == 1:  # SHORT type with single value
                # For SHORT with count=1, the value is in the offset field (inline)
                # But we need to check the byte order
                if byte_order == TIITLE_ENDIAN:
                    orientation = struct.unpack("<H", value_offset_bytes[:2])[0]
                else:
                    orientation = struct.unpack(">H", value_offset_bytes[:2])[0]
                
                if 1 <= orientation <= 8:
                    return orientation
    
    return None


def get_orientation(jpeg_bytes: bytes) -> int | None:
    """Extract the EXIF orientation value from a JPEG byte sequence.
    
    Returns None if no orientation tag is found.
    """
    if len(jpeg_bytes) < 4:
        return None
    
    if struct.unpack(">H", jpeg_bytes[0:2])[0] != SOI:
        return None
    
    pos = 2  # Start after SOI
    while pos < len(jpeg_bytes) - 4:
        marker = struct.unpack(">H", jpeg_bytes[pos:pos+2])[0]
        
        # Check for end of image
        if marker == 0xFFD9 or marker == 0xFFDA:
            break
        elif marker & 0xFF00 == 0xFF00:  # Any segment marker
            if pos + 4 > len(jpeg_bytes):
                break
            segment_length = struct.unpack(">H", jpeg_bytes[pos+2:pos+4])[0]
            
            if marker == APP1:
                # Check for EXIF
                data_start = pos + 4
                data_end = pos + 2 + segment_length
                if data_end > len(jpeg_bytes):
                    data_end = len(jpeg_bytes)
                
                segment_data = jpeg_bytes[data_start:data_end]
                if segment_data.startswith(EXIF_IDENTIFIER):
                    # Found EXIF APP1 segment
                    exif_payload = segment_data[len(EXIF_IDENTIFIER):]
                    orientation = _parse_exif_orientation(exif_payload)
                    if orientation is not None:
                        return orientation
                    
                    # Try parsing the whole segment data
                    orientation = _parse_exif_orientation(segment_data)
                    if orientation is not None:
                        return orientation
            
            # Skip to next segment
            pos += 2 + segment_length
        else:
            pos += 1
    
    return None


if __name__ == "__main__":
    # Test the injector
    import sys
    
    if len(sys.argv) != 4:
        print(f"Usage: {sys.argv[0]} <input.jpg> <output.jpg> <orientation 1-8>")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2]
    orientation = int(sys.argv[3])
    
    with open(input_path, "rb") as f:
        jpeg_bytes = f.read()
    
    oriented = inject_orientation(jpeg_bytes, orientation)
    
    with open(output_path, "wb") as f:
        f.write(oriented)
    
    # Verify
    read_orientation = get_orientation(oriented)
    print(f"Injected orientation {orientation}, read back: {read_orientation}")
    
    if read_orientation != orientation:
        print("ERROR: Orientation mismatch!")
        sys.exit(1)
    
    print("SUCCESS")
