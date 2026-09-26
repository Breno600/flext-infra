"""Public functional contract for multi-environment CI matrix codegen.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, t
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.codegen.project_new import FlextInfraCodegenProjectNew
from tests import u

from ._support import CodegenTestSupport
from .conform_support import TestsFlextInfraConformSupport

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenCiMatrix:
    """Prove codegen emits the CI matrix workflow and distro Dockerfiles."""

    @staticmethod
    def _render_project(root: Path) -> Path:
        """Render one fresh internal_flext project into root and return it."""
        service = FlextInfraCodegenProjectNew(
            flext_source=u.Tests.flext_source(),
            name="flext-demo",
            kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
            output_root=root,
            repository_url="https://github.com/flext-sh/flext-demo.git",
            repository_branch="0.12.0-dev",
            flext_repository_url=u.Tests.repository_ref(config.Infra.name).url,
            flext_repository_ref=u.Tests.provider_branch(),
            provider="flext-sh",
            license="MIT",
            author_name="FLEXT Team",
            author_email="team@flext.dev",
            upstream="flext_cli",
            year=2026,
            apply_changes=True,
        )
        result = service.execute()
        tm.ok(result)
        return root

    @staticmethod
    def _assert_dispatch_only(triggers: str) -> None:
        """Assert a workflow trigger section selects only manual dispatch."""
        tm.that(triggers, has="workflow_dispatch: {}")
        for forbidden in (
            "branches: [main]",
            "pull_request:",
            "ready_for_review",
            "repository_branch",
            "0.12.0-dev",
            "develop",
            "branches: [dev]",
        ):
            tm.that(triggers, lacks=forbidden)

    def test_ci_matrix_profiles_are_topology_complete(self) -> None:
        """Matrix and distro Dockerfiles cover both repository-local profiles."""
        entries = config.Infra.codegen.templates.entries
        matrix = next(
            entry
            for entry in entries
            if entry.destination == ".github/workflows/ci-matrix.yml"
        )
        tm.that(set(matrix.profiles), eq={"workspace", "standalone"})
        docker_dests = {
            f"tests/fixtures/ci/docker/{name}.Dockerfile"
            for name in ("ubuntu", "debian", "fedora", "alpine", "arch")
        }
        for entry in entries:
            if entry.destination not in docker_dests:
                continue
            tm.that(set(entry.profiles), eq={"workspace", "standalone"})

    def test_ci_matrix_workflow_emitted(self, tmp_path: Path) -> None:
        """Generated project carries .github/workflows/ci-matrix.yml."""
        root = self._render_project(tmp_path / "external")
        tm.that((root / ".github" / "workflows" / "ci-matrix.yml").is_file(), eq=True)

    def test_latest_mise_is_owned_only_by_make_setup(self, tmp_path: Path) -> None:
        """Generated workflows never install Mise or uv beside make setup."""
        root = self._render_project(tmp_path / "external")
        workflows = root / ".github" / "workflows"

        for workflow in workflows.glob("*.yml"):
            content = workflow.read_text(encoding="utf-8")
            tm.that(content, lacks="jdx/mise-action")
            tm.that(content, lacks="astral-sh/setup-uv")
            tm.that(content, lacks="Install direnv")

    def test_external_attestation_orchestration_is_not_generated_by_flext(
        self, tmp_path: Path
    ) -> None:
        """FLEXT exposes primitives without selecting AI Hub's GitHub capability."""
        root = self._render_project(tmp_path / "attested")
        makefile = (root / "Makefile").read_text(encoding="utf-8")
        tm.that(makefile, lacks="_builtin_checkpoint_")
        tm.that((root / ".github/scripts/gate-attestation.sh").exists(), eq=False)
        tm.that((root / ".github/workflows/gate-attestation.yml").exists(), eq=False)
        tm.that((root / ".github/attestations/allowed_signers").exists(), eq=False)

    def test_github_apps_are_not_selected_for_draft_prs(self, tmp_path: Path) -> None:
        """Versioned app policy reserves external review for non-Draft PRs."""
        root = self._render_project(tmp_path / "apps-review-only")
        tm.that((root / "cubic.yaml").exists(), eq=False)
        tm.that((root / ".coderabbit.yaml").exists(), eq=False)

    def test_ci_workflow_uses_immutable_action_catalog(self, tmp_path: Path) -> None:
        """Every generated action reference resolves from the typed action SSOT."""
        root = self._render_project(tmp_path / "external")
        workflows = "\n".join(
            (root / ".github" / "workflows" / filename).read_text(encoding="utf-8")
            for filename in ("ci.yml", "ci-matrix.yml")
        )
        catalog = {
            f"{action.repository}@{action.version}"
            for action in config.Infra.codegen.github_actions.values()
        }
        used_actions = tuple(
            line.split("uses:", maxsplit=1)[1].strip().split(maxsplit=1)[0]
            for line in workflows.splitlines()
            if "uses:" in line
        )
        tm.that(len(used_actions), gt=0)
        for action in used_actions:
            tm.that(catalog, has=action)

        tm.that(workflows, lacks="continue-on-error")
        tm.that(workflows, lacks="set +e")
        tm.that(workflows, lacks="|| make")
        tm.that(workflows, lacks="soft-pass")

    def test_blocking_ci_bootstraps_only_through_make_setup(
        self, tmp_path: Path
    ) -> None:
        """Generated blocking CI provisions every binary via the Make surface."""
        root = self._render_project(tmp_path / "external")
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )

        ci_step_runs = tuple(
            f"run: CI=Y make {step.verb}"
            for step in config.Infra.codegen.make.workflow
            if "ci" in step.contexts
        )
        for run_line in ci_step_runs:
            tm.that(workflow, has=run_line)
        # A verb whose workflow row omits the ci context never renders into CI
        # (operator ruling 2026-09-23: make test runs locally and on pre-push).
        for step in config.Infra.codegen.make.workflow:
            if "ci" not in step.contexts:
                tm.that(workflow, lacks=f"run: CI=Y make {step.verb}\n")
        tm.that(ci_step_runs, has="run: CI=Y make setup")
        # `conform` no longer exists as a Make verb (S1, operator law
        # 2026-09-14); the blocking generation gate is the "gen fixed point"
        # step, which runs `make gen` and proves the tree is unchanged.
        tm.that(workflow, has="- name: gen fixed point (blocking)")
        tm.that(workflow, has="CI=Y make gen")
        tm.that(
            workflow,
            has='test -z "$(git status --porcelain --untracked-files=all --ignore-submodules=none)"',
        )
        tm.that(workflow, lacks="run: CI=Y make conform")
        tm.that(workflow, has="run: CI=Y make audit")
        tm.that(workflow, lacks="attest/gates/v1")
        tm.that(workflow, lacks="github verify-gates")
        tm.that(workflow, lacks="WHAT=")
        step_indices = tuple(workflow.index(run_line) for run_line in ci_step_runs)
        tm.that(step_indices, eq=tuple(sorted(step_indices)))
        setup_index = workflow.index("run: CI=Y make setup")
        gen_fixed_point_index = workflow.index("- name: gen fixed point (blocking)")
        audit_index = workflow.index("run: CI=Y make audit")
        check_index = workflow.index("run: CI=Y make check")
        tm.that(
            setup_index < gen_fixed_point_index < audit_index < check_index, eq=True
        )
        header, jobs = workflow.split("\njobs:\n", maxsplit=1)
        tm.that(header, lacks="permissions:")
        ci_job = jobs.split("\n  merge-guard:", maxsplit=1)[0]
        tm.that(ci_job, has="permissions:\n      contents: read")
        tm.that(jobs, has="merge-guard:")
        tm.that(jobs, has="Block WIP heads from protected integration branches")

    def test_blocking_ci_does_not_configure_github_cli_auth(
        self, tmp_path: Path
    ) -> None:
        """FLEXT codegen never selects GitHub CLI authentication."""
        root = self._render_project(tmp_path / "external")
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )

        tm.that(workflow, lacks="- name: Configure GitHub authentication")
        tm.that(workflow, lacks="GH_TOKEN: ${{ github.token }}")
        tm.that(workflow, lacks="run: gh auth setup-git")
        steps_index = workflow.index("    steps:")
        setup_index = workflow.index("run: CI=Y make setup")
        tm.that(steps_index < setup_index, eq=True)

    def test_rendered_workflow_python_commands_compile(self, tmp_path: Path) -> None:
        """YAML block indentation must preserve executable Python command bodies."""
        root = self._render_project(tmp_path / "external")
        workflow = root / ".github" / "workflows" / "ci.yml"
        document = u.Cli.yaml_load_mapping(workflow)
        jobs = t.Cli.JSON_MAPPING_ADAPTER.validate_python(document["jobs"])
        compiled = 0
        for raw_job in jobs.values():
            job = t.Cli.JSON_MAPPING_ADAPTER.validate_python(raw_job)
            steps = job["steps"]
            if not isinstance(steps, list):
                msg = "workflow job steps must be a sequence"
                raise TypeError(msg)
            for raw_step in steps:
                step = t.Cli.JSON_MAPPING_ADAPTER.validate_python(raw_step)
                script = step.get("run")
                if not isinstance(script, str):
                    continue
                for source in re.findall(r"python3 -c '([^']*)'", script):
                    compile(source, str(workflow), "exec")
                    compiled += 1
        tm.that(compiled, gt=0)

    def test_rendered_pre_commit_uses_typed_hook_contexts(self, tmp_path: Path) -> None:
        """The generated staged hooks render the configured workflow partitions."""
        root = self._render_project(tmp_path / "external")
        hooks = (root / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        workflow = config.Infra.codegen.make.workflow
        ci = config.Infra.codegen.make.ci

        for hook_id, context in (
            ("flext-pre-commit-candidate", "pre_commit"),
            ("flext-pre-push-candidate", "pre_push"),
        ):
            enabled = bool(getattr(config.Infra.codegen.make, context))
            commands = "; ".join(
                f"make {step.verb}" for step in workflow if context in step.contexts
            )
            if enabled:
                tm.that(hooks, has=f"id: {hook_id}")
                stage = hooks.split(f"id: {hook_id}", maxsplit=1)[1].split(
                    "pass_filenames:", maxsplit=1
                )[0]
                tm.that(stage, has=f"{commands};")
                tm.that(stage, has=f"unset MAKEFLAGS {ci.variable};")
            else:
                tm.that(hooks, lacks=f"id: {hook_id}")
        tm.that(hooks, lacks=f"export {ci.variable}={ci.value}")

    def test_ci_workflow_cancels_superseded_ref_runs(self, tmp_path: Path) -> None:
        """Generated CI groups competing runs by workflow and ref."""
        root = self._render_project(tmp_path / "external")
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )

        tm.that(workflow, has="concurrency:")
        tm.that(workflow, has="group: ${{ github.workflow }}-${{ github.ref }}")
        tm.that(workflow, has="cancel-in-progress: true")

    def test_ci_workflow_stable_blank_line_without_private_submodules(
        self, tmp_path: Path
    ) -> None:
        """Empty private_submodules include must not accumulate blank lines."""
        root = self._render_project(tmp_path / "member")
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        # The empty include sits between the checkout and the credential-mint
        # step: no blank line may appear there, and exactly one separates the
        # mint step from the setup commentary.
        tm.that(
            workflow, has="fetch-depth: 0\n      # Cross-repo private git dependencies"
        )
        marker = (
            'rm -f "$key_path"\n\n'
            "      # Why: GitHub runners expose umask 002, so git checkout materializes"
        )
        tm.that(workflow, has=marker)
        tm.that(
            workflow,
            lacks=(
                'rm -f "$key_path"\n\n\n'
                "      # Why: GitHub runners expose umask 002, so git checkout materializes"
            ),
        )
        root2 = self._render_project(tmp_path / "member-again")
        workflow2 = (root2 / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        tm.that(workflow2, eq=workflow)

    def test_docs_workflow_inits_private_submodules_when_configured(self) -> None:
        """Docs jobs that run make setup must use the same deploy-key init as CI."""
        private = CodegenTestSupport.Ci.synthetic_private_submodules()
        tpl = (
            Path(__file__).resolve().parents[3]
            / "src/flext_infra/templates/project/base/.github/workflows/docs.yml.j2"
        )
        spec = CodegenTestSupport.Ci.workflow_spec(
            dist="example-workspace",
            make_profile=c.Infra.MakeProfile.WORKSPACE,
            repository_branch="develop",
            ci_trigger_branches=("dev", "develop", "0.12.0-dev", "develop", "main"),
        ).model_copy(update={"private_submodules": private})
        rendered = u.Cli.template_render(tpl, spec)
        tm.ok(rendered)
        rendered_text: str = rendered.value
        tm.that(rendered_text, has="Init private workspace projects")
        tm.that(rendered_text.count("Init private workspace projects"), eq=2)

    def test_ci_uses_typed_action_catalog(self, tmp_path: Path) -> None:
        """Every generated action reference resolves from the typed action SSOT."""
        root = self._render_project(tmp_path / "external")
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        actions = config.Infra.codegen.github_actions
        for action in actions.values():
            if action.repository in workflow:
                tm.that(workflow, has=f"{action.repository}@{action.version}")

    def test_dependabot_does_not_delay_available_updates(self, tmp_path: Path) -> None:
        """Every declared ecosystem can select its newest available release."""
        root = self._render_project(tmp_path / "external")

        document = u.Cli.yaml_load_mapping(root / ".github" / "dependabot.yml")
        updates = t.Cli.JSON_LIST_ADAPTER.validate_python(document["updates"])
        ecosystems = {
            str(t.Cli.JSON_MAPPING_ADAPTER.validate_python(item)["package-ecosystem"])
            for item in updates
        }
        tm.that(ecosystems, eq={"github-actions", "pip"})
        for item in updates:
            update = t.Cli.JSON_MAPPING_ADAPTER.validate_python(item)
            tm.that(update, lacks="cooldown")

    def test_dependabot_renders_cooldown_when_opted_in(self) -> None:
        """A distribution opting into staggered updates gets a cooldown per entry.

        The opt-in is per-distribution config (never fleet-wide): the default
        render stays cooldown-free, so only the distribution that declared
        staggered updates pays for them.
        """
        spec = CodegenTestSupport.Ci.workflow_spec(
            dist="example-dist",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch="develop",
            ci_trigger_branches=CodegenTestSupport.Ci.ci_trigger_branches("develop"),
            has_devcontainer=True,
        ).model_copy(update={"dependabot_cooldown_days": 7})
        template = (
            Path(__file__).resolve().parents[3]
            / "src/flext_infra/templates/project/base/.github/dependabot.yml.j2"
        )
        rendered = u.Cli.template_render(template, spec)
        tm.ok(rendered)
        rendered_text: str = rendered.value
        document = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
            tm.ok(u.Cli.yaml_parse(rendered_text))
        )
        updates = t.Cli.JSON_LIST_ADAPTER.validate_python(document["updates"])
        tm.that(len(updates), eq=3)
        for item in updates:
            update = t.Cli.JSON_MAPPING_ADAPTER.validate_python(item)
            cooldown = t.Cli.JSON_MAPPING_ADAPTER.validate_python(update["cooldown"])
            tm.that(cooldown["default-days"], eq=7)

    def test_distro_dockerfiles_emitted(self, tmp_path: Path) -> None:
        """Generated project carries one Dockerfile per supported distro."""
        root = self._render_project(tmp_path / "external")
        for distro in ("ubuntu", "debian", "fedora", "alpine", "arch"):
            tm.that(
                (
                    root
                    / "tests"
                    / "fixtures"
                    / "ci"
                    / "docker"
                    / f"{distro}.Dockerfile"
                ).is_file(),
                eq=True,
            )

    def test_distro_bootstrap_is_fail_closed_and_self_contained(
        self, tmp_path: Path
    ) -> None:
        """Every distro runs the canonical self-bootstrap fail-closed."""
        root = self._render_project(tmp_path / "external")
        for distro in ("ubuntu", "debian", "fedora", "alpine", "arch"):
            content = (
                root / "tests" / "fixtures" / "ci" / "docker" / f"{distro}.Dockerfile"
            ).read_text(encoding="utf-8")
            tm.that(content, has="make setup")
            tm.that(content, has="ENV CI=Y")
            tm.that(content, lacks="UV_UNMANAGED_INSTALL")
            tm.that(content, lacks="uv python install")
            if distro == "alpine":
                tm.that(content, has="bash")
                tm.that(content, has="build-base")
            tm.that(content, has="USER runner")
            tm.that(content, lacks="./bin/mise install --locked --yes")
            tm.that(content, has="RUN --mount=type=bind,source=.,target=/source,ro")
            tm.that(content, has="cp -R /source/. /workspace/")
            tm.that(content, lacks="COPY")
            tm.that(content, lacks="chmod -R a+rwX")
            # BuildKit exposes the credential only for the setup instruction.
            tm.that(content, lacks="ARG GITHUB_TOKEN")
            tm.that(content, lacks="ENV MISE_GITHUB_TOKEN=")
            tm.that(
                content,
                has="--mount=type=secret,id=github_token,env=GITHUB_TOKEN,required=true",
            )
            tm.that(content, lacks='GITHUB_TOKEN="')

    def test_fedora_dockerfile_installs_libatomic_only_for_fedora(
        self, tmp_path: Path
    ) -> None:
        """Fedora's generated Node runtime has its required atomic library."""
        root = self._render_project(tmp_path / "external")
        fedora = (
            root / "tests" / "fixtures" / "ci" / "docker" / "fedora.Dockerfile"
        ).read_text(encoding="utf-8")
        tm.that(fedora, has="libatomic")
        for distro in ("ubuntu", "debian", "alpine", "arch"):
            content = (
                root / "tests" / "fixtures" / "ci" / "docker" / f"{distro}.Dockerfile"
            ).read_text(encoding="utf-8")
            tm.that("libatomic" not in content, eq=True, msg=distro)

    def test_dockerfiles_render_byte_idempotently(self, tmp_path: Path) -> None:
        """Repeated project generation preserves the generated Dockerfiles."""
        root = self._render_project(tmp_path / "external")
        before = {
            distro: (
                root / "tests" / "fixtures" / "ci" / "docker" / f"{distro}.Dockerfile"
            ).read_bytes()
            for distro in ("ubuntu", "debian", "fedora", "alpine", "arch")
        }
        self._render_project(root)
        after = {
            distro: (
                root / "tests" / "fixtures" / "ci" / "docker" / f"{distro}.Dockerfile"
            ).read_bytes()
            for distro in before
        }
        tm.that(after, eq=before)

    def test_ci_matrix_has_only_supported_generic_legs(self, tmp_path: Path) -> None:
        """Generic Python CI emits only its complete cross-platform legs."""
        root = self._render_project(tmp_path / "external")
        workflow = root / ".github" / "workflows" / "ci-matrix.yml"
        tm.that(workflow.is_file(), eq=True)
        content = u.Cli.yaml_load_mapping(workflow)
        jobs = t.Cli.JSON_MAPPING_ADAPTER.validate_python(content["jobs"])
        for leg in ("distro-matrix", "macos", "windows"):
            tm.that(jobs, has=leg)
        tm.that(jobs, lacks="wsl")
        tm.that(jobs, lacks="kind")

    def test_host_legs_bootstrap_only_through_make_setup(self, tmp_path: Path) -> None:
        """MacOS and Windows bootstrap through the same Make surface."""
        root = self._render_project(tmp_path / "external")
        content = (root / ".github" / "workflows" / "ci-matrix.yml").read_text(
            encoding="utf-8"
        )
        macos = content.split("\n  macos:", maxsplit=1)[1].split(
            "\n  windows:", maxsplit=1
        )[0]
        windows = content.split("\n  windows:", maxsplit=1)[1]
        for host in (macos, windows):
            tm.that(host, has="run: CI=Y make setup")
            tm.that(host, has="run: CI=Y make help")
        tm.that(windows.count("shell: bash"), eq=3)

    def test_runtime_jobs_supply_the_native_github_credential(
        self, tmp_path: Path
    ) -> None:
        """Each Make job inherits a token; pure Git jobs require no extra input."""
        root = self._render_project(tmp_path / "external")
        for filename in ("ci.yml", "ci-matrix.yml"):
            workflow = u.Cli.yaml_load_mapping(
                root / ".github" / "workflows" / filename
            )
            jobs = t.Cli.JSON_MAPPING_ADAPTER.validate_python(workflow["jobs"])
            for value in jobs.values():
                job = t.Cli.JSON_MAPPING_ADAPTER.validate_python(value)
                steps = t.Cli.JSON_LIST_ADAPTER.validate_python(job["steps"])
                commands = tuple(
                    step["run"]
                    for raw in steps
                    if (step := t.Cli.JSON_MAPPING_ADAPTER.validate_python(raw)).get(
                        "run"
                    )
                )
                invokes_make = any(
                    isinstance(command, str) and re.search(r"\bmake\s", command)
                    for command in commands
                )
                if invokes_make:
                    environment = t.Cli.JSON_MAPPING_ADAPTER.validate_python(job["env"])
                    tm.that(environment["GITHUB_TOKEN"], eq="${{ github.token }}")
                elif "env" in job:
                    environment = t.Cli.JSON_MAPPING_ADAPTER.validate_python(job["env"])
                    tm.that(environment, lacks="GITHUB_TOKEN")

    def test_workflow_ci_policy_matrix_default_dispatch_only(
        self, tmp_path: Path
    ) -> None:
        """Blocking CI covers integration; matrix defaults to dispatch-only."""
        root = self._render_project(tmp_path / "external")
        branch = u.Tests.provider_branch()
        blocking = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        matrix = (root / ".github" / "workflows" / "ci-matrix.yml").read_text(
            encoding="utf-8"
        )
        integrations = config.Infra.codegen.branch_policy.ci_trigger_branches
        tm.that(integrations, has=branch)
        for integration in integrations:
            tm.that(blocking, has=f"      - {integration}")
        tm.that(blocking, has="draft == false")
        tm.that(blocking, has="ready_for_review")
        triggers = matrix.split('"on":', maxsplit=1)[1].split(
            "# End SECTION: triggers", maxsplit=1
        )[0]
        self._assert_dispatch_only(triggers)

    def test_draft_wip_selects_no_jobs_and_review_blocks_wip_head(
        self, tmp_path: Path
    ) -> None:
        """Draft is remote durability; only a promoted non-WIP head may land."""
        root = self._render_project(tmp_path / "external")
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        _, jobs = workflow.split("\njobs:\n", maxsplit=1)
        ci_job, merge_guard = jobs.split("\n  merge-guard:", maxsplit=1)

        tm.that(ci_job, has="github.event.pull_request.draft == false")
        tm.that(ci_job, has="make check")
        tm.that(merge_guard, has="github.event.pull_request.draft == false")
        # The merge guard must inspect the PR head, not the refs/pull/N/merge
        # commit that actions/checkout selects by default on pull_request.
        tm.that(merge_guard, has="ref: ${{ github.event.pull_request.head.sha }}")
        tm.that(merge_guard, has="subject=$(git log -1 --format=%s)")
        # WIP markers are config-owned data; the guard matches them generically.
        tm.that(merge_guard, has="grep -qiE")
        tm.that(merge_guard, has="WIP head cannot merge")
        tm.that(merge_guard, lacks="DRAFT PR cannot merge")

    def test_docs_workflow_covers_every_blocking_ci_branch(
        self, tmp_path: Path
    ) -> None:
        """Docs validation follows the same governed branch lanes as CI."""
        root = self._render_project(tmp_path / "external")
        content = (root / ".github" / "workflows" / "docs.yml").read_text(
            encoding="utf-8"
        )

        for branch in config.Infra.codegen.branch_policy.ci_trigger_branches:
            tm.that(content, has=f"      - {branch}")

    def test_docs_workflow_jobs_authenticate_toolchain_resolution(
        self, tmp_path: Path
    ) -> None:
        """Every Docs job running make setup resolves the toolchain authenticated.

        Shared-egress runners exhaust the anonymous REST budget before mise
        resolves the moving @latest backends, so each job that provisions the
        toolchain carries the job token exactly like blocking CI.
        """
        root = self._render_project(tmp_path / "external")
        content = (root / ".github" / "workflows" / "docs.yml").read_text(
            encoding="utf-8"
        )
        _, jobs = content.split("\njobs:\n", maxsplit=1)
        setup_jobs = [
            job for job in re.split(r"\n  (?=\S)", jobs) if "run: make setup" in job
        ]
        tm.that(setup_jobs, empty=False)
        for job in setup_jobs:
            tm.that(job, has="GITHUB_TOKEN: ${{ github.token }}")
            tm.that(job, has="MISE_GITHUB_TOKEN: ${{ github.token }}")

    def test_ci_matrix_check_uses_ci_token_and_never_runs_test(
        self, tmp_path: Path
    ) -> None:
        """Matrix smoke is help+check under CI=Y; it must never run make test."""
        root = self._render_project(tmp_path / "external")
        matrix = (root / ".github" / "workflows" / "ci-matrix.yml").read_text(
            encoding="utf-8"
        )
        ci = config.Infra.codegen.make.ci
        smoke = matrix.split("Bootstrap + verb smoke", maxsplit=1)[1].split(
            "# End SECTION: distro-matrix", maxsplit=1
        )[0]
        tm.that(smoke, has=f"-e {ci.variable}={ci.value}")
        tm.that(smoke, has="-e GITHUB_TOKEN")
        tm.that(smoke, lacks="-e GITHUB_TOKEN=")
        tm.that(smoke, has="make help")
        tm.that(smoke, has="make check")
        tm.that(smoke, lacks="} make test")
        tm.that(
            smoke,
            has="ci-matrix proves bootstrap + check across distros; it never runs make test",
        )
        dockerfiles = list(
            (root / "tests" / "fixtures" / "ci" / "docker").glob("*.Dockerfile")
        )
        tm.that(len(dockerfiles) > 0, eq=True)
        for dockerfile in dockerfiles:
            body = dockerfile.read_text(encoding="utf-8")
            tm.that(body, has="ENV CI=Y")
            tm.that(body, has="make setup")
            tm.that(body, has="RUN --mount=type=secret")

    def test_makefile_normalizes_windows_runtime_paths(self, tmp_path: Path) -> None:
        """Generated POSIX Make resolves Windows uv and virtualenv executables."""
        root = self._render_project(tmp_path / "external")
        content = (root / "Makefile").read_text(encoding="utf-8")
        tm.that(content, has="ifeq ($(OS),Windows_NT)")
        tm.that(content, has='cygpath --path "$(CALLER_PATH)"')
        tm.that(content, has="RUNTIME_BIN := $(RUNTIME_VENV)/Scripts")
        tm.that(content, has="RUNTIME_PYTHON := $(RUNTIME_BIN)/python.exe")
        tm.that(content, has="override PATH := $(RUNTIME_BIN):$(SANITIZED_CALLER_PATH)")
        tm.that(
            content,
            has="_builtin-help:\n\t@printf '%s\\n' 'flext-demo [standalone]' '';",
        )

    @staticmethod
    def _assert_sonarcloud_scope(rendered: str) -> None:
        """Assert one rendered .sonarcloud.properties against the codegen SSOT."""
        tests_dir = c.Infra.DIR_TESTS
        codegen = config.Infra.codegen
        entry = next(
            item
            for item in codegen.templates.entries
            if item.destination == c.Infra.SONARCLOUD_PROPERTIES_FILENAME
        )
        header = rendered.split("\n\n", 1)[0]
        tm.that(header.startswith("# @flext-regenerate: make gen\n"), eq=True)
        tm.that(header, has=entry.source.as_posix())
        properties = {
            key: value
            for key, _, value in (
                line.partition("=")
                for line in rendered.splitlines()
                if line and not line.startswith("#")
            )
        }
        tm.that(properties["sonar.sources"], eq=".")
        # Main and test sets must be disjoint: sonar.exclusions narrows only
        # the main set, so the tests root that sonar.tests declares is excluded.
        tm.that(
            properties["sonar.exclusions"].split(","),
            eq=[*codegen.sonarcloud.exclusions, f"{tests_dir}/**"],
        )
        tm.that(
            properties["sonar.cpd.exclusions"].split(","),
            eq=list(codegen.sonarcloud.cpd_exclusions),
        )
        tm.that(properties["sonar.tests"], eq=tests_dir)
        tm.that(properties["sonar.test.inclusions"], has=tests_dir)
        tm.that(
            any(key.startswith("sonar.issue.ignore") for key in properties), eq=False
        )
        comments = "\n".join(
            line for line in rendered.splitlines() if line.startswith("#")
        )
        for exclusion in codegen.sonarcloud.issue_exclusions:
            tm.that(comments, has=exclusion.rule_key)
            tm.that(comments, has=exclusion.resource_key)

    def test_sonarcloud_properties_projects_ssot_scope(self, tmp_path: Path) -> None:
        """A generated project carries the SSOT SonarCloud scope and its tests root."""
        root = self._render_project(tmp_path / "external")
        rendered = (root / c.Infra.SONARCLOUD_PROPERTIES_FILENAME).read_text(
            encoding="utf-8"
        )
        tm.that((root / c.Infra.DIR_TESTS).is_dir(), eq=True)
        self._assert_sonarcloud_scope(rendered)

    def test_sonarcloud_tests_root_is_always_materialized_by_conform(
        self, infra_git_repo: Path
    ) -> None:
        """sonar.tests always names a real directory, even from a checkout without one.

        Automatic analysis aborts when sonar.tests names an absent directory. The
        file declares tests/ unconditionally because conform itself projects the
        managed tests/ artifacts into every profile: starting from a
        provider-governed clone with no tests/, the plan still materializes them.
        """
        root = infra_git_repo
        TestsFlextInfraConformSupport.seed_infra_package_tree(root)
        u.Tests.write_standalone_workspace_manifest(root, config.Infra.name)
        # The seed ships a tests package; this case starts from a checkout without one.
        shutil.rmtree(root / c.Infra.DIR_TESTS)
        tm.that((root / c.Infra.DIR_TESTS).exists(), eq=False)
        request = u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        plan = tm.ok(FlextInfraCodegenConform(repository_root=root).plan(request))
        managed_tests_files = [
            item.path.as_posix()
            for item in config.Infra.codegen.managed_files
            if item.path.parts[0] == c.Infra.DIR_TESTS
        ]
        tm.that(managed_tests_files, empty=False)
        for relative in managed_tests_files:
            tm.not_none(u.Tests.planned_text(plan, relative))
        rendered = tm.not_none(
            u.Tests.planned_text(plan, c.Infra.SONARCLOUD_PROPERTIES_FILENAME)
        )
        self._assert_sonarcloud_scope(rendered)

    def test_root_dockerignore_reincludes_bootstrap_surface(self) -> None:
        """Root hand-maintained .dockerignore lets clean-machine bootstrap files into the context."""
        root = Path(__file__).resolve().parents[3]
        dockerignore = root / ".dockerignore"
        tm.that(dockerignore.is_file(), eq=True)
        content = dockerignore.read_text(encoding="utf-8")
        for marker in (
            "!Makefile",
            "!*.mk",
            "!pyproject.toml",
            "!README.md",
            "!uv.lock",
            "!.mise.toml",
            "!mise.lock",
            "!bin/",
            "!bin/mise",
            "!bin/mise.cmd",
            "!.python-version",
            "!config/",
            "!scripts/dispatch.py",
            "!tests/fixtures/ci/docker/",
        ):
            tm.that(content, has=marker)
