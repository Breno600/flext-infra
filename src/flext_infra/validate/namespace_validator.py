"""Strict Rope-backed namespace validation service.

AST nodes come only from ``rope.get_pymodule(...).get_ast()``. Parse failures
are violations and never silent exclusions.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra import c, m, t, u

from ..base import s
from .namespace_rules import FlextInfraNamespaceRules

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraNamespaceValidator(s[bool], FlextInfraNamespaceRules):
    """Validate strict layer, facade, typing, and DI invariants."""

    @override
    def execute(self) -> p.Result[bool]:
        """Execute namespace validation for the configured repository root."""
        report_result = self.validate_project(self.repository_root)
        if report_result.failure:
            return r[bool].from_failure(report_result)
        report = report_result.unwrap()
        return r[bool].ok(report.passed)

    def validate_project(
        self, project_root: Path
    ) -> p.Result[m.Infra.ValidationReport]:
        """Validate namespace rules inside one project."""
        files_result = u.Infra.iter_python_files(
            m.Infra.SourceScanRequest(project_roots=(project_root,))
        )
        if files_result.failure:
            return r[m.Infra.ValidationReport].from_failure(files_result)
        files = [
            py_file
            for py_file in files_result.value
            if not self._is_exempt_file(py_file)
            and self._in_declared_scan_scope(py_file, project_root)
        ]
        layout = u.Infra.layout(project_root)
        prefix = layout.class_stem if layout is not None else ""
        package_name = (
            layout.package_dir.name
            if layout is not None
            else project_root.name.replace("-", "_")
        )
        violations: t.MutableSequenceOf[str] = list(
            self._layout_violations(layout.package_dir if layout is not None else None)
        )
        with u.Infra.open_project(project_root) as rope_project:
            for filepath in files:
                tree_result = self._parse_file(rope_project, filepath)
                if tree_result.failure:
                    rel = filepath.relative_to(project_root)
                    violations.append(
                        f"[NS-PARSE-001] {rel}:1 — "
                        f"{tree_result.error or 'Rope AST unavailable'}"
                    )
                    continue
                tree = tree_result.value
                rel = filepath.relative_to(project_root)
                violations.extend(
                    self.check_module(
                        tree,
                        rel,
                        class_stem=prefix,
                        package_name=package_name,
                        source=filepath.read_text(encoding=c.Cli.ENCODING_DEFAULT),
                        is_test_file=self._is_test_file(rel),
                        policy=u.Infra.policy(filepath, rope_project=rope_project),
                    )
                )
        return self._validation_report(files=files, violations=violations)

    @staticmethod
    def _validation_report(
        *, files: t.SequenceOf[Path], violations: t.SequenceOf[str]
    ) -> p.Result[m.Infra.ValidationReport]:
        """Build the namespace validation report."""
        passed = not violations
        summary = (
            f"namespace validation passed ({len(files)} files checked)"
            if passed
            else f"{len(violations)} namespace violation(s) found ({len(files)} files checked)"
        )
        return r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(
                passed=passed, violations=tuple(violations), summary=summary
            )
        )

    def _is_exempt_file(self, filepath: Path) -> bool:
        """Leave generated package projections to their generation contract."""
        name = filepath.name
        return name in {"__init__.py", "__version__.py"}

    def _in_declared_scan_scope(self, filepath: Path, project_root: Path) -> bool:
        """Return whether ``filepath`` lies inside the declared namespace scope.

        Why (cosmos-3flk9, decision A): ``[tool.flext.namespace].scan_dirs``
        scopes enforcement to production sources when a project declares it —
        ``tests/`` host pytest conventions and ``scripts/`` are thin command
        adapters, so governing them as facades contradicts their contract.
        The cyclic-import detector and the canonical-alias gate already honor
        ``u.Infra.namespace_scan_dirs``; the validator silently ignoring the
        same declaration made the declared scope a no-op. Without an explicit
        declaration every file stays in scope (previous behavior).
        """
        declared = u.Infra.namespace_meta(project_root).get("scan_dirs")
        if not isinstance(declared, list) or not declared:
            return True
        scope = frozenset(str(item).strip() for item in declared if str(item).strip())
        return filepath.relative_to(project_root).parts[0] in scope

    def _parse_file(
        self, rope_project: t.Infra.RopeProject, path: Path
    ) -> p.Result[t.Infra.RopeAstNode]:
        """Return the AST module for ``path`` via rope.

        ``r.ok(module)`` on success. ``r.fail(reason)`` when the resource
        cannot be fetched, the module fails to parse, or rope returns no
        ``PyModule``. Callers that want "skip silently" can collapse with
        ``unwrap_or(None)`` or ``.failure``.
        """
        try:
            resource = u.Infra.fetch_python_resource(rope_project, path)
        except c.EXC_OS_SYNTAX as exc:
            return r[t.Infra.RopeAstNode].fail(
                f"fetch_python_resource raised: {exc!s}", exception=exc
            )
        if resource is None:
            return r[t.Infra.RopeAstNode].fail(f"no rope resource for {path}")
        try:
            pymodule = u.Infra.get_pymodule(rope_project, resource)
        except c.EXC_OS_SYNTAX as exc:
            return r[t.Infra.RopeAstNode].fail(
                f"get_pymodule raised: {exc!s}", exception=exc
            )
        ast_module = pymodule.get_ast()
        return r[t.Infra.RopeAstNode].ok(ast_module)

    @staticmethod
    def _layout_violations(package_dir: Path | None) -> t.StrSequence:
        """Require the complete ordered facade and private-family layout."""
        if package_dir is None:
            return ("[NS-LAYOUT-001] project package layout was not discovered",)
        messages: list[str] = []
        required_files: t.VariadicTuple[t.Pair[str, t.VariadicTuple[str]]] = (
            ("settings", ("settings.py", "_settings.py")),
            ("config", ("config.py", "_config.py")),
            ("c", ("constants.py",)),
            ("t", ("typings.py",)),
            ("p", ("protocols.py",)),
            ("m", ("models.py",)),
            ("u", ("utilities.py",)),
            ("base", ("base.py",)),
            ("api", ("api.py",)),
            ("cli", ("cli.py",)),
        )
        for layer, filenames in required_files:
            if not any((package_dir / filename).is_file() for filename in filenames):
                messages.append(
                    f"[NS-LAYOUT-{len(messages) + 1:03d}] missing {layer} facade: "
                    + " or ".join(filenames)
                )
        if not (package_dir / "services").is_dir():
            messages.append(
                f"[NS-LAYOUT-{len(messages) + 1:03d}] missing services composition tree"
            )
        for family in ("_constants", "_typings", "_protocols", "_models", "_utilities"):
            if not (package_dir / family / "base.py").is_file():
                messages.append(
                    f"[NS-LAYOUT-{len(messages) + 1:03d}] {family} must begin with base.py"
                )
        return tuple(messages)

    @staticmethod
    def _is_test_file(rel_path: Path) -> bool:
        """Return True when the file lives under the project's ``tests/`` tree."""
        return any(part == c.Infra.DIR_TESTS for part in rel_path.parts)


__all__: list[str] = ["FlextInfraNamespaceValidator"]
