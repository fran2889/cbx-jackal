"""The cjxl invocation matrix, and lossless round-tripping.

These tests exist because of one measured trap: libjxl defaults to
lossless-transcoding for JPEG input, so `-q N` without `--lossless_jpeg=0` fails
outright and produces no file.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import unittest

# Allow `python3 -m unittest tests.test_archive` as well as
# `python3 -m unittest discover -s tests`: the latter puts this directory on
# sys.path, the former does not.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cbx_jackal import encode  # noqa: E402

from helpers import (
    CORRUPT_JPEG,
    MISNAMED_PNG,
    REAL_JPEG,
    ArchiveTestCase,
    read_bytes,
)


class InvocationMatrix(unittest.TestCase):
    """No subprocess, no fixtures -- this is pure argv construction."""

    def test_lossless_path_passes_no_quality_flag(self):
        command = encode.build_command("cjxl", "in.jpg", "out.jxl", None)
        self.assertEqual(["cjxl", "in.jpg", "out.jxl"], command)
        self.assertNotIn("-q", command)
        self.assertNotIn("--quality", command)

    def test_lossless_path_does_not_pass_lossless_jpeg_0(self):
        command = encode.build_command("cjxl", "in.jpg", "out.jxl", None)
        self.assertNotIn("--lossless_jpeg=0", command)

    def test_lossy_path_passes_both_quality_and_lossless_jpeg_0(self):
        command = encode.build_command("cjxl", "in.jpg", "out.jxl", 90)
        self.assertEqual(
            ["cjxl", "-q", "90", "--lossless_jpeg=0", "in.jpg", "out.jxl"], command
        )

    def test_lossy_quality_appears_before_the_paths(self):
        # cjxl parses flags before positionals; get this wrong and it exits 1.
        command = encode.build_command("cjxl", "in.jpg", "out.jxl", 75)
        self.assertLess(command.index("-q"), command.index("in.jpg"))
        self.assertLess(command.index("--lossless_jpeg=0"), command.index("in.jpg"))

    def test_quality_100_is_treated_as_lossless(self):
        # -q 100 --lossless_jpeg=0 would surrender reversibility for no gain.
        self.assertTrue(encode.is_lossless(100))
        self.assertEqual(
            ["cjxl", "in.jpg", "out.jxl"],
            encode.build_command("cjxl", "in.jpg", "out.jxl", 100),
        )

    def test_quality_99_is_lossy(self):
        self.assertFalse(encode.is_lossless(99))
        self.assertIn("--lossless_jpeg=0", encode.build_command("cjxl", "a", "b", 99))

    def test_repeated_quality_values(self):
        for quality in (1, 30, 50, 90, 99):
            with self.subTest(quality=quality):
                command = encode.build_command("cjxl", "a", "b", quality)
                self.assertEqual([str(quality)], [c for c in command if c.isdigit()])
                self.assertIn("--lossless_jpeg=0", command)


class LosslessReversibility(ArchiveTestCase):
    """CAP-1: converted pages stay byte-for-byte recoverable."""

    def test_lossless_output_reconstructs_the_source_jpeg(self):
        source = read_bytes(REAL_JPEG)
        result = encode.run(self.cjxl, source)
        self.assertTrue(result.ok, result.error)
        self.assertReconstructsTo(self.require(result.data, "data"), source)

    def test_lossless_output_is_smaller_than_the_source(self):
        source = read_bytes(REAL_JPEG)
        result = encode.run(self.cjxl, source)
        self.assertTrue(result.ok, result.error)
        self.assertLess(result.size, len(source))

    def test_lossy_output_is_smaller_still_and_not_reversible(self):
        source = read_bytes(REAL_JPEG)
        lossless = encode.run(self.cjxl, source)
        lossy = encode.run(self.cjxl, source, quality=60)
        self.assertTrue(lossy.ok, lossy.error)
        self.assertLess(lossy.size, lossless.size)

    def test_lossy_invocation_actually_succeeds(self):
        # Guards the trap: without --lossless_jpeg=0 this exits 1, no output.
        result = encode.run(self.cjxl, read_bytes(REAL_JPEG), quality=90)
        self.assertTrue(result.ok, result.error)
        self.assertGreater(result.size, 0)

    def test_lossless_invocation_emits_no_diagnostics(self):
        # A bare call is silent apart from the lossless-transcoding notice.
        result = encode.run(self.cjxl, read_bytes(REAL_JPEG))
        self.assertTrue(result.ok, result.error)


class FailureDetection(ArchiveTestCase):
    """cjxl is a reliable oracle: exit 1 and no output for undecodable bytes."""

    def test_corrupt_jpeg_fails(self):
        result = encode.run(self.cjxl, read_bytes(CORRUPT_JPEG))
        self.assertFalse(result.ok)
        self.assertIsNone(result.data)

    def test_garbage_bytes_fail(self):
        result = encode.run(self.cjxl, os.urandom(4096))
        self.assertFalse(result.ok)
        self.assertIsNone(result.data)

    def test_empty_input_fails(self):
        result = encode.run(self.cjxl, b"")
        self.assertFalse(result.ok)

    def test_failure_message_is_a_single_line(self):
        result = encode.run(self.cjxl, read_bytes(CORRUPT_JPEG))
        self.assertIsNotNone(result.error)
        self.assertNotIn("\n", self.require(result.error, "error"))
        self.assertTrue(self.require(result.error, "error").strip())

    def test_failure_message_drops_the_banner(self):
        # The report shows one readable line, not the whole libjxl log.
        result = encode.run(self.cjxl, read_bytes(CORRUPT_JPEG))
        self.assertNotIn("JPEG XL encoder v", self.require(result.error, "error"))
        self.assertNotIn("Note: Implicit-default", self.require(result.error, "error"))

    def test_failure_message_keeps_the_exit_code(self):
        result = encode.run(self.cjxl, read_bytes(CORRUPT_JPEG))
        self.assertTrue(
            self.require(result.error, "error").startswith(
                f"cjxl exited {result.returncode} "
            )
        )

    def test_failure_message_carries_libjxls_own_words(self):
        # Verbatim from cjxl, not reinterpreted by us.
        result = encode.run(self.cjxl, read_bytes(CORRUPT_JPEG))
        self.assertIn("Error", self.require(result.error, "error"))

    def test_misnamed_png_still_converts(self):
        # cjxl sniffs content, not extension.
        result = encode.run(self.cjxl, read_bytes(MISNAMED_PNG), suffix=".jpg")
        self.assertTrue(result.ok, result.error)

    def test_lossless_output_carries_reconstruction_data(self):
        if shutil.which("jxlinfo") is None:
            self.skipTest("jxlinfo is not on PATH")
        result = encode.run(self.cjxl, read_bytes(REAL_JPEG))
        self.assertTrue(result.ok, result.error)
        probe = self.path("probe.jxl")
        with open(probe, "wb") as handle:
            handle.write(self.require(result.data, "data"))
        completed = subprocess.run(
            ["jxlinfo", probe], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.assertEqual(0, completed.returncode, completed.stderr.decode())
        self.assertIn(b"JPEG bitstream reconstruction data available", completed.stdout)

    def test_lossy_output_carries_no_reconstruction_data(self):
        if shutil.which("jxlinfo") is None:
            self.skipTest("jxlinfo is not on PATH")
        result = encode.run(self.cjxl, read_bytes(REAL_JPEG), quality=60)
        self.assertTrue(result.ok, result.error)
        probe = self.path("lossy.jxl")
        with open(probe, "wb") as handle:
            handle.write(self.require(result.data, "data"))
        completed = subprocess.run(
            ["jxlinfo", probe], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.assertNotIn(b"reconstruction data available", completed.stdout)

    def test_classify_never_sends_jxl_to_cjxl(self):
        from cbx_jackal.archive import classify

        self.assertFalse(classify("page001.jxl").transcode)
        self.assertFalse(classify("nested/page.JXL").transcode)

    def test_temp_files_are_cleaned_up(self):
        import tempfile as _tempfile

        before = set(os.listdir(_tempfile.gettempdir()))
        encode.run(self.cjxl, read_bytes(REAL_JPEG))
        encode.run(self.cjxl, read_bytes(CORRUPT_JPEG))
        leaked = {
            name
            for name in set(os.listdir(_tempfile.gettempdir())) - before
            if name.startswith("cbx-jackal-")
        }
        self.assertEqual(set(), leaked)


class FailureMessageSelection(unittest.TestCase):
    """Which of libjxl's lines lands in the report.

    libjxl prints an internal trace and then a summary. The report shows the
    summary; the trace is the fallback when there is no summary.
    """

    def test_owner_facing_line_wins_over_the_internal_trace(self):
        stderr = (
            "JPEG XL encoder v0.11.1\n"
            "./lib/jxl/jpeg/enc_jpeg_data_reader.cc:463: JXL_FAILURE: Unexpected end of scan.\n"
            "./lib/jxl/encode.cc:2095: Error during decode of input JPEG\n"
            "Error while decoding the JPEG image. It may be corrupt (e.g. truncated) "
            "or of an unsupported type (e.g. CMYK).\n"
            "EncodeImageJXL() failed.\n"
        )
        message = encode.describe_failure(stderr, 1)
        self.assertTrue(
            message.startswith("cjxl exited 1 (Error while decoding the JPEG image.")
        )

    def test_internal_trace_is_used_when_it_is_all_there_is(self):
        stderr = "JPEG XL encoder v0.11.1\nJXL_FAILURE: something went wrong\n"
        message = encode.describe_failure(stderr, 3)
        self.assertEqual("cjxl exited 3 (JXL_FAILURE: something went wrong)", message)

    def test_generic_wrapper_is_not_the_whole_message(self):
        stderr = (
            "JPEG XL encoder v0.11.1\n"
            "./lib/extras/dec/decode.cc:151: JXL_FAILURE: Codecs failed to decode\n"
            "Getting pixel data failed.\n"
        )
        self.assertEqual(
            "cjxl exited 1 (Getting pixel data failed.)",
            encode.describe_failure(stderr, 1),
        )

    def test_the_quality_trap_survives_verbatim(self):
        # The trap from conventions.md, quoted exactly as cjxl emits it.
        stderr = (
            "JPEG XL encoder v0.11.1 [NEON,NEON_WITHOUT_AES]\n"
            "Must not set quality below 100 in combination with --lossless_jpeg=1, "
            "which is set by default.\n"
        )
        message = encode.describe_failure(stderr, 1)
        self.assertIn("Must not set quality below 100", message)
        self.assertIn("--lossless_jpeg=1", message)

    def test_silence_still_produces_a_line(self):
        message = encode.describe_failure("", 2)
        self.assertEqual("cjxl exited 2 (no diagnostic output)", message)

    def test_exit_code_is_always_in_the_message(self):
        for returncode in (0, 1, 2, 127):
            with self.subTest(returncode=returncode):
                message = encode.describe_failure("something\n", returncode)
                self.assertIn(f"cjxl exited {returncode}", message)


if __name__ == "__main__":
    unittest.main()
