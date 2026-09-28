"""``run_deptry`` executes the environment's real ``deptry`` executable."""

from __future__ import annotations

import sys
from pathlib import Path

from flext_tests import tm

from flext_infra import config
from flext_infra.deps.detection import FlextInfraDependencyDetectionService
from tests import c, t, u


class TestsFlextInfraDepsDetectionDeptry:
    """Behaviour of ``run_deptry`` against a deptry executable on disk."""

    @staticmethod
    def _environment(
        tmp_path: Path, report: str | None, *, exit_code: int = 0
    ) -> t.Pair[Path, Path]:
        """Create a project and a ``deptry`` that writes ``report`` as its JSON."""
        venv_bin = tmp_path / "venv" / "bin"
        venv_bin.mkdir(parents=True)
        project = tmp_path / "project"
        project.mkdir()
        (project / c.PYPROJECT_FILENAME).write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        write = ""
        if report is not None:
            payload = tmp_path / "deptry-payload.json"
            payload.write_text(report, encoding=c.Cli.ENCODING_DEFAULT)
            write = (
                'while [ "$#" -gt 0 ]; do\n'
                '  if [ "$1" = "--json-output" ]; then cp '
                f'"{payload}" "$2"; fi\n'
                "  shift\n"
                "done\n"
            )
        deptry = venv_bin / c.Infra.DEPTRY
        deptry.write_text(
            f"#!/bin/sh\n{write}exit {exit_code}\n", encoding=c.Cli.ENCODING_DEFAULT
        )
        deptry.chmod(0o755)
        return venv_bin, project

    def test_issues_and_exit_code_are_reported(
        self, tmp_path: Path, deptry_report_payload: t.JsonPayload
    ) -> None:
        source = tmp_path / "source-report.json"
        tm.ok(u.Cli.json_write(source, deptry_report_payload))
        report = source.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        venv_bin, project = self._environment(tmp_path, report, exit_code=1)

        issues, exit_code = tm.ok(
            FlextInfraDependencyDetectionService().run_deptry(project, venv_bin)
        )

        tm.that(exit_code, eq=1)
        tm.that(len(issues), eq=1)

    def test_project_without_config_is_skipped(self, tmp_path: Path) -> None:
        venv_bin = tmp_path / "venv" / "bin"
        venv_bin.mkdir(parents=True)
        project = tmp_path / "project"
        project.mkdir()

        result = FlextInfraDependencyDetectionService().run_deptry(project, venv_bin)

        tm.that(tm.ok(result), eq=([], 0))

    def test_unlaunchable_deptry_is_a_failure(self, tmp_path: Path) -> None:
        venv_bin, project = self._environment(tmp_path, None)
        (venv_bin / c.Infra.DEPTRY).chmod(0o644)

        tm.fail(FlextInfraDependencyDetectionService().run_deptry(project, venv_bin))

    def test_invalid_or_empty_report_is_a_failure(self, tmp_path: Path) -> None:
        for index, report in enumerate(("{ invalid json }", "")):
            venv_bin, project = self._environment(tmp_path / str(index), report)

            result = FlextInfraDependencyDetectionService().run_deptry(
                project, venv_bin
            )

            tm.that(result.failure, eq=True)

    def test_non_mapping_issue_is_a_failure(self, tmp_path: Path) -> None:
        venv_bin, project = self._environment(
            tmp_path, '["not_a_dict", {"error": {"code": "DEP001"}}]'
        )

        result = FlextInfraDependencyDetectionService().run_deptry(project, venv_bin)

        tm.fail(result, has="must be a mapping")

    @staticmethod
    def _profile_runtime(upstream: str) -> t.StrSequence:
        """Read one shared dependency profile's runtime from the codegen SSOT."""
        return next(
            item.runtime
            for item in config.Infra.codegen.scaffold.project.dependency_profiles
            if item.project is None and item.upstream == upstream
        )

    def test_profile_injected_dependencies_are_governed(self, tmp_path: Path) -> None:
        """Real deptry DEP002 findings for profile requirements are policy."""
        upstream = next(
            item.upstream
            for item in config.Infra.codegen.scaffold.project.dependency_profiles
            if item.project is None
        )
        runtime = self._profile_runtime(upstream)
        declared = ", ".join(f'"{item}"' for item in (*runtime, "six"))
        project = u.Tests.mk_project(
            tmp_path,
            "governed-consumer",
            with_src=True,
            pyproject=(
                '[project]\nname = "governed-consumer"\nversion = "0.1.0"\n'
                f"dependencies = [{declared}]\n"
            ),
        )
        service = FlextInfraDependencyDetectionService()
        issues, _ = tm.ok(service.run_deptry(project, Path(sys.executable).parent))
        unused = {
            u.Infra.dep_name(str(issue.get(c.Infra.MODULE)))
            for issue in issues
            if u.Cli.json_as_mapping(issue.get(c.Infra.ERROR)).get(c.Infra.CODE)
            == c.Infra.DEPTRY_UNUSED_DEPENDENCY_CODE
        }
        tm.that(unused, has="six")
        governed = set(tm.ok(service.governed_profile_dependencies(project)))
        tm.that(governed, eq={u.Infra.dep_name(item) for item in runtime})
        tm.that(governed - unused, empty=True)
        report = service.build_project_report(
            project.name, tm.ok(service.govern_deptry_issues(project, issues))
        )
        tm.that(list(report.deptry.unused), eq=["six"])

    def test_project_without_profile_keeps_every_finding(self, tmp_path: Path) -> None:
        """A project no shared profile governs keeps deptry's findings intact."""
        project = u.Tests.mk_project(
            tmp_path,
            "independent",
            with_src=True,
            pyproject=(
                '[project]\nname = "independent"\nversion = "0.1.0"\n'
                'dependencies = ["six"]\n'
            ),
        )
        service = FlextInfraDependencyDetectionService()
        tm.that(tm.ok(service.governed_profile_dependencies(project)), empty=True)
        issues: t.SequenceOf[t.JsonMapping] = [
            {"error": {"code": c.Infra.DEPTRY_UNUSED_DEPENDENCY_CODE}, "module": "six"}
        ]
        tm.that(tm.ok(service.govern_deptry_issues(project, issues)), eq=tuple(issues))

    def test_default_report_is_removed_after_parsing(self, tmp_path: Path) -> None:
        venv_bin, project = self._environment(tmp_path, "[]")

        result = FlextInfraDependencyDetectionService().run_deptry(
            project, venv_bin, extend_exclude=["tests", "docs"]
        )

        tm.that(tm.ok(result), eq=([], 0))
        tm.that((project / ".deptry-report.json").exists(), eq=False)
