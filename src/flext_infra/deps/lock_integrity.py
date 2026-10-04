"""Committed generated TOML lock integrity verification.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import ClassVar, override

from flext_core import r
from flext_infra import c, p, t
from flext_infra.base import FlextInfraServiceBase


class FlextInfraLockIntegrityVerifier(FlextInfraServiceBase[bool]):
    """Verify the committed generated TOML locks of one repository root.

    Generated locks (``mise.lock``, ``uv.lock``) are projections that must
    never be merge-resolved: a textual merge concatenates tables and re-creates
    duplicate keys that surface far from the merge as cryptic resolver errors.
    The verifier parses each committed lock with the strict stdlib reader and
    fails naming the file, the parser cause, and every duplicated section.
    """

    _TABLE_HEADER: ClassVar[re.Pattern[str]] = re.compile(
        r"(?m)^[ \t]*(?:\[([^\][]+)\]|\[\[([^\][]+)\]\])[ \t]*(?:#.*)?$",
    )

    @classmethod
    def _duplicated_sections(cls, text: str) -> t.StrSequence:
        """Enumerate table headers declared more than once in a corrupt lock.

        Returns:
            The resulting ``t.StrSequence``.

        """
        counts: t.MutableMappingKV[str, int] = {}
        for match in cls._TABLE_HEADER.finditer(text):
            key = (match.group(1) or match.group(2) or "").strip()
            counts[key] = counts.get(key, 0) + 1
        return tuple(sorted(key for key, count in counts.items() if count > 1))

    @classmethod
    def _verify_lock(cls, lock_path: Path) -> t.StrSequence:
        """Verify one committed lock, returning zero or more failure causes.

        Returns:
            The resulting ``t.StrSequence``.

        """
        if not lock_path.is_file():
            return (f"{lock_path.name}: missing committed generated lock",)
        text = lock_path.read_text(encoding="utf-8")
        try:
            tomllib.loads(text)
        except tomllib.TOMLDecodeError as error:
            duplicated = cls._duplicated_sections(text)
            sections = (
                f"; duplicated sections: {', '.join(duplicated)}" if duplicated else ""
            )
            return (f"{lock_path.name}: {error}{sections}",)
        return ()

    @override
    def execute(self) -> p.Result[bool]:
        """Verify every committed generated TOML lock at the repository root.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        failures: t.StrSequence = tuple(
            failure
            for lock_filename in (c.Infra.MISE_LOCK_FILENAME, c.Infra.UV_LOCK_FILENAME)
            for failure in self._verify_lock(self.repository_root / lock_filename)
        )
        if failures:
            return r[bool].fail("; ".join(failures))
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraLockIntegrityVerifier"]
