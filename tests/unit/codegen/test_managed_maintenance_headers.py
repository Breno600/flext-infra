"""Contracts for continuously managed artifact maintenance headers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import t, u

pytestmark = pytest.mark.slow


class TestsFlextInfraManagedMaintenanceHeaders:
    """Validate machine-readable maintenance metadata on rendered artifacts."""

    @staticmethod
    def _fields(text: str) -> t.MutableMappingKV[str, str]:
        fields: t.MutableMappingKV[str, str] = {}
        for line in text.splitlines():
            marker = line.lstrip("# ")
            if not marker.startswith("@flext-") or ":" not in marker:
                continue
            key, value = marker.split(":", 1)
            fields[key] = value.strip()
        return fields

    def test_live_managed_owners_publish_regeneration_contract(
        self,
        tmp_path: Path,
    ) -> None:
        """Publish the real owner and canonical regeneration command."""
        makefile_fields = self._fields(
            u.Tests.scaffold_text(
                tmp_path / "fixture-project",
                c.Infra.MAKEFILE_FILENAME,
            ),
        )
        tm.that(makefile_fields.get("@flext-generated"), eq="continuous")
        tm.that(makefile_fields.get("@flext-regenerate"), eq="make gen")
        tm.that(makefile_fields.get("@flext-owner", ""), has="config/codegen.yaml")
        tm.that(makefile_fields.get("@flext-adjust", ""), has="never this projection")

        pyproject = u.Tests.scaffold_text(
            tmp_path / "fixture-project",
            c.PYPROJECT_FILENAME,
        )
        tm.that(pyproject, starts=c.Infra.BANNER)
        pyproject_fields = self._fields(pyproject)
        tm.that(pyproject_fields.get("@flext-generated"), eq="continuous")
        tm.that(pyproject_fields.get("@flext-regenerate"), eq="make gen")
        tm.that(pyproject_fields.get("@flext-owner", ""), has="config/codegen.yaml")
        tm.that(pyproject_fields.get("@flext-adjust", ""), has="overwrite_project_keys")
        tm.that(pyproject_fields.get("@flext-adjust", ""), has="conflict_sections")

    @staticmethod
    def test_pyproject_header_is_a_fixed_point(tmp_path: Path) -> None:
        """Recomposing a published pyproject keeps exactly one header."""
        root = tmp_path / "fixture-project"
        first = u.Tests.scaffold_text(root, c.PYPROJECT_FILENAME)
        root.mkdir(parents=True, exist_ok=True)
        (root / c.PYPROJECT_FILENAME).write_text(first, encoding="utf-8")
        second = tm.ok(
            FlextInfraCodegenConform.compose_project_artifact(
                root,
                c.PYPROJECT_FILENAME,
                first,
            ),
        ).rendered
        tm.that(second, eq=first)
        tm.that(second.count(c.Infra.BANNER), eq=1)

    def test_scaffold_once_owner_has_no_continuous_contract(
        self,
        tmp_path: Path,
    ) -> None:
        """Keep user-owned scaffold output outside continuous maintenance."""
        custom = u.Tests.scaffold_text(
            tmp_path / "fixture-project",
            c.Infra.CUSTOM_MAKE_FILENAME,
        )
        tm.that(custom, lacks="[MANAGED]")
        tm.that(self._fields(custom), eq={})
