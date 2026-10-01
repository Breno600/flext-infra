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
    def _is_local_class(klass: type, module_name: str) -> bool:
        """Return True when ``klass`` is defined in ``module_name`` (not imported)."""
        return klass.__module__ == module_name

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

    def _check_module(self, module_name: str) -> t.SequenceOf[m.Infra.ValidationReport]:
        """Import one module and run runtime enforcement on its local classes."""
        module = importlib.import_module(module_name)
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
        """Run the runtime census for one project and return a merged report.

        A project without an importable package establishes no census: it
        fails, never passes on empty input.
        """
        layout = u.Infra.layout(project.path, project=project)
        if layout is None:
            return r[m.Infra.ValidationReport].fail(
                f"runtime census: {project.name} has no importable package"
            )
        real_modules = list(self._walk_modules(layout.package_name))
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
            all_reports.extend(self._check_module(module_name))
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
        passed = not merged_violations
        summary = (
            f"runtime census found {len(merged_violations)} violation(s)"
            if not passed
            else "runtime census passed"
        )
        return r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(
                passed=passed, violations=tuple(merged_violations), summary=summary
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
