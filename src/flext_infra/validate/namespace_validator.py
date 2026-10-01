"""Strict Rope-backed namespace validation service.

AST nodes come only from the active Rope module. Parse failures are violations
and never silent exclusions.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra import m, p, t, u

from ..base import s
from .namespace_rules import FlextInfraNamespaceRules

if TYPE_CHECKING:
    from pathlib import Path


class FlextInfraNamespaceValidator(s[bool], FlextInfraNamespaceRules):
    """Validate strict layer, facade, typing, and DI invariants."""

    rope: t.Port[p.Infra.RopeWorkspaceDsl] = m.Field(
        exclude=True,
        description="Shared Rope cycle injected by the composition root",
    )
    _eligible_files: frozenset[Path] | None = u.PrivateAttr(default=None)
    _first_eligible_file: Path | None = u.PrivateAttr(default=None)

    @override
    def execute(self) -> p.Result[bool]:
        """Execute namespace validation for the configured repository root."""
        report_result = self.build_report()
        if report_result.failure:
            return r[bool].from_failure(report_result)
        report = report_result.unwrap()
        return r[bool].ok(report.passed)

    def __call__(
        self,
        workspace: p.Infra.RopeWorkspaceDsl,
        visit: m.Infra.RopeModuleVisit,
        /,
    ) -> p.Result[m.Infra.RopeCallbackOutcome]:
        """Validate one module supplied by the shared Rope owner callback."""
        project_root = self.repository_root.resolve()
        if visit.project_root.resolve() != project_root:
            return r[m.Infra.RopeCallbackOutcome].ok(
                m.Infra.RopeCallbackOutcome(
                    file_path=visit.file_path,
                    project_root=visit.project_root,
                    callback_id="namespace",
                    applicable=False,
                ),
            )
        filepath = visit.file_path.resolve()
        eligible = self._eligible_project_files(workspace)
        if filepath not in eligible:
            return r[m.Infra.RopeCallbackOutcome].ok(
                m.Infra.RopeCallbackOutcome(
                    file_path=visit.file_path,
                    project_root=visit.project_root,
                    callback_id="namespace",
                    applicable=False,
                ),
            )
        layout = visit.convention.project_layout
        rel = filepath.relative_to(project_root)
        violations: t.MutableSequenceOf[str] = []
        if filepath == self._first_eligible_file:
            if layout is None and self._declared_content_only(project_root):
                # A workspace manifest declaring repository.package=false
                # defines a content-only root (a workspace shell whose
                # analyzable surface lives in examples/tests): the facade
                # layout contract scopes projects that publish packages, so
                # the undiscovered layout is the declared receipt, not a
                # defect (invest-6n6u family).
                pass
            else:
                violations.extend(
                    self._layout_violations(
                        layout.package_dir if layout is not None else None,
                    ),
                )
        violations.extend(self.check_module(visit, rel))
        return r[m.Infra.RopeCallbackOutcome].ok(
            m.Infra.RopeCallbackOutcome(
                file_path=visit.file_path,
                project_root=visit.project_root,
                callback_id="namespace",
                violations=tuple(violations),
            ),
        )

    @staticmethod
    def _declared_content_only(project_root: Path) -> bool:
        """Return whether the local manifest declares repository.package=false.

        The workspace manifest is the SSOT for the publish contract: a
        content-only declaration means the analyzable surface lives in
        examples/tests and the facade layout contract does not apply.
        Undeclared or load-failing roots stay loud (the layout error is the
        correct signal when a package was expected).
        """
        resolved = project_root.expanduser().resolve()
        if not u.Infra.workspace_manifest_path(resolved).is_file():
            return False
        declared = u.Infra.load_workspace_manifest(resolved)
        if declared.failure or not declared.value:
            return False
        manifest = declared.value[0]
        return manifest.repository.package is False

    def _eligible_project_files(
        self,
        workspace: p.Infra.RopeWorkspaceDsl,
    ) -> frozenset[Path]:
        """Index the governed files once for this project callback."""
        cached = self._eligible_files
        if cached is not None:
            return cached
        project_root = self.repository_root.resolve()
        eligible = frozenset(
            entry.file_path.resolve()
            for entry in workspace.modules(project_names=(project_root.name,))
            if entry.project_root is not None
            and entry.project_root.resolve() == project_root
            and not self._is_exempt_file(entry.file_path)
            and self._in_declared_scan_scope(entry.file_path, project_root)
        )
        self._eligible_files = eligible
        self._first_eligible_file = min(eligible) if eligible else None
        return eligible

    def build_report(self) -> p.Result[m.Infra.ValidationReport]:
        """Build the project report through the injected shared Rope cycle."""
        cycle_result = self.rope.cycle(
            (self.callback_binding(),),
            project_names=(self.repository_root.resolve().name,),
        )
        if cycle_result.failure:
            return r[m.Infra.ValidationReport].from_failure(cycle_result)
        outcomes = tuple(
            outcome
            for outcome in cycle_result.value.outcomes
            if outcome.callback_id == "namespace" and outcome.applicable
        )
        violations = tuple(
            violation for outcome in outcomes for violation in outcome.violations
        )
        return self._validation_report(
            files_checked=len(outcomes),
            violations=violations,
        )

    def callback_binding(self) -> m.Infra.RopeCallbackBinding:
        """Bind this validator to its exact files before Rope builds syntax trees."""
        return m.Infra.RopeCallbackBinding(
            callback=self,
            file_paths=self._eligible_project_files(self.rope),
        )

    @staticmethod
    def _validation_report(
        *,
        files_checked: int,
        violations: t.SequenceOf[str],
    ) -> p.Result[m.Infra.ValidationReport]:
        """Build the namespace validation report."""
        passed = not violations
        summary = (
            f"namespace validation passed ({files_checked} files checked)"
            if passed
            else f"{len(violations)} namespace violation(s) found ({files_checked} files checked)"
        )
        return r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(
                passed=passed,
                violations=tuple(violations),
                summary=summary,
            ),
        )

    def _is_exempt_file(self, filepath: Path) -> bool:
        """Leave generated package projections to their generation contract."""
        name = filepath.name
        return name in {"__init__.py", "__version__.py"}

    def _in_declared_scan_scope(self, filepath: Path, project_root: Path) -> bool:
        """Return whether ``filepath`` lies inside the declared namespace scope.

        Why: ``[tool.flext.namespace].scan_dirs``
        scopes enforcement to production sources when a project declares it —
        ``tests/`` host pytest conventions and ``scripts/`` are thin command
        adapters, so governing them as facades contradicts their contract.
        The namespace enforcer already honors the declared scan directories;
        the validator silently ignoring the same declaration made the declared
        scope a no-op. Without an explicit
        declaration every file stays in scope (previous behavior).
        """
        declared = u.Infra.namespace_meta(project_root).get("scan_dirs")
        if not isinstance(declared, list) or not declared:
            return True
        scope = frozenset(str(item).strip() for item in declared if str(item).strip())
        return filepath.relative_to(project_root).parts[0] in scope

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
            ("cli", ("cli.py",)),
        )
        for layer, filenames in required_files:
            if not any((package_dir / filename).is_file() for filename in filenames):
                messages.append(
                    f"[NS-LAYOUT-{len(messages) + 1:03d}] missing {layer} facade: "
                    + " or ".join(filenames),
                )
        services_dir = package_dir / "services"
        has_services = services_dir.is_dir() and any(
            path.is_file() and path.suffix == ".py" and path.name != "__init__.py"
            for path in services_dir.iterdir()
        )
        if has_services:
            for layer in ("base", "api"):
                if not (package_dir / f"{layer}.py").is_file():
                    messages.append(
                        f"[NS-LAYOUT-{len(messages) + 1:03d}] missing {layer} facade",
                    )
        for family in ("_constants", "_typings", "_protocols", "_models", "_utilities"):
            if not (package_dir / family / "base.py").is_file():
                messages.append(
                    f"[NS-LAYOUT-{len(messages) + 1:03d}] {family} must begin with base.py",
                )
        return tuple(messages)


__all__: list[str] = ["FlextInfraNamespaceValidator"]
