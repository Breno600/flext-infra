"""Public functional contract for multi-environment CI matrix codegen.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_infra import c, config, m, p, t, u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_tests import tm
from tests import u as test_u

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_TEMPLATES = _PROJECT_ROOT / "src" / "flext_infra" / "templates" / "project"
_DISTROS = ("ubuntu", "debian", "fedora", "alpine", "arch")


def _template_entry(destination: str) -> m.Infra.TemplateEntrySpec:
    """Resolve one scaffold mapping from the typed template manifest."""
    return next(
        entry
        for entry in config.Infra.codegen.templates.entries
        if entry.destination == destination
    )


def _render_artifact(root: Path, destination: str, context: p.Model) -> Path:
    """Render one manifest-owned artifact through the public template owner."""
    entry = _template_entry(destination)
    rendered = tm.ok(u.Cli.template_render(_TEMPLATES / entry.source, context))
    target = root / destination
    tm.ok(u.Cli.ensure_dir(target.parent))
    tm.ok(u.Cli.atomic_write_text_file(target, rendered))
    return target


class TestCodegenCiMatrix:
    """Prove codegen emits the CI matrix workflow and distro Dockerfiles."""

    @staticmethod
    def _hook_entry(rendered: str, hook_id: str) -> str:
        """Return the entry command of one rendered hook, isolated from the rest.

        Searching the whole file proves only that SOME hook carries a prefix; a
        hook that loses it while its sibling keeps it would still pass.
        """
        lines = rendered.splitlines()
        start = next(
            index
            for index, line in enumerate(lines)
            if line.strip() == f"- id: {hook_id}"
        )
        following = lines[start + 1 :]
        end = next(
            (
                index
                for index, line in enumerate(following)
                if line.strip().startswith("- id: ")
            ),
            len(following),
        )
        return "\n".join(following[:end])

    def test_ci_matrix_profiles_exclude_workspace_member(self) -> None:
        """Matrix + distro Dockerfiles are root/standalone only (not members)."""
        entries = config.Infra.codegen.templates.entries
        matrix = next(
            entry
            for entry in entries
            if entry.destination == ".github/workflows/ci-matrix.yml"
        )
        tm.that(set(matrix.profiles), eq={"workspace-root", "standalone"})
        tm.that("workspace-member" in matrix.profiles, eq=False)
        docker_dests = {
            f"tests/fixtures/ci/docker/{name}.Dockerfile" for name in _DISTROS
        }
        for entry in entries:
            if entry.destination not in docker_dests:
                continue
            tm.that(set(entry.profiles), eq={"workspace-root", "standalone"})
            tm.that("workspace-member" in entry.profiles, eq=False)

    def test_ci_matrix_workflow_emitted(self, rendered_project: Path) -> None:
        """Generated project carries .github/workflows/ci-matrix.yml."""
        root = rendered_project
        tm.that((root / ".github" / "workflows" / "ci-matrix.yml").is_file(), eq=True)

    def test_ci_workflow_uses_immutable_action_catalog(
        self, rendered_project: Path
    ) -> None:
        """Every generated action reference resolves from the typed action SSOT."""
        root = rendered_project
        workflows = "\n".join(
            (root / ".github" / "workflows" / filename).read_text(encoding="utf-8")
            for filename in ("ci.yml", "ci-matrix.yml")
        )
        catalog = {
            f"{action.repository}@{action.sha}": action.version
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
            # yamllint requires two spaces before an inline comment.
            tm.that(workflows, has=f"{action}  # {catalog[action]}")

        tm.that(workflows, lacks="continue-on-error")
        tm.that(workflows, lacks="set +e")
        tm.that(workflows, lacks="|| make")
        tm.that(workflows, lacks="soft-pass")

    def test_blocking_ci_bootstraps_only_through_make_setup(
        self, rendered_project: Path
    ) -> None:
        """Generated blocking CI provisions every binary via the Make surface."""
        root = rendered_project
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )

        tm.that(workflow, has="run: CI=Y make setup")
        tm.that(workflow, has="run: CI=Y make check")
        tm.that(workflow, lacks="run: CI=Y make test")
        tm.that(workflow, lacks="run: make test")
        tm.that(workflow, has="run: CI=Y make gen WHAT=apply APPLY=Y")
        tm.that(workflow, has="run: CI=Y make fmt WHAT=apply APPLY=Y")
        tm.that(workflow, has="run: CI=Y make fix WHAT=apply APPLY=Y")

    def test_rendered_pre_commit_uses_typed_hook_contexts(
        self, rendered_project: Path
    ) -> None:
        """The generated staged hooks render the configured workflow partitions."""
        root = rendered_project
        hooks = (root / ".pre-commit-config.yaml").read_text(encoding="utf-8")
        workflow = config.Infra.codegen.make.workflow
        ci = config.Infra.codegen.make.ci
        gates_default: tuple[str, ...] = config.Infra.codegen.make.check_gates_default

        for hook_prefix, context in (
            ("flext-pre-commit", "pre_commit"),
            ("flext-pre-push", "pre_push"),
        ):
            for step in (step for step in workflow if context in step.contexts):
                command = (
                    # Operator law: EVERY pre-commit step carries the fast CI
                    # token; EVERY pre-push step carries the full-suite token.
                    (
                        f"{ci.variable}={ci.value} "
                        if context == "pre_commit"
                        else f"{ci.variable}={ci.local_value} "
                    )
                    + (
                        "CHECK_GATES="
                        + ",".join(
                            gate
                            for gate in gates_default
                            if gate not in step.gates_skip
                        )
                        + " "
                        if step.gates_skip
                        else ""
                    )
                    + f"make {step.verb}"
                    + (f" WHAT={step.what}" if step.what else "")
                    + (
                        f" {config.Infra.codegen.make.apply_variable}="
                        f"{config.Infra.codegen.make.apply_value}"
                        if step.apply
                        else ""
                    )
                )
                hook_id = f"{hook_prefix}-{step.verb}"
                if step.what:
                    hook_id += f"-{step.what}"
                entry = self._hook_entry(hooks, hook_id)
                tm.that(entry, has=command)
                # Every carrier that can smuggle a caller's selector or
                # write-enable token into a hook step is cleared before Make.
                cleanup = (
                    f"unset WHAT MAKEFLAGS {config.Infra.codegen.make.apply_variable}; "
                )
                git_cleanup = "unset $(git rev-parse --local-env-vars); "
                tm.that(entry.count("bash -eu -o pipefail -c"), eq=1)
                tm.that(entry, has=cleanup)
                tm.that(entry, has=git_cleanup)
                tm.that(entry.index(git_cleanup) < entry.index(cleanup), eq=True)
                tm.that(entry.index(cleanup) < entry.index(command), eq=True)
        tm.that(hooks, has="make test")
        tm.that(hooks, lacks=f"export {ci.variable}={ci.value}")

    def test_ci_workflow_cancels_superseded_ref_runs(
        self, rendered_project: Path
    ) -> None:
        """Generated CI groups competing runs by workflow and ref."""
        root = rendered_project
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )

        tm.that(workflow, has="concurrency:")
        tm.that(workflow, has="group: ${{ github.workflow }}-${{ github.ref }}")
        tm.that(workflow, has="cancel-in-progress: true")

    def test_ci_workflow_stable_blank_line_without_private_submodules(
        self, rendered_project: Path
    ) -> None:
        """Verified fixed-point output keeps one empty-include blank line."""
        root = rendered_project
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        marker = "fetch-depth: 0\n\n      - name: Install mise toolchain"
        tm.that(workflow, has=marker)
        tm.that(
            workflow, lacks="fetch-depth: 0\n\n\n      - name: Install mise toolchain"
        )

    def test_docs_workflow_inits_private_submodules_when_configured(self) -> None:
        """Docs jobs that run make setup must use the same deploy-key init as CI."""
        from flext_infra import config, m

        codegen = config.Infra.codegen
        private = codegen.ci_private_submodules.get("cosmos-main")
        tm.that(private is not None, eq=True)
        assert private is not None
        tpl = (
            Path(__file__).resolve().parents[3]
            / "src/flext_infra/templates/project/base/.github/workflows/docs.yml.j2"
        )
        spec = m.Infra.GithubWorkflowRenderSpec(
            dist="cosmos-main",
            make_profile=c.Infra.MakeProfile.WORKSPACE_ROOT,
            repository_branch="develop",
            python_version=codegen.toolchain.python_version,
            github_actions=codegen.github_actions,
            make=codegen.make,
            workspace_repositories=(),
            checkout_submodules=codegen.checkout_submodules,
            private_submodules=private,
        )
        rendered_text = tm.ok(u.Cli.template_render(tpl, spec))
        tm.that(rendered_text, has="Init private workspace members")
        tm.that(rendered_text.count("Init private workspace members"), eq=2)

    def test_docs_workflow_permissions_are_job_scoped(
        self, rendered_project: Path
    ) -> None:
        """Each docs job receives only the GitHub token permissions it needs."""
        workflow = u.Cli.yaml_load_mapping(
            rendered_project / ".github" / "workflows" / "docs.yml"
        )
        permissions = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
            workflow["permissions"]
        )
        jobs = t.Cli.JSON_MAPPING_ADAPTER.validate_python(workflow["jobs"])
        expected = {
            "docs-quality": {"contents": "read"},
            "build": {"contents": "read"},
            "deploy": {"pages": "write", "id-token": "write"},
        }

        tm.that(dict(permissions), eq={})
        for job_name, expected_permissions in expected.items():
            job = t.Cli.JSON_MAPPING_ADAPTER.validate_python(jobs[job_name])
            job_permissions = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
                job["permissions"]
            )
            tm.that(dict(job_permissions), eq=expected_permissions)

    def test_ci_uses_typed_action_catalog(self, rendered_project: Path) -> None:
        """Every generated action reference resolves from the typed action SSOT."""
        root = rendered_project
        workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        actions = config.Infra.codegen.github_actions
        for action in actions.values():
            if action.repository in workflow:
                # yamllint requires two spaces before an inline comment.
                tm.that(
                    workflow,
                    has=f"{action.repository}@{action.sha}  # {action.version}",
                )

    def test_distro_dockerfiles_emitted(self, rendered_project: Path) -> None:
        """Generated project carries one Dockerfile per supported distro."""
        root = rendered_project
        for distro in _DISTROS:
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
        self, rendered_project: Path
    ) -> None:
        """Every distro runs the canonical self-bootstrap fail-closed."""
        root = rendered_project
        for distro in _DISTROS:
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

    def test_fedora_dockerfile_installs_libatomic_only_for_fedora(
        self, rendered_project: Path
    ) -> None:
        """Fedora's generated Node runtime has its required atomic library."""
        root = rendered_project
        fedora = (
            root / "tests" / "fixtures" / "ci" / "docker" / "fedora.Dockerfile"
        ).read_text(encoding="utf-8")
        tm.that(fedora, has="libatomic")
        for distro in (item for item in _DISTROS if item != "fedora"):
            content = (
                root / "tests" / "fixtures" / "ci" / "docker" / f"{distro}.Dockerfile"
            ).read_text(encoding="utf-8")
            tm.that("libatomic" not in content, eq=True, msg=distro)

    def test_dockerfiles_render_byte_idempotently(self, rendered_project: Path) -> None:
        """Repeated project generation preserves the generated Dockerfiles."""
        root = rendered_project
        before = {
            distro: (
                root / "tests" / "fixtures" / "ci" / "docker" / f"{distro}.Dockerfile"
            ).read_bytes()
            for distro in _DISTROS
        }
        spec = m.Infra.DistroDockerRenderSpec(
            package_name="flext_demo",
            python_version=config.Infra.codegen.toolchain.python_version,
            make=config.Infra.codegen.make,
        )
        after = {
            distro: tm.ok(
                u.Cli.template_render(
                    _TEMPLATES
                    / _template_entry(
                        f"tests/fixtures/ci/docker/{distro}.Dockerfile"
                    ).source,
                    spec,
                )
            ).encode()
            for distro in before
        }
        tm.that(after, eq=before)

    def test_ci_matrix_has_only_supported_generic_legs(
        self, rendered_project: Path
    ) -> None:
        """Generic Python CI emits only its complete cross-platform legs."""
        root = rendered_project
        workflow = root / ".github" / "workflows" / "ci-matrix.yml"
        tm.that(workflow.is_file(), eq=True)
        content = u.Cli.yaml_load_mapping(workflow)
        jobs = t.Cli.JSON_MAPPING_ADAPTER.validate_python(content["jobs"])
        for leg in ("distro-matrix", "macos", "windows"):
            tm.that(jobs, has=leg)
        tm.that(jobs, lacks="wsl")
        tm.that(jobs, lacks="kind")

    def test_host_legs_bootstrap_only_through_make_setup(
        self, rendered_project: Path
    ) -> None:
        """MacOS and Windows bootstrap through the same Make surface."""
        root = rendered_project
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
            tm.that(host, has="run: CI=Y make check")
        tm.that(windows.count("shell: bash"), eq=3)

    def test_workflow_ci_policy_matrix_default_dispatch_only(
        self, rendered_project: Path
    ) -> None:
        """Blocking CI covers integration; matrix defaults to dispatch-only."""
        root = rendered_project
        provider = next(
            item for item in config.Infra.codegen.providers if item.name == "flext-sh"
        )
        branch = provider.branch
        blocking = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        matrix = (root / ".github" / "workflows" / "ci-matrix.yml").read_text(
            encoding="utf-8"
        )
        integrations = ("dev", "develop", "0.12.0-dev", "main")
        tm.that(integrations, has=branch)
        for integration in integrations:
            tm.that(blocking, has=f"      - {integration}")
        tm.that(blocking, has="draft == false")
        tm.that(blocking, has="ready_for_review")
        triggers = matrix.split('"on":', maxsplit=1)[1].split(
            "# End SECTION: triggers", maxsplit=1
        )[0]
        tm.that(triggers, has="workflow_dispatch: {}")
        tm.that(triggers, lacks="branches: [main]")
        tm.that(triggers, lacks="pull_request:")
        tm.that(triggers, lacks="ready_for_review")
        tm.that(triggers, lacks="repository_branch")
        tm.that(triggers, lacks="0.12.0-dev")
        tm.that(triggers, lacks="develop")
        tm.that(triggers, lacks="branches: [dev]")

    def test_ci_matrix_template_defaults_dispatch_only(self) -> None:
        """SSOT template gates main-push auto-run behind ci_matrix_auto_run."""
        template = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "flext_infra"
            / "templates"
            / "project"
            / "base"
            / ".github"
            / "workflows"
            / "ci-matrix.yml.j2"
        )
        content = template.read_text(encoding="utf-8")
        triggers = content.split('"on":', maxsplit=1)[1].split(
            "# End SECTION: triggers", maxsplit=1
        )[0]
        tm.that(triggers, has="{%- if ci_matrix_auto_run %}")
        tm.that(triggers, has="branches: [main]")
        tm.that(triggers, has="workflow_dispatch: {}")
        tm.that(triggers, lacks="pull_request:")
        tm.that(triggers, lacks="repository_branch")
        tm.that(triggers, lacks="0.12.0-dev")
        tm.that(triggers, lacks="develop")
        tm.that(triggers, lacks="branches: [dev]")
        tm.that(triggers, lacks="workspace-member")
        tm.that(content, lacks="{% if make_profile")

    def test_ci_matrix_overlay_enables_main_push_auto_run(self) -> None:
        """repository_policy_overlays.ci_matrix_auto_run restores push to main."""
        from flext_infra import m

        codegen = config.Infra.codegen
        tpl = (
            Path(__file__).resolve().parents[3]
            / "src/flext_infra/templates/project/base/.github/workflows/ci-matrix.yml.j2"
        )
        disabled = m.Infra.GithubWorkflowRenderSpec(
            dist="flext-demo",
            make_profile=c.Infra.MakeProfile.STANDALONE,
            repository_branch="develop",
            python_version=codegen.toolchain.python_version,
            github_actions=codegen.github_actions,
            make=codegen.make,
            workspace_repositories=(),
            checkout_submodules=codegen.checkout_submodules,
            ci_matrix_auto_run=False,
        )
        enabled = disabled.model_copy(update={"ci_matrix_auto_run": True})
        disabled_text = tm.ok(u.Cli.template_render(tpl, disabled))
        enabled_text = tm.ok(u.Cli.template_render(tpl, enabled))
        disabled_triggers = disabled_text.split('"on":', maxsplit=1)[1].split(
            "# End SECTION: triggers", maxsplit=1
        )[0]
        enabled_triggers = enabled_text.split('"on":', maxsplit=1)[1].split(
            "# End SECTION: triggers", maxsplit=1
        )[0]
        tm.that(disabled_triggers, has="workflow_dispatch: {}")
        tm.that(disabled_triggers, lacks="branches: [main]")
        tm.that(enabled_triggers, has="branches: [main]")
        tm.that(enabled_triggers, has="workflow_dispatch: {}")
        tm.that(enabled_triggers, lacks="pull_request:")

    def test_no_project_overrides_ci_matrix_auto_run(self) -> None:
        """ci-matrix stays dispatch-only fleet-wide: no project may opt in.

        Operator law (2026-08-08): ci-matrix is fully OFF, owned by flext-infra,
        with `ci_matrix_auto_run` at its default and ZERO overrides in any
        internal or external project. The overlay field still exists as the
        typed knob, but an override that flips it on is a governance violation,
        so the absence is asserted rather than assumed.
        """
        from flext_infra import m

        base = m.Infra.RepositoryRef(
            name="flext-demo",
            distribution="flext-demo",
            url="https://github.com/flext-sh/flext-demo.git",
            path=Path(),
            provider="flext-sh",
            role=c.Infra.RepositoryRole.STANDALONE,
            checkout=c.Infra.CheckoutKind.INDEPENDENT,
            codegen=c.Infra.CodegenKind.CONFORM,
            package=True,
            editable=False,
            read_only=False,
        )

        def build(*, auto_run: bool) -> m.Infra.WorkspaceSpec:
            return m.Infra.WorkspaceSpec(
                version=c.Infra.WORKSPACE_MANIFEST_VERSION,
                name="flext-demo",
                repository=base,
                repository_policy_overlays=(
                    m.Infra.RepositoryPolicyOverlaySpec(
                        project="flext-demo", ci_matrix_auto_run=auto_run
                    ),
                ),
            )

        # The default overlay loads: ci-matrix stays dispatch-only.
        tm.that(len(build(auto_run=False).repository_policy_overlays), eq=1)
        # An override is refused at load time, naming the offending project.
        with pytest.raises(
            c.ValidationError, match="ci_matrix_auto_run cannot be overridden"
        ):
            build(auto_run=True)

    def test_ci_matrix_check_uses_ci_token_and_never_runs_test(
        self, rendered_project: Path
    ) -> None:
        """Matrix smoke is help+check under CI=Y; it must never run make test."""
        root = rendered_project
        matrix = (root / ".github" / "workflows" / "ci-matrix.yml").read_text(
            encoding="utf-8"
        )
        ci = config.Infra.codegen.make.ci
        smoke = matrix.split("Bootstrap + verb smoke", maxsplit=1)[1].split(
            "# End SECTION: distro-matrix", maxsplit=1
        )[0]
        tm.that(smoke, has=f"-e {ci.variable}={ci.value}")
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
            tm.that(body, has="RUN make setup")

    def test_profile_excluded_workflow_orphan_is_planned_absent(
        self, tmp_path: Path
    ) -> None:
        """Profile-excluded member ci-matrix orphans are planned as absent."""
        name = "flext-core"
        root = tmp_path / name
        orphan = root / ".github" / "workflows" / "ci-matrix.yml"
        orphan.parent.mkdir(parents=True)
        orphan.write_text(
            'name: ci-matrix\n"on":\n  push:\n    branches: [0.12.0-dev]\n',
            encoding="utf-8",
        )
        repository = test_u.Tests.repository_ref(
            name, role=c.Infra.RepositoryRole.WORKSPACE_MEMBER, path=Path()
        )
        workspace = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=name,
            repository=repository,
            project=m.Infra.ProjectSpec(
                package_name="flext_core",
                class_stem="FlextCore",
                namespace="FlextCore",
                constant_name="flext-core",
                namespace_attribute="flext_core",
                alias="flext_core",
                environment_prefix="FLEXT_CORE_",
                description="member fixture",
                version="0.12.0.dev0",
                license="MIT",
                author_name="FLEXT Team",
                author_email="team@flext.dev",
                upstream="flext_cli",
                homepage="https://github.com/flext-sh/flext-core",
                documentation="https://github.com/flext-sh/flext-core",
                workspace_root_rel=".",
                year=2026,
            ),
        )
        request = m.Infra.CodegenConformRequest(
            root=root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned = FlextInfraCodegenConform(
            workspace_root=root, request=request, initial_workspace=workspace
        ).plan(request)
        tm.ok(planned)
        absent = tuple(
            item
            for item in planned.value.files
            if item.absent and item.path.resolve() == orphan.resolve()
        )
        tm.that(len(absent), eq=1)
        tm.that(absent[0].changed, eq=True)
        tm.that(orphan.exists(), eq=True)

    def test_makefile_normalizes_windows_runtime_paths(self) -> None:
        """Owner-generated POSIX Make resolves Windows runtime executables."""
        root = _PROJECT_ROOT
        content = (root / "Makefile").read_text(encoding="utf-8")
        tm.that(content, has="ifeq ($(OS),Windows_NT)")
        tm.that(content, has='cygpath --path "$(CALLER_PATH)"')
        tm.that(content, has="RUNTIME_BIN := $(RUNTIME_VENV)/Scripts")
        tm.that(content, has="RUNTIME_PYTHON := $(RUNTIME_BIN)/python.exe")
        tm.that(content, has="override PATH := $(RUNTIME_BIN):$(SANITIZED_CALLER_PATH)")
        tm.that(content, has="_builtin_help_usage:\n\t@printf")
        profile = next(
            line.split("=", 1)[1].strip()
            for line in content.splitlines()
            if line.startswith("MAKE_PROFILE :=")
        )
        tm.that(content, has=f"'{config.Infra.name} [{profile}]' '';")

    def test_root_dockerignore_reincludes_bootstrap_surface(self) -> None:
        """Root hand-maintained .dockerignore lets clean-machine bootstrap files into the context."""
        dockerignore = _PROJECT_ROOT / ".dockerignore"
        tm.that(dockerignore.is_file(), eq=True)
        content = dockerignore.read_text(encoding="utf-8")
        for marker in (
            "!Makefile",
            "!*.mk",
            "!pyproject.toml",
            "!README.md",
            "!uv.lock",
            "!.mise.toml",
            "!.python-version",
            "!.default-python-packages",
            "!config/",
            "!scripts/dispatch.py",
            "!tests/fixtures/ci/docker/",
        ):
            tm.that(content, has=marker)


@pytest.fixture(scope="module")
def rendered_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Render only the typed, manifest-owned CI artifacts under test."""
    root = tmp_path_factory.mktemp("codegen-ci-matrix") / "external"
    codegen = config.Infra.codegen
    provider = next(item for item in codegen.providers if item.name == "flext-sh")
    workflow_spec = m.Infra.GithubWorkflowRenderSpec(
        dist="flext-demo",
        make_profile=c.Infra.MakeProfile.STANDALONE,
        repository_branch=provider.branch,
        python_version=codegen.toolchain.python_version,
        github_actions=codegen.github_actions,
        make=codegen.make,
        workspace_repositories=(),
        checkout_submodules=codegen.checkout_submodules,
    )
    for destination in (
        ".github/workflows/ci.yml",
        ".github/workflows/ci-matrix.yml",
        ".github/workflows/docs.yml",
    ):
        _render_artifact(root, destination, workflow_spec)
    _render_artifact(
        root,
        ".pre-commit-config.yaml",
        m.Infra.MakeWorkflowRenderSpec(dist="flext-demo", make=codegen.make),
    )
    docker_spec = m.Infra.DistroDockerRenderSpec(
        package_name="flext_demo",
        python_version=codegen.toolchain.python_version,
        make=codegen.make,
    )
    for distro in _DISTROS:
        _render_artifact(
            root, f"tests/fixtures/ci/docker/{distro}.Dockerfile", docker_spec
        )
    return root


__all__: list[str] = []
