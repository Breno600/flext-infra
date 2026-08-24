"""Integration tests for flext_infra cross-module flows.

Tests exercise cross-module flows using the public runtime surfaces, validating:
- Output/reporting methods via u.Infra
- Service r chaining
- Command runtime operations via u.Cli.run_checked/capture
- BaseMk generation flow

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from flext_infra import m, r, u
from flext_infra.basemk.generator import FlextInfraBaseMkGenerator
from flext_infra.basemk.renderer import FlextInfraBaseMkTemplateRenderer
from flext_infra.gates.markdown import FlextInfraMarkdownGate
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from flext_infra.workspace.orchestrator import FlextInfraOrchestratorService
from flext_tests import tm
from tests import TestsFlextInfraUtilities as tu

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [pytest.mark.integration]


class TestsFlextInfraIntegrationInfraIntegration:
    """Integration tests for the public FlextInfra surface."""

    @pytest.mark.integration
    def test_workspace_detector_and_orchestrator_share_state(
        self, tmp_path: Path
    ) -> None:
        """Test that FlextInfraWorkspaceDetector and orchestrator share state.

        Validates:
        - Detector can be created
        - Orchestrator can be created
        - Both can access shared workspace information
        """
        workspace_root = tmp_path / "workspace"
        workspace_root.mkdir()
        (workspace_root / ".git").mkdir()
        detector = FlextInfraWorkspaceDetector()
        orchestrator = FlextInfraOrchestratorService(verb="test")
        tm.that(detector, none=False)
        tm.that(orchestrator, none=False)
        tm.that(detector, is_=FlextInfraWorkspaceDetector)
        tm.that(orchestrator, is_=FlextInfraOrchestratorService)

    @pytest.mark.integration
    def test_workspace_detector_returns_flext_result(self) -> None:
        """Test that workspace detector operations return r.

        Validates:
        - Detector methods return r
        - Result typing is correct
        """
        detector = FlextInfraWorkspaceDetector()
        tm.that(detector, none=False)
        tm.that(detector, is_=FlextInfraWorkspaceDetector)

    @pytest.mark.integration
    def test_basemk_template_renderer_and_generator_flow(self, tmp_path: Path) -> None:
        """Test BaseMk template renderer → generator flow.

        Validates:
        - Template renderer can be created
        - Generator can be created
        - Both work together in a flow
        """
        output_dir = tmp_path / "basemk_output"
        output_dir.mkdir()
        renderer = FlextInfraBaseMkTemplateRenderer()
        generator = FlextInfraBaseMkGenerator()
        tm.that(renderer, none=False)
        tm.that(generator, none=False)
        tm.that(renderer, is_=FlextInfraBaseMkTemplateRenderer)
        tm.that(generator, is_=FlextInfraBaseMkGenerator)

    @pytest.mark.integration
    def test_basemk_generator_generates_valid_content(self, tmp_path: Path) -> None:
        """Test BaseMk generator validates rendered output using real make."""
        _ = tmp_path
        generator = FlextInfraBaseMkGenerator()
        generated = generator.execute()
        tm.ok(generated)
        tm.that(generated.value, is_=str)
        tm.that(generated.value, has="STANDARD_VERBS := clean")

    @pytest.mark.integration
    def test_markdown_fix_formats_instead_of_linting(self, tmp_path: Path) -> None:
        """The mutating verb must format Markdown, never lint it.

        ``rumdl check --fix`` is a linter: it exits non-zero whenever a finding
        has no autofix, so a run that repaired every fixable file still failed
        the verb. ``rumdl fmt`` carries formatter-style exit codes, which is
        the contract the mutating verb promises.

        R12 moved every public verb out of ``base.mk`` into the gate pipeline,
        so the owner of this contract is the markdown gate. The document below
        carries an unfixable finding (MD041: no top-level heading) next to a
        fixable one (MD009: trailing whitespace): the linter fails on it, the
        formatter repairs what it can and still succeeds.
        """
        project_dir = tu.Tests.mk_project(tmp_path, "markdown-fmt-contract")
        document = project_dir / "README.md"
        document.write_text("not a heading   \n", encoding="utf-8")
        context = m.Infra.GateContext(
            workspace=tmp_path, reports_dir=tmp_path, apply_fixes=True
        )

        execution = FlextInfraMarkdownGate(tmp_path).fix(project_dir, context)

        tm.that(execution.result.passed, eq=True)
        tm.that(document.read_text(encoding="utf-8"), eq="not a heading\n")

    @pytest.mark.integration
    def test_basemk_renders_shell_continuations_without_blank_lines(self) -> None:
        r"""Every rendered recipe line must keep its shell continuation intact.

        A Jinja loop that emits a bare newline breaks the ``\\`` continuation of
        the surrounding shell construct, so the generated recipe dies with
        'syntax error: unexpected end of file' before running anything.
        """
        generated = FlextInfraBaseMkGenerator().execute()

        tm.ok(generated)
        continued = [
            index
            for index, line in enumerate(generated.value.splitlines())
            if line.rstrip().endswith("\\")
        ]
        lines = generated.value.splitlines()
        tm.that([index for index in continued if not lines[index + 1].strip()], eq=[])

    @pytest.mark.integration
    def test_basemk_invokes_infra_entrypoints_without_eval(self) -> None:
        """Infra entrypoints run directly, never rebuilt as an eval string.

        The entrypoint macros carry an executable guard, so they contain ``;``
        and ``||``. Captured into a shell variable, only the fragment before
        the first ``;`` survives and the guard leaks into the recipe:
        ``FLEXT_INFRA_PYTHON: command not found`` followed by
        ``eval: --: invalid option``.
        """
        generated = FlextInfraBaseMkGenerator().execute()

        tm.ok(generated)
        tm.that("eval $$cmd" in generated.value, eq=False)

    @pytest.mark.integration
    def test_output_singleton_has_expected_methods(self) -> None:
        """Test that reporting/output methods are exposed through u.Infra.

        Validates u.Infra MRO output methods are available:
        - status, summary, error, warning, info, header, progress
        """
        tm.that(callable(u.Cli.status), eq=True)
        tm.that(callable(u.Cli.summary), eq=True)
        tm.that(callable(u.Cli.error), eq=True)
        tm.that(callable(u.Cli.warning), eq=True)
        tm.that(callable(u.Cli.info), eq=True)
        tm.that(callable(u.Cli.header), eq=True)
        tm.that(callable(u.Cli.progress), eq=True)

    @pytest.mark.integration
    def test_output_methods_are_callable_via_u_infra(self) -> None:
        """Test that reporting methods are callable through the real facade.

        Validates:
        - All methods are callable through u.Infra
        """
        tm.that(callable(u.Cli.status), eq=True)
        tm.that(callable(u.Cli.summary), eq=True)
        tm.that(callable(u.Cli.error), eq=True)
        tm.that(callable(u.Cli.warning), eq=True)
        tm.that(callable(u.Cli.info), eq=True)
        tm.that(callable(u.Cli.header), eq=True)
        tm.that(callable(u.Cli.progress), eq=True)

    @pytest.mark.integration
    def test_service_result_chaining_with_map(self) -> None:
        """Test chaining multiple services via .map().

        Validates:
        - r.map() works with service results
        - Type is preserved through chain
        - Value is transformed correctly
        """
        initial_value = 10
        result = r[int].ok(initial_value).map(lambda x: x * 2).map(lambda x: x + 5)
        tm.ok(result)
        tm.that(result.value, eq=25)

    @pytest.mark.integration
    def test_service_result_chaining_with_flat_map(self) -> None:
        """Test chaining multiple services via .flat_map().

        Validates:
        - r.flat_map() works with service results
        - Type is preserved through chain
        - Failures propagate correctly
        """
        initial_value = 10
        result = (
            r[int]
            .ok(initial_value)
            .flat_map(lambda x: r[int].ok(x * 2))
            .flat_map(lambda x: r[int].ok(x + 5))
        )
        tm.ok(result)
        tm.that(result.value, eq=25)

    @pytest.mark.integration
    def test_service_result_chaining_failure_propagation(self) -> None:
        """Test that failures propagate through result chains.

        Validates:
        - Failure stops the chain
        - Error message is preserved
        - Subsequent operations are not executed
        """
        initial_value = 10
        result = (
            r[int]
            .ok(initial_value)
            .flat_map(lambda x: r[int].ok(x * 2))
            .flat_map(lambda _: r[int].fail("intentional error"))
            .flat_map(lambda x: r[int].ok(x + 5))
        )
        tm.fail(result)
        tm.that(result.error, is_=str)
        tm.that(result.error, has="intentional error")

    @pytest.mark.integration
    def test_service_result_chaining_with_mixed_operations(self) -> None:
        """Test chaining with mixed map and flat_map operations.

        Validates:
        - Mixed operations work together
        - Type is preserved
        - Values are transformed correctly
        """
        initial_value = 5
        result = (
            r[int]
            .ok(initial_value)
            .map(lambda x: x * 2)
            .flat_map(lambda x: r[int].ok(x + 3))
            .map(lambda x: x * 2)
        )
        tm.ok(result)
        tm.that(result.value, eq=26)

    @pytest.mark.integration
    def test_discover_projects_via_mro(self) -> None:
        """Test u.Infra.discover_projects flow.

        Validates:
        - discover_projects is callable via u.Infra MRO
        - workspace_root is callable via u.Infra MRO
        """
        tm.that(callable(u.Infra.discover_projects), eq=True)
        tm.that(callable(u.Infra.resolve_workspace_root_or_cwd), eq=True)

    @pytest.mark.integration
    def test_path_utilities_via_mro(self) -> None:
        """Test u.Infra path utility methods are available via MRO."""
        tm.that(callable(u.Infra.resolve_project_root), eq=True)

    @pytest.mark.integration
    def test_cli_capture_git_current_branch_in_real_repo(self, tmp_path: Path) -> None:
        """Test git branch detection through the canonical CLI runtime surface."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        init_result = u.Cli.run_checked(["git", "init"], cwd=repo_root)
        tm.ok(init_result)
        email_result = u.Cli.run_checked(
            ["git", "config", "user.email", "infra@example.com"], cwd=repo_root
        )
        tm.ok(email_result)
        name_result = u.Cli.run_checked(
            ["git", "config", "user.name", "Infra Test"], cwd=repo_root
        )
        tm.ok(name_result)
        sample_file = repo_root / "README.md"
        _ = sample_file.write_text("infra test\n", encoding="utf-8")
        add_result = u.Cli.run_checked(["git", "add", "README.md"], cwd=repo_root)
        tm.ok(add_result)
        commit_result = u.Cli.run_checked(
            ["git", "commit", "-m", "initial"], cwd=repo_root
        )
        tm.ok(commit_result)
        branch_result = u.Cli.capture(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo_root
        )
        tm.ok(branch_result)
        tm.that(branch_result.value, ne="")

    @pytest.mark.integration
    def test_command_runner_capture_executes_real_command(self) -> None:
        """Test u.Cli.capture with a real external command."""
        capture_result = u.Cli.capture(["python3", "-c", "print('infra-ok')"])
        tm.ok(capture_result)
        tm.that(capture_result.value, eq="infra-ok")
