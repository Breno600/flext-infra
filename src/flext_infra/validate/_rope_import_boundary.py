"""FLEXT base for rope-driven module-import boundary validators.

Consolidates the shared skeleton between tier-whitelist and metadata-discipline
validators (and any future rope-import boundary guard): build_report,
_collect_violations, _violations_for_module, _top_module, execute. Subclasses
declare only the banned set, summary strings, and (optionally) override
``_is_allowlisted``/``_is_in_scope``/``_format_violation``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, override

from flext_core import r
from flext_infra import m, t, u

from ..base import s

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraRopeImportBoundaryBase(s[bool]):
    """Base service for rope-driven module-import boundary validators.

    Subclasses set the four ``ClassVar`` declarations below. Optional hooks:
    ``_is_in_scope`` (default: all files), ``_is_allowlisted`` (default: none),
    ``_format_violation`` (default: ``"{path}: {module}"``).
    """

    _BANNED: ClassVar[frozenset[str]] = frozenset()
    _OK_SUMMARY: ClassVar[str] = ""
    _VIOLATION_KIND: ClassVar[str] = ""
    _SCAN_KIND: ClassVar[str] = ""

    def build_report(self, repository_root: Path) -> p.Result[m.Infra.ValidationReport]:
        """Scan ``repository_root`` and return a ``ValidationReport``.

        Scope is the shared source inventory (``u.Infra.iter_python_files``):
        the declared source roots, Git visibility and the ``source_scan_ignore``
        artifact SSOT. A member repository is its own Git repository, so its
        files never enter this checkout's inventory and get their own run.
        """
        try:
            collected = self._collect_violations(repository_root)
        except OSError as exc:
            return r[m.Infra.ValidationReport].fail(
                f"{self._SCAN_KIND} scan failed: {exc}", exception=exc
            )
        if collected.failure:
            return r[m.Infra.ValidationReport].from_failure(collected)
        violations = collected.value
        passed = not violations
        summary = (
            self._OK_SUMMARY
            if passed
            else f"{len(violations)} {self._VIOLATION_KIND} violation(s)"
        )
        return r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(
                passed=passed, violations=list(violations), summary=summary
            )
        )

    def _collect_violations(self, repository_root: Path) -> p.Result[t.StrSequence]:
        """Resolve each inventory file through rope and accumulate violations."""
        files = u.Infra.iter_python_files(
            m.Infra.SourceScanRequest(project_roots=(repository_root,))
        )
        if files.failure:
            return r[t.StrSequence].from_failure(files)
        violations: t.MutableSequenceOf[str] = []
        root = repository_root.resolve()
        with u.Infra.open_project(repository_root) as project:
            for file_path in files.value:
                if not self._is_in_scope(file_path, repository_root=root):
                    continue
                resource = u.Infra.resolve_resource_from_path(project, file_path)
                if resource is None:
                    return r[t.StrSequence].fail(
                        f"{self._SCAN_KIND}: inventory file is not a rope resource: "
                        f"{file_path}"
                    )
                module_imports = u.Infra.resolve_module_imports(project, resource)
                violations.extend(
                    self._violations_for_module(
                        file_path, module_imports, repository_root=root
                    )
                )
        return r[t.StrSequence].ok(tuple(violations))

    @staticmethod
    def _rooted_posix(file_path: Path, repository_root: Path) -> str:
        """Return ``/<path relative to the scanned root>`` for marker matching.

        Every scope and allowlist decision is taken on the path INSIDE the
        scanned repository (X-75/X-77): the working copy's own directory name
        and every ancestor above it never take part in the match.
        """
        return f"/{file_path.resolve().relative_to(repository_root).as_posix()}"

    def _is_in_scope(self, _file_path: Path, *, repository_root: Path) -> bool:
        """Default: every traversed module is in scope. Override to narrow."""
        _ = repository_root
        return True

    def _is_allowlisted(
        self, _file_path: Path, _module_name: str, *, repository_root: Path
    ) -> bool:
        """Per (file, module) allowlist check. Override to exempt canonical owners."""
        _ = repository_root
        return False

    def _violations_for_module(
        self,
        file_path: Path,
        module_imports: t.Infra.RopeModuleImports,
        *,
        repository_root: Path,
    ) -> t.StrSequence:
        """Return banned-import violation strings for one module."""
        out: t.MutableSequenceOf[str] = []
        for stmt in u.Infra.import_statements(module_imports):
            # A relative import (``from .yaml import X``) is intra-package by
            # definition and can never be a bare external-library import. Rope
            # reports only the declared tail as ``module_name`` for it, so
            # treating it as absolute turned ``.yaml`` into a banned ``yaml``
            # import and flagged the owning project's own modules.
            if (getattr(stmt.import_info, "level", 0) or 0) > 0:
                continue
            module_name = u.Infra.import_statement_module_name(stmt)
            if module_name is not None:
                if self._top_module(
                    module_name
                ) in self._BANNED and not self._is_allowlisted(
                    file_path, module_name, repository_root=repository_root
                ):
                    out.append(self._format_violation(file_path, module_name))
                continue
            for imported, _alias in u.Infra.import_statement_names_and_aliases(stmt):
                if self._top_module(
                    imported
                ) in self._BANNED and not self._is_allowlisted(
                    file_path, imported, repository_root=repository_root
                ):
                    out.append(self._format_violation(file_path, imported))
        return tuple(out)

    def _format_violation(self, file_path: Path, module_name: str) -> str:
        """Default: minimal ``path: module`` line. Override for richer messaging."""
        return f"{file_path}: {module_name}"

    @staticmethod
    def _top_module(module_name: str | None) -> str:
        """Return the top-level package name (``a.b.c`` → ``a``)."""
        if not module_name:
            return ""
        return module_name.split(".", maxsplit=1)[0]

    @override
    def execute(self) -> p.Result[bool]:
        """Run the validation against ``self.repository_root``."""
        # Why: the inherited mapper's facade-typed signature degrades to Any
        # under mypy's suppressed PEP-562 imports, so the same mapping is
        # spelled here through the concrete result factory; the returned
        # expression stays typed under both checkers with identical behavior.
        report = self.build_report(self.repository_root)
        if report.failure:
            return r[bool].from_failure(report)
        validated = report.unwrap()
        return r[bool].ok(True) if validated.passed else r[bool].fail(validated.summary)


__all__: t.StrSequence = ("FlextInfraRopeImportBoundaryBase",)
