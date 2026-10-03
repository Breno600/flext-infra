"""Typing declarations are read from real PEP 621 and PEP 735 source.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config
from flext_infra.deps.detection import FlextInfraDependencyDetectionService


class TestsFlextInfraDepsDetectionTypingsFlow:
    """Tests for ``FlextInfraDepsDetectionTypingsFlow``."""

    @staticmethod
    def _governed_follow() -> bool:
        """Read the governed mypy policy from the typed tooling SSOT.

        Returns:
            The resulting ``bool``.

        """
        return config.Infra.tooling.tools.mypy.boolean_settings.get(
            c.Infra.MYPY_FOLLOW_UNTYPED_IMPORTS,
            c.Infra.MYPY_FOLLOW_UNTYPED_IMPORTS_DEFAULT,
        )

    @classmethod
    def _typed_reader(cls, root: Path, *, follow: bool) -> Path:
        """Write a project declaring CUSTOM typings and one mypy policy.

        Returns:
            The resulting ``Path``.

        """
        (root / "src" / "typed_reader").mkdir(parents=True)
        (root / "src" / "typed_reader" / c.Infra.INIT_PY).write_text(
            "",
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text(
            '[project]\nname = "typed-reader"\n'
            "[project.optional-dependencies]\n"
            'typings = ["types-pyyaml>=6.0", "types-requests[extra]==2.28"]\n'
            '[dependency-groups]\ndev = ["types-python-dateutil", "pytest"]\n'
            f"[tool.mypy]\n{c.Infra.MYPY_FOLLOW_UNTYPED_IMPORTS} = "
            f"{str(follow).lower()}\n",
            encoding="utf-8",
        )
        limits = root / "limits.toml"
        limits.write_text("[typing_libraries]\n", encoding="utf-8")
        return limits

    def test_governed_policy_decides_stub_findings(self, tmp_path: Path) -> None:
        """Followed untyped imports make stub packages neither required nor removable."""
        followed = self._governed_follow()
        limits = self._typed_reader(tmp_path, follow=followed)
        report = tm.ok(
            FlextInfraDependencyDetectionService().analyze_required_typings(
                tmp_path,
                limits,
            ),
        )
        tm.that(report.untyped_imports_followed, eq=followed)
        tm.that(report.to_add, empty=True)
        tm.that(
            report.to_remove,
            eq=[] if followed else ["types-pyyaml", "types-requests"],
        )

    def test_project_policy_conflict_fails_loud(self, tmp_path: Path) -> None:
        """A project mypy table that diverges from the governed policy is a conflict."""
        followed = self._governed_follow()
        limits = self._typed_reader(tmp_path, follow=not followed)
        tm.fail(
            FlextInfraDependencyDetectionService().analyze_required_typings(
                tmp_path,
                limits,
            ),
            has="policy conflict",
        )

    @staticmethod
    def test_module_to_types_package() -> None:
        """Test module to types package."""
        service = FlextInfraDependencyDetectionService()
        tm.that(service.module_to_types_package("yaml", {}), eq=None)
        tm.that(service.module_to_types_package("flext_core", {}), eq=None)
        tm.that(service.module_to_types_package("unknown_module", {}), eq=None)
        tm.that(service.module_to_types_package("yaml.parser", {}), eq=None)
        tm.that(
            service.module_to_types_package(
                "yaml",
                {
                    "typing_libraries": {
                        "module_to_package": {"yaml": "custom-types-yaml"},
                    },
                },
            ),
            eq="custom-types-yaml",
        )

    @staticmethod
    def test_custom_typings_and_managed_dev_are_both_available(
        tmp_path: Path,
    ) -> None:
        """Test custom typings and managed dev are both available."""
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "typed-reader"\n'
            "[project.optional-dependencies]\n"
            'typings = ["types-pyyaml>=6.0", "types-requests[extra]==2.28"]\n'
            'feature = ["feature-only"]\n'
            '[dependency-groups]\ndev = ["types-python-dateutil", "pytest"]\n',
            encoding="utf-8",
        )
        service = FlextInfraDependencyDetectionService()
        tm.that(
            service.read_current_typings_from_pyproject(tmp_path),
            eq=["pytest", "types-python-dateutil", "types-pyyaml", "types-requests"],
        )
        tm.that(
            service.read_current_typings_from_pyproject(tmp_path, include_dev=False),
            eq=["types-pyyaml", "types-requests"],
        )

    @staticmethod
    def test_retired_poetry_typings_are_not_a_source(tmp_path: Path) -> None:
        """Test retired poetry typings are not a source."""
        (tmp_path / "pyproject.toml").write_text(
            '[tool.poetry.group.typings.dependencies]\ntypes-requests = "*"\n',
            encoding="utf-8",
        )
        tm.that(
            FlextInfraDependencyDetectionService().read_current_typings_from_pyproject(
                tmp_path,
            ),
            empty=True,
        )

    @staticmethod
    def test_invalid_typings_table_fails_at_ingress(tmp_path: Path) -> None:
        """Test invalid typings table fails at ingress."""
        (tmp_path / "pyproject.toml").write_text(
            '[project.optional-dependencies.typings]\ntypes-requests = "*"\n',
            encoding="utf-8",
        )
        with pytest.raises(c.ValidationError):
            FlextInfraDependencyDetectionService().read_current_typings_from_pyproject(
                tmp_path,
            )

    @staticmethod
    def test_absent_pyproject_has_no_declarations(tmp_path: Path) -> None:
        """Test absent pyproject has no declarations."""
        tm.that(
            FlextInfraDependencyDetectionService().read_current_typings_from_pyproject(
                tmp_path,
            ),
            empty=True,
        )

    @staticmethod
    @pytest.mark.parametrize("requirement", ["", " "])
    def test_blank_typing_requirement_is_rejected(
        tmp_path: Path,
        requirement: str,
    ) -> None:
        """Test blank typing requirement is rejected."""
        (tmp_path / "pyproject.toml").write_text(
            f'[project.optional-dependencies]\ntypings = ["{requirement}"]\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="must not be blank"):
            FlextInfraDependencyDetectionService().read_current_typings_from_pyproject(
                tmp_path,
            )

    @staticmethod
    def test_malformed_pyproject_preserves_read_failure(tmp_path: Path) -> None:
        """Test malformed pyproject preserves read failure."""
        (tmp_path / "pyproject.toml").write_text("[broken", encoding="utf-8")
        with pytest.raises(RuntimeError, match="failed to read"):
            FlextInfraDependencyDetectionService().read_current_typings_from_pyproject(
                tmp_path,
            )
