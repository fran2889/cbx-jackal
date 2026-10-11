# Copyright (C) 2026 Fran
# SPDX-License-Identifier: GPL-3.0-only
"""Every row of the I/O and edge-case matrix, as executable assertions.

One test class or method per row, so a failure names the row that broke.
"""

import glob
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unicodedata
import unittest
import zipfile

# Allow `python3 -m unittest tests.test_archive` as well as
# `python3 -m unittest discover -s tests`: the latter puts this directory on
# sys.path, the former does not.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cbx_jackal import archive, cli, discover, encode, preflight  # noqa: E402
from cbx_jackal.archive import (
    ArchiveError,
    Converter,
    OutputExistsError,
    build_plan,
    classify,
    destination_for,
)

from helpers import (  # noqa: E402
    COMIC_INFO,
    CORRUPT_JPEG,
    FIXTURES,
    MISNAMED_PNG,
    RAR_FIXTURE,
    README,
    REAL_JPEG,
    REAL_JPEG_2,
    REAL_JPEG_3,
    ArchiveTestCase,
    build_7z,
    build_zip,
    compress_types,
    contents,
    encrypted_cb7,
    names_in_order,
    read_bytes,
    rich_cb7,
    sevenzip_entry_names,
    sevenzip_listing,
    solid_cb7,
)


class Classification(unittest.TestCase):
    """The per-entry decision matrix, decided from names alone."""

    def test_jpeg_extensions_any_case_transcode(self):
        for name in ("a.jpg", "a.jpeg", "a.JPG", "a.JPEG", "dir/a.JpG"):
            with self.subTest(name=name):
                self.assertTrue(classify(name).transcode)

    def test_jpeg_output_name_swaps_only_the_extension(self):
        self.assertEqual("a.jxl", classify("a.jpg").output_name)
        self.assertEqual("dir/a.jxl", classify("dir/a.jpeg").output_name)
        self.assertEqual("a.tar.jxl", classify("a.tar.jpg").output_name)

    def test_case_of_the_source_extension_is_preserved(self):
        # Only the trailing extension is rewritten; the stem is verbatim.
        self.assertEqual("A.jxl", classify("A.JPG").output_name)

    def test_existing_jxl_passes_through(self):
        for name in ("a.jxl", "a.JXL", "dir/a.jxl"):
            with self.subTest(name=name):
                plan = classify(name)
                self.assertFalse(plan.transcode)
                self.assertEqual(name, plan.output_name)

    def test_metadata_passes_through_unchanged(self):
        for name in ("ComicInfo.xml", "readme.txt", "Info.txt", "page.png"):
            with self.subTest(name=name):
                plan = classify(name)
                self.assertFalse(plan.transcode)
                self.assertEqual(name, plan.output_name)

    def test_directories_and_resource_forks_pass_through(self):
        for name in ("__MACOSX/", "__MACOSX/._a.jpg", "bonus/", "bonus/art.png"):
            with self.subTest(name=name):
                plan = classify(name)
                self.assertFalse(plan.transcode)
                self.assertEqual(name, plan.output_name)

    def test_extensionless_entry_passes_through(self):
        plan = classify("noext")
        self.assertFalse(plan.transcode)
        self.assertEqual("noext", plan.output_name)

    def test_destination_is_a_new_file_beside_the_input(self):
        self.assertEqual(
            os.path.join("/x", "book.jxl.cbz"), destination_for("/x/book.cbz")
        )
        # Never in-place, whatever the input extension.
        self.assertEqual(
            os.path.join("/x", "book.jxl.cbz"), destination_for("/x/book.zip")
        )
        # Only the final extension is replaced, so a dotted stem survives.
        self.assertEqual(
            os.path.join("/x", "vol.1.jxl.cbz"), destination_for("/x/vol.1.cbz")
        )
        # A relative path resolves against the working directory, never in place.
        self.assertEqual(
            os.path.abspath("book.jxl.cbz"), destination_for("book.cbz")
        )

    def test_the_destination_refuses_a_format_it_cannot_name(self):
        # The name builder is the one place a suffix is built, so the check
        # belongs there: an output this tool's scan would hand straight back in
        # is the drift `destination_for` exists to prevent, and a format
        # carrying a separator would escape the input's directory besides.
        for page_format in ("webp", "", "../../etc/evil", "JXL", "jxl.cbz"):
            with self.subTest(page_format=page_format):
                with self.assertRaises(ValueError):
                    destination_for("/lib/book.cbz", page_format)

    def test_plan_preserves_order(self):
        names = ["z.jpg", "a.jpg", "ComicInfo.xml", "m.jpg"]
        self.assertEqual(names, [p.name for p in build_plan(names)])


class HappyPath(ArchiveTestCase):
    """200-page-style archive of valid .jpg: complete, ordered, smaller."""

    def setUp(self):
        super().setUp()
        self.converter = Converter(self.cjxl)
        self.source = self.sample()
        self.destination = destination_for(self.source)

    def test_output_is_a_new_file_named_jxl_cbz(self):
        self.converter.convert(self.source)
        self.assertTrue(os.path.exists(self.destination))
        self.assertFalse(os.path.exists(self.destination + ".tmp"))
        self.assertNoTempFiles()

    def test_entry_count_is_unchanged(self):
        self.converter.convert(self.source)
        self.assertEqual(
            len(names_in_order(self.source)), len(names_in_order(self.destination))
        )

    def test_entry_order_is_identical_to_the_input(self):
        self.converter.convert(self.source)
        before = names_in_order(self.source)
        after = names_in_order(self.destination)
        # Same positions, with only the extension swapped on converted pages.
        self.assertEqual(
            [classify(n).output_name for n in before],
            after,
        )

    def test_no_page_is_renumbered_or_sorted(self):
        # The sample is deliberately out of order (page002 before page001).
        source = self.sample()
        before = [classify(n).output_name for n in names_in_order(source)]
        self.converter.convert(source)
        after = names_in_order(destination_for(source))
        self.assertEqual(before, after)
        self.assertNotEqual(sorted(after), after)

    def test_output_is_smaller(self):
        self.converter.convert(self.source)
        self.assertLess(
            os.path.getsize(self.destination), os.path.getsize(self.source)
        )

    def test_conversion_reports_all_jpegs(self):
        report = self.converter.convert(self.source)
        self.assertEqual(2, report.converted)
        self.assertEqual(0, report.not_converted)
        self.assertEqual(2, report.passed_through)
        self.assertTrue(report.ok)

    def test_input_archive_is_never_modified(self):
        before = contents(self.source)
        self.converter.convert(self.source)
        self.assertEqual(before, contents(self.source))

    def test_many_pages_keep_order_and_lose_nothing(self):
        pages = [
            (f"page{index:03d}.jpg", read_bytes(REAL_JPEG)) for index in range(1, 21)
        ]
        source = build_zip(self.path("book.cbz"), pages)
        report = Converter(self.cjxl).convert(source)
        self.assertEqual(20, report.converted)
        self.assertEqual(20, len(names_in_order(destination_for(source))))
        self.assertEqual(
            [f"page{index:03d}.jxl" for index in range(1, 21)],
            names_in_order(destination_for(source)),
        )


class LosslessGuarantee(ArchiveTestCase):
    """CAP-1: djxl on the output reproduces the source JPEG byte-for-byte."""

    def test_every_converted_page_round_trips(self):
        source = build_zip(
            self.path("rt.cbz"),
            [("a.jpg", read_bytes(REAL_JPEG)), ("b.jpg", read_bytes(REAL_JPEG_2))],
        )
        Converter(self.cjxl).convert(source)
        out = destination_for(source)
        originals = {
            "a.jpg": read_bytes(REAL_JPEG),
            "b.jpg": read_bytes(REAL_JPEG_2),
        }
        for name, data in contents(out).items():
            if name.endswith(".jxl"):
                self.assertReconstructsTo(data, originals[name[:-4] + ".jpg"])

    def test_lossless_is_the_default_with_no_flag(self):
        source = build_zip(self.path("d.cbz"), [("a.jpg", read_bytes(REAL_JPEG))])
        report = Converter(self.cjxl).convert(source)
        self.assertTrue(report.ok)
        self.assertReconstructsTo(
            contents(destination_for(source))["a.jxl"], read_bytes(REAL_JPEG)
        )

    def test_decoding_the_output_yields_identical_pixels(self):
        source = build_zip(self.path("p.cbz"), [("a.jpg", read_bytes(REAL_JPEG))])
        Converter(self.cjxl).convert(source)
        self.assertPixelsIdentical(
            contents(destination_for(source))["a.jxl"],
            read_bytes(REAL_JPEG),
        )

    def test_lossy_output_does_differ_in_pixels(self):
        # The counterpart to the above: lossy mode really does lose something,
        # so the pixel check above is not passing vacuously. The helper returns
        # the two PNGs rather than asserting them, so a failed cjxl/djxl call
        # still fails here instead of reading as "the pixels differ".
        source_jpeg = read_bytes(REAL_JPEG)
        source = build_zip(self.path("pl.cbz"), [("a.jpg", source_jpeg)])
        Converter(self.cjxl, quality=50).convert(source)
        lossy_jxl = contents(destination_for(source))["a.jxl"]
        self.assertNotEqual(source_jpeg, self._reconstruct(lossy_jxl))
        source_png, output_png = self.decodedPixels(lossy_jxl, source_jpeg)
        self.assertNotEqual(source_png, output_png)

    def _reconstruct(self, jxl_bytes: bytes) -> bytes:
        djxl = shutil.which("djxl")
        if djxl is None:
            self.skipTest("djxl is not on PATH")
        path = self.path("recon.jpg")
        with open(path, "wb") as handle:
            handle.write(jxl_bytes)
        completed = subprocess.run(
            [djxl, path, self.path("out.jpg")], capture_output=True
        )
        self.assertEqual(0, completed.returncode, completed.stderr.decode())
        return read_bytes(self.path("out.jpg"))


class MetadataPassthrough(ArchiveTestCase):
    """CAP-3: everything not a JPEG page is copied byte-identical, in place."""

    def test_metadata_entries_are_byte_identical(self):
        source = build_zip(
            self.path("meta.cbz"),
            [
                ("ComicInfo.xml", COMIC_INFO),
                ("readme.txt", README),
                ("__MACOSX/._page001.jpg", b"resource fork junk"),
                ("bonus/cover.png", read_bytes(MISNAMED_PNG)),
                ("page001.jpg", read_bytes(REAL_JPEG)),
            ],
        )
        Converter(self.cjxl).convert(source)
        out = contents(destination_for(source))
        for name, expected in (
            ("ComicInfo.xml", COMIC_INFO),
            ("readme.txt", README),
            ("__MACOSX/._page001.jpg", b"resource fork junk"),
            ("bonus/cover.png", read_bytes(MISNAMED_PNG)),
        ):
            with self.subTest(name=name):
                self.assertEqual(expected, out[name])

    def test_pass_through_names_are_unchanged(self):
        source = self.sample()
        Converter(self.cjxl).convert(source)
        self.assertIn("ComicInfo.xml", names_in_order(destination_for(source)))
        self.assertIn("readme.txt", names_in_order(destination_for(source)))

    def test_pass_throughs_do_not_affect_exit_code(self):
        source = self.sample()
        code = cli.main([source])
        self.assertEqual(0, code, "pass-throughs must never look like failure")

    def test_nested_structure_is_preserved(self):
        source = build_zip(
            self.path("nested.cbz"),
            [
                ("vol1/page001.jpg", read_bytes(REAL_JPEG)),
                ("vol1/page002.jpg", read_bytes(REAL_JPEG_2)),
                ("vol1/notes.txt", README),
            ],
        )
        Converter(self.cjxl).convert(source)
        self.assertEqual(
            ["vol1/page001.jxl", "vol1/page002.jxl", "vol1/notes.txt"],
            names_in_order(destination_for(source)),
        )

    def test_comicinfo_pages_count_needs_no_rewrite(self):
        # Entry count never changes, so <Pages Count> stays correct untouched.
        source = build_zip(
            self.path("ci.cbz"),
            [("ComicInfo.xml", COMIC_INFO), ("a.jpg", read_bytes(REAL_JPEG))],
        )
        Converter(self.cjxl).convert(source)
        out = contents(destination_for(source))
        self.assertEqual(COMIC_INFO, out["ComicInfo.xml"])
        self.assertEqual(2, len(out))

    def test_directory_entries_survive(self):
        source = build_zip(
            self.path("dirs.cbz"),
            [("bonus/", b""), ("bonus/a.jpg", read_bytes(REAL_JPEG))],
        )
        Converter(self.cjxl).convert(source)
        self.assertIn("bonus/", names_in_order(destination_for(source)))


class AlreadyJxl(ArchiveTestCase):
    """An existing .jxl is copied verbatim and never re-encoded."""

    def test_jxl_entry_is_copied_verbatim(self):
        converted = encode.run(self.cjxl, read_bytes(REAL_JPEG))
        self.assertTrue(converted.ok, converted.error)
        jxl_bytes = converted.data
        source = build_zip(
            self.path("j.cbz"),
            [("a.jpg", read_bytes(REAL_JPEG)), ("b.jxl", jxl_bytes)],
        )
        report = Converter(self.cjxl).convert(source)
        self.assertEqual(1, report.converted)
        self.assertEqual(1, report.passed_through)
        self.assertEqual(jxl_bytes, contents(destination_for(source))["b.jxl"])
        self.assertCleanReport(report)


class CorruptPage(ArchiveTestCase):
    """CAP-3/CAP-4: a failed page is copied through under its original name."""

    def setUp(self):
        super().setUp()
        self.converter = Converter(self.cjxl)
        self.source = build_zip(
            self.path("corrupt.cbz"),
            [
                ("page001.jpg", read_bytes(REAL_JPEG)),
                ("page002.jpg", read_bytes(CORRUPT_JPEG)),
                ("page003.jpg", read_bytes(REAL_JPEG_2)),
            ],
        )
        self.destination = destination_for(self.source)
        self.report = self.converter.convert(self.source)

    def test_archive_is_still_complete(self):
        before = names_in_order(self.source)
        after = names_in_order(self.destination)
        self.assertEqual(len(before), len(after))

    def test_every_entry_stays_at_its_source_position(self):
        # The invariant that makes ordering a correctness property: entry i in
        # the output descends from entry i in the input, and only the extension
        # ever changes.
        before = names_in_order(self.source)
        after = names_in_order(self.destination)
        for source_name, output_name in zip(before, after):
            with self.subTest(entry=source_name):
                self.assertEqual(
                    os.path.dirname(source_name), os.path.dirname(output_name)
                )
                self.assertEqual(
                    os.path.splitext(source_name)[0],
                    os.path.splitext(output_name)[0],
                )

    def test_corrupt_page_is_present_under_its_original_name(self):
        self.assertIn("page002.jpg", names_in_order(self.destination))
        self.assertNotIn("page002.jxl", names_in_order(self.destination))

    def test_corrupt_page_bytes_are_untouched(self):
        self.assertEqual(
            read_bytes(CORRUPT_JPEG), contents(self.destination)["page002.jpg"]
        )

    def test_other_pages_did_convert(self):
        out = contents(self.destination)
        self.assertIn("page001.jxl", out)
        self.assertIn("page003.jxl", out)

    def test_report_names_the_failure_once(self):
        lines = self.report.failure_lines()
        self.assertEqual(1, len(lines))
        self.assertTrue(lines[0].startswith("page002.jpg: "))

    def test_summary_counts_are_three_way(self):
        self.assertEqual(2, self.report.converted)
        self.assertEqual(0, self.report.passed_through)
        self.assertEqual(1, self.report.not_converted)
        self.assertIn("2/3 converted", self.report.summary())

    def test_exit_code_is_non_zero(self):
        self.assertEqual(cli.EXIT_FAILED, cli.main([self.source, "--force"]))

    def test_order_is_unchanged_despite_the_hole(self):
        self.assertEqual(
            ["page001.jxl", "page002.jpg", "page003.jxl"],
            names_in_order(self.destination),
        )


class MidRunAbort(ArchiveTestCase):
    """A read failure partway through aborts the run and leaves no output."""

    def _corrupt_payload(self, path: str, entry_index: int = 1) -> str:
        """Flip a payload byte inside one entry, leaving the zip structurally valid."""
        with open(path, "rb") as handle:
            raw = bytearray(handle.read())
        offsets = []
        cursor = 0
        while True:
            found = raw.find(b"PK\x03\x04", cursor)
            if found < 0:
                break
            offsets.append(found)
            cursor = found + 4
        header = offsets[entry_index]
        name_length = int.from_bytes(raw[header + 26 : header + 28], "little")
        extra_length = int.from_bytes(raw[header + 28 : header + 30], "little")
        start = header + 30 + name_length + extra_length
        raw[start + 50] ^= 0xFF
        with open(path, "wb") as handle:
            handle.write(bytes(raw))
        return path

    def test_bad_crc_aborts_and_leaves_no_output(self):
        source = self._corrupt_payload(self.sample())
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        self.assertIn("CRC-32", str(caught.exception))
        self.assertFalse(os.path.exists(destination_for(source)))
        self.assertNoTempFiles()

    def test_a_preexisting_output_survives_a_later_abort_untouched(self):
        # An abort must not delete or truncate an output the owner already has.
        # The only thing that publishes is os.replace, and an abort never
        # reaches it, so the earlier good output has to survive byte-for-byte.
        source = self.sample()
        destination = destination_for(source)
        Converter(self.cjxl).convert(source)
        before = contents(destination)

        self._corrupt_payload(source)
        with self.assertRaises(ArchiveError):
            Converter(self.cjxl).convert(source, force=True)

        self.assertEqual(before, contents(destination))
        self.assertNoTempFiles()


class OutputExists(ArchiveTestCase):
    """An existing output is refused unless --force is given."""

    def setUp(self):
        super().setUp()
        self.converter = Converter(self.cjxl)
        self.source = self.sample()
        self.destination = destination_for(self.source)
        self.converter.convert(self.source)
        self.sentinel = contents(self.destination)

    def test_refuses_without_force(self):
        with self.assertRaises(OutputExistsError):
            self.converter.convert(self.source)
        self.assertEqual(self.sentinel, contents(self.destination))

    def test_input_untouched_when_refused(self):
        before = contents(self.source)
        with self.assertRaises(OutputExistsError):
            self.converter.convert(self.source)
        self.assertEqual(before, contents(self.source))

    def test_force_overwrites(self):
        self.converter.convert(self.source, force=True)
        self.assertEqual(self.sentinel, contents(self.destination))
        self.assertNoTempFiles()

    def test_cli_exits_non_zero_when_output_exists(self):
        self.assertEqual(cli.EXIT_ENVIRONMENT, cli.main([self.source]))


class UnreadableArchive(ArchiveTestCase):
    """An archive we cannot read is not safe to rewrite. Leave no output."""

    def test_bad_zip_leaves_no_output(self):
        bad = self.path("bad.cbz")
        with open(bad, "wb") as handle:
            handle.write(b"this is not a zip file at all")
        with self.assertRaises(ArchiveError):
            Converter(self.cjxl).convert(bad)
        self.assertFalse(os.path.exists(destination_for(bad)))
        self.assertNoTempFiles()

    def test_missing_file_leaves_no_output(self):
        missing = self.path("nope.cbz")
        with self.assertRaises(ArchiveError):
            Converter(self.cjxl).convert(missing)
        self.assertFalse(os.path.exists(destination_for(missing)))

    def test_cli_reports_unreadable_archive_without_traceback(self):
        from contextlib import redirect_stderr, redirect_stdout

        bad = self.path("bad2.cbz")
        with open(bad, "wb") as handle:
            handle.write(b"not a zip")
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main([bad])
        self.assertNotEqual(0, code)
        self.assertNotIn("Traceback", err.getvalue())
        self.assertFalse(os.path.exists(destination_for(bad)))


class LossyMode(ArchiveTestCase):
    """CAP-2: deliberate quality control, with the mode stated."""

    def test_lossy_output_is_smaller_than_lossless(self):
        lossless = Converter(self.cjxl).convert(
            build_zip(self.path("l.cbz"), [("a.jpg", read_bytes(REAL_JPEG))])
        )
        lossy = Converter(self.cjxl, quality=60).convert(
            build_zip(self.path("y.cbz"), [("a.jpg", read_bytes(REAL_JPEG))])
        )
        lossless_bytes = contents(destination_for(self.path("l.cbz")))["a.jxl"]
        lossy_bytes = contents(destination_for(self.path("y.cbz")))["a.jxl"]
        self.assertLess(len(lossy_bytes), len(lossless_bytes))
        self.assertLess(len(lossy_bytes), len(read_bytes(REAL_JPEG)))
        self.assertTrue(lossless.ok)
        self.assertTrue(lossy.ok)

    def test_mode_is_stated_in_the_report(self):
        report = Converter(self.cjxl, quality=60).convert(
            build_zip(self.path("m.cbz"), [("a.jpg", read_bytes(REAL_JPEG))])
        )
        rendered = report.render(quality=60)
        self.assertIn("lossy", rendered)
        self.assertIn("quality 60", rendered)
        self.assertIn("NOT recoverable", rendered)

    def test_default_mode_states_recoverability(self):
        report = Converter(self.cjxl).convert(
            build_zip(self.path("n.cbz"), [("a.jpg", read_bytes(REAL_JPEG))])
        )
        rendered = report.render(quality=None)
        self.assertIn("lossless", rendered)
        self.assertIn("recoverable", rendered)

    def test_quality_below_100_succeeds(self):
        # Without --lossless_jpeg=0 every lossy run exits 1.
        report = Converter(self.cjxl, quality=90).convert(
            build_zip(self.path("q.cbz"), [("a.jpg", read_bytes(REAL_JPEG))])
        )
        self.assertTrue(report.ok, report.failure_lines())


class StrictMode(ArchiveTestCase):
    """--strict turns a page failure into "write nothing at all"."""

    def test_strict_writes_no_output(self):
        source = build_zip(
            self.path("s.cbz"),
            [
                ("page001.jpg", read_bytes(REAL_JPEG)),
                ("page002.jpg", read_bytes(CORRUPT_JPEG)),
            ],
        )
        with self.assertRaises(ArchiveError):
            Converter(self.cjxl, strict=True).convert(source)
        self.assertFalse(os.path.exists(destination_for(source)))
        self.assertNoTempFiles()

    def test_strict_is_happy_when_all_pages_convert(self):
        source = self.sample()
        report = Converter(self.cjxl, strict=True).convert(source)
        self.assertTrue(report.ok)
        self.assertTrue(os.path.exists(destination_for(source)))


class DryRun(ArchiveTestCase):
    """--dry-run writes nothing but reports the plan and size figures."""

    def setUp(self):
        super().setUp()
        self.source = self.sample()
        self.destination = destination_for(self.source)

    def test_nothing_is_written(self):
        report = Converter(self.cjxl).convert(self.source, dry_run=True)
        self.assertFalse(os.path.exists(self.destination))
        self.assertTrue(report.ok)

    def test_plan_is_reported(self):
        report = Converter(self.cjxl).convert(self.source, dry_run=True)
        self.assertEqual(2, report.converted)
        self.assertEqual(2, report.passed_through)
        self.assertIn("2/4 converted", report.summary())

    def test_size_figures_are_reported(self):
        report = Converter(self.cjxl).convert(self.source, dry_run=True)
        self.assertGreater(report.output_bytes, 0)
        self.assertIn("bytes", self.require(report.size_line(), "size_line"))
        self.assertLess(report.output_bytes, report.source_bytes)

    def test_dry_run_over_a_corrupt_page_reports_the_failure(self):
        source = build_zip(
            self.path("dc.cbz"),
            [("a.jpg", read_bytes(REAL_JPEG)), ("b.jpg", read_bytes(CORRUPT_JPEG))],
        )
        report = Converter(self.cjxl).convert(source, dry_run=True)
        self.assertFalse(report.ok)
        self.assertEqual(1, report.not_converted)
        self.assertFalse(os.path.exists(destination_for(source)))

    def test_dry_run_does_not_trip_the_exists_check(self):
        # A dry run writes nothing, so an existing output cannot collide with it.
        # Reporting on a library you already converted should not demand --force.
        Converter(self.cjxl).convert(self.source)
        report = Converter(self.cjxl).convert(self.source, dry_run=True)
        self.assertTrue(report.ok)

    def test_dry_run_leaves_an_existing_output_untouched(self):
        Converter(self.cjxl).convert(self.source)
        before = contents(self.destination)
        Converter(self.cjxl).convert(self.source, dry_run=True)
        self.assertEqual(before, contents(self.destination))

    def test_rendered_output_flags_dry_run(self):
        report = Converter(self.cjxl).convert(self.source, dry_run=True)
        self.assertIn("dry run", report.render(dry_run=True))


class ContainerContract(ArchiveTestCase):
    """Every entry written out is ZIP_STORED; nothing is deflated."""

    def test_all_entries_are_stored(self):
        source = self.sample()
        Converter(self.cjxl).convert(source)
        types = compress_types(destination_for(source))
        for name, value in types.items():
            with self.subTest(name=name):
                self.assertEqual(zipfile.ZIP_STORED, value)

    def test_deflated_input_is_written_out_stored(self):
        source = build_zip(
            self.path("deflate.cbz"),
            [("a.jpg", read_bytes(REAL_JPEG)), ("readme.txt", README)],
            compress_type=zipfile.ZIP_DEFLATED,
        )
        self.assertEqual(
            zipfile.ZIP_DEFLATED, compress_types(source)["readme.txt"]
        )
        Converter(self.cjxl).convert(source)
        self.assertEqual(
            zipfile.ZIP_STORED,
            compress_types(destination_for(source))["readme.txt"],
        )

    def test_pass_through_content_survives_a_recompression(self):
        source = build_zip(
            self.path("recomp.cbz"),
            [("readme.txt", README)],
            compress_type=zipfile.ZIP_DEFLATED,
        )
        Converter(self.cjxl).convert(source)
        self.assertEqual(README, contents(destination_for(source))["readme.txt"])

    def test_no_temp_file_survives_a_successful_run(self):
        Converter(self.cjxl).convert(self.sample())
        self.assertNoTempFiles()

    def test_no_temp_file_survives_a_failed_run(self):
        source = build_zip(
            self.path("ft.cbz"), [("a.jpg", read_bytes(CORRUPT_JPEG))]
        )
        Converter(self.cjxl).convert(source)
        self.assertNoTempFiles()


class StubSource:
    """A source in memory: names and bytes, no filesystem, no archiver.

    The registry maps a suffix to a callable that builds a source from a path,
    and a stub has nothing to build from one, so the test registers a closure
    over an instance instead. The path still has to exist on disk, because
    `convert` measures the source file's size.
    """

    def __init__(self, entries, templates=None, fail_on=None):
        # `entries` is the source's own stored order, deliberately unsorted by
        # callers: nothing may sort it and nothing may walk it.
        self._entries = list(entries)
        self._templates = templates or {}
        self._fail_on = fail_on
        self.closed = False

    def names_in_order(self):
        return [name for name, _ in self._entries]

    def read(self, name):
        if name == self._fail_on:
            raise ArchiveError(f"cannot read {name}: simulated unreadable entry")
        for entry_name, data in self._entries:
            if entry_name == name:
                return data
        raise ArchiveError(f"cannot read {name}: not in the archive")

    def template_for(self, name):
        return self._templates.get(name)

    def close(self):
        self.closed = True


class SourceSeam(ArchiveTestCase):
    """Entry 6's seam: a source that is not a ZIP converts end to end."""

    def register(self, stub, suffix=".stub"):
        """One book backed by `stub`, at a real path with that suffix."""
        original = dict(archive.SOURCE_READERS)
        archive.SOURCE_READERS[suffix] = lambda path: stub

        def restore():
            archive.SOURCE_READERS.clear()
            archive.SOURCE_READERS.update(original)

        self.addCleanup(restore)
        path = self.path(f"book{suffix}")
        with open(path, "wb") as handle:
            handle.write(b"stub: the registry supplies the reader")
        return path

    def test_a_stub_book_converts_end_to_end_in_the_sources_order(self):
        # Deliberately unsorted, and the fork is not a page even though its
        # name says .jpg: the gate decides from the name, and the seam carries
        # that unchanged. The output order is the input order, not sorted.
        stub = StubSource(
            [
                ("extras/", b""),
                ("__MACOSX/._page002.jpg", b"\x00\x00applefork"),
                ("zpage999.jpg", read_bytes(REAL_JPEG)),
                ("apage001.jpg", read_bytes(REAL_JPEG_2)),
                ("ComicInfo.xml", COMIC_INFO),
            ]
        )
        path = self.register(stub)
        report = Converter(self.cjxl).convert(path)

        self.assertTrue(stub.closed, "the source was never closed")
        out = destination_for(path)
        self.assertEqual(
            [
                "extras/",
                "__MACOSX/._page002.jpg",
                "zpage999.jxl",
                "apage001.jxl",
                "ComicInfo.xml",
            ],
            names_in_order(out),
        )
        written = contents(out)
        self.assertEqual(b"\x00\x00applefork", written["__MACOSX/._page002.jpg"])
        self.assertEqual(COMIC_INFO, written["ComicInfo.xml"])
        self.assertEqual(2, report.converted)
        self.assertEqual(3, report.passed_through)
        self.assertEqual(0, report.not_converted)

    def test_a_container_no_reader_claims_is_refused_before_any_output(self):
        # `.dat` because no epic will ever register it, and the file holds a
        # perfectly valid ZIP's bytes on purpose: the refusal is by suffix,
        # never by content, so a fallback reader that opens it anyway is the
        # bug this test exists to catch. Nothing about any real archiver is
        # named.
        path = self.path("book.dat")
        build_zip(path, [("readme.txt", README)])
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(path)
        self.assertIn("no reader", str(caught.exception))
        self.assertIn(".dat", str(caught.exception))
        self.assertFalse(os.path.exists(destination_for(path)))
        self.assertNoTempFiles()

    def test_a_source_offering_no_template_gets_the_documented_default(self):
        stub = StubSource([("readme.txt", README)])
        path = self.register(stub)
        Converter(self.cjxl).convert(path)
        with zipfile.ZipFile(destination_for(path)) as out:
            info = out.getinfo("readme.txt")
            self.assertEqual(
                archive.DEFAULT_ENTRY_TEMPLATE.date_time, info.date_time
            )
            # `writestr` preserves a nonzero attribute and stamps its own
            # `0o600 << 16` when the value is 0 -- the same mode every entry
            # zipfile itself creates carries. Either way the outcome is
            # fixed, which is the point: nothing is read from the clock.
            self.assertEqual(0o600 << 16, info.external_attr)

    def test_a_read_failure_names_the_entry_and_writes_nothing(self):
        stub = StubSource(
            [("a.jpg", read_bytes(REAL_JPEG)), ("bad.txt", README)],
            fail_on="bad.txt",
        )
        path = self.register(stub)
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(path)
        self.assertIn("bad.txt", str(caught.exception))
        self.assertFalse(os.path.exists(destination_for(path)))
        self.assertNoTempFiles()

    def test_a_stub_source_survives_a_dry_run(self):
        stub = StubSource([("a.jpg", read_bytes(REAL_JPEG)), ("readme.txt", README)])
        path = self.register(stub)
        report = Converter(self.cjxl).convert(path, dry_run=True)
        self.assertFalse(os.path.exists(destination_for(path)))
        self.assertEqual(1, report.converted)
        self.assertTrue(stub.closed)
        self.assertNoTempFiles()


class SevenZipListingMetadata(unittest.TestCase):
    """`7z`'s mode string maps to the Unix `st_mode` a ZIP entry carries."""

    def test_the_mode_string_maps_to_the_unix_st_mode(self):
        cases = {
            "-rw-r--r--": 0o100644,
            "-rwxr-xr-x": 0o100755,
            "-rw-r-----": 0o100640,
            "drwxr-xr-x": 0o40755,
            "lrwxrwxrwx": 0o120777,
            "-rwsr-xr-x": 0o104755,
            "-rwSr--r--": 0o104644,
            "-rw-rw-rwt": 0o101667,
        }
        for mode, expected in cases.items():
            with self.subTest(mode=mode):
                self.assertEqual(expected, archive._parse_mode(mode))

    def test_a_mode_that_is_not_a_mode_is_none(self):
        for mode in ("", "not-a-mode", "-rw-r--r-", "?rw-r--r--", "drwxr-xr-x-"):
            with self.subTest(mode=mode):
                self.assertIsNone(archive._parse_mode(mode))


class SevenZipSource(ArchiveTestCase):
    """The staged-extraction reader: a CB7 or 7Z converts end to end.

    These sit beside `SourceSeam` because both prove the same seam with a
    source that is not the ZIP one; the difference is that this one is real.
    """

    requires_7z = True

    def test_a_cb7_converts_end_to_end_in_the_listings_order(self):
        # Deliberately unsorted: 7z owns the order, and the reader must
        # reproduce the listing's, not the order handed to the builder.
        source = build_7z(
            self.path("book.cb7"),
            [
                ("zpage999.jpg", read_bytes(REAL_JPEG)),
                ("ComicInfo.xml", COMIC_INFO),
                ("nested/inner.txt", README),
            ],
        )
        report = Converter(self.cjxl).convert(source)
        out = destination_for(source)

        # 7z sorts by name, so the listing order is the source order.
        self.assertEqual(
            ["ComicInfo.xml", "nested/inner.txt", "zpage999.jxl"],
            names_in_order(out),
        )
        written = contents(out)
        self.assertEqual(COMIC_INFO, written["ComicInfo.xml"])
        self.assertEqual(README, written["nested/inner.txt"])
        self.assertEqual(1, report.converted)
        self.assertEqual(2, report.passed_through)
        self.assertEqual(0, report.not_converted)
        self.assertNoTempFiles()

    def test_a_7z_input_is_registered_and_converts_too(self):
        source = build_7z(
            self.path("book.7z"),
            [("page001.jpg", read_bytes(REAL_JPEG))],
        )
        report = Converter(self.cjxl).convert(source)
        out = destination_for(source)
        self.assertEqual(["page001.jxl"], names_in_order(out))
        self.assertEqual(1, report.converted)
        self.assertReconstructsTo(contents(out)["page001.jxl"], read_bytes(REAL_JPEG))

    def test_a_rar_input_is_registered_and_converts_too(self):
        # RAR is the one container 7z reads but cannot create, so the fixture
        # is committed rather than built. book.rar holds page001.jpg,
        # page002.jpg and page003.jpg, in that order.
        # Copy so the committed fixture is never written to.
        source = self.path("book.rar")
        shutil.copyfile(RAR_FIXTURE, source)
        report = Converter(self.cjxl).convert(source)
        out = destination_for(source)
        # 7z lists and extracts in name order, so page001, page002, page003
        self.assertEqual(
            ["page001.jxl", "page002.jxl", "page003.jxl"],
            names_in_order(out),
        )
        self.assertEqual(3, report.converted)
        written = contents(out)
        self.assertReconstructsTo(written["page001.jxl"], read_bytes(REAL_JPEG))
        self.assertReconstructsTo(written["page002.jxl"], read_bytes(REAL_JPEG_2))
        self.assertReconstructsTo(written["page003.jxl"], read_bytes(REAL_JPEG_3))
        self.assertNoTempFiles()

    def test_the_entry_metadata_is_carried_from_the_listing(self):
        # `7z l -slt` carries a `Modified` and an `Attributes` mode, and a
        # reader that can supply real values does rather than defaulting.
        source = build_7z(
            self.path("meta.cb7"),
            [("page001.jpg", read_bytes(REAL_JPEG))],
        )
        Converter(self.cjxl).convert(source)
        with zipfile.ZipFile(destination_for(source)) as out:
            info = out.getinfo("page001.jxl")
        mode = info.external_attr >> 16
        self.assertEqual(0o100000, mode & 0o170000, "a regular file's type bits")
        self.assertNotEqual(0, mode & 0o777, "the listing's permissions")
        self.assertEqual(3, info.create_system)
        self.assertNotEqual(
            archive.DEFAULT_ENTRY_TEMPLATE.date_time,
            info.date_time,
            "the listing's Modified should replace the fixed default",
        )

    def test_a_symlink_entry_is_refused_and_never_materialised(self):
        if not hasattr(os, "symlink"):
            self.skipTest("this platform cannot create symlinks")
        source = build_7z(
            self.path("link.cb7"),
            [("page001.jpg", read_bytes(REAL_JPEG))],
            symlink=("link.jpg", "page001.jpg"),
        )
        before = self.workdirs()
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        self.assertIn("link.jpg", str(caught.exception))
        self.assertFalse(os.path.exists(destination_for(source)))
        self.assertEqual(before, self.workdirs())

    def test_no_temp_directory_survives_a_failed_listing(self):
        source = self.path("broken.cb7")
        with open(source, "wb") as handle:
            handle.write(b"this is not a 7z archive")
        before = self.workdirs()
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        self.assertIn("cannot read", str(caught.exception))
        self.assertFalse(os.path.exists(destination_for(source)))
        self.assertEqual(before, self.workdirs())

    def test_no_temp_directory_survives_a_failed_extraction(self):
        # The matrix's "fails to extract" row, which the listing-failure case
        # above does not reach: the header stays readable so `7z l` succeeds,
        # and the corrupted data makes `7z x` the step that fails.
        source = build_7z(
            self.path("crc.cb7"),
            [("page.bin", os.urandom(20000)), ("ComicInfo.xml", COMIC_INFO)],
        )
        damaged = bytearray(read_bytes(source))
        for offset in (len(damaged) // 3, len(damaged) // 2):
            damaged[offset] ^= 0xFF
        with open(source, "wb") as handle:
            handle.write(bytes(damaged))
        before = self.workdirs()
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        self.assertIn("cannot read", str(caught.exception))
        self.assertFalse(os.path.exists(destination_for(source)))
        self.assertEqual(before, self.workdirs())

    def test_a_directory_entry_stays_a_directory(self):
        # `7z l` lists a directory with no trailing slash; the reader restores
        # one, so the gate sees what the ZIP path would have shown it and the
        # output keeps a directory rather than a zero-byte file of that name.
        directory = self.make_dir("stage")
        os.mkdir(os.path.join(directory, "emptydir"))
        with open(os.path.join(directory, "f.txt"), "wb") as handle:
            handle.write(README)
        source = self.path("dirs.cb7")
        subprocess.run(
            ["7z", "a", "-t7z", source, "emptydir", "f.txt"],
            cwd=directory,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        Converter(self.cjxl).convert(source)
        with zipfile.ZipFile(destination_for(source)) as out:
            self.assertTrue(out.getinfo("emptydir/").is_dir())
            self.assertFalse(out.getinfo("f.txt").is_dir())


class GeneratedFixtures(ArchiveTestCase):
    """The 7z fixture builder is byte-stable, so a fixture can be regenerated.

    Needs `7z` to build, not `cjxl` to convert: these assert the fixtures, not a
    conversion.
    """

    requires_cjxl = False
    requires_7z = True

    def test_a_cb7_fixture_is_byte_stable(self):
        first = build_7z(
            self.path("one.cb7"),
            [("a.jpg", read_bytes(REAL_JPEG)), ("ComicInfo.xml", COMIC_INFO)],
        )
        second = build_7z(
            self.path("two.cb7"),
            [("a.jpg", read_bytes(REAL_JPEG)), ("ComicInfo.xml", COMIC_INFO)],
        )
        self.assertEqual(read_bytes(first), read_bytes(second))

    def test_every_unencrypted_fixture_is_byte_stable(self):
        # `7z` embeds each entry's mtime, so this is what the pinned stamp buys:
        # a fixture regenerated tomorrow is the same file as today's. The
        # encrypted one is deliberately absent -- see below.
        for build in (rich_cb7, solid_cb7):
            with self.subTest(builder=build.__name__):
                first = build(self.path("first.cb7"))
                second = build(self.path("second.cb7"))
                self.assertEqual(read_bytes(first), read_bytes(second))

    def test_an_encrypted_fixture_cannot_be_byte_stable(self):
        # Not an oversight to fix: `7z`'s AES picks a random salt per archive, so
        # two encrypted fixtures built from identical input differ by design. The
        # test pins that rather than leaving it to be rediscovered, and asserts
        # the property the fixture is for.
        first = read_bytes(encrypted_cb7(self.path("e1.cb7")))
        second = read_bytes(encrypted_cb7(self.path("e2.cb7")))
        self.assertNotEqual(first, second)
        self.assertIn("Encrypted = +", sevenzip_listing(self.path("e1.cb7")))

    def test_the_solid_fixture_is_solid(self):
        listing = sevenzip_listing(solid_cb7(self.path("solid.cb7")))
        self.assertIn("Solid = +", listing)

    def test_the_encrypted_fixture_is_encrypted(self):
        listing = sevenzip_listing(encrypted_cb7(self.path("enc.cb7")))
        self.assertIn("Encrypted = +", listing)

    def test_the_rich_fixture_holds_its_entries_in_the_listings_order(self):
        source = rich_cb7(self.path("rich.cb7"))
        self.assertEqual(
            [
                "ComicInfo.xml",
                "__MACOSX/._page001.jpg",
                "extras/note.txt",
                "page001.jpg",
            ],
            sevenzip_entry_names(source),
        )


class SolidArchive(ArchiveTestCase):
    """A solid source converts byte-exact, which is why the reader stages one
    extraction: per-member extraction would decompress the block every time."""

    requires_7z = True

    def test_a_solid_archive_converts_with_its_entries_byte_exact(self):
        source = solid_cb7(self.path("solid.cb7"))
        # The premise, not just the fixture's name: without this the test would
        # pass against a plain archive and prove nothing about the solid case.
        self.assertIn("Solid = +", sevenzip_listing(source))

        report = Converter(self.cjxl).convert(source)
        out = destination_for(source)
        self.assertEqual(
            ["ComicInfo.xml", "page001.jpg", "page002.jpg"],
            sevenzip_entry_names(source),
        )
        self.assertEqual(3, report.total)
        self.assertEqual(2, report.converted)
        self.assertEqual(1, report.passed_through)

        written = contents(out)
        # The untouched entry is byte-identical, and the pages are in the
        # source's order: transcode changes the name, nothing changes position.
        self.assertEqual(COMIC_INFO, written["ComicInfo.xml"])
        self.assertEqual(
            ["ComicInfo.xml", "page001.jxl", "page002.jxl"], names_in_order(out)
        )
        # Each page is its own, not merely present: a read that handed back the
        # wrong member would keep the names and change the content.
        self.assertReconstructsTo(written["page001.jxl"], read_bytes(REAL_JPEG))
        self.assertReconstructsTo(written["page002.jxl"], read_bytes(REAL_JPEG_2))


class TruncatedSource(ArchiveTestCase):
    """A truncated CB7 leaves no output, exits non-zero, and does not stop the
    healthy inputs beside it in the same run."""

    requires_7z = True

    def truncate(self, name: str) -> str:
        source = rich_cb7(self.path(name))
        data = read_bytes(source)
        with open(source, "wb") as handle:
            handle.write(data[: len(data) // 2])
        return source

    def test_a_truncated_cb7_leaves_no_output_and_no_traceback(self):
        source = self.truncate("book.cb7")
        before = self.workdirs()
        code, _, err = self.capture([source])
        self.assertEqual(cli.EXIT_FAILED, code)
        self.assertFalse(os.path.exists(destination_for(source)))
        self.assertNotIn("Traceback", err)
        # `assertNoTempFiles` scans this case's own directory; the reader stages
        # under the system temp, so `workdirs` is what sees a leaked one.
        self.assertEqual(before, self.workdirs())

    def test_a_healthy_input_beside_a_truncated_one_still_converts(self):
        good = rich_cb7(self.path("good.cb7"))
        bad = self.truncate("bad.cb7")
        # The bad one first: with the good one first it would already be
        # converted by the time the failure hit, so a CLI that aborted on the
        # first failure would pass this test.
        code, _, err = self.capture([bad, good])
        # The run is non-zero because one path failed, but the other is still
        # work the owner asked for: it converts, and only the bad one is refused.
        self.assertEqual(cli.EXIT_FAILED, code)
        self.assertTrue(os.path.exists(destination_for(good)))
        self.assertFalse(os.path.exists(destination_for(bad)))
        self.assertIn("bad.cb7", err)


class EncryptedSource(ArchiveTestCase):
    """An encrypted archive is refused by name, and the run carries on."""

    requires_7z = True

    def test_an_encrypted_archive_is_refused_by_name(self):
        source = encrypted_cb7(self.path("enc.cb7"))
        code, _, err = self.capture([source])
        self.assertEqual(cli.EXIT_FAILED, code)
        self.assertFalse(os.path.exists(destination_for(source)))
        self.assertIn("encrypted", err.lower())
        self.assertNotIn("Traceback", err)
        # The point of the entry: not `7z`'s own unhelpful diagnostic.
        self.assertNotIn("Break signaled", err)

    def test_a_plain_input_beside_an_encrypted_one_still_converts(self):
        good = rich_cb7(self.path("good.cb7"))
        bad = encrypted_cb7(self.path("bad.cb7"))
        # The encrypted one first, so a run that stopped at the first failure
        # could not convert the good one.
        code, _, err = self.capture([bad, good])
        self.assertEqual(cli.EXIT_FAILED, code)
        self.assertTrue(os.path.exists(destination_for(good)))
        self.assertFalse(os.path.exists(destination_for(bad)))
        self.assertIn("encrypted", err.lower())

    def test_the_run_never_waits_for_input(self):
        # A live stdin pipe that is never written: the reader passes DEVNULL to
        # every `7z` call, so a reader that let `7z` prompt would block here
        # until the timeout rather than returning.
        source = encrypted_cb7(self.path("enc.cb7"))
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        completed = subprocess.run(
            [sys.executable, "-m", "cbx_jackal.cli", source],
            cwd=root,
            env=dict(os.environ, PYTHONPATH=root),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
        )
        self.assertNotEqual(0, completed.returncode)
        self.assertIn(b"encrypted", completed.stderr.lower())


class SevenZipPreflight(ArchiveTestCase):
    """`7z` absent refuses only the inputs that need it; the rest still convert."""

    def test_absent_7z_exits_two_naming_the_tool(self):
        source = self.path("book.cb7")
        with open(source, "wb") as handle:
            handle.write(b"irrelevant: the suffix decides")

        real_which = shutil.which
        shutil.which = lambda name, *a, **k: (
            None if name == "7z" else real_which(name, *a, **k)
        )
        self.addCleanup(setattr, shutil, "which", real_which)

        opened = []
        real_open = archive.open_source
        archive.open_source = lambda path: opened.append(path) or real_open(path)
        self.addCleanup(setattr, archive, "open_source", real_open)

        code, out, err = self.capture([source])

        self.assertEqual(cli.EXIT_ENVIRONMENT, code)
        self.assertIn("7z", err)
        self.assertNotIn("Traceback", err)
        self.assertEqual([], opened, "an archive was opened without 7z")
        self.assertFalse(os.path.exists(destination_for(source)))

    def _hide_7z(self) -> list:
        """Hide `7z` and record every tool name looked up while it is hidden."""
        real_which = shutil.which
        queried = []

        def which(name, *args, **kwargs):
            queried.append(name)
            if name == "7z":
                return None
            return real_which(name, *args, **kwargs)

        shutil.which = which
        self.addCleanup(setattr, shutil, "which", real_which)
        return queried

    def _spy_open(self) -> list:
        """Record every archive path the converter is asked to open."""
        opened = []
        real_open = archive.open_source
        archive.open_source = lambda path: opened.append(path) or real_open(path)
        self.addCleanup(setattr, archive, "open_source", real_open)
        return opened

    def test_a_cb7_beside_a_cbz_converts_the_cbz_and_refuses_the_cb7(self):
        # The whole point of the input-driven severity: a library holding one
        # CB7 beside forty CBZs must not convert nothing. Only the CB7 is
        # refused, the CBZ still converts, and the run exits 2.
        cbz = self.make_archive(self.tmp, "book.cbz")
        cb7 = self.path("annual.cb7")
        with open(cb7, "wb") as handle:
            handle.write(b"irrelevant: the suffix decides")

        self._hide_7z()
        opened = self._spy_open()

        code, out, err = self.capture([cbz, cb7])

        self.assertEqual(cli.EXIT_ENVIRONMENT, code)
        self.assertEqual(1, err.count("7z was not found on PATH"), err)
        self.assertNotIn("Traceback", err)
        self.assertTrue(os.path.exists(destination_for(cbz)))
        self.assertFalse(os.path.exists(destination_for(cb7)))
        self.assertEqual([cbz], opened, "only the CBZ may be opened")
        self.assertIn(cb7, err)

    def test_an_all_cbz_list_never_looks_for_7z(self):
        # The counterpart: a run with no non-ZIP input never needs the tool, so
        # it must not check for it at all -- a lookup here would be a promise to
        # a user with no CB7s that their run depends on an archiver it does not.
        first = self.make_archive(self.tmp, "one.cbz")
        second = self.make_archive(self.tmp, "two.cbz")
        queried = self._hide_7z()

        code, out, err = self.capture([first, second])

        self.assertEqual(0, code, err)
        self.assertNotIn("7z", queried)
        self.assertTrue(os.path.exists(destination_for(first)))
        self.assertTrue(os.path.exists(destination_for(second)))


class MissingDependency(ArchiveTestCase):
    """CAP-5: exit before opening any archive, naming the tool."""

    requires_cjxl = False

    def test_message_names_the_tool(self):
        message = preflight.missing_message([preflight.TOOLS[preflight.TOOL]])
        self.assertIn("cjxl", message)

    def test_message_points_at_documentation(self):
        message = preflight.missing_message([preflight.TOOLS[preflight.TOOL]])
        self.assertIn("README.md", message)

    def test_message_covers_all_three_platforms(self):
        message = preflight.missing_message([preflight.TOOLS[preflight.TOOL]]).lower()
        for platform in ("linux", "mac", "windows"):
            with self.subTest(platform=platform):
                self.assertIn(platform, message)

    def test_message_is_platform_neutral(self):
        # No "command not found", no shell jargon, no traceback.
        message = preflight.missing_message([preflight.TOOLS[preflight.TOOL]])
        self.assertNotIn("Traceback", message)
        self.assertNotIn("command not found", message.lower())

    def test_find_tool_reports_the_resolved_path_when_present(self):
        if shutil.which("cjxl") is None:
            self.skipTest("cjxl is not on PATH")
        resolved = preflight.find_tool(preflight.TOOL)
        self.assertIsNotNone(resolved)
        self.assertTrue(os.path.exists(self.require(resolved, "resolved path")))

    def test_find_tool_reports_none_when_absent(self):
        resolved = preflight.find_tool("definitely-not-a-real-tool-xyz")
        self.assertIsNone(resolved)

    def test_cli_exits_non_zero_and_names_the_tool(self):
        from contextlib import redirect_stderr, redirect_stdout

        source = self.sample()
        real_which = shutil.which
        shutil.which = lambda name, *a, **k: None if name == "cjxl" else real_which(
            name, *a, **k
        )
        self.addCleanup(setattr, shutil, "which", real_which)

        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main([source])
        self.assertNotEqual(0, code)
        self.assertIn("cjxl", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        # And it never opened the archive: no output was produced.
        self.assertFalse(os.path.exists(destination_for(source)))

    def test_the_preflight_runs_before_a_directory_is_even_scanned(self):
        # CAP-5 said "before reading any archive"; a scan reads a directory
        # full of them, so this is where that promise is actually at risk.
        # Asserting only on the absence of output is not enough: expansion
        # prints nothing when a directory holds archives, so moving the call
        # above the preflight would leave the rest of the suite green.
        lib = self.make_dir("lib")
        for index in range(10):
            self.make_archive(lib, f"issue{index:02d}.cbz")

        real_which = shutil.which
        shutil.which = lambda name, *a, **k: None if name == "cjxl" else real_which(
            name, *a, **k
        )
        self.addCleanup(setattr, shutil, "which", real_which)

        scanned = []
        real_expand = discover.expand

        def spy(paths, recursive=False):
            scanned.append(list(paths))
            return real_expand(paths, recursive=recursive)

        discover.expand = spy
        self.addCleanup(setattr, discover, "expand", real_expand)

        code, out, err = self.capture([lib])

        self.assertEqual(cli.EXIT_ENVIRONMENT, code)
        self.assertEqual([], scanned, "the directory was scanned before the preflight")
        self.assertEqual(1, err.count("cjxl was not found on PATH"), err)
        self.assertEqual("", out)
        self.assertNoTempFiles(lib)
        for index in range(10):
            self.assertFalse(
                os.path.exists(os.path.join(lib, f"issue{index:02d}.jxl.cbz"))
            )

    def test_both_tools_absent_names_only_cjxl(self):
        # The run stops before expansion, so `7z` is not yet known to be needed
        # and must not be named: naming it would promise a check that never ran.
        cb7 = self.path("book.cb7")
        with open(cb7, "wb") as handle:
            handle.write(b"irrelevant: the suffix decides")

        real_which = shutil.which
        shutil.which = lambda name, *a, **k: (
            None if name in ("cjxl", "7z") else real_which(name, *a, **k)
        )
        self.addCleanup(setattr, shutil, "which", real_which)

        code, out, err = self.capture([cb7])

        self.assertEqual(cli.EXIT_ENVIRONMENT, code)
        self.assertIn("cjxl", err)
        self.assertNotIn("7z", err)
        self.assertFalse(os.path.exists(destination_for(cb7)))


class CliSurface(ArchiveTestCase):
    """Exit codes, and the flags the plan requires."""

    def test_clean_run_exits_zero(self):
        self.assertEqual(0, cli.main([self.sample()]))

    def test_multiple_paths_are_all_processed(self):
        first = build_zip(self.path("one.cbz"), [("a.jpg", read_bytes(REAL_JPEG))])
        second = build_zip(self.path("two.cbz"), [("a.jpg", read_bytes(REAL_JPEG_2))])
        self.assertEqual(0, cli.main([first, second]))
        self.assertTrue(os.path.exists(destination_for(first)))
        self.assertTrue(os.path.exists(destination_for(second)))

    def test_one_bad_archive_makes_the_whole_run_non_zero(self):
        good = build_zip(self.path("g.cbz"), [("a.jpg", read_bytes(REAL_JPEG))])
        bad = self.path("bad3.cbz")
        with open(bad, "wb") as handle:
            handle.write(b"not a zip")
        self.assertEqual(cli.EXIT_FAILED, cli.main([good, bad]))
        self.assertTrue(os.path.exists(destination_for(good)))

    def test_dry_run_flag_writes_nothing(self):
        source = self.sample()
        self.assertEqual(0, cli.main([source, "--dry-run"]))
        self.assertFalse(os.path.exists(destination_for(source)))

    def test_force_flag_overwrites(self):
        source = self.sample()
        self.assertEqual(0, cli.main([source]))
        self.assertEqual(0, cli.main([source, "--force"]))

    def test_quality_flag_is_accepted(self):
        self.assertEqual(0, cli.main([self.sample(), "--quality", "70"]))

    def test_strict_flag_passes_a_clean_run(self):
        self.assertEqual(0, cli.main([self.sample(), "--strict"]))

    def test_strict_flag_reports_a_corrupt_page(self):
        source = build_zip(
            self.path("sc.cbz"),
            [("a.jpg", read_bytes(REAL_JPEG)), ("b.jpg", read_bytes(CORRUPT_JPEG))],
        )
        self.assertEqual(cli.EXIT_FAILED, cli.main([source, "--strict"]))
        self.assertFalse(os.path.exists(destination_for(source)))

    def test_out_of_range_quality_is_a_usage_error(self):
        with self.assertRaises(SystemExit):
            cli.main([self.sample(), "--quality", "0"])
        with self.assertRaises(SystemExit):
            cli.main([self.sample(), "--quality", "101"])

    def test_parser_exposes_every_documented_flag(self):
        parser = cli.build_parser()
        options = {
            option
            for action in parser._actions
            for option in action.option_strings
        }
        for flag in (
            "--quality",
            "--format",
            "--strict",
            "--dry-run",
            "--force",
            "--recursive",
        ):
            with self.subTest(flag=flag):
                self.assertIn(flag, options)

    def test_the_format_flag_matches_the_run_without_it_byte_for_byte(self):
        # Row 2 of the matrix, and the reason the flag is threaded as a default:
        # --format jxl has to be the flagless run, not merely an equivalent one.
        # Two directories, so neither run has to force over the other.
        without = self.make_dir("without")
        flagged = self.make_dir("flagged")
        plain = self.make_archive(without, "book.cbz")
        explicit = self.make_archive(flagged, "book.cbz")

        code, _, err = self.capture([plain])
        self.assertEqual(0, code, err)
        code, _, err = self.capture([explicit, "--format", "jxl"])
        self.assertEqual(0, code, err)

        self.assertEqual(
            read_bytes(os.path.join(without, "book.jxl.cbz")),
            read_bytes(os.path.join(flagged, "book.jxl.cbz")),
        )

    def test_the_parsed_format_reaches_the_converter(self):
        # `jxl` is both the default and the only legal value, so the bytes on
        # disk cannot tell a threaded --format from an ignored one. The call
        # can: the parsed value has to arrive as `page_format` rather than
        # falling back to a constructor default that happens to hold the same
        # string today and would not when a second format lands.
        recorded = {}
        real_converter = cli.Converter

        class RecordingConverter(real_converter):
            def __init__(self, *args, **kwargs):
                recorded.update(kwargs)
                super().__init__(*args, **kwargs)

        cli.Converter = RecordingConverter
        self.addCleanup(setattr, cli, "Converter", real_converter)

        code, _, err = self.capture(
            [self.make_archive(self.tmp, "book.cbz"), "--format", "jxl"]
        )

        self.assertEqual(0, code, err)
        self.assertIn("page_format", recorded, "--format never reached the Converter")
        self.assertEqual("jxl", recorded["page_format"])

    def test_a_zip_input_with_the_flag_is_still_a_jxl_cbz(self):
        self.make_archive(self.tmp, "book.zip")

        code, _, err = self.capture([self.tmp, "--format", "jxl"])

        self.assertEqual(0, code, err)
        self.assertTrue(os.path.exists(self.path("book.jxl.cbz")))
        self.assertFalse(os.path.exists(self.path("book.jxl.zip")))

    def test_an_unsupported_format_is_a_usage_error_that_writes_nothing(self):
        source = self.make_archive(self.tmp, "book.cbz")
        from contextlib import redirect_stderr

        captured = io.StringIO()
        with redirect_stderr(captured):
            with self.assertRaises(SystemExit) as caught:
                cli.main([source, "--format", "webp"])

        message = captured.getvalue()
        self.assertEqual(cli.EXIT_ENVIRONMENT, caught.exception.code)
        self.assertIn("webp", message)
        self.assertIn("unsupported", message)
        self.assertNotIn("Traceback", message)
        self.assertEqual(["book.cbz"], os.listdir(self.tmp))
        self.assertNoTempFiles()

    def test_a_case_variant_of_the_format_is_accepted_and_normalised(self):
        # Case-insensitive the way every suffix table in the tool is, and the
        # name comes out in the declared spelling either way.
        code, out, err = self.capture(
            [self.make_archive(self.tmp, "book.cbz"), "--format", "JXL"]
        )

        self.assertEqual(0, code, err)
        self.assertTrue(os.path.exists(self.path("book.jxl.cbz")))
        self.assertFalse(os.path.exists(self.path("book.JXL.cbz")))
        self.assertIn("book.cbz -> ", out)

    def test_an_unsupported_format_message_names_an_empty_value(self):
        from contextlib import redirect_stderr

        captured = io.StringIO()
        with redirect_stderr(captured):
            with self.assertRaises(SystemExit):
                cli.main([self.make_archive(self.tmp, "book.cbz"), "--format", ""])

        # Rendered, so the message still reads as a value rather than as
        # `unsupported --format ;`.
        self.assertIn("unsupported --format ''", captured.getvalue())

    def test_the_format_is_checked_before_the_preflight(self):
        # cjxl is off PATH here, so a message about `webp` at all is the proof:
        # the other order exits 2 as well, naming the tool instead.
        source = self.make_archive(self.tmp, "book.cbz")
        real_which = shutil.which
        shutil.which = lambda name, *a, **k: None if name == "cjxl" else real_which(
            name, *a, **k
        )
        self.addCleanup(setattr, shutil, "which", real_which)
        from contextlib import redirect_stderr

        captured = io.StringIO()
        with redirect_stderr(captured):
            with self.assertRaises(SystemExit) as caught:
                cli.main([source, "--format", "webp"])

        message = captured.getvalue()
        self.assertEqual(cli.EXIT_ENVIRONMENT, caught.exception.code)
        self.assertIn("webp", message)
        self.assertNotIn("cjxl", message)
        self.assertEqual(["book.cbz"], os.listdir(self.tmp))


class MisnamedEntry(ArchiveTestCase):
    """A `.jpg` holding non-JPEG bytes is refused rather than transcoded.

    `cjxl` sniffs content and would encode a PNG under a `.jxl` name without
    complaint, so the check is ours. Absence of the JPEG SOI marker proves only
    that the entry is not a JPEG; the report says that and nothing more.
    """

    def test_mislabelled_entry_is_not_converted(self):
        source = build_zip(
            self.path("mis.cbz"),
            [
                ("page.jpg", read_bytes(MISNAMED_PNG)),
                ("real.jpg", read_bytes(REAL_JPEG)),
            ],
        )
        report = Converter(self.cjxl).convert(source)
        self.assertFalse(report.ok)
        self.assertEqual(["page.jpg: not a JPEG"], report.failure_lines())
        out = contents(destination_for(source))
        self.assertNotIn("page.jxl", out)
        self.assertEqual(read_bytes(MISNAMED_PNG), out["page.jpg"])
        self.assertIn("real.jxl", out)

    def test_the_real_page_still_converts_alongside_it(self):
        source = build_zip(
            self.path("mix.cbz"),
            [
                ("page.jpg", read_bytes(MISNAMED_PNG)),
                ("real.jpg", read_bytes(REAL_JPEG)),
            ],
        )
        Converter(self.cjxl).convert(source)
        out = contents(destination_for(source))
        self.assertReconstructsTo(out["real.jxl"], read_bytes(REAL_JPEG))

    def test_a_dry_run_predicts_the_same_failure(self):
        source = build_zip(
            self.path("dry.cbz"),
            [
                ("page.jpg", read_bytes(MISNAMED_PNG)),
                ("real.jpg", read_bytes(REAL_JPEG)),
            ],
        )
        report = Converter(self.cjxl).convert(source, dry_run=True)
        self.assertFalse(report.ok)
        self.assertEqual(["page.jpg: not a JPEG"], report.failure_lines())

class ShippedFixture(ArchiveTestCase):
    """End-to-end over the committed tests/fixtures/sample.cbz."""

    @property
    def fixture(self) -> str:
        return os.path.join(FIXTURES, "sample.cbz")

    def setUp(self):
        super().setUp()
        self.work = build_zip(self.path("sample.cbz"), [])
        # Copy so the committed fixture is never written to.
        shutil.copyfile(self.fixture, self.work)

    def test_fixture_exists_and_has_jpeg_pages(self):
        self.assertTrue(os.path.exists(os.path.join(FIXTURES, "sample.cbz")))
        self.assertTrue(any(n.endswith(".jpg") for n in names_in_order(self.work)))

    def test_converts_and_shrinks(self):
        report = Converter(self.cjxl).convert(self.work)
        self.assertCleanReport(report)
        self.assertEqual(3, report.converted)
        self.assertLess(
            os.path.getsize(destination_for(self.work)), os.path.getsize(self.work)
        )

    def test_every_page_round_trips(self):
        source = contents(self.work)
        Converter(self.cjxl).convert(self.work)
        for name, data in contents(destination_for(self.work)).items():
            if name.endswith(".jxl"):
                self.assertReconstructsTo(data, source[name[:-4] + ".jpg"])

    def test_entry_order_survives(self):
        before = [classify(n).output_name for n in names_in_order(self.work)]
        Converter(self.cjxl).convert(self.work)
        self.assertEqual(before, names_in_order(destination_for(self.work)))

    def test_cli_writes_jxl_cbz_beside_the_input(self):
        self.assertEqual(0, cli.main([self.work]))
        self.assertTrue(os.path.exists(self.path("sample.jxl.cbz")))


class OutputPermissions(ArchiveTestCase):
    """The published file is an ordinary user file, not a private temp file."""

    def test_output_is_not_created_private(self):
        # NamedTemporaryFile would hand us 0600; the output must be readable.
        source = self.sample()
        Converter(self.cjxl).convert(source)
        mode = os.stat(destination_for(source)).st_mode & 0o777
        self.assertNotEqual(0o600, mode)
        self.assertTrue(mode & 0o400, "owner should be able to read the output")


class DegenerateArchives(ArchiveTestCase):
    """Edge-shaped archives that real libraries contain."""

    def test_empty_archive_yields_an_empty_archive(self):
        source = build_zip(self.path("e.cbz"), [])
        report = Converter(self.cjxl).convert(source)
        self.assertCleanReport(report)
        self.assertEqual([], names_in_order(destination_for(source)))

    def test_metadata_only_archive_converts_nothing_and_succeeds(self):
        source = build_zip(
            self.path("mo.cbz"), [("ComicInfo.xml", COMIC_INFO), ("readme.txt", README)]
        )
        report = Converter(self.cjxl).convert(source)
        self.assertCleanReport(report)
        self.assertEqual(0, report.converted)
        self.assertEqual(2, report.passed_through)
        out = contents(destination_for(source))
        self.assertEqual(COMIC_INFO, out["ComicInfo.xml"])
        self.assertEqual(README, out["readme.txt"])

    def test_zero_byte_jpeg_entry_is_reported_not_dropped(self):
        source = build_zip(
            self.path("z.cbz"),
            [("empty.jpg", b""), ("ok.jpg", read_bytes(REAL_JPEG))],
        )
        report = Converter(self.cjxl).convert(source)
        self.assertEqual(1, report.converted)
        self.assertEqual(1, report.not_converted)
        out = contents(destination_for(source))
        self.assertIn("empty.jpg", out)
        self.assertEqual(b"", out["empty.jpg"])
        self.assertIn("ok.jxl", out)

    def test_garbage_jpeg_entry_is_reported_not_dropped(self):
        source = build_zip(
            self.path("g.cbz"), [("junk.jpg", b"\x00\x01\x02not an image at all")]
        )
        report = Converter(self.cjxl).convert(source)
        self.assertEqual(1, report.not_converted)
        self.assertEqual(b"\x00\x01\x02not an image at all",
                         contents(destination_for(source))["junk.jpg"])

    def test_unicode_entry_names_survive(self):
        source = build_zip(
            self.path("u.cbz"),
            [("ページ001.jpg", read_bytes(REAL_JPEG)), ("第一章.txt", README)],
        )
        report = Converter(self.cjxl).convert(source)
        self.assertCleanReport(report)
        self.assertEqual(
            ["ページ001.jxl", "第一章.txt"],
            names_in_order(destination_for(source)),
        )

    def test_entry_timestamp_survives(self):
        stamp = (2019, 5, 6, 7, 8, 10)
        source = build_zip(
            self.path("t.cbz"),
            [("a.jpg", read_bytes(REAL_JPEG)), ("b.txt", README)],
            date_time=stamp,
        )
        with zipfile.ZipFile(source) as before:
            self.assertEqual(stamp, before.getinfo("a.jpg").date_time)
        Converter(self.cjxl).convert(source)
        with zipfile.ZipFile(destination_for(source)) as out:
            self.assertEqual(stamp, out.getinfo("a.jxl").date_time)
            self.assertEqual(stamp, out.getinfo("b.txt").date_time)


class FilesystemErrors(ArchiveTestCase):
    """Filesystem trouble is reported as filesystem trouble, not as corruption."""

    @unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() != 0, "needs non-root")
    def test_unwritable_directory_is_reported_as_a_write_problem(self):
        directory = self.path("locked")
        os.makedirs(directory)
        source = build_zip(
            os.path.join(directory, "a.cbz"), [("a.jpg", read_bytes(REAL_JPEG))]
        )
        destination = os.path.join(directory, "a.jxl.cbz")
        os.chmod(directory, 0o500)
        self.addCleanup(os.chmod, directory, 0o700)

        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        message = str(caught.exception)
        self.assertIn("cannot write", message)
        self.assertNotIn("cannot read", message)
        self.assertFalse(os.path.exists(destination))

    @unittest.skipUnless(hasattr(os, "geteuid") and os.geteuid() != 0, "needs non-root")
    def test_unreadable_archive_is_reported_as_a_read_problem(self):
        source = self._make_unreadable(self.path("locked.cbz"))
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        self.assertIn("cannot read", str(caught.exception))

    def _make_unreadable(self, path: str) -> str:
        build_zip(path, [("a.jpg", read_bytes(REAL_JPEG))])
        os.chmod(path, 0o000)
        self.addCleanup(os.chmod, path, 0o600)
        return path


class OutputNameCollision(ArchiveTestCase):
    """Two entries claiming one output name must abort, not shadow each other.

    A ZIP permits duplicate member names; `zipfile` resolves a read to the last
    one. So writing both `page001.jpg` -> `page001.jxl` alongside an existing
    `page001.jxl` would leave a converted page unreachable inside an archive
    that reports success. Renaming is forbidden by the spec, so the only safe
    answer is to refuse the archive.
    """

    def _colliding(self, name: str = "collide.cbz") -> str:
        return build_zip(
            self.path(name),
            [
                ("page001.jpg", read_bytes(REAL_JPEG)),
                ("page001.jxl", read_bytes(REAL_JPEG)),
            ],
        )

    def test_case_differing_existing_jxl_aborts(self):
        """`page.jpg` -> `page.jxl` beside an existing `page.JXL`.

        Distinct strings, but ZIP readers on macOS and Windows resolve member
        names case-insensitively, so the converted page would shadow or be
        shadowed while the run reported success.
        """
        source = build_zip(
            self.path("case.cbz"),
            [
                ("page001.jpg", read_bytes(REAL_JPEG)),
                ("page001.JXL", read_bytes(REAL_JPEG)),
            ],
        )
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        message = str(caught.exception)
        self.assertIn("collision", message)
        self.assertIn("page001.jpg", message)
        self.assertIn("page001.JXL", message)

    def test_nfd_and_nfc_names_abort(self):
        """Archives built on macOS can carry NFD-normalised names.

        Two entries whose names differ only by normalisation form collide once
        a reader normalises them, so the check has to as well.
        """
        nfc_name = "page\u00e9.jpg"
        nfd_name = unicodedata.normalize("NFD", nfc_name)
        if nfd_name == nfc_name:
            self.skipTest("platform normalises the name to a single form")
        # The two names differ ONLY by normalisation form, so the collision is
        # normalisation's doing alone -- casefolding plays no part in it.
        source = build_zip(
            self.path("nfd.cbz"),
            [
                (nfc_name, read_bytes(REAL_JPEG)),
                (nfd_name, read_bytes(REAL_JPEG)),
            ],
        )
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        self.assertIn("collision", str(caught.exception))

    def test_distinct_names_still_convert(self):
        """Folding must not refuse archives that genuinely do not collide."""
        source = build_zip(
            self.path("distinct.cbz"),
            [
                ("page001.jpg", read_bytes(REAL_JPEG)),
                ("page002.JPEG", read_bytes(REAL_JPEG)),
                ("notes.txt", b"hello"),
            ],
        )
        report = Converter(self.cjxl).convert(source)
        self.assertEqual(report.converted, 2)
        self.assertEqual(report.not_converted, 0)

    def test_collision_aborts_the_run(self):
        source = self._colliding()
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        self.assertIn("collision", str(caught.exception))

    def test_collision_names_both_entries(self):
        source = self._colliding()
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        message = str(caught.exception)
        self.assertIn("page001.jpg", message)
        self.assertIn("page001.jxl", message)

    def test_collision_writes_no_output_at_all(self):
        source = self._colliding()
        with self.assertRaises(ArchiveError):
            Converter(self.cjxl).convert(source)
        self.assertFalse(os.path.exists(destination_for(source)))
        self.assertNoTempFiles()

    def test_collision_exits_non_zero(self):
        self.assertEqual(cli.EXIT_FAILED, cli.main([self._colliding()]))

    def test_collision_leaves_the_input_untouched(self):
        source = self._colliding()
        before = names_in_order(source)
        with self.assertRaises(ArchiveError):
            Converter(self.cjxl).convert(source)
        self.assertEqual(before, names_in_order(source))

    def test_collision_is_detected_before_any_writing(self):
        # No archive is opened for output at all, so the check cannot be too
        # late to matter.
        source = self._colliding()
        with self.assertRaises(ArchiveError):
            Converter(self.cjxl).convert(source)
        self.assertNoTempFiles()

    def test_collision_check_is_conservative_and_runs_up_front(self):
        # Whether a page converts is not known until cjxl has run, so the check
        # is on the plan, not the outcome: the archive is refused even in the
        # case where the page would have failed and kept its .jpg name. Refusing
        # one archive that might have been fine beats writing a book with a hole
        # in it and calling it success.
        with self.assertRaises(ArchiveError):
            build_plan(["page001.jpg", "page001.jxl"])

    def test_a_distinct_stem_does_not_collide(self):
        source = build_zip(
            self.path("distinct.cbz"),
            [
                ("page001.jpg", read_bytes(REAL_JPEG)),
                ("page002.jpg", read_bytes(REAL_JPEG_2)),
            ],
        )
        report = Converter(self.cjxl).convert(source)
        self.assertCleanReport(report)
        self.assertEqual(
            ["page001.jxl", "page002.jxl"], names_in_order(destination_for(source))
        )

    def test_contents_helper_flags_duplicate_members(self):
        # The reason the collision bug escaped the suite: a dict keyed by name
        # hides the duplicate. The helper must object.
        source = self._colliding()
        with zipfile.ZipFile(source, "a") as archive:
            archive.writestr("page001.jpg", read_bytes(REAL_JPEG_2))
        self.assertEqual(
            3, len(names_in_order(source)), "three members, two of them named alike"
        )
        with self.assertRaises(AssertionError):
            contents(source)


class ReportedSizes(ArchiveTestCase):
    """The size line must describe the files on disk, not payload sums.

    Entry payload bytes exclude ZIP framing and ignore whatever compression the
    *source* used, so summing them could claim a large saving on a deflated
    archive whose published file barely shrank -- or hide an archive that grew.
    """

    def test_stored_source_matches_the_file_on_disk(self):
        source = self.sample()
        report = Converter(self.cjxl).convert(source)
        destination = destination_for(source)
        self.assertEqual(os.path.getsize(source), report.source_size_bytes)
        self.assertEqual(os.path.getsize(destination), report.output_size_bytes)
        self.assertIn(str(os.path.getsize(destination)), self.require(report.size_line(), "size_line"))

    def test_deflated_source_is_compared_like_for_like(self):
        # Deflating the JXL pages on disk leaves the output effectively the same
        # size, so the reported percentage must follow the file, not the payload.
        source = build_zip(
            self.path("deflate.cbz"),
            [("page001.jpg", read_bytes(REAL_JPEG))],
            compress_type=zipfile.ZIP_DEFLATED,
        )
        report = Converter(self.cjxl).convert(source)
        destination = destination_for(source)
        before = os.path.getsize(source)
        expected = abs(before - os.path.getsize(destination)) / before * 100.0
        self.assertIn(f"{expected:.1f}%", self.require(report.size_line(), "size_line"))

    def test_a_grown_archive_is_reported_as_larger(self):
        # Zeros deflate to almost nothing and are written back STORED, so the
        # published file is far bigger than the source. A payload-sum figure
        # would show 0% here and quietly hide the growth.
        source = build_zip(
            self.path("zeros.cbz"),
            [("blank.jpg", b"\x00" * 8192)],
            compress_type=zipfile.ZIP_DEFLATED,
        )
        report = Converter(self.cjxl).convert(source)
        destination = destination_for(source)
        self.assertGreater(
            os.path.getsize(destination),
            os.path.getsize(source),
            "this fixture is meant to grow once written STORED",
        )
        self.assertIn("larger", self.require(report.size_line(), "size_line"))
        self.assertNotIn("smaller", self.require(report.size_line(), "size_line"))

    def test_dry_run_does_not_pass_an_estimate_off_as_a_measurement(self):
        report = Converter(self.cjxl).convert(self.sample(), dry_run=True)
        self.assertIsNone(report.output_size_bytes)
        self.assertIn("entry data only", self.require(report.size_line(), "size_line"))


class AbortPathReporting(ArchiveTestCase):
    """An abort still has to name the pages that failed. CAP-4."""

    def _with_corrupt_page(self, name: str = "ac.cbz") -> str:
        return build_zip(
            self.path(name),
            [
                ("page001.jpg", read_bytes(REAL_JPEG)),
                ("page002.jpg", read_bytes(CORRUPT_JPEG)),
            ],
        )

    def test_strict_abort_carries_the_report(self):
        source = self._with_corrupt_page()
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl, strict=True).convert(source)
        report = caught.exception.report
        self.assertIsNotNone(report)
        self.assertEqual(1, self.require(report, "report").not_converted)

    def test_strict_names_the_failed_page_on_the_abort_path(self):
        from contextlib import redirect_stderr

        source = self._with_corrupt_page()
        captured = io.StringIO()
        with redirect_stderr(captured):
            code = cli.main([source, "--strict"])
        self.assertEqual(cli.EXIT_FAILED, code)
        self.assertIn("page002.jpg", captured.getvalue())

    def test_strict_abort_still_prints_the_summary(self):
        from contextlib import redirect_stderr

        source = self._with_corrupt_page()
        captured = io.StringIO()
        with redirect_stderr(captured):
            cli.main([source, "--strict"])
        self.assertIn("converted", captured.getvalue())

    def test_unreadable_archive_still_gets_a_bare_message(self):
        # No entries were ever seen, so there is no report to render.
        from contextlib import redirect_stderr

        bad = self.path("nope.zip")
        with open(bad, "wb") as handle:
            handle.write(b"not a zip")
        captured = io.StringIO()
        with redirect_stderr(captured):
            code = cli.main([bad])
        self.assertEqual(cli.EXIT_FAILED, code)
        self.assertIn("cbx-jackal:", captured.getvalue())


class UnsupportedMembers(ArchiveTestCase):
    """An encrypted or undecodable member is a clean error, not a traceback.

    `ZipFile.open` raises RuntimeError for an encrypted member and
    NotImplementedError for a compression method it cannot decode. Both mean the
    same thing here -- this archive cannot be rewritten -- so both must arrive
    as an `ArchiveError`.
    """

    @staticmethod
    def _patch_headers(path: str, signature: bytes, offset: int, mutate) -> str:
        with open(path, "rb") as handle:
            raw = bytearray(handle.read())
        cursor = 0
        while True:
            found = raw.find(signature, cursor)
            if found < 0:
                break
            mutate(raw, found + offset)
            cursor = found + 4
        with open(path, "wb") as handle:
            handle.write(bytes(raw))
        return path

    def _as_encrypted(self, path: str) -> str:
        """Set the general-purpose 'encrypted' bit on local and central headers.

        `zipfile` refuses to read a member flagged this way, which is exactly the
        RuntimeError path being tested -- no `zip` binary required.
        """
        for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
            self._patch_headers(
                path, signature, offset, lambda raw, i: raw.__setitem__(i, raw[i] | 1)
            )
        return path

    def test_encrypted_member_is_an_archive_error(self):
        source = self._as_encrypted(self.sample())
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        self.assertIn("encrypted", str(caught.exception))

    def test_encrypted_member_writes_no_output(self):
        source = self._as_encrypted(self.sample())
        with self.assertRaises(ArchiveError):
            Converter(self.cjxl).convert(source)
        self.assertFalse(os.path.exists(destination_for(source)))
        self.assertNoTempFiles()

    def test_encrypted_member_exits_non_zero_without_a_traceback(self):
        from contextlib import redirect_stderr

        source = self._as_encrypted(self.sample())
        captured = io.StringIO()
        with redirect_stderr(captured):
            code = cli.main([source])
        self.assertEqual(cli.EXIT_FAILED, code)
        self.assertNotIn("Traceback", captured.getvalue())

    def _as_unsupported_compression(self, path: str) -> str:
        """Claim a compression method no decoder implements (method 99)."""
        for signature, offset in ((b"PK\x03\x04", 8), (b"PK\x01\x02", 10)):
            self._patch_headers(
                path,
                signature,
                offset,
                lambda raw, i: raw.__setitem__(
                    slice(i, i + 2), (99).to_bytes(2, "little")
                ),
            )
        return path

    def test_unsupported_compression_is_an_archive_error(self):
        source = self._as_unsupported_compression(
            build_zip(self.path("weird.cbz"), [("a.jpg", read_bytes(REAL_JPEG))])
        )
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        self.assertIn("a.jpg", str(caught.exception))

    def test_unsupported_compression_writes_no_output(self):
        source = self._as_unsupported_compression(
            build_zip(self.path("weird2.cbz"), [("a.jpg", read_bytes(REAL_JPEG))])
        )
        with self.assertRaises(ArchiveError):
            Converter(self.cjxl).convert(source)
        self.assertFalse(os.path.exists(destination_for(source)))
        self.assertNoTempFiles()


class DryRunParity(ArchiveTestCase):
    """A dry run must reach the same verdict as the real run."""

    def _corrupt_payload(self, path: str, entry_index: int = 1) -> str:
        with open(path, "rb") as handle:
            raw = bytearray(handle.read())
        offsets = []
        cursor = 0
        while True:
            found = raw.find(b"PK\x03\x04", cursor)
            if found < 0:
                break
            offsets.append(found)
            cursor = found + 4
        header = offsets[entry_index]
        name_length = int.from_bytes(raw[header + 26 : header + 28], "little")
        extra_length = int.from_bytes(raw[header + 28 : header + 30], "little")
        start = header + 30 + name_length + extra_length
        raw[start + 50] ^= 0xFF
        with open(path, "wb") as handle:
            handle.write(bytes(raw))
        return path

    def _bad_crc_archive(self, name: str = "parity.cbz") -> str:
        return self._corrupt_payload(
            build_zip(
                self.path(name),
                [
                    ("page001.jpg", read_bytes(REAL_JPEG)),
                    ("readme.txt", README * 400),
                ],
            )
        )

    def test_real_run_aborts_on_a_bad_crc_pass_through(self):
        source = self._bad_crc_archive("parity.cbz")
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source)
        self.assertIn("CRC-32", str(caught.exception))

    def test_dry_run_reaches_the_same_verdict(self):
        # The pass-through entry is never written on a dry run, so reading it is
        # the only way the preview can notice a bad CRC. Skipping it made the
        # dry run promise success for a run that then failed.
        source = self._bad_crc_archive("parity2.cbz")
        with self.assertRaises(ArchiveError) as caught:
            Converter(self.cjxl).convert(source, dry_run=True)
        self.assertIn("CRC-32", str(caught.exception))

    def test_dry_run_writes_nothing_when_it_aborts(self):
        source = self._bad_crc_archive("parity3.cbz")
        with self.assertRaises(ArchiveError):
            Converter(self.cjxl).convert(source, dry_run=True)
        self.assertFalse(os.path.exists(destination_for(source)))

    def test_a_clean_archive_still_dry_runs(self):
        source = build_zip(
            self.path("clean.cbz"),
            [("page001.jpg", read_bytes(REAL_JPEG)), ("readme.txt", README)],
        )
        report = Converter(self.cjxl).convert(source, dry_run=True)
        self.assertCleanReport(report)
        self.assertEqual(1, report.converted)
        self.assertEqual(1, report.passed_through)


class MultiplePaths(ArchiveTestCase):
    """One refusal must not abandon the rest of the list."""

    def test_output_exists_does_not_stop_the_remaining_paths(self):
        already = build_zip(
            self.path("one.cbz"), [("a.jpg", read_bytes(REAL_JPEG))]
        )
        fresh = build_zip(
            self.path("two.cbz"), [("b.jpg", read_bytes(REAL_JPEG_2))]
        )
        self.assertEqual(0, cli.main([already]))
        self.assertTrue(os.path.exists(destination_for(already)))

        from contextlib import redirect_stderr

        captured = io.StringIO()
        with redirect_stderr(captured):
            code = cli.main([already, fresh])

        self.assertEqual(cli.EXIT_ENVIRONMENT, code)
        self.assertTrue(
            os.path.exists(destination_for(fresh)),
            "the fresh input should still have been converted",
        )

    def test_the_refusal_is_still_reported(self):
        already = build_zip(
            self.path("three.cbz"), [("a.jpg", read_bytes(REAL_JPEG))]
        )
        self.assertEqual(0, cli.main([already]))
        from contextlib import redirect_stderr

        captured = io.StringIO()
        with redirect_stderr(captured):
            cli.main([already])
        self.assertIn("already exists", captured.getvalue())


class ArchiveSuffixes(unittest.TestCase):
    """`discover`'s vocabulary, decided from names alone.

    Most of these names are reachable only indirectly, through `expand`.
    A regression to case-sensitive matching would drop every uppercase archive
    from every scan, and the suite would stay green -- so they are pinned here,
    directly, rather than left to whatever a scan happens to cover.
    """

    def test_archive_suffixes_are_every_container_with_a_reader(self):
        # Extended by the archive-containers epic: a suffix is an input exactly
        # when `SOURCE_READERS` claims it, and these two maps are extended
        # together. Entry 5 registered .rar. Entry 12 registered .cbr and .cbt.
        self.assertEqual(
            (".cbz", ".zip", ".cb7", ".7z", ".rar", ".cbr", ".cbt"), discover.ARCHIVE_SUFFIXES
        )

    def test_output_suffix_is_fixed_at_jxl_cbz(self):
        self.assertEqual(".jxl.cbz", discover.OUTPUT_SUFFIX)

    def test_every_declared_suffix_is_recognised(self):
        for suffix in discover.ARCHIVE_SUFFIXES:
            with self.subTest(suffix=suffix):
                self.assertTrue(discover.is_archive(f"book{suffix}"))

    def test_other_extensions_are_not_archives(self):
        # `page.jpg` is deliberately here: a JPEG is a page, not an archive.
        for name in ("notes.txt", "page.jpg", "book.jxl", "book", "book.cbz.tmp"):
            with self.subTest(name=name):
                self.assertFalse(discover.is_archive(name))

    def test_matching_is_case_insensitive(self):
        for name in ("Alpha.CBZ", "beta.ZIP", "Gamma.CbZ", "delta.Zip"):
            with self.subTest(name=name):
                self.assertTrue(discover.is_archive(name))

    def test_this_tools_own_output_is_never_an_input(self):
        for name in ("book.jxl.cbz", "book.JXL.CBZ", "book.zip.jxl.cbz"):
            with self.subTest(name=name):
                self.assertFalse(discover.is_archive(name))

    def test_the_converter_and_the_scan_read_one_suffix(self):
        # The drift guard: change the output suffix in one place only and this
        # is where it shows. Both input suffixes, because the `.cbz` case alone
        # would pass while `.zip` silently started yielding `.jxl.zip`.
        for name in ("book.cbz", "book.zip"):
            with self.subTest(name=name):
                produced = os.path.basename(destination_for(name))
                self.assertTrue(produced.endswith(discover.OUTPUT_SUFFIX))
                self.assertFalse(
                    discover.is_archive(produced),
                    "the converter's output must be invisible to a scan",
                )

    def test_the_output_suffix_is_the_container_after_the_default_format(self):
        # Derived rather than written out, which is what keeps the literal
        # assertion above and the tests reaching it through `report_sources`
        # true without being edited. The container does not vary with the format
        # any more than it varies with the input.
        self.assertEqual(".cbz", discover.CONTAINER_SUFFIX)
        self.assertIn(discover.DEFAULT_FORMAT, discover.PAGE_FORMATS)
        self.assertEqual(
            f".{discover.DEFAULT_FORMAT}{discover.CONTAINER_SUFFIX}",
            discover.OUTPUT_SUFFIX,
        )

    def test_every_declared_format_names_an_output_the_scan_skips(self):
        # The rescan skip reads the declared set, so adding a format to it is
        # the only change a new format needs to be skipped rather than refed in.
        for page_format in discover.PAGE_FORMATS:
            with self.subTest(page_format=page_format):
                name = f"book.{page_format}.cbz"
                self.assertTrue(discover.is_output_name(name))
                self.assertTrue(discover.is_output_name(name.upper()))
                self.assertFalse(discover.is_archive(name))

    def test_an_output_name_is_one_this_tool_could_have_written(self):
        # Not "any dotted word before .cbz": a book this tool cannot name is
        # still a book, and skipping it would drop it without a word.
        for name in ("book.cbz", "vol.1.cbz", "book.webp.cbz"):
            with self.subTest(name=name):
                self.assertFalse(discover.is_output_name(name))
                self.assertTrue(discover.is_archive(name))


class PatternRecognition(unittest.TestCase):
    """What counts as a pattern, which is the rule a literal path depends on."""

    def test_metacharacters_make_a_pattern(self):
        for pattern in ("lib/*.cbz", "lib/x?.cbz", "lib/[ab].cbz", "lib/a*b.cbz"):
            with self.subTest(pattern=pattern):
                self.assertTrue(discover.has_magic(pattern))

    def test_a_plain_path_is_not_a_pattern(self):
        for path in ("book.cbz", "lib/a.cbz", "lib/sub/", "weird]name.cbz"):
            with self.subTest(path=path):
                self.assertFalse(discover.has_magic(path))


class DirectoryDiscovery(ArchiveTestCase):
    """A directory argument means the archives it holds, and nothing else."""

    def lib(self) -> str:
        return self.make_dir("lib")

    def test_a_file_path_is_converted_exactly_as_before(self):
        source = self.make_archive(self.tmp, "a.cbz")
        code, out, err = self.capture([source])
        self.assertEqual(0, code, err)
        self.assertTrue(os.path.exists(destination_for(source)))
        self.assertIn("a.cbz -> ", out)

    def test_root_archives_convert_and_subdirectories_are_left_alone(self):
        lib = self.lib()
        first = self.make_archive(lib, "a.cbz")
        second = self.make_archive(lib, "b.cbz")
        with open(os.path.join(lib, "notes.txt"), "w") as handle:
            handle.write("not an archive\n")
        sub = self.make_dir(os.path.join("lib", "sub"))
        buried = self.make_archive(sub, "c.cbz")

        code, out, err = self.capture([lib])

        self.assertEqual(0, code, err)
        self.assertTrue(os.path.exists(destination_for(first)))
        self.assertTrue(os.path.exists(destination_for(second)))
        self.assertFalse(
            os.path.exists(destination_for(buried)),
            "sub/c.cbz must not be converted without --recursive",
        )
        self.assertNotIn("sub/c.cbz", out)
        self.assertTrue(os.path.exists(os.path.join(lib, "notes.txt")))

    def test_uppercase_extensions_are_scanned_too(self):
        # Comic libraries are full of `.CBZ`. A regression to case-sensitive
        # matching would drop these silently, which is what this pins.
        lib = self.lib()
        shout = self.make_archive(lib, "Alpha.CBZ")
        quiet = self.make_archive(lib, "beta.ZIP")

        code, out, err = self.capture([lib])

        self.assertEqual(0, code, err)
        self.assertEqual([shout, quiet], self.report_sources(out))
        self.assertTrue(os.path.exists(destination_for(shout)))
        self.assertTrue(os.path.exists(destination_for(quiet)))

    def test_a_zip_input_yields_a_jxl_cbz_never_a_jxl_zip(self):
        lib = self.lib()
        self.make_archive(lib, "b.zip")
        code, _, err = self.capture([lib])
        self.assertEqual(0, code, err)
        self.assertTrue(os.path.exists(os.path.join(lib, "b.jxl.cbz")))
        self.assertFalse(os.path.exists(os.path.join(lib, "b.jxl.zip")))

    def test_a_directory_and_an_explicit_path_convert_together(self):
        lib = self.lib()
        first = self.make_archive(lib, "a.cbz")
        second = self.make_archive(lib, "b.zip")
        # A sibling *file*, not a directory that happens to be called c.cbz:
        # an explicit argument is a path, and the point of this row is a file
        # named alongside the scan.
        outside = self.make_archive(self.tmp, "c.cbz", read_bytes(REAL_JPEG_2))

        code, out, err = self.capture([lib, outside])

        self.assertEqual(0, code, err)
        self.assertEqual([first, second, outside], self.report_sources(out))
        for source in (first, second, outside):
            self.assertTrue(os.path.exists(destination_for(source)))

    def test_a_previous_runs_output_is_not_converted_again(self):
        lib = self.lib()
        source = self.make_archive(lib, "a.cbz")
        self.assertEqual(0, self.capture([lib])[0])
        self.assertTrue(os.path.exists(os.path.join(lib, "a.jxl.cbz")))

        # The scan itself skips this tool's own output; the one archive it does
        # return is refused for already existing, and the run says so with the
        # same exit code a single file would have given.
        self.assertEqual([source], discover.expand([lib]))

        code, _, err = self.capture([lib])

        self.assertEqual(cli.EXIT_ENVIRONMENT, code)
        self.assertIn("already exists", err)
        self.assertFalse(
            os.path.exists(os.path.join(lib, "a.jxl.jxl.cbz")),
            "the output must never be fed back in as an input",
        )

    def test_one_stem_two_suffixes_converts_one_and_refuses_the_other(self):
        lib = self.lib()
        keeper = self.make_archive(lib, "a.cbz")
        loser = self.make_archive(lib, "a.zip")
        other = self.make_archive(lib, "z.cbz")

        code, out, err = self.capture([lib])

        self.assertEqual(cli.EXIT_ENVIRONMENT, code)
        self.assertIn(destination_for(loser), err)
        self.assertTrue(os.path.exists(destination_for(keeper)))
        self.assertTrue(
            os.path.exists(destination_for(other)),
            "the rest of the directory is still work the owner asked for",
        )
        # a.cbz sorts first, so it is the one that wins the destination.
        self.assertLess(
            out.index("a.cbz -> "),
            out.index("a.zip -> ") if "a.zip -> " in out else len(out),
        )

    def test_a_directory_with_no_archives_says_so_once_and_exits_zero(self):
        lib = self.lib()
        with open(os.path.join(lib, "notes.txt"), "w") as handle:
            handle.write("nothing to convert\n")

        code, out, err = self.capture([lib])

        self.assertEqual(0, code)
        self.assertEqual("", err)
        self.assertEqual(1, out.count(lib), out)
        self.assertEqual(1, len(out.splitlines()))

    def test_a_nonexistent_path_is_reported_as_before(self):
        missing = self.path("missing.cbz")
        code, _, err = self.capture([missing])
        self.assertEqual(cli.EXIT_FAILED, code)
        self.assertIn("cannot read", err)
        self.assertFalse(os.path.exists(destination_for(missing)))

    def test_a_nonexistent_directory_is_reported_as_before(self):
        code, _, err = self.capture([self.path("missing_dir")])
        self.assertEqual(cli.EXIT_FAILED, code)
        self.assertIn("cannot read", err)

    def test_paths_are_reported_as_typed_not_absolutised(self):
        # The converter resolves the destination itself, so absolutising here
        # would only make a relative invocation report something the owner did
        # not type -- noisier than the single-file behaviour it replaced.
        lib = self.lib()
        self.make_archive(lib, "a.cbz")
        relative = os.path.relpath(lib)
        expected = os.path.join(relative, "a.cbz")

        self.assertEqual([expected], discover.expand([relative]))

        code, out, err = self.capture([relative])

        self.assertEqual(0, code, err)
        self.assertEqual([expected], self.report_sources(out))

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symlink support")
    def test_symlinked_archives_are_not_followed(self):
        lib = self.lib()
        real = self.make_archive(lib, "a.cbz")
        os.symlink(real, os.path.join(lib, "link.cbz"))

        code, out, err = self.capture([lib])

        self.assertEqual(0, code, err)
        self.assertNotIn("link.cbz", out)
        self.assertFalse(os.path.exists(os.path.join(lib, "link.jxl.cbz")))

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symlink support")
    def test_symlinked_directories_are_not_descended_into(self):
        lib = self.lib()
        elsewhere = self.make_dir("elsewhere")
        buried = self.make_archive(elsewhere, "d.cbz")
        os.symlink(elsewhere, os.path.join(lib, "series"))

        code, _, err = self.capture([lib, "--recursive"])

        self.assertEqual(0, code, err)
        self.assertFalse(os.path.exists(destination_for(buried)))

    @unittest.skipUnless(hasattr(os, "symlink"), "needs symlink support")
    def test_a_named_symlinked_directory_is_followed(self):
        # The deliberate other half of the two tests above. A link found *by a
        # scan* is skipped, because that is where a loop or two spellings of one
        # archive lurk. A link the owner names is the owner's decision.
        elsewhere = self.make_dir("elsewhere")
        buried = self.make_archive(elsewhere, "d.cbz")
        link = self.path("linked")
        os.symlink(elsewhere, link)

        code, out, err = self.capture([link])

        self.assertEqual(0, code, err)
        self.assertTrue(os.path.exists(destination_for(buried)))
        self.assertEqual([os.path.join(link, "d.cbz")], self.report_sources(out))

    def test_a_directory_with_one_archive_reports_it_once(self):
        source = self.make_archive(self.lib(), "only.cbz")
        code, out, err = self.capture([self.path("lib")])
        self.assertEqual(0, code, err)
        self.assertEqual(1, out.count(f"{source} -> "), out)
        self.assertTrue(os.path.exists(destination_for(source)))

    def test_a_directory_named_twice_converts_each_archive_once(self):
        # Without the dedupe the second pass hits this run's own output and
        # reports a refusal, downgrading a perfectly healthy batch to exit 2.
        lib = self.lib()
        first = self.make_archive(lib, "a.cbz")
        second = self.make_archive(lib, "b.cbz")

        code, out, err = self.capture([lib, lib])

        self.assertEqual(0, code, err)
        self.assertEqual([first, second], self.report_sources(out))

    def test_a_directory_and_a_file_inside_it_convert_the_archive_once(self):
        lib = self.lib()
        first = self.make_archive(lib, "a.cbz")
        second = self.make_archive(lib, "b.cbz")

        code, out, err = self.capture([lib, os.path.join(lib, "a.cbz")])

        self.assertEqual(0, code, err)
        self.assertEqual([first, second], self.report_sources(out))
        self.assertTrue(os.path.exists(destination_for(first)))

    def test_a_file_named_twice_is_converted_once(self):
        source = self.make_archive(self.tmp, "twice.cbz")

        code, out, err = self.capture([source, source])

        self.assertEqual(0, code, err)
        self.assertEqual([source], self.report_sources(out))

    def test_a_named_unreadable_directory_is_reported_as_cannot_read(self):
        # The other half of the nested/named split in the walk. An unreadable
        # directory the owner named is not a scan that came up empty, so it is
        # handed on and the converter reports it as any path it cannot open.
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root reads anything")
        lib = self.lib()
        reachable = self.make_archive(lib, "a.cbz")
        locked = self.make_dir("locked")
        self.make_archive(locked, "b.cbz")
        os.chmod(locked, 0o000)
        self.addCleanup(os.chmod, locked, 0o700)

        code, out, err = self.capture([locked, lib])

        self.assertEqual(cli.EXIT_FAILED, code)
        self.assertIn("cannot read", err)
        self.assertIn("locked", err)
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "locked.jxl.cbz")))
        self.assertTrue(
            os.path.exists(destination_for(reachable)),
            "one unreadable directory must not abandon the rest of the batch",
        )


class RecursiveDiscovery(ArchiveTestCase):
    """--recursive mirrors the input tree, never hoisting anything."""

    def lib(self) -> str:
        return self.make_dir("lib")

    def test_a_subdirectory_archive_is_converted_where_it_sits(self):
        lib = self.lib()
        first = self.make_archive(lib, "a.cbz")
        second = self.make_archive(lib, "b.zip")
        sub = self.make_dir(os.path.join("lib", "sub"))
        buried = self.make_archive(sub, "c.cbz")

        code, out, err = self.capture([lib, "--recursive"])

        self.assertEqual(0, code, err)
        self.assertEqual([first, second, buried], self.report_sources(out))
        for source in (first, second, buried):
            self.assertTrue(
                os.path.exists(destination_for(source)),
                "each output belongs beside its own input",
            )
        self.assertFalse(
            os.path.exists(os.path.join(lib, "c.jxl.cbz")),
            "output must land beside its own input, never hoisted to the parent",
        )

    def test_two_subdirectories_with_the_same_stem_both_convert(self):
        lib = self.lib()
        left = self.make_dir(os.path.join("lib", "a"))
        right = self.make_dir(os.path.join("lib", "b"))
        first = self.make_archive(left, "book.cbz")
        second = self.make_archive(right, "book.cbz", read_bytes(REAL_JPEG_2))

        code, _, err = self.capture([lib, "--recursive"])

        self.assertEqual(0, code, err)
        self.assertTrue(os.path.exists(destination_for(first)))
        self.assertTrue(os.path.exists(destination_for(second)))
        self.assertEqual("", err)

    def test_recursion_is_depth_first_and_sorted_at_every_level(self):
        # Built in an order scandir has no reason to reproduce, so a scan that
        # does not sort shows up as a report in a different order.
        lib = self.lib()
        b = self.make_dir(os.path.join("lib", "b"))
        a = self.make_dir(os.path.join("lib", "a"))
        deep = self.make_dir(os.path.join("lib", "b", "deep"))
        self.make_archive(lib, "zz.cbz")
        self.make_archive(lib, "aa.cbz")
        self.make_archive(b, "m.cbz")
        self.make_archive(a, "n.cbz")
        self.make_archive(deep, "q.cbz")

        # Each level sorts on its own names, and a subdirectory is descended into
        # at the position its name sorts to -- so "a" comes before "aa.cbz", and
        # "b" before "b/m.cbz" but after its own "deep".
        expected = [
            os.path.join(a, "n.cbz"),
            os.path.join(lib, "aa.cbz"),
            os.path.join(deep, "q.cbz"),
            os.path.join(b, "m.cbz"),
            os.path.join(lib, "zz.cbz"),
        ]
        self.assertEqual(expected, list(discover.iter_directory(lib, True)))
        self.assertEqual(
            expected,
            list(discover.iter_directory(lib, True)),
            "two scans of one tree must agree",
        )

        code, out, err = self.capture([lib, "--recursive"])

        self.assertEqual(0, code, err)
        self.assertEqual(expected, self.report_sources(out))

    def test_an_unreadable_subdirectory_is_skipped_with_a_warning(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root reads anything")
        lib = self.lib()
        reachable = self.make_archive(lib, "a.cbz")
        locked = self.make_dir(os.path.join("lib", "locked"))
        buried = self.make_archive(locked, "b.cbz")
        os.chmod(locked, 0o000)
        self.addCleanup(os.chmod, locked, 0o700)

        code, out, err = self.capture([lib, "--recursive"])

        self.assertEqual(0, code)
        self.assertIn("locked", err)
        self.assertTrue(
            os.path.exists(destination_for(reachable)),
            "an unreadable subdirectory must not abandon the rest of the tree",
        )
        self.assertFalse(os.path.exists(destination_for(buried)))


class PatternDiscovery(ArchiveTestCase):
    """A wildcard argument names archives, the way a directory does."""

    def lib(self) -> str:
        return self.make_dir("lib")

    def test_a_pattern_converts_its_matches_in_sorted_order(self):
        lib = self.lib()
        # Created in an order glob has no reason to reproduce: glob yields
        # filesystem order, which is no more alphabetical than scandir's.
        third = self.make_archive(lib, "c.cbz")
        first = self.make_archive(lib, "a.cbz")
        second = self.make_archive(lib, "b.cbz")

        pattern = os.path.join(lib, "*.cbz")

        self.assertEqual(
            [first, second, third],
            discover.expand([pattern]),
            "glob's filesystem order is not sorted order",
        )

        code, out, err = self.capture([pattern])

        self.assertEqual(0, code, err)
        self.assertEqual([first, second, third], self.report_sources(out))

    def test_a_pattern_matching_nothing_says_so_once_and_exits_zero(self):
        lib = self.lib()
        self.make_archive(lib, "a.cbz")
        pattern = os.path.join(lib, "nope*.cbz")

        code, out, err = self.capture([pattern])

        self.assertEqual(0, code)
        self.assertEqual("", err)
        self.assertEqual(1, out.count(pattern), out)
        self.assertEqual(1, len(out.splitlines()))
        self.assertEqual(["a.cbz"], sorted(os.listdir(lib)), "nothing may be written")

    def test_a_pattern_ignores_files_that_are_not_archives(self):
        lib = self.lib()
        keep = self.make_archive(lib, "keep.cbz")
        # A directory whose name carries an archive extension is the shape that
        # would otherwise be handed straight to the converter as a zip.
        self.make_dir(os.path.join("lib", "old.cbz"))
        for name in ("notes.txt", "page.jpg", "other.jxl.cbz", "old.jxl"):
            with open(os.path.join(lib, name), "w") as handle:
                handle.write("not an archive\n")

        pattern = os.path.join(lib, "*")

        self.assertEqual([keep], discover.expand([pattern]))

        code, out, err = self.capture([pattern])

        self.assertEqual(0, code, err)
        self.assertEqual([keep], self.report_sources(out))

    def test_a_pattern_skips_this_tools_own_output(self):
        lib = self.lib()
        self.make_archive(lib, "a.cbz")
        self.assertEqual(0, self.capture([lib])[0])

        pattern = os.path.join(lib, "*.cbz")

        # `a.jxl.cbz` matches `*.cbz` and must still be filtered out, or the
        # second run would write the very `a.jxl.jxl.cbz` the skip prevents.
        # So a pattern and a directory over the same tree must agree here.
        survivor = [os.path.join(lib, "a.cbz")]
        self.assertEqual(survivor, discover.expand([lib]))
        self.assertEqual(survivor, discover.expand([pattern]))

        code, out, err = self.capture([pattern])

        self.assertEqual(cli.EXIT_ENVIRONMENT, code)
        self.assertIn("already exists", err)
        self.assertFalse(os.path.exists(os.path.join(lib, "a.jxl.jxl.cbz")))

    def test_a_pattern_and_a_directory_convert_each_archive_once(self):
        lib = self.lib()
        first = self.make_archive(lib, "a.cbz")
        second = self.make_archive(lib, "b.cbz")

        code, out, err = self.capture([os.path.join(lib, "*.cbz"), lib])

        self.assertEqual(0, code, err)
        self.assertEqual([first, second], self.report_sources(out))

    def test_a_pattern_is_not_recursive(self):
        # `**` is documented as behaving as `*`: --recursive is the only thing
        # that descends, so one flag must not mean two behaviours.
        lib = self.lib()
        self.make_archive(lib, "top.cbz")
        sub = self.make_dir(os.path.join("lib", "sub"))
        near = self.make_archive(sub, "deep.cbz")
        far = self.make_archive(self.make_dir(os.path.join("lib", "sub", "deeper")),
                                "deepest.cbz")

        self.assertEqual(
            [near],
            discover.expand([os.path.join(lib, "**", "*.cbz")]),
            "** must stop where * stops, not walk the whole tree",
        )
        self.assertEqual(
            [far],
            discover.expand([os.path.join(lib, "*", "*", "*.cbz")]),
        )

    def test_a_question_mark_pattern_matches_one_character(self):
        lib = self.lib()
        one = self.make_archive(lib, "issue1.cbz")
        two = self.make_archive(lib, "issue2.cbz")
        self.make_archive(lib, "issue10.cbz")

        self.assertEqual([one, two], discover.expand([os.path.join(lib, "issue?.cbz")]))

    def test_several_arguments_are_converted_in_the_order_given(self):
        lib = self.lib()
        lone = self.make_archive(self.tmp, "solo.cbz")
        first = self.make_archive(lib, "x-one.cbz")
        second = self.make_archive(lib, "x-two.cbz")

        code, out, err = self.capture(
            [lone, lib, os.path.join(lib, "x-*.cbz")]
        )

        self.assertEqual(0, code, err)
        self.assertEqual([lone, first, second], self.report_sources(out))

    def test_a_literal_path_is_never_globbed_or_filtered(self):
        lib = self.lib()
        self.make_archive(lib, "a.cbz")
        odd = self.make_archive(lib, "a*.cbz")
        notes = os.path.join(lib, "notes.txt")
        with open(notes, "w") as handle:
            handle.write("not an archive\n")

        # `notes.txt` reaches the converter, which reports it, exactly as it did
        # before expansion existed. Extension filtering is for scans and
        # patterns only; a literal path is the owner's decision.
        self.assertEqual([notes], discover.expand([notes]))

        code, out, err = self.capture([notes])
        self.assertEqual(cli.EXIT_FAILED, code)
        self.assertIn("cannot read", err)

        # And a name holding `*` is a file to convert, not a pattern to
        # reinterpret into some other file.
        code, out, err = self.capture([odd])
        self.assertEqual(0, code, err)
        self.assertTrue(os.path.exists(destination_for(odd)))


if __name__ == "__main__":
    unittest.main()
