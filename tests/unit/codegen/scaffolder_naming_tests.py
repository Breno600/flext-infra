"""Tests for scaffolder generated code validity and naming conventions.

Validates AST parseability and {Prefix}{Suffix} class naming convention
for both src/ and tests/ generated modules.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.codegen.scaffolder import FlextInfraCodegenScaffolder
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import m, t


class TestsFlextInfraCodegenScaffolderNaming:
    """Test suite for scaffolder generated code validity and naming conventions."""

    def _parse_class_names(self, source: str) -> t.StrSequence:
        """Extract all class names from Python source via the codegen regex authority.

        Single Responsibility: detect class definitions only.
        """
        return c.Infra.DETECTION_CLASS_DECL_RE.findall(source)

    def _validate_modules_parse(self, base_dir: Path, modules: t.StrSequence) -> None:
        """Validate that all modules in base_dir compile as valid Python.

        Utility: eliminates duplicate syntax validation logic.
        """
        for mod in modules:
            source = (base_dir / mod).read_text(encoding="utf-8")
            _ = compile(source, str(base_dir / mod), "exec")

    def _validate_class_names(
        self, base_dir: Path, filename_to_expected_class: t.StrMapping
    ) -> None:
        """Validate expected class names exist in modules.

        Utility: eliminates duplicate class name extraction and validation.
        """
        for filename, expected_class in filename_to_expected_class.items():
            source = (base_dir / filename).read_text(encoding="utf-8")
            class_names = self._parse_class_names(source)
            tm.that(
                expected_class in class_names,
                eq=True,
                msg=f"{filename} should contain {expected_class}",
            )

    def _project_info(
        self, project: Path, *, package_name: str = "test_project"
    ) -> m.Infra.ProjectInfo:
        return u.Tests.create_project_info(
            project, name=project.name, package_name=package_name
        )

    class TestsGeneratedFilesAreValidPython:
        """Generated source and test modules compile as Python."""

        def _validate_modules_parse(
            self, base_dir: Path, modules: t.StrSequence
        ) -> None:
            for mod in modules:
                source = (base_dir / mod).read_text(encoding="utf-8")
                _ = compile(source, str(base_dir / mod), "exec")

        def _project_info(
            self, project: Path, *, package_name: str = "test_project"
        ) -> m.Infra.ProjectInfo:
            return u.Tests.create_project_info(
                project, name=project.name, package_name=package_name
            )

        def test_generated_src_modules_parse_successfully(self, tmp_path: Path) -> None:
            """Compile every generated source facade module."""
            project = u.Tests.create_scaffolder_test_project(
                tmp_path=tmp_path, with_all_modules=False
            )
            scaffolder = FlextInfraCodegenScaffolder(repository_root=tmp_path)
            _ = scaffolder.run(projects=[self._project_info(project)])
            pkg = project / "src" / "test_project"
            self._validate_modules_parse(pkg, u.Tests.src_module_files())

        def test_generated_tests_modules_parse_successfully(
            self, tmp_path: Path
        ) -> None:
            """Compile every generated test facade module."""
            project = u.Tests.create_scaffolder_test_project(
                tmp_path=tmp_path, with_all_modules=True
            )
            tests_dir = project / "tests"
            tests_dir.mkdir()
            scaffolder = FlextInfraCodegenScaffolder(repository_root=tmp_path)
            _ = scaffolder.run(projects=[self._project_info(project)])
            self._validate_modules_parse(tests_dir, u.Tests.src_module_files())

    class TestsGeneratedClassNamingConvention:
        """Generated class names follow the canonical prefix and suffix contract."""

        def _parse_class_names(self, source: str) -> t.StrSequence:
            return c.Infra.DETECTION_CLASS_DECL_RE.findall(source)

        def _validate_class_names(
            self, base_dir: Path, filename_to_expected_class: t.StrMapping
        ) -> None:
            for filename, expected_class in filename_to_expected_class.items():
                source = (base_dir / filename).read_text(encoding="utf-8")
                class_names = self._parse_class_names(source)
                tm.that(
                    expected_class in class_names,
                    eq=True,
                    msg=f"{filename} should contain {expected_class}",
                )

        def _project_info(
            self, project: Path, *, package_name: str = "test_project"
        ) -> m.Infra.ProjectInfo:
            return u.Tests.create_project_info(
                project, name=project.name, package_name=package_name
            )

        def test_src_class_names_use_prefix_suffix(self, tmp_path: Path) -> None:
            """Use the project prefix on generated source facade classes."""
            project = u.Tests.create_scaffolder_test_project(
                tmp_path=tmp_path, with_all_modules=False
            )
            scaffolder = FlextInfraCodegenScaffolder(repository_root=tmp_path)
            _ = scaffolder.run(projects=[self._project_info(project)])
            pkg = project / "src" / "test_project"
            self._validate_class_names(
                pkg,
                {
                    "constants.py": "TestProjectConstants",
                    "typings.py": "TestProjectTypes",
                    "protocols.py": "TestProjectProtocols",
                    "models.py": "TestProjectModels",
                    "utilities.py": "TestProjectUtilities",
                },
            )

        def test_tests_class_names_use_tests_prefix_suffix(
            self, tmp_path: Path
        ) -> None:
            """Use the Tests prefix on generated test facade classes."""
            project = u.Tests.create_scaffolder_test_project(
                tmp_path=tmp_path, with_all_modules=True
            )
            tests_dir = project / "tests"
            tests_dir.mkdir()
            scaffolder = FlextInfraCodegenScaffolder(repository_root=tmp_path)
            _ = scaffolder.run(projects=[self._project_info(project)])
            self._validate_class_names(
                tests_dir,
                {
                    "constants.py": "TestsTestProjectConstants",
                    "typings.py": "TestsTestProjectTypes",
                    "protocols.py": "TestsTestProjectProtocols",
                    "models.py": "TestsTestProjectModels",
                    "utilities.py": "TestsTestProjectUtilities",
                },
            )

        def test_no_prefix_returns_empty_result(self, tmp_path: Path) -> None:
            """Skip generation when no package prefix is available."""
            project = tmp_path / "empty-project"
            project.mkdir()
            (project / "Makefile").touch()
            scaffolder = FlextInfraCodegenScaffolder(repository_root=tmp_path)
            [result] = scaffolder.run(
                projects=[
                    u.Tests.create_project_info(
                        project, name="empty-project", package_name=""
                    )
                ]
            )
            tm.that(result.files_created, empty=True)
            tm.that(result.files_skipped, empty=True)
            tm.that(result.project, eq="empty-project")
