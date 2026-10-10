"""Read a CBZ in stored order, transcode its JPEG pages, write a new CBZ.

Ordering is a correctness property, not cosmetics. Entries are iterated in the
source's stored order verbatim -- no natural sort, no renumbering, no repair
of archives whose ordering is already wrong. Readers own the sort; this tool never
silently reorders a book. Because nothing is renumbered, a page that fails and is
copied through stays at its original index, so the book gets a hole rather than a
misnumbering.

Every entry written out is ZIP_STORED. JXL is already entropy-coded, so deflate
measured under 1% gain while costing real CPU on every page.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unicodedata
import zipfile
from dataclasses import dataclass
from typing import Callable, Protocol

from . import encode, preflight
from .discover import DEFAULT_FORMAT, output_suffix
from .report import CONVERTED, NOT_CONVERTED, PASSED_THROUGH, EntryOutcome, Report
from .geometry import compute_page_geometry, get_jpeg_dimensions, PageGeometry
from .resize import resize_page, ResizeResult
from .report_downscale import (
    PIXELS, ExtendedEntryOutcome, DownscaledInfo, SpreadInfo, DownscaleReport, 
    format_per_page_lines, format_run_level_mode
)

#: Extensions whose entries are handed to `cjxl`. Case-insensitive: comic
#: archives are full of `.JPG` and `.JPEG`.
JPEG_SUFFIXES = (".jpg", ".jpeg")

#: The JPEG SOI (Start Of Image) marker every JPEG file begins with. Used as a
#: presence check, not a parser: absence proves the entry is not a JPEG at all,
#: and it cannot reject a real one, however unusual its structure.
JPEG_MAGIC = b"\xff\xd8\xff"

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


@dataclass(frozen=True)
class EntryTemplate:
    """The per-entry metadata an output entry carries.

    The five fields are the ones a `zipfile.ZipInfo` offers that the output
    keeps: written timestamp, attributes, and comment. A source that has no
    notion of one of them supplies the default instead, never a guess.
    """

    date_time: tuple
    external_attr: int = 0
    internal_attr: int = 0
    create_system: int = 0
    comment: bytes = b""


#: The template a source gets when it offers none of its own. Fixed to the ZIP
#: epoch rather than read from the clock, so a converted book is byte-identical
#: across runs and a dry run can be compared against the real one. A reader
#: that can supply real values does; one that cannot degrades to this, and is
#: never refused for lacking them.
DEFAULT_ENTRY_TEMPLATE = EntryTemplate(date_time=(1980, 1, 1, 0, 0, 0))


class EntrySource(Protocol):
    """What any container must offer to be converted.

    Three things, no more: entry names in the order the source stores them,
    the bytes of one named entry, and an optional per-entry output template.
    The order is *supplied* -- a reader that staged its extraction to a
    directory and then walked it would return filesystem order, and the entry
    count and order guarantee would be unenforceable. A read that fails raises
    `ArchiveError` naming that entry. `template_for` returning `None` means
    the source has no notion of metadata and the documented default applies.

    A reader creates regular files only, if it touches the filesystem at all,
    inside a directory the tool owns, and cleans up on every exit path the
    way `encode.run` does. An entry that is a link or a device is refused
    rather than materialised.
    """

    def names_in_order(self) -> list[str]: ...

    def read(self, name: str) -> bytes: ...

    def template_for(self, name: str) -> EntryTemplate | None: ...

    def close(self) -> None: ...


class ZipSource:
    """The ZIP reader: stored order, bytes by name, metadata from `ZipInfo`."""

    def __init__(self, path: str) -> None:
        try:
            self._zip = zipfile.ZipFile(path, "r")
        except (zipfile.BadZipFile, OSError) as exc:
            raise ArchiveError(f"cannot read {path}: {exc}") from exc
        # Duplicate input names always collide as output names, so `build_plan`
        # refuses them before any read: a dict is faithful here.
        self._by_name = {info.filename: info for info in self._zip.infolist()}

    def names_in_order(self) -> list[str]:
        """Source entries in stored order, verbatim."""
        return [info.filename for info in self._zip.infolist()]

    def read(self, name: str) -> bytes:
        """Read one entry's full contents.

        A corrupt compressed stream or a bad CRC raises, which aborts the run:
        an archive we cannot read entries from is not safe to rewrite. So do
        an encrypted member and an unsupported compression method: both mean
        the same thing here, and both must arrive as an `ArchiveError` rather
        than a traceback.
        """
        info = self._info(name)
        chunks = []
        try:
            with self._zip.open(info, "r") as handle:
                while True:
                    chunk = handle.read(CHUNK)
                    if not chunk:
                        break
                    chunks.append(chunk)
        except (RuntimeError, NotImplementedError) as exc:
            # RuntimeError: encrypted member. NotImplementedError: compression
            # method this Python cannot decode.
            raise ArchiveError(
                f"cannot read {name}: {exc or type(exc).__name__}"
            ) from exc
        return b"".join(chunks)

    def template_for(self, name: str) -> EntryTemplate:
        """The entry's own timestamp and attributes, carried to the output."""
        info = self._info(name)
        return EntryTemplate(
            date_time=info.date_time,
            external_attr=info.external_attr,
            internal_attr=info.internal_attr,
            create_system=info.create_system,
            comment=info.comment,
        )

    def close(self) -> None:
        self._zip.close()

    def _info(self, name: str) -> zipfile.ZipInfo:
        info = self._by_name.get(name)
        if info is None:
            # Unreachable through `convert`, which only feeds back the names
            # the source itself supplied, but the seam is a public shape and
            # fails loudly here rather than by `None` dereference.
            raise ArchiveError(f"cannot read {name}: not in the archive")
        return info


#: The staging directory a `SevenZipSource` owns. Named apart from `encode.run`'s
#: per-page directory so a leak is attributable to the reader that caused it.
SEVENZIP_WORKDIR_PREFIX = "cbx-jackal-7z-"
UNRAR_WORKDIR_PREFIX = "cbx-jackal-unrar-"

#: The file-type bits of a POSIX `st_mode`, keyed by the first character of an
#: `ls -l` mode string. Spelled numerically rather than through `stat.S_IF*`,
#: because `stat` omits a few of these on Windows and the reader runs there too.
_MODE_TYPES = {
    "-": 0o100000,
    "d": 0o040000,
    "l": 0o120000,
    "b": 0o060000,
    "c": 0o020000,
    "p": 0o010000,
    "s": 0o140000,
}

#: The type mask, and the two kinds a staged extraction may materialise. Every
#: other kind -- link, device, fifo, socket -- is refused before extraction.
_MODE_TYPE_MASK = 0o170000
_REGULAR_OR_DIRECTORY = (0o100000, 0o040000)


@dataclass(frozen=True)
class _SevenZipEntry:
    """One `7z l -slt` block: a name plus what the output template needs."""

    name: str
    is_directory: bool
    date_time: tuple | None
    mode: int | None
    encrypted: bool


def _parse_mode(mode: str) -> int | None:
    """Octal `st_mode` from a 10-character `ls -l` mode string, or None."""
    if len(mode) != 10:
        return None
    base = _MODE_TYPES.get(mode[0])
    if base is None:
        return None
    value = base
    for who in range(3):
        digit = 0
        for position, char in enumerate(mode[1 + who * 3 : 4 + who * 3]):
            bit = 1 << (2 - position)
            if char in "rwx":
                digit |= bit
            elif char == "s":
                digit |= bit
                value |= 0o4000 if who == 0 else 0o2000
            elif char == "S":
                value |= 0o4000 if who == 0 else 0o2000
            elif char == "t":
                digit |= bit
                value |= 0o1000
            elif char == "T":
                value |= 0o1000
            elif char != "-":
                return None
        value |= digit << (3 * (2 - who))
    return value


def _mode_token(attributes: str) -> str | None:
    """The `ls -l` mode word in an `Attributes` value, or None.

    `7z` prints `Attributes = A -rw-r--r--` on POSIX and a bare flag word on a
    filesystem with no mode; only the ten-character word carries anything.
    """
    for token in attributes.split():
        if len(token) == 10 and token[0] in _MODE_TYPES:
            return token
    return None


def _parse_modified(value: str) -> tuple | None:
    """`(Y, M, D, h, m, s)` from `7z`'s `Modified` stamp, or None."""
    match = re.match(r"(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})", value)
    if match is None:
        return None
    return tuple(int(part) for part in match.groups())


def _sevenzip_entry(block: "dict[str, str]") -> _SevenZipEntry:
    """One parsed block, or None-worthy defaults where a field is absent.

    A directory's `Path` carries no trailing slash, unlike a ZIP's, and
    `classify` decides from the name alone. So the slash is restored here: a
    directory entry reaches the gate the way the ZIP path presents one, and the
    output keeps a directory where a directory was, instead of a zero-byte file.
    """
    mode_token = _mode_token(block.get("Attributes", ""))
    mode = _parse_mode(mode_token) if mode_token else None
    is_directory = mode_token is not None and mode_token[0] == "d"
    name = block["Path"]
    if is_directory and not name.endswith("/"):
        name += "/"
    return _SevenZipEntry(
        name=name,
        is_directory=is_directory,
        date_time=_parse_modified(block.get("Modified", "")),
        mode=mode,
        # `7z` marks an encrypted member in the listing, so the reader knows
        # before it extracts -- which is where it would otherwise emit its
        # unhelpful "Break signaled".
        encrypted=block.get("Encrypted", "").strip() == "+",
    )


def _parse_sevenzip_listing(text: str) -> list[_SevenZipEntry]:
    """The entry blocks of `7z l -slt`, in the order `7z` printed them.

    That order is the archive's stored order; nothing here sorts or walks. The
    archive's own header is a block too, but it carries `Physical Size` and
    `Headers Size` rather than a plain `Size`, so requiring `Path` and `Size`
    skips it without depending on the separator line.
    """
    entries: list[_SevenZipEntry] = []
    block: dict[str, str] = {}

    def flush() -> None:
        if "Path" in block and "Size" in block:
            entries.append(_sevenzip_entry(block))

    for line in text.splitlines():
        if not line.strip():
            flush()
            block = {}
            continue
        key, separator, value = line.partition(" = ")
        if separator:
            block[key] = value
    flush()
    return entries


@dataclass(frozen=True)
class _UnrarEntry:
    """One `unrar l` block: a name plus what the output template needs."""

    name: str
    is_directory: bool
    date_time: tuple | None
    mode: int | None
    encrypted: bool


def _parse_unrar_listing(text: str) -> list[_UnrarEntry]:
    """The entry blocks of `unrar l`, in the order `unrar` printed them.

    That order is the archive's stored order; nothing here sorts or walks.
    Unrar output is a simple table with columns: Attributes, Size, Date, Time, Name
    """
    entries: list[_UnrarEntry] = []
    
    lines = text.splitlines()
    in_table = False
    
    for line in lines:
        line = line.rstrip()
        
        # Skip header lines and separators
        if not line.strip():
            continue
        if line.startswith("UNRAR") or line.startswith("Archive:") or line.startswith("Details:"):
            continue
        if line.strip().startswith("--------"):
            # Separator line - if we see this after header, we're in the table
            in_table = True
            continue
        if "total" in line.lower():
            # End of table
            continue
        
        # Check if this is the header line
        if "Name" in line and ("Attributes" in line or "Size" in line):
            in_table = True
            continue
        
        # If we're in the table, parse the line
        if in_table and line.strip():
            # Skip lines that look like totals (mostly spaces and numbers)
            stripped = line.strip()
            if all(c in " 0123456789" for c in stripped):
                continue
            
            # Unrar table format: Attributes Size Date Time Name
            parts = line.split()
            
            if len(parts) >= 5:
                # We need: attributes, size, date, time, name
                name = parts[-1]
                if name and name not in ("Name", "Size", "Date", "Time", "Attributes") and not name.isdigit():
                    # Try to parse the metadata from the first parts
                    attributes = parts[0]
                    size_str = parts[1]
                    date_part = parts[2]
                    time_part = parts[3]
                    entries.append(_unrar_entry_from_parts(name, attributes, size_str, f"{date_part} {time_part}"))
            elif len(parts) >= 1:
                # Fallback: last token might be the filename
                name = parts[-1]
                if name and name not in ("Name", "Size", "Date", "Time", "Attributes") and not name.isdigit():
                    entries.append(_unrar_entry_from_parts(name, "", "", ""))
    
    return entries


def _unrar_entry_from_parts(name: str, attributes: str, size_str: str, date_time_str: str) -> _UnrarEntry:
    """Create UnrarEntry from parsed unrar table parts."""
    is_directory = name.endswith("/") or name.endswith("\\")
    
    # Parse date/time
    date_time = None
    try:
        from datetime import datetime
        # Try common formats: "2026-10-08 21:19"
        if date_time_str:
            for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
                try:
                    dt = datetime.strptime(date_time_str.strip(), fmt)
                    date_time = (dt.year, dt.month, dt.day, dt.hour, dt.minute, 0)
                    break
                except ValueError:
                    continue
    except (ValueError, ImportError):
        pass
    
    # Parse mode from attributes (e.g., "-rw-rw-r--")
    mode = None
    if attributes:
        mode = _parse_mode(attributes)
    
    # Check for encrypted flag - unrar shows this differently
    encrypted = False
    
    return _UnrarEntry(
        name=name,
        is_directory=is_directory,
        date_time=date_time,
        mode=mode,
        encrypted=encrypted
    )


def _sevenzip_diagnostic(completed: subprocess.CompletedProcess) -> str:
    """One line naming why `7z` failed, preferring its own `ERROR:` line."""
    text = completed.stderr.decode("utf-8", "replace")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("ERROR"):
            return stripped
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else f"7z exited {completed.returncode}"


def _run_sevenzip(arguments: list[str], path: str) -> subprocess.CompletedProcess:
    """Run `7z` non-interactively, turning a missing tool into an `ArchiveError`.

    stdin is closed, so `7z` can never block an unattended run on a prompt.
    """
    sevenzip = shutil.which(preflight.SEVENZIP)
    if sevenzip is None:
        raise ArchiveError(f"cannot read {path}: {preflight.SEVENZIP} was not found on PATH")
    try:
        return subprocess.run(
            [sevenzip, *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise ArchiveError(f"cannot read {path}: {exc}") from exc


def _unrar_diagnostic(completed: subprocess.CompletedProcess) -> str:
    """One line naming why `unrar` failed."""
    text = completed.stderr.decode("utf-8", "replace")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return f"unrar exited {completed.returncode}"


def _run_unrar(arguments: list[str], path: str) -> subprocess.CompletedProcess:
    """Run `unrar` non-interactively, turning a missing tool into an `ArchiveError`.

    stdin is closed, so `unrar` can never block an unattended run on a prompt.
    """
    unrar = shutil.which(preflight.UNRAR)
    if unrar is None:
        raise ArchiveError(f"cannot read {path}: {preflight.UNRAR} was not found on PATH")
    try:
        return subprocess.run(
            [unrar, *arguments],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise ArchiveError(f"cannot read {path}: {exc}") from exc


class SevenZipSource:
    """The CB7/7Z reader: a staged extraction behind the same seam as ZIP.

    `7z l -slt` supplies the entry order and each entry's metadata *before* any
    extraction, so nothing walks the extracted tree. The listing is read first
    so a link or device entry is refused before `7z x` could materialise it.
    Extraction is one `7z x` into a temp directory this reader owns; `close`
    removes it on every exit path `Converter.convert` takes.
    """

    def __init__(self, path: str) -> None:
        self._workdir = tempfile.mkdtemp(prefix=SEVENZIP_WORKDIR_PREFIX)
        try:
            # l = list contents, -slt = show technical information for that listing.
            listing = _run_sevenzip(["l", "-slt", path], path)
            if listing.returncode != 0:
                raise ArchiveError(
                    f"cannot read {path}: {_sevenzip_diagnostic(listing)}"
                )
            self._entries = _parse_sevenzip_listing(
                listing.stdout.decode("utf-8", "replace")
            )
            self._refuse_encrypted(path)
            self._refuse_links(path)
            self._by_name = {entry.name: entry for entry in self._entries}
            self._extract(path)
        except BaseException:
            # Every exit path, including a failure while listing, removes the
            # staging directory this reader created.
            self.close()
            raise

    def _refuse_encrypted(self, path: str) -> None:
        """Refuse the whole source, by name, if any entry needs a password.

        Refused from the listing rather than left to extraction, which is where
        `7z` reports only "Break signaled" -- and refused rather than skipped,
        because the output is rebuilt from entries that must be read, so there
        is no pass-through answer. The owner gets a line saying what it is, and
        every other input in the run still converts.
        """
        for entry in self._entries:
            if entry.encrypted:
                raise ArchiveError(
                    f"cannot read {path}: {entry.name!r} is encrypted; "
                    f"cbx-jackal cannot supply a password"
                )

    def _refuse_links(self, path: str) -> None:
        """Refuse the whole source before `7z x` if any entry is not a file.

        Extraction is all-or-nothing into one tree, so a link cannot be skipped
        while the rest is served; the alternative to refusing is materialising
        it, which contract 1.6 forbids. A hard link shows up as a regular file
        in the listing, so only a typed link or device is caught here.
        """
        for entry in self._entries:
            if entry.mode is None:
                continue
            if (entry.mode & _MODE_TYPE_MASK) not in _REGULAR_OR_DIRECTORY:
                raise ArchiveError(
                    f"cannot read {path}: refusing to materialise {entry.name!r}, "
                    f"which is a link or a device, not a regular file"
                )

    def _extract(self, path: str) -> None:
        # x = eXtract with full paths, -y = assume yes on all queries, -o = output directory.
        extraction = _run_sevenzip(["x", "-y", f"-o{self._workdir}", path], path)
        if extraction.returncode != 0:
            raise ArchiveError(
                f"cannot read {path}: {_sevenzip_diagnostic(extraction)}"
            )

    def names_in_order(self) -> list[str]:
        """Source entries in `7z l -slt`'s order, verbatim."""
        return [entry.name for entry in self._entries]

    def read(self, name: str) -> bytes:
        """Read one extracted entry's full contents.

        A directory entry has no bytes of its own, so it reads as empty, the
        same answer `zipfile` gives for a directory member.
        """
        entry = self._entry(name)
        target = os.path.join(self._workdir, name)
        if entry.is_directory or os.path.isdir(target):
            return b""
        try:
            with open(target, "rb") as handle:
                return handle.read()
        except OSError as exc:
            raise ArchiveError(f"cannot read {name}: {exc}") from exc

    def template_for(self, name: str) -> EntryTemplate | None:
        """The entry's own timestamp and mode, carried to the output.

        Returns None only when the listing carried neither, so the documented
        default applies: a reader that can supply real values does. The mode is
        a Unix `st_mode`, so it lands in `external_attr` as `mode << 16` with a
        Unix `create_system`, exactly the shape a ZIP entry carries it in.
        """
        entry = self._entry(name)
        if entry.date_time is None and entry.mode is None:
            return None
        return EntryTemplate(
            date_time=entry.date_time or DEFAULT_ENTRY_TEMPLATE.date_time,
            external_attr=(entry.mode << 16) if entry.mode is not None else 0,
            create_system=3 if entry.mode is not None else 0,
        )

    def close(self) -> None:
        """Remove the staging directory; safe to call more than once."""
        shutil.rmtree(self._workdir, ignore_errors=True)

    def _entry(self, name: str) -> _SevenZipEntry:
        entry = self._by_name.get(name)
        if entry is None:
            # Unreachable through `convert`, which only feeds back the names
            # the source itself supplied, but the seam is a public shape and
            # fails loudly here rather than by `None` dereference.
            raise ArchiveError(f"cannot read {name}: not in the archive")
        return entry


class UnrarSource:
    """The RAR/CBR reader: a staged extraction behind the same seam as ZIP.

    `unrar l` supplies the entry order and each entry's metadata *before* any
    extraction, so nothing walks the extracted tree. The listing is read first
    so a link or device entry is refused before `unrar x` could materialise it.
    Extraction is one `unrar x` into a temp directory this reader owns; `close`
    removes it on every exit path `Converter.convert` takes.
    
    Note: There is no fallback to 7z for RAR/CBR files - unrar is always required.
    """

    def __init__(self, path: str) -> None:
        self._workdir = tempfile.mkdtemp(prefix=UNRAR_WORKDIR_PREFIX)
        try:
            # l = list contents, same command letter 7z uses.
            listing = _run_unrar(["l", path], path)
            if listing.returncode != 0:
                raise ArchiveError(
                    f"cannot read {path}: {_unrar_diagnostic(listing)}"
                )
            self._entries = _parse_unrar_listing(
                listing.stdout.decode("utf-8", "replace")
            )
            self._refuse_encrypted(path)
            self._refuse_links(path)
            self._by_name = {entry.name: entry for entry in self._entries}
            self._extract(path)
        except BaseException:
            # Every exit path, including a failure while listing, removes the
            # staging directory this reader created.
            self.close()
            raise

    def _refuse_encrypted(self, path: str) -> None:
        """Refuse the whole source, by name, if any entry needs a password."""
        for entry in self._entries:
            if entry.encrypted:
                raise ArchiveError(
                    f"cannot read {path}: {entry.name!r} is encrypted; "
                    f"cbx-jackal cannot supply a password"
                )

    def _refuse_links(self, path: str) -> None:
        """Refuse the whole source before `unrar x` if any entry is not a file."""
        for entry in self._entries:
            if entry.mode is None:
                continue
            if (entry.mode & _MODE_TYPE_MASK) not in _REGULAR_OR_DIRECTORY:
                raise ArchiveError(
                    f"cannot read {path}: refusing to materialise {entry.name!r}, "
                    f"which is a link or a device, not a regular file"
                )

    def _extract(self, path: str) -> None:
        # x = extract with full paths, -y = assume Yes on all queries.
        extraction = _run_unrar(["x", "-y", path, self._workdir], path)
        if extraction.returncode != 0:
            raise ArchiveError(
                f"cannot read {path}: {_unrar_diagnostic(extraction)}"
            )

    def names_in_order(self) -> list[str]:
        """Source entries in `unrar l`'s order, verbatim."""
        return [entry.name for entry in self._entries]

    def read(self, name: str) -> bytes:
        """Read one extracted entry's full contents."""
        entry = self._entry(name)
        target = os.path.join(self._workdir, name)
        if entry.is_directory or os.path.isdir(target):
            return b""
        try:
            with open(target, "rb") as handle:
                return handle.read()
        except OSError as exc:
            raise ArchiveError(f"cannot read {name}: {exc}") from exc

    def template_for(self, name: str) -> EntryTemplate | None:
        """The entry's own timestamp and mode, carried to the output."""
        entry = self._entry(name)
        if entry.date_time is None and entry.mode is None:
            return None
        return EntryTemplate(
            date_time=entry.date_time or (),
            external_attr=(entry.mode << 16) if entry.mode else 0,
        )

    def _entry(self, name: str) -> "_UnrarEntry":
        entry = self._by_name.get(name)
        if entry is None:
            raise ArchiveError(f"cannot read {name}: {name!r} not in archive")
        return entry

    def close(self) -> None:
        """Remove the staging directory and its contents."""
        shutil.rmtree(self._workdir, ignore_errors=True)

    def __enter__(self) -> "UnrarSource":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


#: Readers by recognised input suffix, lowercase. This map and
#: `discover.ARCHIVE_SUFFIXES` are extended together: a suffix is an input
#: exactly when a reader is registered for it here.
SOURCE_READERS: "dict[str, Callable[[str], EntrySource]]" = {
    ".cbz": ZipSource,
    ".zip": ZipSource,
    ".cb7": SevenZipSource,
    ".7z": SevenZipSource,
    ".rar": UnrarSource,
    ".cbr": UnrarSource,
    ".cbt": UnrarSource,
}


def requires_sevenzip(path: str) -> bool:
    """Whether opening `path` will need `7z` on PATH.

    Read off the registry rather than a second suffix list, so registering a
    reader is the only edit a new container needs. A suffix no reader claims
    needs no tool here: `open_source` refuses it as unreadable before any tool
    is required.
    """
    return SOURCE_READERS.get(os.path.splitext(path)[1].lower()) is SevenZipSource


def requires_unrar(path: str) -> bool:
    """Whether opening `path` will need `unrar` on PATH.

    Read off the registry rather than a second suffix list, so registering a
    reader is the only edit a new container needs. A suffix no reader claims
    needs no tool here: `open_source` refuses it as unreadable before any tool
    check runs. There is no fallback to 7z for RAR/CBR/CBT files.
    """
    return SOURCE_READERS.get(os.path.splitext(path)[1].lower()) is UnrarSource


def open_source(path: str) -> EntrySource:
    """Open `path` with the reader its recognised suffix names.

    No fallback and no sniffing: a file whose suffix no reader claims is an
    unreadable archive, exit 1, the answer it gives today. By-content
    detection belongs to a reader at open time, which is where the
    measurement put it.
    """
    suffix = os.path.splitext(path)[1].lower()
    reader = SOURCE_READERS.get(suffix)
    if reader is None:
        raise ArchiveError(f"cannot read {path}: no reader for {suffix!r}")
    return reader(path)


#: The years a ZIP's DOS date can carry: the field is seven bits from 1980.
_ZIP_MIN_YEAR, _ZIP_MAX_YEAR = 1980, 2107


def _zip_date_time(date_time: tuple) -> tuple:
    """A timestamp ZIP can store, or the documented default when it cannot.

    `zipfile` raises below 1980 and overflows its struct above 2107, and a
    source's stamp is not something this tool can vouch for -- `7z` stores a
    1970 epoch for a file with no usable mtime, and a crafted archive can carry
    anything. A traceback is not the answer; the default is, which is exactly
    what a source with no timestamp gets.
    """
    if len(date_time) != 6 or not _ZIP_MIN_YEAR <= date_time[0] <= _ZIP_MAX_YEAR:
        return DEFAULT_ENTRY_TEMPLATE.date_time
    return date_time


def _stored_info(plan: OutputPlan, template: EntryTemplate) -> zipfile.ZipInfo:
    """A fresh ZipInfo for the output, preserving name, timestamp and attrs."""
    info = zipfile.ZipInfo(plan.output_name, date_time=_zip_date_time(template.date_time))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = template.external_attr
    info.internal_attr = template.internal_attr
    info.create_system = template.create_system
    info.comment = template.comment
    return info


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
        max_width: int | None = None,
        max_height: int | None = None,
        magick: str | None = None,
    ):
        if not cjxl:
            raise ArchiveError("cjxl path is required; run the preflight first")
        self.cjxl = cjxl
        self.quality = quality
        self.strict = strict
        self.page_format = page_format
        self.max_width = max_width
        self.max_height = max_height
        self.magick = magick
        # Box is requested if either dimension bound is set
        self.box_requested = max_width is not None or max_height is not None

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
            source = open_source(path)
        except ArchiveError as exc:
            # The message, not any report, names the input here: no entry
            # outcome exists yet, so the CLI prints the bare reason either
            # way. The report is attached only so an `ArchiveError` out of
            # `convert` still always carries one, as it did before the seam.
            raise ArchiveError(str(exc), report) from exc

        # Taken after the archive opened, so a missing file is already an
        # ArchiveError above rather than a bare OSError from here.
        report.source_size_bytes = os.path.getsize(path)

        temp_path = None
        handle = None
        target = None
        try:
            try:
                names = source.names_in_order()
                plans = build_plan(names)
                if not dry_run:
                    temp_path, handle, target = self._open_temp(destination)

                try:
                    for name, plan in zip(names, plans):
                        if target is not None:
                            self._process(name, plan, source, target, report)
                        else:
                            self._process_dry_run(name, plan, source, report)
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
            finally:
                source.close()

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
        name: str,
        plan: OutputPlan,
        source: EntrySource,
        target: zipfile.ZipFile,
        report: Report,
    ) -> None:
        data = source.read(name)
        size = len(data)
        template = source.template_for(name) or DEFAULT_ENTRY_TEMPLATE

        if not plan.transcode:
            target.writestr(_stored_info(plan, template), data)
            report.add(
                EntryOutcome(
                    name=plan.name,
                    classification=PASSED_THROUGH,
                    source_size=size,
                    output_size=size,
                )
            )
            return

        if not data.startswith(JPEG_MAGIC):
            # The name says JPEG, the bytes do not. `cjxl` sniffs content and
            # would happily encode a PNG or an XML file under a `.jxl` name, so
            # the check has to happen here rather than be left to it. Absence of
            # the SOI marker proves only that this is not a JPEG; it says
            # nothing about what it is, so the reason does not guess.
            passthrough_plan = OutputPlan(plan.name, plan.name, transcode=False)
            target.writestr(_stored_info(passthrough_plan, template), data)
            report.add(
                EntryOutcome(
                    name=plan.name,
                    classification=NOT_CONVERTED,
                    reason="not a JPEG",
                    source_size=size,
                    output_size=size,
                )
            )
            return

        # Check if downscaling is needed for this JPEG page
        processed_data = data
        # A downscaled page spends its quality at the intermediate and is then
        # preserved losslessly. Encoding it again at `self.quality` would be a
        # second lossy pass over damage the resample has already done, and it
        # measures worse and larger than encoding nothing at all.
        encode_quality = self.quality
        downscaled_info = None
        spread_info = None
        recoverability = None
        
        if self.box_requested and self.magick:
            # Extract dimensions from JPEG
            jpeg_dims = get_jpeg_dimensions(data)
            if jpeg_dims is not None:
                jpeg_width, jpeg_height = jpeg_dims
                
                # Compute page geometry including EXIF orientation and spread detection
                page_geometry = compute_page_geometry(
                    data, jpeg_width, jpeg_height, self.max_width, self.max_height
                )
                
                if page_geometry is not None:
                    if page_geometry.is_spread:
                        # Spread pages are exempt from downscaling
                        spread_info = SpreadInfo(
                            display_width=page_geometry.display_width,
                            display_height=page_geometry.display_height
                        )
                        recoverability = PIXELS  # Spreads keep original pixels
                    elif page_geometry.needs_downscale:
                        # Need to downscale this page
                        resize_result = resize_page(
                            self.magick,
                            data,
                            jpeg_width,
                            jpeg_height,
                            self.max_width,
                            self.max_height,
                            quality=self.quality
                        )
                        
                        if resize_result.ok and resize_result.data is not None:
                            processed_data = resize_result.data
                            downscaled_info = DownscaledInfo(
                                original_width=resize_result.original_width,
                                original_height=resize_result.original_height,
                                target_width=resize_result.target_width,
                                target_height=resize_result.target_height
                            )
                            # JPEG intermediate means pixels are recoverable but source JPEG is not
                            recoverability = PIXELS
                            # The quality was spent at the intermediate above;
                            # what is left is to preserve it, not re-encode it.
                            encode_quality = None
                        # If resize failed, continue with original data and it will fail in cjxl

        result = encode.run(
            self.cjxl,
            processed_data,
            suffix=os.path.splitext(plan.name)[1],
            quality=encode_quality,
        )
        # `encode.run` only sets ok=True alongside data, so the second half of
        # this guard is unreachable. It is spelled out because a page that
        # somehow succeeded without bytes must still leave a hole rather than
        # reach writestr as None.
        if not result.ok or result.data is None:
            # Original bytes, original name, original position. The hole is
            # visible in the archive and again in the exit code.
            passthrough_plan = OutputPlan(plan.name, plan.name, transcode=False)
            target.writestr(_stored_info(passthrough_plan, template), data)
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

        target.writestr(_stored_info(plan, template), result.data)
        
        # Create extended outcome for reporting if this is a JPEG with downscaling/spread info
        if downscaled_info is not None or spread_info is not None:
            extended_outcome = ExtendedEntryOutcome(
                name=plan.output_name,
                classification=CONVERTED,
                source_size=size,
                output_size=result.size,
                downscaled=downscaled_info,
                spread=spread_info,
                recoverability=recoverability
            )
            # Add to a separate tracking or extend the existing report
            # For now, we'll use the regular EntryOutcome and handle extended reporting separately
            report.add(
                EntryOutcome(
                    name=plan.output_name,
                    classification=CONVERTED,
                    source_size=size,
                    output_size=result.size,
                )
            )
            
            # Store extended info for later reporting
            if not hasattr(report, '_extended_outcomes'):
                report._extended_outcomes = []
            report._extended_outcomes.append(extended_outcome)
        else:
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
        name: str,
        plan: OutputPlan,
        source: EntrySource,
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
        data = source.read(name)
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

        if not data.startswith(JPEG_MAGIC):
            # Same check as the writing path, reported the same way so a dry
            # run predicts the exit code a real run would produce.
            report.add(
                EntryOutcome(
                    name=plan.name,
                    classification=NOT_CONVERTED,
                    reason="not a JPEG",
                    source_size=size,
                    output_size=size,
                )
            )
            return

        # Check if downscaling is needed for this JPEG page
        processed_data = data
        # A downscaled page spends its quality at the intermediate and is then
        # preserved losslessly. Encoding it again at `self.quality` would be a
        # second lossy pass over damage the resample has already done, and it
        # measures worse and larger than encoding nothing at all.
        encode_quality = self.quality
        downscaled_info = None
        spread_info = None
        recoverability = None
        
        if self.box_requested and self.magick:
            # Extract dimensions from JPEG
            jpeg_dims = get_jpeg_dimensions(data)
            if jpeg_dims is not None:
                jpeg_width, jpeg_height = jpeg_dims
                
                # Compute page geometry including EXIF orientation and spread detection
                page_geometry = compute_page_geometry(
                    data, jpeg_width, jpeg_height, self.max_width, self.max_height
                )
                
                if page_geometry is not None:
                    if page_geometry.is_spread:
                        # Spread pages are exempt from downscaling
                        spread_info = SpreadInfo(
                            display_width=page_geometry.display_width,
                            display_height=page_geometry.display_height
                        )
                        recoverability = PIXELS  # Spreads keep original pixels
                    elif page_geometry.needs_downscale:
                        # Need to downscale this page
                        resize_result = resize_page(
                            self.magick,
                            data,
                            jpeg_width,
                            jpeg_height,
                            self.max_width,
                            self.max_height,
                            quality=self.quality
                        )
                        
                        if resize_result.ok and resize_result.data is not None:
                            processed_data = resize_result.data
                            downscaled_info = DownscaledInfo(
                                original_width=resize_result.original_width,
                                original_height=resize_result.original_height,
                                target_width=resize_result.target_width,
                                target_height=resize_result.target_height
                            )
                            # JPEG intermediate means pixels are recoverable but source JPEG is not
                            recoverability = PIXELS
                            # The quality was spent at the intermediate above;
                            # what is left is to preserve it, not re-encode it.
                            encode_quality = None
                        # If resize failed, continue with original data and it will fail in cjxl

        result = encode.run(
            self.cjxl,
            processed_data,
            suffix=os.path.splitext(plan.name)[1],
            quality=encode_quality,
        )
        
        if result.ok:
            # Store extended info for later reporting if this is a downscaled or spread page
            if downscaled_info is not None or spread_info is not None:
                extended_outcome = ExtendedEntryOutcome(
                    name=plan.output_name,
                    classification=CONVERTED,
                    source_size=size,
                    output_size=result.size,
                    downscaled=downscaled_info,
                    spread=spread_info,
                    recoverability=recoverability
                )
                # Store extended info for later reporting
                if not hasattr(report, '_extended_outcomes'):
                    report._extended_outcomes = []
                report._extended_outcomes.append(extended_outcome)
            
            report.add(
                EntryOutcome(
                    name=plan.output_name,
                    classification=CONVERTED,
                    source_size=size,
                    output_size=result.size,
                )
            )
            return

        # For failed cases, still store extended info if we had downscaling/spread detection
        if downscaled_info is not None or spread_info is not None:
            extended_outcome = ExtendedEntryOutcome(
                name=plan.name,
                classification=NOT_CONVERTED,
                reason=result.error,
                source_size=size,
                output_size=size,
                downscaled=downscaled_info,
                spread=spread_info,
                recoverability=recoverability
            )
            # Store extended info for later reporting
            if not hasattr(report, '_extended_outcomes'):
                report._extended_outcomes = []
            report._extended_outcomes.append(extended_outcome)

        report.add(
            EntryOutcome(
                name=plan.name,
                classification=NOT_CONVERTED,
                reason=result.error,
                source_size=size,
                output_size=size,
            )
        )
