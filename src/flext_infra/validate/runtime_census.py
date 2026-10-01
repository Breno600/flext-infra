"""Runtime Beartype census validator.

Imports every ``flext_*`` module in selected projects and runs
``u.check()`` against every locally-defined class.
Aggregates violations by rule/project into the standard validation report.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import re
import sys
import types
from collections import defaultdict
from collections.abc import MutableMapping
from typing import TYPE_CHECKING, Annotated, Self, override

from flext_core import r
from flext_infra import c, config, m, t, u

from ..base import s

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p


class FlextInfraRuntimeCensusValidator(s[bool]):
    """Post-import runtime enforcement census across workspace projects."""

    project_filter: Annotated[
        str | None, m.Field(description="Project filter (comma-separated)")
    ] = None
    census_gate: Annotated[
        str,
        m.Field(
            description=(
                "Gate whose census rule families this run grades: the runtime "
                "census gate grades every family no other gate owns"
            )
        ),
    ] = c.Infra.RUNTIME_CENSUS

    @classmethod
    def for_project(cls, project_dir: Path, *, census_gate: str) -> Self:
        """Scope one census run to ``project_dir`` for ``census_gate``.

        The filter is the declared project name, never the checkout directory
        name: a worktree or renamed checkout keeps its manifest identity, and
        the census discovery keys projects by exactly that pyproject name.
        """
        # A checkout without a manifest declares no project: the census then
        # selects nothing and reports that typed failure. A present manifest
        # that cannot be read raises instead of falling back to the directory.
        if not (project_dir / c.PYPROJECT_FILENAME).is_file():
            return cls(repository_root=project_dir, census_gate=census_gate)
        metadata = u.Infra.read_project_metadata_result(project_dir).unwrap()
        return cls(
            repository_root=project_dir,
            project_filter=metadata.project.name,
            census_gate=census_gate,
        )

    @staticmethod
    def _gate_rule_families() -> t.MappingKV[str, frozenset[str]]:
        """Census rule families owned by a gate other than the runtime census.

        Operator ruling 2026-10-01: no smell enters ``make check``; the
        ``make smells`` verb owns every smell family. The family set derives
        from the flext-core smell catalog — every smell tag plus the rule id
        of every catalog row carrying one — so a smell added to the catalog
        moves to the smells gate in the same edit, with no second list.
        """
        return {
            c.Infra.SMELLS: frozenset({
                *c.ENFORCEMENT_SMELL_TAGS,
                *c.SMELL_RULES_TEXT,
            })
        }

    @staticmethod
    def _package_name_for_project(project: p.Infra.ProjectInfo) -> str | None:
        """Resolve the importable package name for a project root."""
        layout = u.Infra.layout(project.path, project=project)
        if layout is not None:
            package_name: str = layout.package_name
            return package_name
        src_dir = project.path / c.Infra.DEFAULT_SRC_DIR
        if not src_dir.is_dir():
            return None
        for child in sorted(src_dir.iterdir()):
            if child.is_dir() and (child / c.Infra.INIT_PY).is_file():
                child_name: str = child.name
                return child_name
        return None

    @staticmethod
    def _is_local_class(klass: type, module_name: str) -> bool:
        """Return True when ``klass`` is defined in ``module_name`` (not imported)."""
        return getattr(klass, "__module__", "") == module_name

    @classmethod
    def _walk_modules(cls, package_name: str) -> t.SequenceOf[str]:
        """Return all importable module names under ``package_name``."""
        package = importlib.import_module(package_name)
        prefix = package.__name__ + "."
        modules: list[str] = [package.__name__]
        for _, modname, _ in pkgutil.walk_packages(
            package.__path__, prefix=prefix, onerror=cls._raise_package_walk_error
        ):
            modules.append(modname)
        return modules

    @staticmethod
    def _raise_package_walk_error(module_name: str) -> None:
        """Propagate the package import exception with its original traceback."""
        exception = sys.exception()
        if exception is None:
            msg = f"package discovery failed without an exception: {module_name}"
            raise RuntimeError(msg)
        raise exception.with_traceback(exception.__traceback__)

    @staticmethod
    def _is_declared_island(module: types.ModuleType) -> bool:
        """Whether the module lives under a declared stdlib island path.

        Why: ADR-0018 declares the native hook-client island the sole,
        performance-motivated exception to the FLEXT enforcement surface; it
        is stdlib-only and cannot consume ``ai_hub._constants``, so the same
        declaration the boundary, namespace, and silent-failure gates honor
        keeps the runtime census from enforcing family constants on it.
        """
        module_file = getattr(module, "__file__", None)
        if module_file is None:
            return False
        posix = str(module_file).replace("\\", "/")
        return any(
            fragment in posix
            for fragment in c.Infra.NAMESPACE_STDLIB_ISLAND_PATH_FRAGMENTS
        )

    def _check_module(self, module_name: str) -> t.SequenceOf[m.Infra.ValidationReport]:
        """Import one module and run runtime enforcement on its local classes."""
        module = importlib.import_module(module_name)
        if self._is_declared_island(module):
            return [
                m.Infra.ValidationReport(
                    passed=True, violations=(), summary=f"{module_name}: clean"
                )
            ]
        violations: list[str] = []
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if not self._is_local_class(obj, module.__name__):
                continue
            report = u.check(obj)
            for violation in report.violations:
                file_part = f"{violation.file_path}:" if violation.file_path else ""
                line_part = f"{violation.line_number}:" if violation.line_number else ""
                rule_part = f" [{violation.rule_id}]" if violation.rule_id else ""
                violations.append(
                    f"{file_part}{line_part}{obj.__qualname__}{rule_part}: "
                    f"{violation.message}"
                )
        return [
            m.Infra.ValidationReport(
                passed=not violations,
                violations=tuple(violations),
                summary=(
                    f"{module_name}: {len(violations)} runtime violation(s)"
                    if violations
                    else f"{module_name}: clean"
                ),
            )
        ]

    def _project_report(
        self, project: p.Infra.ProjectInfo
    ) -> p.Result[m.Infra.ValidationReport]:
        """Run the runtime census for one project and return a merged report."""
        package_name = self._package_name_for_project(project)
        if package_name is None:
            return r[m.Infra.ValidationReport].ok(
                m.Infra.ValidationReport(
                    passed=True,
                    violations=(),
                    summary=f"{project.name}: no importable package found",
                )
            )
        # Operator stability contract (2026-09-16): an unimportable package is
        # a census violation to report, never a verb crash.
        walked = r[t.SequenceOf[str]].create_from_callable(
            lambda: self._walk_modules(package_name)
        )
        if walked.failure:
            return r[m.Infra.ValidationReport].ok(
                m.Infra.ValidationReport(
                    passed=False,
                    violations=(
                        (
                            f"{package_name}: package import failed: "
                            f"{type(walked.exception).__name__}: {walked.error}"
                        ),
                    ),
                    summary=f"{project.name}: package import failed",
                )
            )
        real_modules = list(walked.value)
        if self.target_module is not None:
            real_modules = [
                name
                for name in real_modules
                if name == self.target_module
                or name.startswith(self.target_module + ".")
            ]
        real_modules = [
            name
            for name in real_modules
            if not frozenset(config.Infra.codegen.source_scan_ignored).intersection(
                name.split(".")
            )
        ]
        all_reports: list[m.Infra.ValidationReport] = []
        for module_name in real_modules:
            # Operator stability contract (2026-09-16): a module that cannot
            # import is a census violation to report, never a verb crash —
            # findings feed the generator, the Make verb completes.
            checked = r[t.SequenceOf[m.Infra.ValidationReport]].create_from_callable(
                lambda name=module_name: self._check_module(name)
            )
            if checked.success:
                all_reports.extend(checked.value)
            else:
                all_reports.append(
                    m.Infra.ValidationReport(
                        passed=False,
                        violations=(
                            (
                                f"{module_name}: import failed: "
                                f"{type(checked.exception).__name__}: {checked.error}"
                            ),
                        ),
                        summary=f"{module_name}: import failed",
                    )
                )
        merged_violations = tuple(
            violation for report in all_reports for violation in report.violations
        )
        passed = not merged_violations
        summary = (
            f"{project.name}: {len(merged_violations)} runtime violation(s)"
            if not passed
            else f"{project.name}: runtime census passed ({len(real_modules)} module(s))"
        )
        return r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(
                passed=passed, violations=merged_violations, summary=summary
            )
        )

    @staticmethod
    def _violation_rule_token(violation: str) -> str | None:
        """Return the trailing ``[rule]`` token of one census violation line.

        Every enforcement violation ends with its rule id (``[ENFORCE-046]``)
        when the catalog maps the tag, else the raw tag itself
        (``[class_prefix]``); bracketless lines (import failures) own no rule
        family and stay with the runtime census.
        """
        match = re.search(r"\[([^[\]]+)\]$", violation)
        if match is None:
            return None
        token: str = match.group(1)
        return token

    @staticmethod
    def _matches_census_family(token: str, family: str) -> bool:
        """Match one rule token against one configured census family.

        ENFORCE-* families name one exact catalog rule and must never
        prefix-capture a sibling (``ENFORCE-04`` would otherwise swallow
        ``ENFORCE-046``); every other family is a tag prefix.
        """
        if family.startswith("ENFORCE-"):
            return token == family
        return token.startswith(family)

    def _gate_owned(self, violations: t.SequenceOf[str]) -> tuple[str, ...]:
        """The violations ``census_gate`` owns; every other gate never sees them.

        A gate that owns census families grades exactly those families; the
        runtime census gate grades every family no other gate owns. Ownership
        is routing, never suppression: a family another gate owns is neither
        counted nor reported here. Bracketless lines (import failures) own no
        family and stay with the runtime census.
        """
        owned = self._gate_rule_families()
        own_families = owned.get(self.census_gate)
        foreign_families = frozenset(
            family
            for gate, families in owned.items()
            if gate != self.census_gate
            for family in families
        )
        kept: list[str] = []
        for violation in violations:
            token = self._violation_rule_token(violation)
            if own_families is None:
                keep = token is None or not any(
                    self._matches_census_family(token, family)
                    for family in foreign_families
                )
            else:
                keep = token is not None and any(
                    self._matches_census_family(token, family)
                    for family in own_families
                )
            if keep:
                kept.append(violation)
        return tuple(kept)

    def build_report(self) -> p.Result[m.Infra.ValidationReport]:
        """Build one validation report for the selected workspace projects."""
        owning_gates = frozenset({c.Infra.RUNTIME_CENSUS, *self._gate_rule_families()})
        if self.census_gate not in owning_gates:
            return r[m.Infra.ValidationReport].fail(
                f"runtime census has no rule families for gate {self.census_gate!r}; "
                f"owning gates: {', '.join(sorted(owning_gates))}"
            )
        projects_result = u.Infra.resolve_projects(self.repository_root, ())
        if projects_result.failure:
            return r[m.Infra.ValidationReport].from_failure(projects_result)
        projects = self._filtered_projects(projects_result.unwrap())
        if not projects:
            return r[m.Infra.ValidationReport].fail(
                f"runtime census selected no projects: root={self.repository_root}, "
                f"filter={self.project_filter!r}"
            )
        merged_violations: list[str] = []
        for project in projects:
            report_result = self._project_report(project)
            if report_result.failure:
                return r[m.Infra.ValidationReport].from_failure(report_result)
            report = report_result.value
            merged_violations.extend(report.violations)
        # Every owned finding blocks: ownership routes a family to its gate,
        # it never suspends one (operator order 2026-10-01, gc-wisp-1n83u4).
        owned_violations = self._gate_owned(merged_violations)
        label = (
            "runtime census"
            if self.census_gate == c.Infra.RUNTIME_CENSUS
            else f"runtime census ({self.census_gate})"
        )
        passed = not owned_violations
        summary = (
            f"{label} found {len(owned_violations)} violation(s)"
            if not passed
            else f"{label} passed"
        )
        return r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(
                passed=passed, violations=owned_violations, summary=summary
            )
        )

    @override
    def execute(self) -> p.Result[bool]:
        """Execute runtime census and collapse the report to ``r[bool]``."""
        report_result = self.build_report()
        if report_result.failure:
            return r[bool].from_failure(report_result)
        report = report_result.value
        if report.passed:
            return r[bool].ok(True)
        if self.output_format == c.Cli.OutputFormats.JSON:
            return r[bool].fail(report.model_dump_json())
        return r[bool].fail(self._render_text_summary(report))

    @staticmethod
    def _render_text_summary(report: m.Infra.ValidationReport) -> str:
        """Render violations grouped by rule with file:line context.

        The flat list the census used to emit made it impossible to see which
        rule or file owned the bulk of the debt. Grouping by rule_id (falling
        back to 'UNKNOWN' when a violation string carries no bracket) gives the
        operator a histogram and a per-rule file list in one read.
        """
        rule_buckets: MutableMapping[str, list[str]] = defaultdict(list)
        for violation in report.violations:
            match = re.search(r"\[(ENFORCE-\d+)\]", violation)
            rule_id = match.group(1) if match else "UNKNOWN"
            rule_buckets[rule_id].append(violation)
        header = f"{report.summary}\n"
        sections: list[str] = [header]
        for rule_id in sorted(rule_buckets):
            entries = rule_buckets[rule_id]
            sections.append(f"  {rule_id}: {len(entries)} violation(s)")
            seen: set[str] = set()
            for entry in entries:
                short = entry.split(": ", 1)[-1] if ": " in entry else entry
                if short not in seen:
                    seen.add(short)
                    sections.append(f"    {short}")
        return "\n".join(sections)


__all__: list[str] = ["FlextInfraRuntimeCensusValidator"]
