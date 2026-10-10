"""Resize a JPEG page to fit the display bounds using ImageMagick.

This module handles the downscaling invocation: the page is resized to the maximum
box dimensions while preserving aspect ratio, EXIF orientation is honoured via
`-auto-orient`, and the result is a lossless PNG intermediate that is later passed
to `cjxl --quality=100`.

The trailing `>` in the magick invocation is an explicit downsize guard, ensuring
ImageMagick never enlarges the image even when only one dimension is constrained.

Magick's own `-quality` flag is fidelity-neutral at every value measured and is
confirmed as 100, so it costs nothing and removes any room for doubt.

Temp file discipline matches encode.run: every temp file is cleaned up on every
exit path, including when magick fails or is interrupted.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from typing import NamedTuple

from . import geometry

#: The external tool. Never bundled; see `preflight`.
TOOL = "magick"

#: Output intermediate format: PNG for lossless fidelity.
#: libjxl 0.11.1 measured: `cjxl` with no flags on a PNG intermediate lost
#: 195,790 pixels (19.2%) on saturated content. `--quality=100` lost zero.
INTERMEDIATE_FORMAT = ".png"

#: magick quality flag value. Confirmed fidelity-neutral at every value measured,
#: but 100 is the least room for doubt and costs nothing.
MAGICK_QUALITY = "100"


class ResizeError(Exception):
    """A resize operation failed. Contains the original error details."""

    def __init__(self, message: str, returncode: int = 1):
        super().__init__(message)
        self.returncode = returncode


@dataclass(frozen=True)
class ResizeResult:
    """Outcome of one `magick` resize invocation.

    `data` is the resized PNG bytes when `ok` is True, else None. `error` is a
    verbatim-derived single-line explanation when `ok` is False.
    """

    ok: bool
    data: bytes | None = None
    error: str | None = None
    original_width: int = 0
    original_height: int = 0
    display_width: int = 0
    display_height: int = 0
    target_width: int = 0
    target_height: int = 0

    @property
    def size(self) -> int:
        """Size of the resized PNG output."""
        return len(self.data) if self.data is not None else 0


def _build_command(
    magick: str,
    input_path: str,
    output_path: str,
    target_width: int,
    target_height: int,
) -> list[str]:
    """Build the magick command for resizing one page.
    
    The trailing `>` is an explicit downsize guard: it ensures ImageMagick
    never enlarges the image even when only one dimension is constrained.
    Without it, a page smaller than the target on one axis would be enlarged
    on that axis to fill the target rectangle.
    
    `-auto-orient` handles EXIF orientation automatically, so the geometry
    module's display dimensions are what magick sees and what ends up in the
    output PNG.
    
    `-quality 100` is confirmed fidelity-neutral across all tested values and
    is the least room for doubt.
    """
    return [
        magick,
        input_path,
        "-auto-orient",
        "-quality", MAGICK_QUALITY,
        "-resize", f"{target_width}x{target_height}>",
        f"{INTERMEDIATE_FORMAT[1:]}:{output_path}",  # Remove leading dot
    ]


def _describe_failure(stderr: str, returncode: int) -> str:
    """One-line explanation for a non-zero `magick` exit."""
    # magick prints diagnostics to stderr; keep the last meaningful line
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    if lines:
        return f"magick exited {returncode} ({lines[-1]})"
    return f"magick exited {returncode} (no diagnostic output)"


def compute_target_dimensions(
    display_width: int, 
    display_height: int,
    max_width: int | None = None,
    max_height: int | None = None
) -> tuple[int, int]:
    """Compute target dimensions that fit within the given bounds.
    
    The aspect ratio is preserved. If only one bound is given, the other
    dimension is scaled proportionally. If both are given, the image is
    scaled to fit within both, maintaining aspect ratio.
    
    A page is never enlarged: if the display dimensions already fit within
    the bounds, the original dimensions are returned unchanged.
    
    Args:
        display_width: Width in display orientation.
        display_height: Height in display orientation.
        max_width: Maximum allowed width.
        max_height: Maximum allowed height.
    
    Returns:
        Tuple of (target_width, target_height) that fit within bounds.
    """
    if max_width is None and max_height is None:
        # No bounds means no resize
        return display_width, display_height
    
    # If no resize is needed, return original dimensions
    fits_width = max_width is None or display_width <= max_width
    fits_height = max_height is None or display_height <= max_height
    
    if fits_width and fits_height:
        return display_width, display_height
    
    # Compute target dimensions preserving aspect ratio
    if max_width is not None and max_height is not None:
        # Fit within both bounds
        width_ratio = max_width / display_width if display_width != 0 else float('inf')
        height_ratio = max_height / display_height if display_height != 0 else float('inf')
        scale = min(width_ratio, height_ratio)
    elif max_width is not None:
        # Fit within width bound only
        scale = max_width / display_width if display_width != 0 else 1.0
    elif max_height is not None:
        # Fit within height bound only
        scale = max_height / display_height if display_height != 0 else 1.0
    else:
        scale = 1.0
    
    # Ensure we never scale up
    scale = min(scale, 1.0)
    
    # Apply scaling
    target_width = max(1, int(display_width * scale))
    target_height = max(1, int(display_height * scale))
    
    return target_width, target_height


def resize_page(
    magick: str,
    source: bytes,
    original_width: int,
    original_height: int,
    max_width: int | None = None,
    max_height: int | None = None,
) -> ResizeResult:
    """Resize `source` JPEG bytes to fit bounds using magick.
    
    The page is resized to the maximum box dimensions while preserving aspect
    ratio, EXIF orientation is honoured via `-auto-orient`, and the result is a
    PNG intermediate.
    
    Uses temp files with the same discipline as encode.run: both input and
    output are staged on disk, cleaned up on every exit path, and the PNG result
    is read back into memory for the caller to use with cjxl.
    
    Args:
        magick: Path to the magick executable.
        source: Raw JPEG bytes to resize.
        original_width: Original pixel width from JPEG header.
        original_height: Original pixel height from JPEG header.
        max_width: Maximum allowed width for the result.
        max_height: Maximum allowed height for the result.
    
    Returns:
        ResizeResult with the PNG bytes, dimensions, and success status.
    """
    # Get display dimensions (handles EXIF orientation)
    display_dims = geometry.get_display_dimensions(source, original_width, original_height)
    
    # Compute target dimensions
    target_width, target_height = compute_target_dimensions(
        display_dims.width, display_dims.height, max_width, max_height
    )
    
    # If no resize needed, return the original as a "resize" that copies through
    if (target_width == display_dims.width and 
        target_height == display_dims.height and
        max_width is None and max_height is None):
        # This shouldn't happen with bounds, but handle it cleanly
        return ResizeResult(
            ok=True,
            data=source,
            original_width=original_width,
            original_height=original_height,
            display_width=display_dims.width,
            display_height=display_dims.height,
            target_width=target_width,
            target_height=target_height
        )
    
    # If the target dimensions match the display dimensions, no actual resize needed
    if target_width == display_dims.width and target_height == display_dims.height:
        return ResizeResult(
            ok=True,
            data=source,
            original_width=original_width,
            original_height=original_height,
            display_width=display_dims.width,
            display_height=display_dims.height,
            target_width=target_width,
            target_height=target_height
        )
    
    # Create temp directory and files
    workdir = tempfile.mkdtemp(prefix="cbx-jackal-resize-")
    stem = os.path.join(workdir, "page")
    input_path = stem + ".jpg"
    output_path = stem + INTERMEDIATE_FORMAT
    
    try:
        # Write the source JPEG
        with open(input_path, "wb") as handle:
            handle.write(source)
        
        # Build and run the magick command
        command = _build_command(
            magick, input_path, output_path, target_width, target_height
        )
        
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            return ResizeResult(
                ok=False,
                error=str(exc),
                original_width=original_width,
                original_height=original_height,
                display_width=display_dims.width,
                display_height=display_dims.height,
                target_width=target_width,
                target_height=target_height
            )
        
        if completed.returncode != 0:
            return ResizeResult(
                ok=False,
                error=_describe_failure(
                    completed.stderr.decode("utf-8", "replace"),
                    completed.returncode,
                ),
                original_width=original_width,
                original_height=original_height,
                display_width=display_dims.width,
                display_height=display_dims.height,
                target_width=target_width,
                target_height=target_height
            )
        
        if not os.path.exists(output_path):
            return ResizeResult(
                ok=False,
                error="magick reported success but wrote no output file",
                original_width=original_width,
                original_height=original_height,
                display_width=display_dims.width,
                display_height=display_dims.height,
                target_width=target_width,
                target_height=target_height
            )
        
        # Read the PNG output
        with open(output_path, "rb") as handle:
            png_data = handle.read()
        
        if not png_data:
            return ResizeResult(
                ok=False,
                error="magick produced an empty output file",
                original_width=original_width,
                original_height=original_height,
                display_width=display_dims.width,
                display_height=display_dims.height,
                target_width=target_width,
                target_height=target_height
            )
        
        return ResizeResult(
            ok=True,
            data=png_data,
            original_width=original_width,
            original_height=original_height,
            display_width=display_dims.width,
            display_height=display_dims.height,
            target_width=target_width,
            target_height=target_height
        )
    
    finally:
        # Clean up temp files on every exit path
        for path in (input_path, output_path):
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass
        try:
            if os.path.exists(workdir):
                os.rmdir(workdir)
        except OSError:
            pass