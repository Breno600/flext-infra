"""Tests that generation formats TOML with the locked Taplo identity.

The configuration declares the moving selector; only ``make upg`` resolves it,
into the committed ``mise.lock``. Generation must therefore read the pinned
release and never ask a tool manager to resolve a version mid-run: a missing
lock is a loud failure, not a silent acceptance of whatever binary the host
exposes or a network lookup.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

import flext_infra
from flext_infra import c, config, p, u


class TestsFlextInfraGenUsesLockedTaploIdentity:
    """The formatter identity comes from the lock, never from resolution."""

    _SOURCE = "a = 1\n\n[tool]\nb = 2\n"

    @staticmethod
    def _toolchain_root(tmp_path: Path, lock_body: str | None) -> Path:
        """Build a toolchain root holding the declared config and *lock_body*.

        Returns:
            The resulting ``Path``.

        """
        root = tmp_path / "toolchain"
        root.mkdir()
        (root / c.Infra.TAPLO_CONFIG_FILENAME).write_text("", encoding="utf-8")
        if lock_body is not None:
            (root / c.Infra.MISE_LOCK_FILENAME).write_text(lock_body, encoding="utf-8")
        return root

    def _format(self, root: Path, declared: str) -> p.Result[str]:
        """Format through the public utility facade for the given selector.

        Returns:
            The resulting ``p.Result[str]``.

        """
        return u.Infra.format_toml_source(
            self._SOURCE,
            path=root / c.PYPROJECT_FILENAME,
            toolchain_root=root,
            taplo_version=declared,
        )

    def test_missing_lock_fails_loud(self, tmp_path: Path) -> None:
        """An absent ``mise.lock`` is never replaced by host resolution."""
        root = self._toolchain_root(tmp_path, None)

        result = self._format(root, c.Infra.MISE_MOVING_SELECTOR)

        tm.that(result.failure, eq=True)
        tm.that(c.Infra.MISE_LOCK_FILENAME in (result.error or ""), eq=True)

    def test_missing_lock_entry_fails_loud(self, tmp_path: Path) -> None:
        """A lock without the pinned entry never falls back to a shim."""
        root = self._toolchain_root(tmp_path, "[tools]\n")

        result = self._format(root, c.Infra.MISE_MOVING_SELECTOR)

        tm.that(result.failure, eq=True)
        tm.that(c.Infra.MISE_LOCK_FILENAME in (result.error or ""), eq=True)

    def test_declared_repository_lock_satisfies_the_identity(self) -> None:
        """The live checkout formats with its own committed lock, as configured."""
        root = Path(flext_infra.__file__).resolve().parents[2]

        formatted = tm.ok(
            self._format(root, config.Infra.codegen.toolchain.taplo_version),
        )
        payload = u.Cli.toml_mapping_from_text(formatted)

        tm.that(payload is not None, eq=True)
        tool = dict(payload or {}).get("tool")
        tm.that(dict(tool or {}), eq={"b": 2})
