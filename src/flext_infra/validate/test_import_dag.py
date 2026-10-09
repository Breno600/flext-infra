"""Rope-semantic guard for the strict package-test import DAG.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_infra import c, m, r, t, u
from flext_infra.base_selection import FlextInfraProjectSelectionServiceBase

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraValidateTestImportDag(FlextInfraProjectSelectionServiceBase[bool]):
    """Enforce directed imports between production, tests, and test facets."""

    def build_report(self, repository_root: Path) -> p.Result[m.Infra.ValidationReport]:
        """Scan every governed project as an independent import unit.

        Returns:
            The resulting ``p.Result[m.Infra.ValidationReport]``.

        """
        try:
            roots = u.Infra.discover_project_roots(repository_root) or (
                repository_root,
            )
            violations = tuple(
                violation
                for project_root in roots
                for violation in self._project_violations(project_root)
            )
        except OSError as exc:
            return r[m.Infra.ValidationReport].fail_op("test-import-dag scan", exc)
        summary = (
            f"strict test import DAG respected ({len(roots)} project(s))"
            if not violations
            else f"{len(violations)} strict test import DAG violation(s)"
        )
        return r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(
                passed=not violations,
                violations=violations,
                summary=summary,
            ),
        )

    def _project_violations(self, project_root: Path) -> t.StrSequence:
        project_state = u.Infra.project_state(project_root)
        allowed_shared_imports = frozenset({
            project_state.package_name,
            *(name.replace("-", "_") for name in project_state.dependency_names),
        })
        violations: list[str] = []
        with u.Infra.open_project(project_root) as project:
            for resource in u.Infra.python_resources(project):
                file_path = u.Infra.resource_file_path(project, resource)
                if file_path is None:
                    continue
                module_imports = u.Infra.resolve_module_imports(project, resource)
                for imported in u.Infra.imported_module_paths(module_imports):
                    reason = self._edge_violation(
                        file_path,
                        imported,
                        project_root,
                        package_name=project_state.package_name,
                        allowed_shared_imports=allowed_shared_imports,
                    )
                    if reason is not None:
                        violations.append(f"{file_path}: {imported}: {reason}")
        return tuple(violations)

    @staticmethod
    def _facet(file_path: Path) -> str | None:
        if c.Infra.DIR_TESTS not in file_path.parts:
            return None
        return u.Infra.facade_family_of_file(file_path.name)

    @staticmethod
    def _imported_facet(imported: str) -> str | None:
        parts = imported.split(".")
        if not parts or parts[0] != c.Infra.DIR_TESTS:
            return None
        return next(
            (
                family
                for part in parts[1:]
                if (
                    family := u.Infra.facade_family_of_file(
                        f"{part}{c.Infra.EXT_PYTHON}",
                    )
                )
                is not None
            ),
            None,
        )

    @classmethod
    def _edge_violation(
        cls,
        file_path: Path,
        imported: str,
        project_root: Path,
        *,
        package_name: str,
        allowed_shared_imports: frozenset[str],
    ) -> str | None:
        relative = file_path.resolve().relative_to(project_root.resolve())
        in_tests = c.Infra.DIR_TESTS in relative.parts
        imported_parts = imported.split(".")
        imports_tests = bool(imported_parts) and imported_parts[0] in {
            c.Infra.DIR_TESTS,
            *(
                (imported_parts[0],)
                if imported_parts[0].endswith(f"_{c.Infra.DIR_TESTS}")
                else ()
            ),
        }
        if not in_tests and imports_tests:
            return "production code cannot import test infrastructure"
        if package_name.endswith(f"_{c.Infra.DIR_TESTS}") and (
            "fixtures" in relative.parts or file_path.stem.startswith("conftest")
        ):
            top = imported_parts[0] if imported_parts else ""
            if top.startswith("flext_") and top not in allowed_shared_imports:
                return "shared test infrastructure cannot import consumer packages"
        if not in_tests:
            return None
        source_facet = cls._facet(file_path)
        imported_facet = cls._imported_facet(imported)
        imports_test_support = (
            imported_parts[0] == c.Infra.DIR_TESTS
            and imported != c.Infra.DIR_TESTS
            and imported_facet is None
        )
        if source_facet is not None:
            if imported == c.Infra.DIR_TESTS:
                return "test facets cannot import the tests package root"
            if imports_test_support:
                return "test facets cannot import fixtures, conftest, or test modules"
            facade_order = tuple(u.Infra.facade_families())
            if imported_facet is not None and facade_order.index(
                imported_facet,
            ) < facade_order.index(source_facet):
                return "reverse canonical test-facet edge"
        if (
            file_path.name == c.Infra.INIT_PY
            and relative.parent.name == c.Infra.DIR_TESTS
            and imports_test_support
        ):
            return "tests package root cannot import fixtures, conftest, or tests"
        return None

    @override
    def execute(self) -> p.Result[bool]:
        return self._report_execution(self.build_report(self.repository_root))


__all__: t.StrSequence = ("FlextInfraValidateTestImportDag",)
