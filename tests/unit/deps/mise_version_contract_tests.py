"""Contract: the declared toolchain versions stay exact and lockable.

The 2026-09-29/30 fleet outage came from ``config/codegen.yaml`` declaring
``ast_grep_version: "0.45.3~7a027ead"`` (an aube resolved identity, not an npm
specifier) and ``jscpd_version: latest`` while ``mise.lock`` recorded the
resolved identity. ``mise install --locked`` then failed in every repository and
took the whole fleet CI red. These tests read the committed SSOT, the generated
``.mise.toml`` and ``mise.lock`` and refuse the recurrence.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from flext_tests import tm

from flext_infra import t

_REPO_ROOT = Path(__file__).resolve().parents[3]
_RESOLVED_IDENTITY_SEPARATOR = "~"


def _declared_versions(tools: t.JsonMapping) -> dict[str, str]:
    """Return the version string each declared mise tool carries."""
    versions: dict[str, str] = {}
    for name, entry in tools.items():
        if isinstance(entry, dict):
            value = entry.get("version")
            versions[name] = value if isinstance(value, str) else ""
        elif isinstance(entry, str):
            versions[name] = entry
        else:
            versions[name] = ""
    return versions


def _lock_specifiers(tools: t.JsonMapping) -> dict[str, set[str]]:
    """Return every specifier the committed lock records for each tool."""
    specifiers: dict[str, set[str]] = {}
    for name, entries in tools.items():
        recorded: set[str] = set()
        for entry in entries if isinstance(entries, list) else [entries]:
            if isinstance(entry, dict):
                specs = entry.get("specifiers")
                if isinstance(specs, list):
                    recorded.update(spec for spec in specs if isinstance(spec, str))
        specifiers[name] = recorded
    return specifiers


class TestsFlextInfraMiseVersionContract:
    """The declared toolchain versions stay exact and lockable."""

    @staticmethod
    def test_declared_versions_carry_no_resolved_identity() -> None:
        """No declared ``*_version`` value may embed a resolved identity."""
        source = (_REPO_ROOT / "config" / "codegen.yaml").read_text(encoding="utf-8")
        offenders = tuple(
            line.strip()
            for line in source.splitlines()
            if "_version" in line and _RESOLVED_IDENTITY_SEPARATOR in line
        )
        tm.that(offenders, eq=())

    @staticmethod
    def test_mise_tools_exist_in_the_committed_lock() -> None:
        """Every generated ``.mise.toml`` tool spec is recorded in the lock."""
        declared = _declared_versions(
            tomllib.loads((_REPO_ROOT / ".mise.toml").read_text(encoding="utf-8"))[
                "tools"
            ],
        )
        locked = _lock_specifiers(
            tomllib.loads((_REPO_ROOT / "mise.lock").read_text(encoding="utf-8"))[
                "tools"
            ],
        )
        missing = {
            name: version
            for name, version in declared.items()
            if version and version not in locked.get(name, set())
        }
        tm.that(missing, eq={})
