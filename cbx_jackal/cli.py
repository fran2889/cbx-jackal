"""Command line interface.

Exit code is non-zero if and only if a JPEG entry failed to convert, plus the
reserved codes for usage and environment problems. Pass-throughs never make a
healthy run look failed.
"""

from __future__ import annotations

import argparse
import sys

from . import __version__, discover, preflight
from .archive import ArchiveError, Converter, OutputExistsError
from .encode import TOOL

EXIT_OK = 0
#: A JPEG entry failed to convert, or the archive could not be processed.
EXIT_FAILED = 1
#: Usage error, missing dependency, or a refused write.
EXIT_ENVIRONMENT = 2

EPILOG = """\
exit codes:
  0  every JPEG page converted (pass-through entries do not affect this)
  1  at least one JPEG page failed to convert, or an archive was unreadable
  2  usage error, missing cjxl, or the output already exists without --force

A path may be an archive, a directory, or a wildcard pattern such as
'lib/*.cbz'. A directory is scanned for archives in sorted order and each
archive is converted where it sits; subdirectories are left alone unless
--recursive is given. Already-converted .<format>.cbz files are skipped, and an
archive named more than once is converted once. A directory or pattern that
matches nothing is a note, not an error. Quote a pattern so the shell does not
expand it before this tool sees it.

The output is always a new file named <input>.<format>.cbz beside the input,
where <format> is what --format names -- .cbz never varies with the input. The
input is never modified. Requires cjxl from the libjxl tools package; see
README.md -> Installing cjxl.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cbx-jackal",
        description=(
            "Transcode a CBZ's JPEG pages to JPEG XL losslessly and byte-reversibly, "
            "preserving entry order and passing through everything else unchanged."
        ),
        epilog=EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "paths",
        nargs="+",
        metavar="CBZ|DIR|PATTERN",
        help=(
            "one or more comic archives to convert, directories to scan for them, "
            "or wildcard patterns such as 'lib/*.cbz'. Directories are not "
            "descended into without --recursive. Quote a pattern so the shell "
            "leaves it alone."
        ),
    )
    parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="descend into subdirectories when a path is a directory",
    )
    parser.add_argument(
        "--quality",
        type=int,
        metavar="N",
        default=None,
        help=(
            "encode lossy at quality N (1-100) instead of losslessly. "
            "Surrenders byte-for-byte JPEG recovery. 100 and above is lossless."
        ),
    )
    parser.add_argument(
        "--format",
        dest="page_format",
        default=discover.DEFAULT_FORMAT,
        metavar="FMT",
        help=(
            "page format of the output; legal values: "
            f"{', '.join(discover.PAGE_FORMATS)}. The output is named "
            "<input>.<format>.cbz either way, and the container never varies "
            "with the input. Default: %(default)s."
        ),
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "write nothing at all if any page fails to convert, instead of copying "
            "the failed page through and completing the archive"
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="report the plan and the size figures without writing anything",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite an existing <name>.<format>.cbz",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"cbx-jackal {__version__}",
    )
    return parser


def _validate_quality(quality: int | None) -> int | None:
    if quality is None:
        return None
    if not 1 <= quality <= 100:
        raise ValueError(f"--quality must be between 1 and 100, got {quality}")
    return quality


def _validate_format(page_format: str) -> str:
    """Reject a format this tool cannot name an output after, in any case.

    A usage error rather than a fallback to the default: a run asked for WebP
    and handed back JXL is worse than a run that refused, because the name it
    writes still looks like what was asked for. Case is folded the way the
    suffix tables fold it, and the declared spelling comes back so the output
    name never varies with how the flag was typed. The offending value is
    rendered as it was given, so an empty one still reads as a value.
    """
    for supported in discover.PAGE_FORMATS:
        if page_format.casefold() == supported.casefold():
            return supported
    raise ValueError(
        f"unsupported --format {page_format!r}; supported formats are "
        f"{', '.join(discover.PAGE_FORMATS)}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    # Both checks raise, and `parser.error` exits 2 from inside this try: a bad
    # flag is answered before the preflight, so it costs no tool on PATH and
    # opens nothing.
    try:
        quality = _validate_quality(args.quality)
        page_format = _validate_format(args.page_format)
    except ValueError as exc:
        parser.error(str(exc))

    # CAP-5: before opening any archive, so a missing dependency cannot be
    # discovered partway through a 200-page run.
    cjxl, error = preflight.check(TOOL)
    if cjxl is None:
        print(f"cbx-jackal: {error}", file=sys.stderr)
        return EXIT_ENVIRONMENT

    # After the preflight, so a missing cjxl is one message over a 300-file scan
    # rather than 300 of them, and before the loop, so the loop keeps its shape
    # and each expanded path keeps its own report and error handling.
    paths = discover.expand(args.paths, recursive=args.recursive)

    converter = Converter(
        cjxl, quality=quality, strict=args.strict, page_format=page_format
    )
    exit_code = EXIT_OK

    for path in paths:
        try:
            report = converter.convert(
                path, force=args.force, dry_run=args.dry_run
            )
        except OutputExistsError as exc:
            # Only this path is refused. The rest of the list is still work the
            # owner asked for, so carry on rather than abandoning it.
            print(f"cbx-jackal: {exc}", file=sys.stderr)
            exit_code = EXIT_ENVIRONMENT
            continue
        except ArchiveError as exc:
            # An abort still knows which pages failed. CAP-4 requires one line
            # per failed page, so print the report when there is one and only
            # fall back to the bare reason when the run never got that far.
            report = exc.report
            if report is not None and report.total:
                print(
                    report.render(quality=quality, dry_run=args.dry_run),
                    file=sys.stderr,
                )
            else:
                print(f"cbx-jackal: {exc}", file=sys.stderr)
            exit_code = EXIT_FAILED
            continue

        print(report.render(quality=quality, dry_run=args.dry_run))
        if report.not_converted:
            exit_code = EXIT_FAILED

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
