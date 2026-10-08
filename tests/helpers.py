"""Shared fixtures. Stdlib only -- the project keeps zero third-party deps."""

from __future__ import annotations

import calendar
import io
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile
from typing import TypeVar

from cbx_jackal import cli, discover, preflight

#: Bound to whatever `ArchiveTestCase.require` is asked to narrow.
T = TypeVar("T")

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

#: The modification time stamped on every staged fixture file, so a `7z` fixture
#: is byte-stable across runs. `7z` embeds each entry's mtime, so without this a
#: rebuilt fixture differs from the last one and anything hashing it is flaky.
SEVENZIP_FIXTURE_MTIME = calendar.timegm((2026, 1, 1, 0, 0, 0, 0, 0, 0))


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


def build_7z(
    path: str,
    entries,
    *,
    solid: bool = False,
    password: str | None = None,
    symlink=None,
) -> str:
    """Write a 7z or CB7 archive holding `entries`. `entries` is (name, bytes).

    Shells out to `7z`, which owns the stored order: it sorts entries, so the
    order a reader must reproduce is `7z`'s listing order, not the order given
    here. Every staged file is stamped with `SEVENZIP_FIXTURE_MTIME`, so the
    archive's bytes are the same on every run; the reader takes its timestamps
    from the listing, which is what that stamp is there to make checkable.

    `symlink` is an optional `(name, target)` pair stored with `-snl`, so a
    source holding a link entry can be built without materialising one outside
    the archive.
    """
    sevenzip = shutil.which(preflight.SEVENZIP)
    if sevenzip is None:
        raise unittest.SkipTest(f"{preflight.SEVENZIP} is not on PATH")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # `7z a` updates an archive it finds, keeping entries it was not given, so a
    # reused path would hold more than `entries`. Replace rather than merge, as
    # `build_zip` does by opening with "w".
    if os.path.exists(path):
        os.remove(path)
    with tempfile.TemporaryDirectory(prefix="cbx-jackal-7z-build-") as staging:
        names = []
        for name, data in entries:
            target = os.path.join(staging, name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(data)
            os.utime(target, (SEVENZIP_FIXTURE_MTIME, SEVENZIP_FIXTURE_MTIME))
            names.append(name)
        if symlink is not None:
            link_name, link_target = symlink
            link_path = os.path.join(staging, link_name)
            os.symlink(link_target, link_path)
            os.utime(
                link_path,
                (SEVENZIP_FIXTURE_MTIME, SEVENZIP_FIXTURE_MTIME),
                follow_symlinks=False,
            )
            names.append(link_name)

        command = [sevenzip, "a", "-t7z"]
        if solid:
            command.append("-ms=on")
        if password is not None:
            command.append(f"-p{password}")
        if symlink is not None:
            command.append("-snl")
        command += [path, *names]
        completed = subprocess.run(
            command,
            cwd=staging,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if completed.returncode != 0:
            raise AssertionError(
                f"7z could not build {path}: "
                f"{completed.stderr.decode('utf-8', 'replace')}"
            )
    return path


def rich_cb7(path: str) -> str:
    """A CB7 holding a page, a resource fork, a nested file and a `ComicInfo.xml`.

    The shape the end-to-end tests use: one fixture covering transcode, the
    `__MACOSX` fork rule, a nested path and a pass-through at once. It does not
    stage a directory entry or a bare `._` file, which `classify` also decides;
    those are built where they are tested.
    """
    return build_7z(
        path,
        [
            ("page001.jpg", read_bytes(REAL_JPEG)),
            ("__MACOSX/._page001.jpg", b"\x00\x00applefork"),
            ("extras/note.txt", README),
            ("ComicInfo.xml", COMIC_INFO),
        ],
    )


def solid_cb7(path: str) -> str:
    """A solid CB7: every member shares one compressed block.

    This is the case per-member extraction would re-decompress whole, which is
    why the reader stages one extraction instead.
    """
    return build_7z(
        path,
        [
            ("page001.jpg", read_bytes(REAL_JPEG)),
            ("page002.jpg", read_bytes(REAL_JPEG_2)),
            ("ComicInfo.xml", COMIC_INFO),
        ],
        solid=True,
    )


def encrypted_cb7(path: str, password: str = "secret") -> str:
    """A CB7 whose members need a password, so the reader must refuse it.

    The point is that it must refuse rather than hang: `7z` prompts for a
    password, so a reader that does not force a non-interactive failure would
    block an unattended run here.
    """
    return build_7z(
        path, [("page001.jpg", read_bytes(REAL_JPEG))], password=password
    )


def sevenzip_listing(path: str) -> str:
    """`7z l -slt` output for `path`, so a test can assert what `7z` stored."""
    sevenzip = shutil.which(preflight.SEVENZIP)
    if sevenzip is None:
        raise unittest.SkipTest(f"{preflight.SEVENZIP} is not on PATH")
    completed = subprocess.run(
        [sevenzip, "l", "-slt", path],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.decode("utf-8", "replace")


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
    #: Set on a class whose tests need the `7z` archiver, so it skips cleanly
    #: where that tool is absent -- the same shape `requires_cjxl` already uses.
    requires_7z = False

    #: Absolute path to cjxl. Any class that did not set requires_cjxl =
    #: False has skipped by the time any test body runs, so this is always a
    #: real path where it is read; the opting-out class gets "" and never
    #: reads it, driving preflight.check itself instead.
    cjxl: str = ""

    @classmethod
    def setUpClass(cls):
        resolved = preflight.find_tool()
        if cls.requires_cjxl and resolved is None:
            raise unittest.SkipTest("cjxl is not on PATH")
        cls.cjxl = resolved or ""
        if cls.requires_7z and shutil.which(preflight.SEVENZIP) is None:
            raise unittest.SkipTest("7z is not on PATH")

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="cbx-jackal-test-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def require(self, value: T | None, what: str) -> T:
        """Return `value`, failing the test if it is None.

        For the places where the code under test guarantees a non-None value but
        a checker cannot see the guarantee -- `Report.size_line()` before the
        sizes are known, `EncodeResult.error` on a failed page, the encoded
        bytes on a converted one. Naming what was missing beats letting None
        reach `assertIn` or `write`, which raises a TypeError that says nothing
        about which expectation broke.
        """
        if value is None:
            self.fail("expected %s to be set, but it was None" % what)
        return value

    def path(self, name: str) -> str:
        return os.path.join(self.tmp, name)

    def make_dir(self, name: str) -> str:
        """A subdirectory of `self.tmp`, cleaned up along with it.

        Lives here rather than in each discovery test class so the scratch
        layout is one definition: a copy per class is a copy to drift.
        """
        directory = self.path(name)
        os.makedirs(directory, exist_ok=True)
        return directory

    def capture(self, argv) -> tuple[int, str, str]:
        """Run `cli.main(argv)` with both streams captured.

        Returns `(code, out, err)`. Every discovery test needs to say something
        about both streams -- a report block on one, a refusal or a warning on
        the other -- so this is the shared form rather than a per-class copy.
        """
        from contextlib import redirect_stderr, redirect_stdout

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(argv)
        return code, out.getvalue(), err.getvalue()

    def report_sources(self, out: str) -> list[str]:
        """The `source` of every report block in captured stdout, in order.

        Only lines whose destination ends in the output suffix count: a bare
        `" -> "` split would also swallow the `36006 -> 20815 bytes` size line.
        """
        sources = []
        for line in out.splitlines():
            source, _, destination = line.partition(" -> ")
            if destination.endswith(discover.OUTPUT_SUFFIX):
                sources.append(source)
        return sources

    def make_archive(self, directory: str, name: str, page: bytes = b"") -> str:
        """One real one-page archive at `directory/name`, returning its path.

        `name` is joined onto `directory`, so `make_archive(self.tmp, "c.cbz")`
        is a sibling *file*. Naming a directory the same way builds a directory,
        which is never what a test about explicit paths wants.
        """
        return build_zip(
            os.path.join(directory, name),
            [("page001.jpg", page or read_bytes(REAL_JPEG))],
        )

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
