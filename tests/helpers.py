"""Shared fixtures. Stdlib only -- the project keeps zero third-party deps."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile

from cbx_jackal import preflight

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

#: A real JPEG, so the lossless and reversibility assertions mean something.
REAL_JPEG = os.path.join(FIXTURES, "page001.jpg")
#: A second real JPEG, for order-preservation tests.
REAL_JPEG_2 = os.path.join(FIXTURES, "page002.jpg")
#: A truncated JPEG. cjxl exits 1 and writes no output for it.
CORRUPT_JPEG = os.path.join(FIXTURES, "corrupt.jpg")
#: A PNG named .jpg -- cjxl sniffs content, so it converts.
MISNAMED_PNG = os.path.join(FIXTURES, "page003.png")

COMIC_INFO = b'<?xml version="1.0"?><ComicInfo><Pages Count="2"/></ComicInfo>'
README = b"This is a readme, not a page.\n"


def read_bytes(path: str) -> bytes:
    with open(path, "rb") as handle:
        return handle.read()


def build_zip(
    path: str,
    entries,
    compress_type: int = zipfile.ZIP_STORED,
    date_time: tuple = (2026, 1, 1, 0, 0, 0),
) -> str:
    """Write a zip in exactly the order given. `entries` is (name, bytes).

    Timestamps are pinned so a conversion test can assert they survive.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=compress_type) as archive:
        for name, data in entries:
            info = zipfile.ZipInfo(name, date_time=date_time)
            info.compress_type = compress_type
            archive.writestr(info, data)
    return path


def names_in_order(path: str) -> list[str]:
    with zipfile.ZipFile(path, "r") as archive:
        return [info.filename for info in archive.infolist()]


def contents(path: str) -> dict[str, bytes]:
    """Every entry's bytes, keyed by name.

    Raises on a repeated name rather than collapsing it: `ZipFile.read` returns
    the last member for a duplicate, so a dict comprehension here would make a
    ZIP with two members under one name look like a correct single-entry archive
    and hide exactly the shadowing bug this helper exists to catch.
    """
    with zipfile.ZipFile(path, "r") as archive:
        found = {}
        duplicates = []
        for info in archive.infolist():
            if info.filename in found:
                duplicates.append(info.filename)
            found[info.filename] = archive.read(info)
    if duplicates:
        raise AssertionError(
            f"{path} has duplicate entries, which is a shadowing bug: "
            f"{sorted(set(duplicates))}"
        )
    return found


def compress_types(path: str) -> dict[str, int]:
    with zipfile.ZipFile(path, "r") as archive:
        return {i.filename: i.compress_type for i in archive.infolist()}


class ArchiveTestCase(unittest.TestCase):
    """Base class giving each test its own scratch directory."""

    requires_cjxl = True

    @classmethod
    def setUpClass(cls):
        cls.cjxl = preflight.find_tool()
        if cls.requires_cjxl and cls.cjxl is None:
            raise unittest.SkipTest("cjxl is not on PATH")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cbx-jackal-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def path(self, name: str) -> str:
        return os.path.join(self.tmp, name)

    def sample(self) -> str:
        """A two-page archive with metadata, in a deliberately unsorted order."""
        return build_zip(
            self.path("sample.cbz"),
            [
                ("readme.txt", README),
                ("page002.jpg", read_bytes(REAL_JPEG_2)),
                ("ComicInfo.xml", COMIC_INFO),
                ("page001.jpg", read_bytes(REAL_JPEG)),
            ],
        )

    def assertNoTempFiles(self, directory: str | None = None):
        """No cbx-jackal temp file survives a run, on any exit path."""
        directory = directory or self.tmp
        leftovers = [
            name
            for name in os.listdir(directory)
            if name.startswith(".cbx-jackal-") or name.endswith(".cbz.tmp")
        ]
        self.assertEqual([], leftovers, f"temp files left behind: {leftovers}")

    def assertCleanReport(self, report):
        """No page failed and the run is not marked aborted."""
        self.assertEqual([], report.failure_lines())
        self.assertTrue(report.ok)

    def assertPixelsIdentical(
        self, jxl_bytes: bytes, original: bytes, name: str = "page"
    ):
        """CAP-1, pixel half: zero differing pixels when one decoder does both."""
        source_png, output_png = self.decodedPixels(jxl_bytes, original, name)
        self.assertEqual(source_png, output_png)

    def decodedPixels(
        self, jxl_bytes: bytes, original: bytes, name: str = "page"
    ) -> tuple[bytes, bytes]:
        """Decode both sides through libjxl and return the two PNGs.

        Comparing a libjxl decode against a different decoder's decode of the
        source JPEG reports differences that come from the *decoders* -- chroma
        upsampling and IDCT rounding differ between libjxl and libjpeg -- not
        from the transcode. So both sides go through libjxl here: the source is
        transcoded to JXL and decoded back, the output is decoded directly, and
        the caller compares the two PNGs.

        Returned rather than asserted so a caller can legitimately expect the
        pixels to differ without having to swallow an AssertionError, which
        would also swallow a failed `cjxl`/`djxl` invocation.
        """
        cjxl, djxl = shutil.which("cjxl"), shutil.which("djxl")
        if cjxl is None or djxl is None:
            self.skipTest("cjxl and djxl are needed to compare pixels")

        source_jpeg = self.path(f"{name}-source.jpg")
        source_jxl = self.path(f"{name}-source.jxl")
        source_png = self.path(f"{name}-source.png")
        output_png = self.path(f"{name}-output.png")
        output_jxl = self.path(f"{name}-output.jxl")

        with open(source_jpeg, "wb") as handle:
            handle.write(original)
        with open(output_jxl, "wb") as handle:
            handle.write(jxl_bytes)

        # Put the source through libjxl too, so both sides are decoded by the
        # same code and any difference is attributable to the transcode.
        transcoded = subprocess.run(
            [cjxl, source_jpeg, source_jxl],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(0, transcoded.returncode, transcoded.stderr.decode())

        for jxl_path, png_path in (
            (source_jxl, source_png),
            (output_jxl, output_png),
        ):
            completed = subprocess.run(
                [djxl, jxl_path, png_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertEqual(0, completed.returncode, completed.stderr.decode())

        return read_bytes(source_png), read_bytes(output_png)

    def assertReconstructsTo(self, jxl_bytes: bytes, original: bytes):
        """CAP-1: djxl on the output reproduces the source JPEG byte-for-byte."""
        djxl = shutil.which("djxl")
        if djxl is None:
            self.skipTest("djxl is not on PATH")
        jxl_path = self.path("roundtrip.jxl")
        jpg_path = self.path("roundtrip.jpg")
        with open(jxl_path, "wb") as handle:
            handle.write(jxl_bytes)
        completed = subprocess.run(
            [djxl, jxl_path, jpg_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(0, completed.returncode, completed.stderr.decode())
        self.assertEqual(original, read_bytes(jpg_path))
