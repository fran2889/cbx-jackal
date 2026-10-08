"""Read a CBZ in stored order, transcode its JPEG pages, write a new CBZ.

Ordering is a correctness property, not cosmetics. Entries are iterated in the
source ZIP's stored order verbatim -- no natural sort, no renumbering, no repair
of archives whose ordering is already wrong. Readers own the sort; this tool never
silently reorders a book. Because nothing is renumbered, a page that fails and is
copied through stays at its original index, so the book gets a hole rather than a
misnumbering.

Every entry written out is ZIP_STORED. JXL is already entropy-coded, so deflate
measured under 1% gain while costing real CPU on every page.
"""

from __future__ import annotations

import os
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass

from . import encode
from .discover import DEFAULT_FORMAT, output_suffix
from .report import CONVERTED, NOT_CONVERTED, PASSED_THROUGH, EntryOutcome, Report

#: Extensions whose entries are handed to `cjxl`. Case-insensitive: comic
#: archives are full of `.JPG` and `.JPEG`.
JPEG_SUFFIXES = (".jpg", ".jpeg")

#: Never handed to `cjxl`. Re-encoding an existing `.jxl` strips the JPEG
#: bitstream reconstruction data, which is the one way to silently destroy
#: reversibility.
JXL_SUFFIX = ".jxl"

#: Read/convert buffers. Large enough that a 300dpi A4 page never spills to
#: disk mid-read.
CHUNK = 1 << 20


class ArchiveError(Exception):
    """The run could not proceed. Raised before any output is published.

    `report` carries whatever was learned before the abort, so the CLI can still
    name the pages that failed instead of printing only the abort reason.
    """

    def __init__(self, message: str, report: Report | None = None):
        super().__init__(message)
        self.report = report


class OutputExistsError(ArchiveError):
    """The destination file is present and `--force` was not given."""


@dataclass(frozen=True)
class OutputPlan:
    """One entry's intended outcome, decided before any bytes move."""

    name: str
    #: Name in the output archive. Identical to `name` for pass-throughs.
    output_name: str
    transcode: bool


def classify(name: str) -> OutputPlan:
    """Decide what to do with one entry, from its name alone.

    Directory entries pass through. `.jpg`/`.jpeg` in any case are transcoded.
    Everything else -- `ComicInfo.xml`, `readme.txt`, `__MACOSX/` junk, existing
    `.jxl` -- is copied verbatim. Content is not sniffed: `cjxl` does that, and a
    mislabelled entry that says `.jpg` is still transcoded correctly.
    """
    if name.endswith("/"):
        return OutputPlan(name, name, transcode=False)

    parts = name.split("/")
    # `__MACOSX/` holds AppleDouble resource forks, never real pages. Their names
    # often end in .jpg but their bytes are not a JPEG, so handing them to cjxl
    # would turn harmless resource-fork junk into a reported failure. Junk is
    # copied through, never cleaned -- that is a separate opinion the owner has
    # not asked for.
    if "__MACOSX" in parts[:-1]:
        return OutputPlan(name, name, transcode=False)
    if parts[-1].startswith("._"):
        return OutputPlan(name, name, transcode=False)

    _, suffix = os.path.splitext(name)
    lowered = suffix.lower()

    if lowered in JPEG_SUFFIXES:
        stem = name[: -len(suffix)] if suffix else name
        return OutputPlan(name, stem + JXL_SUFFIX, transcode=True)

    return OutputPlan(name, name, transcode=False)


def destination_for(path: str, page_format: str = DEFAULT_FORMAT) -> str:
    """`<name>.<format>.cbz` beside the input. Never in-place.

    The suffix comes from `discover.output_suffix`, the single place it is
    declared, because this function and the directory scan's skip of this tool's
    own output have to agree. Two literals would drift: name the format segment
    in one place only and a rescan would skip one output while this wrote
    another, so an already-converted book would come back as a second
    generation -- the very `a.jxl.jxl.cbz` the skip exists to prevent.

    `page_format` is defaulted rather than required: `--format jxl` has to be
    the run without the flag, byte for byte, and a required parameter cannot be
    that. A format outside `discover.PAGE_FORMATS` raises `ValueError` rather
    than producing a name the scan would re-ingest.
    """
    directory = os.path.dirname(os.path.abspath(path))
    stem = os.path.basename(path)
    stem = os.path.splitext(stem)[0]
    return os.path.join(directory, stem + output_suffix(page_format))


def collision_key(output_name: str) -> str:
    """The name a reader will actually resolve an output entry by.

    Comparing output names literally is not enough. ``page.jxl`` and
    ``page.JXL`` are distinct strings, so a literal check writes both and
    reports success -- yet ZIP readers on macOS and Windows routinely resolve
    member names case-insensitively, and archives assembled on macOS can carry
    NFD-normalised names that collide after normalisation. Either way the second
    member shadows the first and a converted page silently vanishes.

    So the comparison folds case and normalises to NFC. Folding can report a
    collision where the names would in fact have stayed distinct on a strictly
    case-sensitive reader; that costs a refused archive the owner can resolve by
    renaming, which is far cheaper than a silent duplicate.
    """
    return unicodedata.normalize("NFC", output_name).casefold()


def build_plan(names: list[str]) -> list[OutputPlan]:
    """Classify every entry, in the order given.

    Aborts when two entries would be written under a name a reader resolves
    identically. Writing a ZIP with a duplicate member is not an error as far as
    `zipfile` is concerned: the second member simply shadows the first, so a
    converted page would silently vanish from a run that then reports success.
    Renaming is not an option either -- the spec forbids it -- so the only safe
    answer is to refuse the archive and say which entries collide.
    """
    plans = [classify(name) for name in names]

    owner: dict[str, str] = {}
    for plan in plans:
        key = collision_key(plan.output_name)
        previous = owner.get(key)
        if previous is not None:
            raise ArchiveError(
                f"output name collision: {plan.name} and {previous} both resolve "
                f"to {plan.output_name} in a reader; one entry would be lost, so "
                f"nothing is written"
            )
        owner[key] = plan.name

    return plans


def _stored_info(plan: OutputPlan, template: zipfile.ZipInfo) -> zipfile.ZipInfo:
    """A fresh ZipInfo for the output, preserving name, timestamp and attrs."""
    info = zipfile.ZipInfo(plan.output_name, date_time=template.date_time)
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = template.external_attr
    info.internal_attr = template.internal_attr
    info.create_system = template.create_system
    info.comment = template.comment
    return info


def _entries(source: zipfile.ZipFile) -> list[zipfile.ZipInfo]:
    """Source entries in stored order, verbatim."""
    return list(source.infolist())


def _read_entry(source: zipfile.ZipFile, info: zipfile.ZipInfo) -> bytes:
    """Read one entry's full contents.

    A corrupt compressed stream or a bad CRC raises, which aborts the run: an
    archive we cannot read entries from is not safe to rewrite. So do an
    encrypted member and an unsupported compression method: both mean the same
    thing here, and both must arrive as an `ArchiveError` rather than a
    traceback.
    """
    chunks = []
    try:
        with source.open(info, "r") as handle:
            while True:
                chunk = handle.read(CHUNK)
                if not chunk:
                    break
                chunks.append(chunk)
    except (RuntimeError, NotImplementedError) as exc:
        # RuntimeError: encrypted member. NotImplementedError: compression
        # method this Python cannot decode.
        raise ArchiveError(
            f"cannot read {info.filename}: {exc or type(exc).__name__}"
        ) from exc
    return b"".join(chunks)


class Converter:
    """Transcodes one archive, reporting as it goes.

    `strict` promotes a page-level `cjxl` failure into a fatal error: no output
    file is published at all. Without it, a failed page is copied through under
    its original name so the archive stays complete, and the exit code is
    non-zero.

    `page_format` is the segment between the stem and the container in every
    output name, and nothing else: the bytes written are the same either way
    until a second format is one this tool can encode.
    """

    def __init__(
        self,
        cjxl: str,
        quality: int | None = None,
        strict: bool = False,
        page_format: str = DEFAULT_FORMAT,
    ):
        if not cjxl:
            raise ArchiveError("cjxl path is required; run the preflight first")
        self.cjxl = cjxl
        self.quality = quality
        self.strict = strict
        self.page_format = page_format

    def convert(
        self,
        path: str,
        force: bool = False,
        dry_run: bool = False,
    ) -> Report:
        """Convert `path`, publishing `<name>.<format>.cbz` atomically.

        Returns a `Report`. Raises `ArchiveError` only when no output could be
        produced at all; the exception carries the partial `report` so the caller
        can still name the pages that failed.
        """
        destination = destination_for(path, self.page_format)
        report = Report(source=path, destination=destination)

        # A dry run writes nothing, so an existing output cannot collide with it.
        if not dry_run and os.path.exists(destination) and not force:
            raise OutputExistsError(
                f"{destination} already exists; pass --force to overwrite it"
            )

        try:
            source = zipfile.ZipFile(path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            raise ArchiveError(f"cannot read {path}: {exc}", report) from exc

        # Taken after the archive opened, so a missing file is already an
        # ArchiveError above rather than a bare OSError from here.
        report.source_size_bytes = os.path.getsize(path)

        temp_path = None
        handle = None
        target = None
        try:
            with source:
                infos = _entries(source)
                plans = build_plan([i.filename for i in infos])
                if not dry_run:
                    temp_path, handle, target = self._open_temp(destination)

                try:
                    for info, plan in zip(infos, plans):
                        if target is not None:
                            self._process(info, plan, source, target, report)
                        else:
                            self._process_dry_run(info, plan, source, report)
                finally:
                    # ZipFile.close() does not close a handle it did not open,
                    # so the handle is closed here too. Until it is, the ZIP's
                    # buffer has not been flushed to the descriptor.
                    if target is not None:
                        target.close()
                    if handle is not None:
                        handle.close()

                if self.strict and report.failures:
                    raise ArchiveError(
                        f"{len(report.failures)} page(s) failed to convert "
                        f"and --strict was given; nothing written",
                        report,
                    )

                if temp_path is not None:
                    self._publish(temp_path, destination)
                    temp_path = None
                    report.output_size_bytes = os.path.getsize(destination)

            return report
        except ArchiveError as exc:
            report.abort_reason = str(exc)
            if exc.report is None:
                exc.report = report
            raise
        except zipfile.BadZipFile as exc:
            message = f"cannot read {path}: {exc}"
            report.abort_reason = message
            raise ArchiveError(message, report) from exc
        except OSError as exc:
            # A bad CRC surfaces here as BadZipFile; the rest are filesystem
            # problems, and calling them "cannot read the archive" would
            # misdescribe them.
            message = f"cannot write {destination}: {exc}"
            report.abort_reason = message
            raise ArchiveError(message, report) from exc
        finally:
            # Every exit path, including failure, removes the temp archive.
            if temp_path is not None:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _open_temp(self, destination: str):
        """Temp file in the destination directory, so os.replace is atomic.

        Returns `(temp_path, handle, target)`. The handle is returned rather than
        dropped because `ZipFile` will not close a file object it did not open,
        and an unflushed buffer would be fsynced as-is.
        """
        directory = os.path.dirname(destination) or "."
        handle = tempfile.NamedTemporaryFile(
            prefix=".cbx-jackal-",
            suffix=".cbz.tmp",
            dir=directory,
            delete=False,
        )
        temp_path = handle.name
        try:
            target = zipfile.ZipFile(
                handle, mode="w", compression=zipfile.ZIP_STORED, allowZip64=True
            )
        except Exception:
            handle.close()
            try:
                os.remove(temp_path)
            except OSError:
                pass
            raise
        return temp_path, handle, target

    def _publish(self, temp_path: str, destination: str) -> None:
        """fsync the bytes, then rename onto the destination."""
        # NamedTemporaryFile creates 0600. The output is an ordinary user file,
        # so give it the permissions a normal create would have produced rather
        # than a private mode the owner never asked for.
        umask = os.umask(0)
        os.umask(umask)
        os.chmod(temp_path, 0o666 & ~umask)

        file_descriptor = os.open(temp_path, os.O_RDONLY)
        try:
            os.fsync(file_descriptor)
        finally:
            os.close(file_descriptor)
        os.replace(temp_path, destination)

    def _process(
        self,
        info: zipfile.ZipInfo,
        plan: OutputPlan,
        source: zipfile.ZipFile,
        target: zipfile.ZipFile,
        report: Report,
    ) -> None:
        data = _read_entry(source, info)
        size = len(data)

        if not plan.transcode:
            target.writestr(_stored_info(plan, info), data)
            report.add(
                EntryOutcome(
                    name=plan.name,
                    classification=PASSED_THROUGH,
                    source_size=size,
                    output_size=size,
                )
            )
            return

        result = encode.run(
            self.cjxl,
            data,
            suffix=os.path.splitext(plan.name)[1],
            quality=self.quality,
        )
        # `encode.run` only sets ok=True alongside data, so the second half of
        # this guard is unreachable. It is spelled out because a page that
        # somehow succeeded without bytes must still leave a hole rather than
        # reach writestr as None.
        if not result.ok or result.data is None:
            # Original bytes, original name, original position. The hole is
            # visible in the archive and again in the exit code.
            passthrough_plan = OutputPlan(plan.name, plan.name, transcode=False)
            target.writestr(_stored_info(passthrough_plan, info), data)
            report.add(
                EntryOutcome(
                    name=plan.name,
                    classification=NOT_CONVERTED,
                    reason=result.error,
                    source_size=size,
                    output_size=size,
                )
            )
            return

        target.writestr(_stored_info(plan, info), result.data)
        report.add(
            EntryOutcome(
                name=plan.output_name,
                classification=CONVERTED,
                source_size=size,
                output_size=result.size,
            )
        )

    def _process_dry_run(
        self,
        info: zipfile.ZipInfo,
        plan: OutputPlan,
        source: zipfile.ZipFile,
        report: Report,
    ) -> None:
        """Classify and measure without writing anything.

        Every entry is read, not just the pages: a pass-through whose CRC is bad
        must fail the dry run exactly as it fails the real run, or the preview
        would promise an outcome the real run does not deliver.

        Pages are still encoded so the report can state real size figures rather
        than estimates, but the bytes land in a per-page temp file that
        `encode.run` removes before returning.
        """
        data = _read_entry(source, info)
        size = len(data)

        if not plan.transcode:
            report.add(
                EntryOutcome(
                    name=plan.name,
                    classification=PASSED_THROUGH,
                    source_size=size,
                    output_size=size,
                )
            )
            return

        result = encode.run(
            self.cjxl,
            data,
            suffix=os.path.splitext(plan.name)[1],
            quality=self.quality,
        )
        if result.ok:
            report.add(
                EntryOutcome(
                    name=plan.output_name,
                    classification=CONVERTED,
                    source_size=size,
                    output_size=result.size,
                )
            )
            return

        report.add(
            EntryOutcome(
                name=plan.name,
                classification=NOT_CONVERTED,
                reason=result.error,
                source_size=size,
                output_size=size,
            )
        )
