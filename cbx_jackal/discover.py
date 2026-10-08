"""Turn a command-line path into the list of archives to convert.

An argument is one of three things, and `expand` decides which in that order: a
wildcard pattern, a directory, or a literal path. All three land in one flat list
of archives, which is the whole trick -- it lets an owner with a 300-book library
point at a folder or a glob instead of writing a shell loop, without giving the
converter anything new to understand.

Four rules make expansion safe rather than merely convenient:

- **Only a path carrying metacharacters is globbed.** A literal path is handed on
  untouched, so an archive genuinely called `a*.cbz` is still converted, and
  globbing it can never quietly swap in a different file than the one named.
- **Filter by extension.** Otherwise a scan feeds `notes.txt` to `zipfile` and an
  ordinary folder becomes a wall of `cannot read` failures.
- **Skip symlinks found inside a scan**, for files as well as directories. A
  symlinked directory could loop forever, and two spellings of one archive would
  race for one destination, so the existing-output refusal would fire for reasons
  that look like a bug. A symlink *named on the command line* is followed,
  because the user named it; that is not a loop hazard.
- **Skip this tool's own output.** A `<stem>.<format>.cbz` for any declared
  format would otherwise be rescanned and become `a.jxl.jxl.cbz` on the second
  run over the same directory.

Order is deterministic: each directory's own entries are sorted, then descended
into depth-first, and pattern matches are sorted too -- `glob` returns
filesystem order, which is no more alphabetical than `os.scandir`'s. Without the
sort the report order and the winner of a collision would depend on filesystem
internals. A sort of the finished list is not needed -- output mirrors the input
tree, so `lib/a/book.cbz` and `lib/b/book.cbz` resolve to distinct outputs, and
the only collision a scan can produce is between two inputs in one directory.

Nothing found twice is converted twice. A directory argument alongside a file
inside it, or a pattern overlapping either, yields one path per archive: the
first mention wins and later ones collapse, because a second report block for the
same archive would otherwise either duplicate the output line or -- without
`--force` -- refuse an output this very run just wrote and downgrade a healthy
batch to exit 2.
"""

from __future__ import annotations

import glob
import os
import sys
from typing import Iterator

#: Extensions a scan or a pattern treats as an archive. Case-insensitive,
#: because comic libraries are full of `.CBZ`.
ARCHIVE_SUFFIXES = (".cbz", ".zip", ".cb7", ".7z", ".rar")

#: The container every output is written in, whatever the input was. `book.zip`
#: becomes `book.jxl.cbz`, never `book.jxl.zip`: once converted, a book is
#: indistinguishable from one that arrived as a `.cbz`, which is what keeps a
#: RAR or CB7 input honest about what it now is.
CONTAINER_SUFFIX = ".cbz"

#: The page formats an output may be named after. `jxl` is the only one that
#: converts today; `webp` arrives with its own entry, and adding it here is the
#: whole of what that entry needs to say about naming.
PAGE_FORMATS = ("jxl",)

#: The format used when `--format` is absent. Declared beside the set rather
#: than read off its end, so the default is a value the CLI can validate like
#: any other instead of one that silently escapes the check.
DEFAULT_FORMAT = "jxl"

#: What makes an argument a pattern rather than a literal path. `]` alone is not
#: magic: it is an ordinary character in a filename, and globbing on it would be
#: surprising for a reason no user asked for.
GLOB_MAGIC = ("*", "?", "[")


def output_suffix(page_format: str = DEFAULT_FORMAT) -> str:
    """The suffix an output in `page_format` carries: `.jxl.cbz` today.

    Raises `ValueError` for anything not declared in `PAGE_FORMATS`. The check
    belongs here rather than at the call sites because this is the one place an
    output name is built: a name this tool cannot produce is a name its own scan
    hands straight back in, and a format carrying a path separator would escape
    the input's directory besides.
    """
    if page_format not in PAGE_FORMATS:
        supported = ", ".join(PAGE_FORMATS)
        raise ValueError(
            f"unsupported page format {page_format!r}; "
            f"supported formats are {supported}"
        )
    return f".{page_format}{CONTAINER_SUFFIX}"


#: The suffix on every output when no `--format` is given. Derived rather than
#: written out, so it cannot drift from `output_suffix`. New code should prefer
#: `is_output_name`: a reader that filters on this constant quietly stops
#: covering WebP the day that format lands.
OUTPUT_SUFFIX = output_suffix()


def has_magic(name: str) -> bool:
    """Whether `name` is a pattern to expand rather than a literal path.

    A path with none of `GLOB_MAGIC` in it is never handed to `glob`, so an
    archive whose name really does contain `*` is converted rather than
    reinterpreted.
    """
    return any(character in name for character in GLOB_MAGIC)


def is_output_name(name: str) -> bool:
    """Whether `name` is an output this tool could have written.

    One suffix per declared format, not "any dotted word before `.cbz`". A
    `.cbz` this tool cannot name is still a book worth converting, and skipping
    it because its stem happens to contain a dot would drop it without a word;
    the day a second format is declared, its outputs are covered here by adding
    to `PAGE_FORMATS` and by nothing else.
    """
    lowered = name.lower()
    return any(
        lowered.endswith(output_suffix(page_format)) for page_format in PAGE_FORMATS
    )


def is_archive(name: str) -> bool:
    """Whether `name` is an input this tool converts.

    An output of this tool is excluded even though `.cbz` is in
    `ARCHIVE_SUFFIXES`, so rescanning a converted directory is a no-op rather
    than a second generation of output. Which names those are comes from
    `is_output_name`, the same declaration the output name is built from.
    """
    if is_output_name(name):
        return False
    return os.path.splitext(name)[1].lower() in ARCHIVE_SUFFIXES


def iter_pattern(pattern: str) -> list[str]:
    """The archives `pattern` matches, sorted.

    `glob` yields filesystem order, which is no more alphabetical than
    `os.scandir`'s, so this needs the same sort a directory scan gets.

    Matching is deliberately not recursive: `**` behaves as `*`, because
    `--recursive` is what governs descending into subdirectories, and letting a
    glob walk the tree too would give two flags' worth of behaviour for one. A
    subdirectory a pattern matches is not descended into -- a pattern names
    archives, and `isfile` is what keeps a directory called `old.cbz` from being
    handed to the converter. A symlink a pattern matches is followed when it
    resolves to a file, because the owner named it; only entries *found inside a
    scan* are checked for link-ness.
    """
    return sorted(
        match
        for match in glob.glob(pattern)
        if is_archive(os.path.basename(match)) and os.path.isfile(match)
    )


def iter_directory(directory: str, recursive: bool = False) -> Iterator[str]:
    """Yield the archive paths directly inside `directory`, sorted by name.

    With `recursive`, descends depth-first into subdirectories, each of its own
    entries sorted the same way.

    An `OSError` from the directory named here propagates: the owner asked for
    that directory by name, so failing to read it is a real error rather than an
    accident to shrug off. One raised further down does not -- see `_walk`.
    """
    return _walk(directory, recursive=recursive, nested=False)


def _walk(directory: str, recursive: bool, nested: bool) -> Iterator[str]:
    """One level of the scan, recursing into subdirectories.

    `nested` marks whether this level is somewhere the owner did not name
    directly, and so decides who absorbs a filesystem error: a skipped
    subdirectory is a warning and the rest of the tree is still work, whereas an
    unreadable named directory propagates.

    Paths are reported as written, never absolutised. The converter's
    `destination_for` resolves the destination on its own, so joining onto
    `directory` as typed is what echoes back the path the owner typed.
    """
    try:
        with os.scandir(directory) as entries:
            # Sorted before use: scandir's own order is filesystem-defined.
            found = sorted(entries, key=lambda entry: entry.name)
    except OSError as exc:
        if not nested:
            raise
        print(
            f"cbx-jackal: cannot read directory {directory}, skipping it: {exc}",
            file=sys.stderr,
        )
        return

    for entry in found:
        try:
            is_dir = entry.is_dir(follow_symlinks=False)
            is_file = entry.is_file(follow_symlinks=False)
        except OSError as exc:
            # Tolerated either way: an entry that cannot even be classified is
            # neither a directory to descend into nor an archive to convert.
            print(
                f"cbx-jackal: cannot stat {entry.path}, skipping it: {exc}",
                file=sys.stderr,
            )
            continue

        if is_dir:
            if recursive:
                yield from _walk(entry.path, recursive=True, nested=True)
        elif is_file and is_archive(entry.name):
            yield entry.path


def expand(paths: list[str], recursive: bool = False) -> list[str]:
    """Expand `paths` into the flat, deduplicated list of archives to convert.

    A directory becomes the archives it holds, recursively with `recursive`. A
    wildcard pattern becomes the archives it matches. Either coming up empty
    produces no work and no exit-code change: the owner pointed at a folder of
    metadata or a typo, and one note naming the argument is the whole response.
    A path that is neither -- a plain file, or one that does not exist -- is
    passed through untouched, so the converter reports it exactly as it always
    has.
    """
    expanded: list[str] = []
    seen: set[str] = set()

    def add(path: str) -> None:
        """Append `path` unless this archive has already been reached."""
        # Keyed on the path as written, so `lib/a.cbz` named twice collapses
        # while `lib/./a.cbz` and `lib/a.cbz` do not. That second case is a
        # caller mistake, and `normpath` would silence it by rewriting the path
        # the owner typed -- which is the path the report echoes back.
        if path not in seen:
            seen.add(path)
            expanded.append(path)

    for path in paths:
        if has_magic(path):
            matched = iter_pattern(path)
            for match in matched:
                add(match)
            if not matched:
                # Informational, not a warning, and to stdout for the reason the
                # empty-directory note is: a run that exits 0 should not have
                # written to the error stream.
                print(f"cbx-jackal: no archives matched {path}")
            continue

        if not os.path.isdir(path):
            add(path)
            continue

        try:
            found = list(iter_directory(path, recursive=recursive))
        except OSError:
            # An unreadable directory is not a scan that came up empty. Hand the
            # path on, so the converter reports `cannot read` for it exactly as
            # it does for any other path it cannot open.
            add(path)
            continue

        # Note emptiness, not novelty: a directory whose archives were all
        # already reached has work, and saying otherwise would be a lie.
        if not found:
            print(f"cbx-jackal: no archives found in {path}")

        for archive in found:
            add(archive)

    return expanded
