"""CAP-5: verify the external toolchain before any archive is opened."""

from __future__ import annotations

import shutil

TOOL = "cjxl"

#: The input-driven archiver. Needed only by inputs whose reader shells out to
#: it, so its check runs after expansion and only when such an input is present.
SEVENZIP = "7z"

MISSING_TOOL_MESSAGE = (
    "{tool} was not found on PATH.\n"
    "\n"
    "cbx-jackal shells out to {tool} from the libjxl tools package; it is never\n"
    "bundled, because two libjxl copies on one host fight over global decoder\n"
    "handler registration and the wrong one can win silently.\n"
    "\n"
    "Install it for your platform, then re-run:\n"
    "\n"
    "  linux    apt install libjxl-tools        (or your distro's equivalent)\n"
    "  mac      brew install libjxl\n"
    "  windows  libjxl release build on PATH,   or a package manager\n"
    "\n"
    "See README.md -> Installing cjxl for full instructions."
)

SEVENZIP_MISSING_MESSAGE = (
    "{tool} was not found on PATH.\n"
    "\n"
    "cbx-jackal shells out to {tool} to read CB7 and 7Z archives; it is never\n"
    "bundled, because no standard-library module reads those containers.\n"
    "\n"
    "Install it for your platform, then re-run:\n"
    "\n"
    "  linux    apt install p7zip-full        (or your distro's equivalent)\n"
    "  mac      brew install sevenzip\n"
    "  windows  7-Zip release build on PATH,  or a package manager\n"
    "\n"
    "See README.md for installation instructions."
)


def missing_tool_message(tool: str = TOOL) -> str:
    """Platform-neutral guidance naming the tool, with no stack trace."""
    return MISSING_TOOL_MESSAGE.format(tool=tool)


def find_tool(tool: str = TOOL) -> str | None:
    """Absolute path to `tool`, or None when it is not on PATH."""
    return shutil.which(tool)


def check(tool: str = TOOL) -> tuple[str | None, str | None]:
    """Preflight the external tool.

    Returns `(resolved_path, error_message)`. Exactly one is None. Callers must
    abort on an error message *before* opening any archive.
    """
    resolved = find_tool(tool)
    if resolved is None:
        return None, missing_tool_message(tool)
    return resolved, None


def check_sevenzip() -> tuple[str | None, str | None]:
    """Preflight `7z`, the tool only some inputs need.

    Returns `(resolved_path, error_message)` exactly as `check` does, but with
    the guidance that fits the archiver rather than libjxl.
    """
    resolved = find_tool(SEVENZIP)
    if resolved is None:
        return None, SEVENZIP_MISSING_MESSAGE.format(tool=SEVENZIP)
    return resolved, None
