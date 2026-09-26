"""Typing declarations are read from real PEP 621 and PEP 735 source."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config
from flext_infra.deps.detection import FlextInfraDependencyDetectionService


class TestsFlextInfraDepsDetectionTypingsFlow:
    @staticmethod
    def _governed_follow() -> bool:
        """Read the governed mypy policy from the typed tooling SSOT."""
        return config.Infra.tooling.tools.mypy.boolean_settings.get(
            c.Infra.MYPY_FOLLOW_UNTYPED_IMPORTS,
            c.Infra.MYPY_FOLLOW_UNTYPED_IMPORTS_DEFAULT,
        )

    @classmethod
    def _typed_reader(cls, root: Path, *, follow: bool) -> Path:
        """Write a project declaring CUSTOM typings and one mypy policy."""
        (root / "src" / "typed_reader").mkdir(parents=True)
        (root / "src" / "typed_reader" / c.Infra.INIT_PY).write_text(
            "", encoding="utf-8"
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
            FlextInfraDependencyDetectionService().get_required_typings(
                tmp_path, limits
            )
        )
        tm.that(report.untyped_imports_followed, eq=followed)
        tm.that(report.to_add, empty=True)
        tm.that(
            report.to_remove, eq=[] if followed else ["types-pyyaml", "types-requests"]
        )

    def test_project_policy_conflict_fails_loud(self, tmp_path: Path) -> None:
        """A project mypy table that diverges from the governed policy is a conflict."""
        followed = self._governed_follow()
        limits = self._typed_reader(tmp_path, follow=not followed)
        tm.fail(
            FlextInfraDependencyDetectionService().get_required_typings(
                tmp_path, limits
            ),
            has="policy conflict",
        )

    def test_module_to_types_package(self) -> None:
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
                        "module_to_package": {"yaml": "custom-types-yaml"}
                    }
                },
            ),
            eq="custom-types-yaml",
        )

    def test_custom_typings_and_managed_dev_are_both_available(
        self, tmp_path: Path
    ) -> None:
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
            service.get_current_typings_from_pyproject(tmp_path),
            eq=["pytest", "types-python-dateutil", "types-pyyaml", "types-requests"],
        )
        tm.that(
            service.get_current_typings_from_pyproject(tmp_path, include_dev=False),
            eq=["types-pyyaml", "types-requests"],
        )

    def test_retired_poetry_typings_are_not_a_source(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[tool.poetry.group.typings.dependencies]\ntypes-requests = "*"\n',
            encoding="utf-8",
        )
        tm.that(
            FlextInfraDependencyDetectionService().get_current_typings_from_pyproject(
                tmp_path
            ),
            empty=True,
        )

    def test_invalid_typings_table_fails_at_ingress(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text(
            '[project.optional-dependencies.typings]\ntypes-requests = "*"\n',
            encoding="utf-8",
        )
        with pytest.raises(c.ValidationError):
            FlextInfraDependencyDetectionService().get_current_typings_from_pyproject(
                tmp_path
            )

    def test_absent_pyproject_has_no_declarations(self, tmp_path: Path) -> None:
        tm.that(
            FlextInfraDependencyDetectionService().get_current_typings_from_pyproject(
                tmp_path
            ),
            empty=True,
        )

    @pytest.mark.parametrize("requirement", ["", " "])
    def test_blank_typing_requirement_is_rejected(
        self, tmp_path: Path, requirement: str
    ) -> None:
        (tmp_path / "pyproject.toml").write_text(
            f'[project.optional-dependencies]\ntypings = ["{requirement}"]\n',
            encoding="utf-8",
        )
        with pytest.raises(ValueError, match="must not be blank"):
            FlextInfraDependencyDetectionService().get_current_typings_from_pyproject(
                tmp_path
            )

    def test_malformed_pyproject_preserves_read_failure(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[broken", encoding="utf-8")
        with pytest.raises(RuntimeError, match="failed to read"):
            FlextInfraDependencyDetectionService().get_current_typings_from_pyproject(
                tmp_path
            )
