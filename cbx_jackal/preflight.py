"""CAP-5: verify the external toolchain before any archive is opened."""

from __future__ import annotations

import shutil

TOOL = "cjxl"

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
