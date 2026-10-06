"""Every row of the I/O and edge-case matrix, as executable assertions.

One test class or method per row, so a failure names the row that broke.
"""

from __future__ import annotations

import io
import os
import shutil
import subprocess
import sys
import unittest
import zipfile

# Allow `python3 -m unittest tests.test_archive` as well as
# `python3 -m unittest discover -s tests`: the latter puts this directory on
# sys.path, the former does not.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cbx_jackal import cli, encode, preflight  # noqa: E402
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
    README,
    REAL_JPEG,
    REAL_JPEG_2,
    ArchiveTestCase,
    build_zip,
    compress_types,
    contents,
    names_in_order,
    read_bytes,
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
        self.assertIn("bytes", report.size_line())
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


class MissingDependency(ArchiveTestCase):
    """CAP-5: exit before opening any archive, naming the tool."""

    requires_cjxl = False

    def test_message_names_the_tool(self):
        message = preflight.missing_tool_message()
        self.assertIn("cjxl", message)

    def test_message_points_at_documentation(self):
        message = preflight.missing_tool_message()
        self.assertIn("README.md", message)

    def test_message_covers_all_three_platforms(self):
        message = preflight.missing_tool_message().lower()
        for platform in ("linux", "mac", "windows"):
            with self.subTest(platform=platform):
                self.assertIn(platform, message)

    def test_message_is_platform_neutral(self):
        # No "command not found", no shell jargon, no traceback.
        message = preflight.missing_tool_message()
        self.assertNotIn("Traceback", message)
        self.assertNotIn("command not found", message.lower())

    def test_check_reports_the_resolved_path_when_present(self):
        if shutil.which("cjxl") is None:
            self.skipTest("cjxl is not on PATH")
        resolved, error = preflight.check()
        self.assertIsNone(error)
        self.assertTrue(os.path.exists(resolved))

    def test_check_reports_an_error_when_absent(self):
        resolved, error = preflight.check("definitely-not-a-real-tool-xyz")
        self.assertIsNone(resolved)
        self.assertIn("definitely-not-a-real-tool-xyz", error)

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
        for flag in ("--quality", "--strict", "--dry-run", "--force"):
            with self.subTest(flag=flag):
                self.assertIn(flag, options)


class MisnamedEntry(ArchiveTestCase):
    """A .jpg holding PNG bytes still converts -- cjxl sniffs content."""

    def test_mislabelled_entry_converts(self):
        source = build_zip(
            self.path("mis.cbz"),
            [
                ("page.jpg", read_bytes(MISNAMED_PNG)),
                ("real.jpg", read_bytes(REAL_JPEG)),
            ],
        )
        report = Converter(self.cjxl).convert(source)
        self.assertTrue(report.ok, report.failure_lines())
        self.assertIn("page.jxl", names_in_order(destination_for(source)))

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
        self.assertIn(str(os.path.getsize(destination)), report.size_line())

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
        self.assertIn(f"{expected:.1f}%", report.size_line())

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
        self.assertIn("larger", report.size_line())
        self.assertNotIn("smaller", report.size_line())

    def test_dry_run_does_not_pass_an_estimate_off_as_a_measurement(self):
        report = Converter(self.cjxl).convert(self.sample(), dry_run=True)
        self.assertIsNone(report.output_size_bytes)
        self.assertIn("entry data only", report.size_line())


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
        self.assertEqual(1, report.not_converted)

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


if __name__ == "__main__":
    unittest.main()
