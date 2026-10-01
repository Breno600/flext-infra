"""Tests for Rope-based silent failure detection and validation."""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from flext_cli import u as cli_u
from flext_tests import tm

from flext_infra import main as infra_main, u as infra_u
from flext_infra.detectors.silent_failure_detector import (
    FlextInfraSilentFailureDetector,
)
from flext_infra.validate.silent_failure import FlextInfraSilentFailureValidator
from tests import m, t, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraSilentFailure:
    """Silent-failure detector and validator suite."""

    def _create_silent_failure_project(
        self,
        tmp_path: Path,
        *,
        name: str = "flext-infra",
    ) -> Path:
        project: Path = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name=name,
            pkg_name=name.replace("-", "_"),
            files={
                "utilities.py": (
                    "from __future__ import annotations\n\n"
                    "from collections.abc import Mapping, Sequence\n\n"
                    "from flext_core import r\n\n"
                    "def run_guard(validation_result: p.Result[bool]) -> p.Result[bool]:\n"
                    "    if validation_result.failure:\n"
                    "        return False\n"
                    "    return r[bool].ok(True)\n\n"
                    "def run_except() -> p.Result[bool]:\n"
                    "    try:\n"
                    "        raise ValueError('boom')\n"
                    "    except ValueError as exc:\n"
                    "        return None\n\n"
                    "def run_unwrap(validation_result: p.Result[bool]) -> bool:\n"
                    "    return validation_result.unwrap_or(False)\n"
                ),
            },
        )
        (project / "pyproject.toml").write_text(
            (f"[project]\nname='{name}'\ndependencies=['flext-core>=0.1.0']\n"),
            encoding="utf-8",
        )
        return project

    def test_detect_file_reports_guard_except_and_unwrap(self, tmp_path: Path) -> None:
        project = self._create_silent_failure_project(tmp_path)
        file_path = project / "src" / "flext_infra" / "utilities.py"
        rope_project = u.Infra.init_rope_project(project)
        try:
            issues = FlextInfraSilentFailureDetector.detect_file(
                m.Infra.DetectorContext(
                    file_path=file_path,
                    project_root=project,
                    rope_project=rope_project,
                ),
            )
        finally:
            rope_project.close()

        tm.that(len(issues), eq=3)
        codes = tuple(issue.code for issue in issues)
        tm.that(codes, has="silent-failure-guard")
        tm.that(codes, has="silent-failure-except")
        tm.that(codes, has="silent-failure-unwrap-or")

    def test_tuple_form_handler_is_as_narrow_as_the_single_form(self) -> None:
        """``except (A, B):`` declares narrow exceptions, exactly like ``except A:``.

        Both handler rules resolved the clause through the expression resolver,
        which returns the empty name for an ``ast.Tuple`` -- the same value a
        bare ``except:`` yields. Every tuple handler was therefore reported as
        a broad handler that fails to propagate.
        """
        source = (
            "def narrow_tuple(path):\n"
            "    try:\n"
            "        return parse(path)\n"
            "    except (ValueError, KeyError) as exc:\n"
            "        raise RuntimeError(path) from exc\n"
            "\n"
            "\n"
            "def narrow_single(path):\n"
            "    try:\n"
            "        return parse(path)\n"
            "    except ValueError as exc:\n"
            "        raise RuntimeError(path) from exc\n"
            "\n"
            "\n"
            "def broad_tuple(path):\n"
            "    try:\n"
            "        return parse(path)\n"
            "    except (ValueError, Exception):\n"
            "        return None\n"
        )
        findings = infra_u.Infra.collect_silent_failure_findings(
            ast.parse(source),
            source,
        )

        broad_lines = tuple(
            finding.line
            for finding in findings
            if finding.kind == "silent-failure-broad-except"
        )
        # The narrow handlers propagate, so neither form is reported; the one
        # that names Exception among its types still is.
        tm.that(len(broad_lines), eq=1)
        tm.that(
            source.splitlines()[broad_lines[0] - 1].strip(),
            eq="except (ValueError, Exception):",
        )

    def test_relaxations_for_collectors_predicates_and_test_teardown(self) -> None:
        """Only production failure paths are flagged."""
        source = (
            "import contextlib\n"
            "\n"
            "\n"
            "def collect_probe_findings(path):\n"
            "    result = parse(path)\n"
            "    if result.failure:\n"
            "        return []\n"
            "    return []\n"
            "\n"
            "\n"
            "def has_header(path):\n"
            "    try:\n"
            "        return parse(path)\n"
            "    except RegistryError:\n"
            "        return False\n"
            "\n"
            "\n"
            "def run_guard(validation_result):\n"
            "    if validation_result.failure:\n"
            "        return False\n"
            "    return True\n"
            "\n"
            "\n"
            "def teardown(pid):\n"
            "    with contextlib.suppress(ProcessLookupError):\n"
            "        os.kill(pid, 9)\n"
        )
        tree = ast.parse(source)
        production = infra_u.Infra.collect_silent_failure_findings(tree, source)
        production_kinds = tuple(finding.kind for finding in production)
        tm.that(production_kinds, has="silent-failure-guard")
        tm.that(production_kinds, has="silent-failure-suppress")
        tm.that(production_kinds, excludes="silent-failure-except")
        test_module = infra_u.Infra.collect_silent_failure_findings(
            tree,
            source,
            is_test_module=True,
        )
        test_kinds = tuple(finding.kind for finding in test_module)
        tm.that(test_kinds, excludes="silent-failure-suppress")
        tm.that(test_kinds, has="silent-failure-guard")

    def test_fix_silent_failure_sentinels_rewrites_deterministic_cases(
        self,
        tmp_path: Path,
    ) -> None:
        project = self._create_silent_failure_project(tmp_path)
        file_path = project / "src" / "flext_infra" / "utilities.py"
        rope_project = u.Infra.init_rope_project(project)
        try:
            resource = u.Infra.resolve_resource_from_path(rope_project, file_path)
            resource = tm.not_none(resource)
            updated, changes = u.Infra.fix_silent_failure_sentinels(
                rope_project,
                resource,
                apply=False,
            )
        finally:
            rope_project.close()

        tm.that(len(changes), eq=1)
        tm.that(
            updated,
            has="return r[bool].fail(validation_result.error or 'validation failed')",
        )
        tm.that(updated, has="return r[bool].fail(str(exc), exception=exc)")
        tm.that(updated, has="return validation_result.unwrap_or(False)")

    def test_execute_reports_detected_issues(self, tmp_path: Path) -> None:
        project = self._create_silent_failure_project(tmp_path)
        result = FlextInfraSilentFailureValidator(
            repository_root=project,
            project_filter="flext-infra",
        ).execute()

        tm.fail(result, has="silent failure validation found 3 issue(s)")
        error = result.error or ""
        tm.that(error, has="silent-failure-guard")
        tm.that(error, has="silent-failure-except")

    def test_execute_json_output_format_emits_full_report(self, tmp_path: Path) -> None:
        project = self._create_silent_failure_project(tmp_path)
        result = FlextInfraSilentFailureValidator(
            repository_root=project,
            project_filter="flext-infra",
            output_format="json",
        ).execute()

        tm.that(result.failure, eq=True)
        report = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
            cli_u.Cli.json_loads(result.error or "").unwrap(),
        )
        tm.that(report["passed"], eq=False)
        violations = t.Cli.JSON_LIST_ADAPTER.validate_python(report["violations"])
        tm.that(len(violations), eq=3)
        tm.that(report["summary"], has="found 3 issue(s)")

    def test_execute_text_output_reports_all_findings_uncapped(
        self,
        tmp_path: Path,
    ) -> None:
        finding_count = 25
        source = "from __future__ import annotations\n\n" + "\n".join(
            f"def run_guard_{index:02d}(res: p.Result[bool]) -> p.Result[bool]:\n"
            "    if res.failure:\n"
            "        return False\n"
            "    return r[bool].ok(True)\n"
            for index in range(finding_count)
        )
        project = u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name="flext-infra",
            pkg_name="flext_infra",
            files={"utilities.py": source},
        )
        result = FlextInfraSilentFailureValidator(
            repository_root=project,
            project_filter="flext-infra",
        ).execute()

        tm.fail(result, has=f"found {finding_count} issue(s)")
        error = result.error or ""
        tm.that(error.count("silent-failure-guard"), eq=finding_count)

    def test_validate_cli_route_returns_non_zero_for_violations(
        self,
        tmp_path: Path,
    ) -> None:
        project = self._create_silent_failure_project(tmp_path)
        exit_code = infra_main([
            "validate",
            "silent-failure",
            "--repository-root",
            str(project),
            "--project-filter",
            "flext-infra",
        ])

        tm.that(exit_code, eq=1)

    def test_validate_cli_route_help_returns_zero(self) -> None:
        tm.that(infra_main(["validate", "silent-failure", "--help"]), eq=0)
