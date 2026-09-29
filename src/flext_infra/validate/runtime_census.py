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
from typing import TYPE_CHECKING, Annotated, override

from flext_core import r
from flext_infra import c, config, m, t, u

from ..base import s

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraRuntimeCensusValidator(s[bool]):
    """Post-import runtime enforcement census across workspace projects."""

    project_filter: Annotated[
        str | None, m.Field(description="Project filter (comma-separated)")
    ] = None

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
        and can never be suspended.
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

    @classmethod
    def _partition_suspended(
        cls, violations: t.SequenceOf[str]
    ) -> t.Pair[tuple[str, ...], tuple[t.Pair[str, int], ...]]:
        """Split violations into kept lines and per-suspended-gate counts.

        Consistency contract (gc-wisp-d7mnad): the census honors exactly the
        rule families the operator already suspended for their dedicated
        check gates in ``check_gate_suspensions`` — no new waiver surface.
        Matching families leave the failure count under one loud INFO line
        per family carrying the recorded authority; every unmapped family
        stays fully blocking.
        """
        suspensions = config.Infra.codegen.make.check_gate_suspensions
        kept: list[str] = []
        family_counts: dict[t.Pair[str, str], int] = {}
        gate_counts: dict[str, int] = {}
        for violation in violations:
            token = cls._violation_rule_token(violation)
            owner = None
            if token is not None:
                for suspension in suspensions:
                    if any(
                        cls._matches_census_family(token, family)
                        for family in suspension.census_rule_families
                    ):
                        owner = suspension
                        break
            if owner is None or token is None:
                kept.append(violation)
                continue
            for family in owner.census_rule_families:
                if cls._matches_census_family(token, family):
                    family_counts[owner.gate, family] = (
                        family_counts.get((owner.gate, family), 0) + 1
                    )
            gate_counts[owner.gate] = gate_counts.get(owner.gate, 0) + 1
        for suspension in suspensions:
            for family in suspension.census_rule_families:
                count = family_counts.get((suspension.gate, family), 0)
                if count:
                    u.Cli.info(
                        f"SUSPENDED census rule family {family} "
                        f"(gate {suspension.gate}); "
                        f"authority={suspension.authority}; "
                        f"reason={suspension.reason}; "
                        f"suppressed {count} finding(s)"
                    )
        return tuple(kept), tuple(gate_counts.items())

    def build_report(self) -> p.Result[m.Infra.ValidationReport]:
        """Build one validation report for the selected workspace projects."""
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
        kept_violations, suppressed_by_gate = self._partition_suspended(
            merged_violations
        )
        suppressed_total = len(merged_violations) - len(kept_violations)
        suppression_note = (
            (
                f"; {suppressed_total} suppressed under recorded gate suspensions "
                f"({', '.join(f'{gate}={count}' for gate, count in suppressed_by_gate)})"
            )
            if suppressed_total
            else ""
        )
        passed = not kept_violations
        summary = (
            f"runtime census found {len(kept_violations)} violation(s)"
            if not passed
            else "runtime census passed"
        ) + suppression_note
        return r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(
                passed=passed, violations=kept_violations, summary=summary
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
