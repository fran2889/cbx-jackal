# Copyright (C) 2026 Fran
# SPDX-License-Identifier: GPL-3.0-only
"""Invoke `cjxl` for a single page.

The invocation matrix below is the whole reason this module exists. libjxl
defaults to lossless *transcoding* for JPEG input, so `--lossless_jpeg=1`
restates that default rather than changing it:

    cjxl --lossless_jpeg=1 in.jpg out.jxl                     # lossless, reversible
    cjxl --quality=90 in.jpg out.jxl                          # exit 1, no output
    cjxl --quality=90 --lossless_jpeg=0 in.jpg out.jxl        # lossy, irreversible

The middle form fails because libjxl sets `lossless_jpeg=1` by default and
refuses a quality below 100 alongside it:

    Must not set quality below 100 in combination with --lossless_jpeg=1,
    which is set by default.

So every lossy invocation must also pass `--lossless_jpeg=0`. Only the lossless
form embeds JPEG bitstream reconstruction data, which is why reversibility is
exclusive to it and why an existing `.jxl` must never be re-encoded.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass

#: The external tool. Never bundled; see `preflight`.
TOOL = "cjxl"

#: libjxl prints its diagnostics on stderr, including the failure text above.
#: The banner and progress chatter are filtered so report lines stay readable,
#: but nothing is rewritten or reinterpreted.
_NOISE_PREFIXES = (
    "JPEG XL encoder v",
    "Note: Implicit-default for JPEG is lossless-transcoding",
    "Encoding [",
    "Compressed to ",
)


@dataclass(frozen=True)
class EncodeResult:
    """Outcome of one `cjxl` invocation.

    `data` is the encoded JXL bytes when `ok` is True, else None. `error` is a
    verbatim-derived single-line explanation when `ok` is False.
    """

    ok: bool
    data: bytes | None = None
    error: str | None = None
    returncode: int = 0

    @property
    def size(self) -> int:
        return len(self.data) if self.data is not None else 0


def is_lossless(quality: int | None) -> bool:
    """True when the run keeps JPEG bitstream reconstruction data.

    `quality` of None means lossless. A quality of 100 or above is clamped to
    the lossless invocation rather than emitted as
    `--quality=100 --lossless_jpeg=0`, which would silently surrender
    reversibility for no size benefit.
    """
    return quality is None or quality >= 100


def build_command(
    cjxl: str,
    input_path: str,
    output_path: str,
    quality: int | None,
) -> list[str]:
    """The `cjxl` argv for one page.

    Lossless passes only `--lossless_jpeg=1`. Lossy passes **both**
    `--quality=N` and `--lossless_jpeg=0`; dropping the second flag makes
    every lossy run fail. Every flag is written in libjxl's long form, which
    `cjxl` spells as `--name=value`.
    """
    if is_lossless(quality):
        return [cjxl, "--lossless_jpeg=1", input_path, output_path]
    return [cjxl, f"--quality={quality}", "--lossless_jpeg=0", input_path, output_path]


def _meaningful_lines(stderr: str) -> list[str]:
    """stderr lines with banner and progress chatter removed.

    libjxl puts its human-readable summary near the end, after the internal
    `JXL_FAILURE` lines, so the tail is the informative end.
    """
    lines = []
    for raw in stderr.splitlines():
        line = raw.strip()
        if not line:
            continue
        if any(line.startswith(prefix) for prefix in _NOISE_PREFIXES):
            continue
        lines.append(line)
    return lines


#: libjxl traces failures through its own source before reaching a summary, as
#: `./lib/jxl/encode.cc:2095: ...` or `JXL_FAILURE: ...`. Those lines are
#: verbatim and worth keeping as a fallback, but they are not what an owner
#: needs to read.
_INTERNAL_TRACE = re.compile(r"(JXL_FAILURE:|^\S*\.cc:\d+:)")


def _best_line(lines: list[str]) -> str | None:
    """The first line libjxl wrote for the owner rather than for itself.

    Verified on 0.11.1: a corrupt JPEG ends with "Error while decoding the JPEG
    image..." above the generic wrapper, undecodable bytes end with "Getting
    pixel data failed.", and the quality trap is a single plain line.
    """
    if not lines:
        return None
    for line in lines:
        if not _INTERNAL_TRACE.search(line):
            return line
    return lines[-1]


def describe_failure(stderr: str, returncode: int) -> str:
    """One-line explanation for a non-zero `cjxl` exit.

    Kept verbatim from `stderr` apart from dropping the banner and preferring
    libjxl's owner-facing line over its internal traces, and summarised as
    `cjxl exited N (reason)` so the exit code stays visible in the report.
    """
    lines = _meaningful_lines(stderr)
    reason = _best_line(lines)
    if reason is None:
        reason = " ".join(lines) if lines else "no diagnostic output"
    return f"cjxl exited {returncode} ({reason})"


def run(
    cjxl: str,
    source: bytes,
    suffix: str = ".jpg",
    quality: int | None = None,
) -> EncodeResult:
    """Transcode `source` bytes to JXL via a per-page temp file pair.

    The page bytes are staged on disk because `cjxl` only accepts file paths,
    and the encoded result is read back into memory so the caller can write a
    single clean archive. Both temp files are removed on every exit path.

    `cjxl` is a reliable oracle: it exits non-zero and writes no output for
    truncated and garbage JPEGs, so a non-zero exit alone is sufficient to
    classify the entry as not-converted. Any partial output it might leave is
    ignored rather than trusted.
    """
    workdir = tempfile.mkdtemp(prefix="cbx-jackal-")
    stem = os.path.join(workdir, "page")
    input_path = stem + suffix
    output_path = stem + ".jxl"
    try:
        with open(input_path, "wb") as handle:
            handle.write(source)

        command = build_command(cjxl, input_path, output_path, quality)
        try:
            completed = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except OSError as exc:
            return EncodeResult(ok=False, error=str(exc), returncode=-1)

        if completed.returncode != 0:
            return EncodeResult(
                ok=False,
                error=describe_failure(
                    completed.stderr.decode("utf-8", "replace"),
                    completed.returncode,
                ),
                returncode=completed.returncode,
            )

        if not os.path.exists(output_path):
            return EncodeResult(
                ok=False,
                error="cjxl reported success but wrote no output file",
                returncode=completed.returncode,
            )

        with open(output_path, "rb") as handle:
            data = handle.read()

        if not data:
            return EncodeResult(
                ok=False,
                error="cjxl produced an empty output file",
                returncode=completed.returncode,
            )

        return EncodeResult(ok=True, data=data)
    finally:
        for path in (input_path, output_path):
            try:
                os.remove(path)
            except OSError:
                pass
        try:
            os.rmdir(workdir)
        except OSError:
            pass
