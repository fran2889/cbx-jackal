"""CAP-5: verify the external toolchain before any archive is opened."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from typing import Iterable, Sequence

#: The tool every run needs. Never bundled.
TOOL = "cjxl"

#: The input-driven archiver. Needed only by inputs whose reader shells out to
#: it, so its check runs after expansion and only when such an input is present.
SEVENZIP = "7z"

#: `cjxl`'s guidance, verbatim apart from the tool name. One copy, shared by the
#: registry and the single-tool compatibility helper.
CJXL_GUIDANCE = (
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

#: `7z`'s guidance, verbatim apart from the tool name.
SEVENZIP_GUIDANCE = (
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


@dataclass(frozen=True)
class Tool:
    """One external tool: its name, install guidance and what its absence costs.

    `stops_run` is the severity. It records what a missing tool does to the run,
    not why the tool is needed: whether it is required by a flag or by an input
    is a fact about the caller, and only the caller knows it. That is what keeps
    this module free of both the CLI's flags and the reader registry.
    """

    name: str
    guidance: str
    stops_run: bool


#: Every external tool, by name. `missing` reads it, and the CLI stages the
#: checks by severity: stop-tools before expansion, input-driven ones after.
TOOLS: "dict[str, Tool]" = {
    TOOL: Tool(
        name=TOOL,
        guidance=CJXL_GUIDANCE.format(tool=TOOL),
        stops_run=True,
    ),
    SEVENZIP: Tool(
        name=SEVENZIP,
        guidance=SEVENZIP_GUIDANCE.format(tool=SEVENZIP),
        stops_run=False,
    ),
}


def find_tool(tool: str = TOOL) -> str | None:
    """Absolute path to `tool`, or None when it is not on PATH."""
    return shutil.which(tool)


def missing(names: Iterable[str]) -> list[Tool]:
    """The registered tools in `names` that are not on PATH.

    An unknown name is ignored rather than raising: the registry is the whole
    vocabulary here, and a caller naming something outside it has already made
    a mistake this cannot report.
    """
    absent: list[Tool] = []
    for name in names:
        tool = TOOLS.get(name)
        if tool is not None and find_tool(name) is None:
            absent.append(tool)
    return absent


def missing_message(tools: Sequence[Tool]) -> str:
    """One message naming every missing tool, in severity order.

    A header names them all; each block then carries that tool's own install
    guidance and says whether it stops the run or only skips the inputs that
    need it. Stop-severity tools come first, so the one that cannot be worked
    around is named before the one that can.
    """
    ordered = sorted(tools, key=lambda tool: not tool.stops_run)
    names = ", ".join(tool.name for tool in ordered)
    blocks = "\n\n".join(_tool_block(tool) for tool in ordered)
    # The header names them; it does not grade them. Calling an input-driven
    # tool "required" here would contradict its own block two lines down, and
    # contract 1.5 gives every tool its own severity line instead.
    return f"missing tools: {names}\n\n{blocks}"


def _tool_block(tool: Tool) -> str:
    """One tool's own block: what was missing, its severity and its guidance."""
    if tool.stops_run:
        severity = (
            f"{tool.name} is required for every run, so the run stops when it "
            f"is absent."
        )
    else:
        severity = (
            f"{tool.name} is needed only by some inputs, so only those inputs "
            f"are refused and the rest of the run continues."
        )
    return f"{tool.name} was not found on PATH.\n{severity}\n\n{tool.guidance}"


def missing_tool_message(tool: str = TOOL) -> str:
    """The one-tool message for `tool`, built by the shared message builder.

    Kept only for the existing suite: no production caller remains now that the
    CLI stages its checks through `missing` and `missing_message`. Removing it
    means editing the tests that use it, which this entry's acceptance criterion
    forbids; entry 10's refactor sweep is where that cleanup belongs. A
    registered name uses its own guidance; an unregistered one falls back to the
    `cjxl` guidance that has always named an arbitrary tool.
    """
    registered = TOOLS.get(tool)
    if registered is not None:
        return missing_message([registered])
    return missing_message(
        [
            Tool(
                name=tool,
                guidance=CJXL_GUIDANCE.format(tool=tool),
                stops_run=True,
            )
        ]
    )


def check(tool: str = TOOL) -> tuple[str | None, str | None]:
    """Preflight one tool.

    Returns `(resolved_path, error_message)`. Exactly one is None. Kept only for
    the existing suite, as `missing_tool_message` is: the CLI stages its checks
    through `missing` and `missing_message`, and entry 10 removes both.
    """
    resolved = find_tool(tool)
    if resolved is None:
        return None, missing_tool_message(tool)
    return resolved, None
