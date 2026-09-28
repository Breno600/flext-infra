"""Unit tests for the pattern smell detector.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import config, u
from tests import m

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraPatternSmellDetector:
    """Behavior contract for FlextInfraPatternSmellDetector."""

    @staticmethod
    def _kinds(file_path: Path, rope_project: t.Infra.RopeProject) -> set[str]:
        violations = u.Infra.detect_static_rules(
            m.Infra.DetectorContext(file_path=file_path, rope_project=rope_project),
            config.Infra.enforcement.rules,
        )
        return {v.kind for v in violations}

    @pytest.mark.parametrize(
        ("source", "expected_kind"),
        [
            pytest.param(
                "from __future__ import annotations\n"
                "from typing import List\n"
                "x: List[int] = []\n",
                "typing_list_import",
                id="typing-list-import",
            ),
            pytest.param(
                "from __future__ import annotations\n"
                "import typing\n"
                "x: typing.List[int] = []\n",
                "typing_list_attr",
                id="typing-list-attr",
            ),
            pytest.param(
                "from __future__ import annotations\nfrom pydantic import BaseModel\n",
                "direct_pydantic_import",
                id="direct-pydantic-import",
            ),
            pytest.param(
                "from __future__ import annotations\n"
                "import structlog\n"
                "logger = structlog.get_logger()\n",
                "direct_structlog_import",
                id="direct-structlog-import",
            ),
            pytest.param(
                "from __future__ import annotations\nimport oracledb\n",
                "direct_oracledb_import",
                id="direct-oracledb-import",
            ),
            pytest.param(
                "from __future__ import annotations\nfrom ldap3 import Server\n",
                "direct_ldap3_import",
                id="direct-ldap3-import",
            ),
        ],
    )
    def test_detects_declared_pattern_smell(
        self,
        tmp_path: Path,
        rope_project: t.Infra.RopeProject,
        source: str,
        expected_kind: str,
    ) -> None:
        """Each declared enforcement pattern is reported by its own kind."""
        sample = tmp_path / "sample.py"
        sample.write_text(source, encoding="utf-8")
        tm.that(self._kinds(sample, rope_project), has=expected_kind)

    @pytest.mark.parametrize(
        ("project_name", "expect_violation"),
        [
            pytest.param("flext-core", False, id="owning-project-is-exempt"),
            pytest.param("flext-target-ldap", True, id="consumer-project-is-detected"),
        ],
    )
    def test_owned_library_import_depends_on_the_owning_project(
        self,
        tmp_path: Path,
        rope_project: t.Infra.RopeProject,
        project_name: str,
        *,
        expect_violation: bool,
    ) -> None:
        """A library import is a violation everywhere except in its owning project."""
        sample = tmp_path / "sample.py"
        sample.write_text(
            "from __future__ import annotations\nfrom pydantic import BaseModel\n",
            encoding="utf-8",
        )
        violations = u.Infra.detect_static_rules(
            m.Infra.DetectorContext(
                file_path=sample, rope_project=rope_project, project_name=project_name
            ),
            config.Infra.enforcement.rules,
        )
        tm.that(
            any(v.kind == "direct_pydantic_import" for v in violations),
            eq=expect_violation,
        )
