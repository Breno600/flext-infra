"""Tests that parsing a Make surface never runs an interpreter.

GNU Make expands every ``:=`` assignment while it parses, before it knows which
target was requested. A ``$(shell ...)`` that starts a Python interpreter is
therefore paid by *every* invocation -- ``make help`` included -- and, because
the verb dispatcher re-enters make for hook probing, it is paid several times
per command.

Values that need an interpreter belong in the recipe that consumes them, where
Make's lazy ``=`` assignment defers the cost to the one verb that needs it.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import pytest
from flext_tests import tm

import flext_infra
from flext_infra import c
from tests import t


class TestsFlextInfraMakeParseIsSideEffectFree:
    # ``$(shell ...)`` call marker. Assignment identity uses
    # c.Infra.MAKE_ASSIGNMENT_RE; immediacy is ``:=`` / ``::=`` (name token
    # ends with ``:`` before ``=``).
    _SHELL_CALL = re.compile(r"\$\(shell\b")
    # Executing an interpreter costs hundreds of milliseconds to seconds. Merely
    # *locating* one (`command -v python3`) is a cheap PATH lookup and is allowed:
    # the toolchain has to resolve its own interpreter before it can dispatch.
    _INTERPRETER_RUN = re.compile(
        r"(?<!command -v )(?:\buv run\b|\bpython[0-9.]*\s+-[cm]\b|\bnode\s+-e\b)"
    )

    def _repository_root(self) -> Path:
        """Return the repository root that owns this checkout."""
        return Path(__file__).resolve().parents[2]

    def _make_surfaces(self) -> t.VariadicTuple[Path]:
        """Return every Make surface plus the templates that generate them."""
        root = self._repository_root()
        names = (c.Infra.MAKEFILE_FILENAME, c.Infra.CUSTOM_MAKE_FILENAME)
        templates = Path(flext_infra.__file__).resolve().parent / "templates"
        return (
            *(path for name in names if (path := root / name).is_file()),
            *sorted(templates.rglob("*.mk.j2")),
        )

    def _is_immediate_shell_assignment(self, line: str) -> bool:
        """True when a column-0 Make assignment is immediate and calls $(shell)."""
        if c.Infra.MAKE_ASSIGNMENT_RE.match(line) is None:
            return False
        before_eq, sep, _after = line.partition("=")
        if sep != "=" or not before_eq.rstrip().endswith(":"):
            return False
        return (
            self._SHELL_CALL.search(line) is not None
            and self._INTERPRETER_RUN.search(line) is not None
        )

    def _interpreter_at_parse_time(self, surface: Path) -> t.VariadicTuple[str]:
        """Return immediate assignments that spawn an interpreter while parsing."""
        return tuple(
            f"{surface.name}:{number}: {line.strip()}"
            for number, line in enumerate(
                surface.read_text(encoding="utf-8").splitlines(), start=1
            )
            if self._is_immediate_shell_assignment(line)
        )

    def _silencing_lines(self, surface: Path) -> t.VariadicTuple[str]:
        """Return recipe lines that discard a command's exit status."""
        return tuple(
            f"{surface.name}:{number}: {line.strip()}"
            for number, line in enumerate(
                surface.read_text(encoding="utf-8").splitlines(), start=1
            )
            if line.startswith("\t") and "|| true" in line
        )

    @pytest.mark.parametrize(
        "scan_name",
        ["_interpreter_at_parse_time", "_silencing_lines"],
        ids=["no-interpreter-at-parse-time", "no-silenced-recipe-failure"],
    )
    def test_make_surfaces_preserve_execution_boundaries(self, scan_name: str) -> None:
        """Parsing starts no interpreter and recipes never swallow failures."""
        scan: Callable[[Path], t.VariadicTuple[str]] = getattr(self, scan_name)
        offenders = {
            surface.name: lines
            for surface in self._make_surfaces()
            if (lines := scan(surface))
        }

        tm.that(len(offenders), eq=0)
