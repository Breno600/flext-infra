"""Public functional contract for new and existing project conformance.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import sys
from difflib import unified_diff
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, main
from flext_infra.codegen import (
    FlextInfraCodegenConform,
    FlextInfraCodegenMiseArtifacts,
    FlextInfraCodegenProjectNew,
)
from flext_infra.deps import FlextInfraPyprojectModernizer
from flext_infra.docs import FlextInfraDocGenerator
from flext_infra.services.cli_routes_codegen import CodegenRoutes
from flext_infra.workspace import FlextInfraWorkspaceDetector
from tests import c, m, p, u

pytestmark = [pytest.mark.slow, pytest.mark.usefixtures("isolate_github_trigger_sha")]


def _conform_target(
    root: Path, repository: m.Infra.RepositoryRef, *, make_profile: c.Infra.MakeProfile
) -> m.Infra.RepositoryConformTarget:
    """Build a typed rendering target from the same provider SSOT as production."""
    provider = tm.ok(
        u.Infra.repository_provider(repository, config.Infra.codegen.providers)
    )
    return m.Infra.RepositoryConformTarget(
        repository=repository,
        root=root,
        make_profile=make_profile,
        beads=u.Tests.beads_project(repository.name),
        canonical_project_name=repository.distribution,
        baseline_branch=provider.branch,
        baseline_reference=f"refs/remotes/origin/{provider.branch}",
        ci_enabled=True,
        technical_branch_patterns=(
            config.Infra.codegen.branch_policy.technical_branch_patterns
        ),
        governed_branch_patterns=(
            config.Infra.codegen.branch_policy.governed_branch_patterns
        ),
    )


def _standalone_workspace(root: Path) -> m.Infra.WorkspaceSpec:
    """Load the smallest repository-local topology for conform tests."""
    return u.Tests.standalone_workspace(root)


def _apply_conform_surface(
    root: Path, workspace: m.Infra.WorkspaceSpec, surface: c.Infra.CodegenConformSurface
) -> None:
    """Materialize one exact public conform surface for a focused test."""
    tm.ok(
        FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                what=surface,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            initial_workspace=workspace,
        )
    )


def _project_tree(root: Path) -> tuple[tuple[str, bytes], ...]:
    """Return the versionable project tree independently of Git test fixtures."""
    return tuple(
        sorted(
            (path.relative_to(root).as_posix(), path.read_bytes())
            for path in root.rglob("*")
            if path.is_file()
            and ".git" not in path.relative_to(root).parts
            and ".infra-baseline" not in path.relative_to(root).parts
        )
    )


def _project_tree_diff(
    expected: tuple[tuple[str, bytes], ...], actual: tuple[tuple[str, bytes], ...]
) -> str:
    """Render only differing generated files when a fixed-point contract fails."""
    expected_files = dict(expected)
    actual_files = dict(actual)
    return "\n".join(
        line
        for path in sorted(expected_files.keys() | actual_files.keys())
        if expected_files.get(path) != actual_files.get(path)
        for line in unified_diff(
            expected_files.get(path, b"").decode(errors="replace").splitlines(),
            actual_files.get(path, b"").decode(errors="replace").splitlines(),
            fromfile=f"created/{path}",
            tofile=f"conformed/{path}",
            lineterm="",
        )
    )


def _seed_infra_package_tree(root: Path) -> None:
    """Seed the minimal flext-infra tree (pyproject, src package, tests package).

    The conform templates materialize tests/fixtures/ci/docker/*, and the
    existing-tree tooling render discovers python roots from directories that
    exist on disk (env_dirs). Seeding tests/ makes the first render match the
    post-apply fixed point.
    """
    dist = u.Tests.repository_ref(config.Infra.name).distribution
    tm.ok(
        u.Cli.atomic_write_text_file(
            root / "pyproject.toml",
            f'[project]\nname = "{dist}"\nversion = "0.12.0.dev0"\n'
            'description = "Existing repository fixture"\n'
            'requires-python = ">=3.13,<3.14"\n',
        )
    )
    package_init = root / "src" / "flext_infra" / "__init__.py"
    package_init.parent.mkdir(parents=True, exist_ok=True)
    tm.ok(u.Cli.atomic_write_text_file(package_init, ""))
    tests_init = root / "tests" / "__init__.py"
    tests_init.parent.mkdir(parents=True, exist_ok=True)
    tm.ok(u.Cli.atomic_write_text_file(tests_init, ""))


def _self_check_conform_service(
    root: Path,
) -> tuple[FlextInfraCodegenConform, m.Infra.CodegenConformRequest]:
    """Materialize the standalone root fixture and its CHECK-mode conform service."""
    repository = u.Tests.repository_ref("flext-infra").model_copy(
        update={"path": Path()}
    )
    workspace = m.Infra.WorkspaceSpec(
        name=repository.name,
        beads=u.Tests.beads_project(repository.name),
        repository=repository,
        project=u.Tests.project_spec(repository.name),
    )
    (root / "pyproject.toml").write_text(
        f"[project]\nname = '{repository.distribution}'\nversion = '0.1.0'\n",
        encoding="utf-8",
    )
    package = root / "src" / repository.distribution.replace("-", "_")
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("", encoding="utf-8")
    request = u.Tests.conform_request(
        root,
        scope=c.Infra.CodegenConformScope.SELF,
        mode=c.Infra.CodegenConformMode.CHECK,
    )
    service = FlextInfraCodegenConform(
        repository_root=root, request=request, initial_workspace=workspace
    )
    return service, request


class TestCodegenConform:
    """Prove one SSOT for project creation and existing-tree conformance."""

    def test_pyproject_plan_preserves_runtime_dependencies_before_conformance(
        self, tmp_path: Path
    ) -> None:
        """Render package requirements, canonicalize internal refs, then replan."""
        service, request = _self_check_conform_service(tmp_path)
        request = request.model_copy(
            update={"what": c.Infra.CodegenConformSurface.PYPROJECT}
        )
        pyproject = tmp_path / c.Infra.PYPROJECT_FILENAME
        source = pyproject.read_text(encoding="utf-8")
        pyproject.write_text(
            source + 'dependencies = ["custom-runtime>=0.22", '
            '"flext-custom @ ../flext-custom"]\n',
            encoding="utf-8",
        )
        first = tm.ok(service.plan(request))
        rendered = u.Tests.codegen_file_text(
            next(file for file in first.files if file.path == pyproject)
        )
        workspace = service.initial_workspace
        assert workspace is not None
        canonical = tm.ok(
            u.Infra.pyproject_dependencies_conform(
                pyproject.read_text(encoding="utf-8"),
                providers=config.Infra.codegen.providers,
                workspace=workspace,
                workspace_mode=c.Infra.MakeProfile.STANDALONE,
            )
        )
        dependencies = u.Tests.toml_strings_at(rendered, "project", "dependencies")
        tm.that("custom-runtime>=0.22" in dependencies, eq=True)
        tm.that(
            set(u.Tests.toml_strings_at(canonical, "project", "dependencies"))
            <= set(dependencies),
            eq=True,
        )
        tm.that(rendered, lacks="../flext-custom")
        pyproject.write_text(rendered, encoding="utf-8")
        second = tm.ok(service.plan(request))
        tm.that(
            u.Tests.codegen_file_text(
                next(file for file in second.files if file.path == pyproject)
            ),
            eq=rendered,
        )

    def _conform_with_rendered_makefile(
        self, root: Path, help_text: str
    ) -> p.Result[m.Infra.CodegenResult]:
        """Apply conform after declaring ``help_text`` into the rendered Makefile.

        The managed Makefile renders ``verb.description`` for every declared
        ``extra_verbs`` entry into its help block, so a repository manifest
        carrying multi-line help puts those exact lines in the rendered
        artifact through the production renderer -- no substitution of it.
        """
        distribution = u.Tests.repository_ref(config.Infra.name).distribution
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "{distribution}"\nversion = "0.12.0.dev0"\n'
            'requires-python = ">=3.13,<3.14"\n',
            encoding="utf-8",
        )
        package_init = root / "src" / distribution.replace("-", "_") / "__init__.py"
        package_init.parent.mkdir(parents=True, exist_ok=True)
        package_init.write_text("", encoding="utf-8")
        u.Tests.write_standalone_workspace_manifest(
            root,
            config.Infra.name,
            extra_verbs=(
                m.Infra.MakeVerbSpec(
                    name="probe", description=help_text, requires_apply=False
                ),
            ),
        )
        return FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )

    @pytest.mark.slow
    def test_rendered_conflict_marker_is_rejected_before_target_changes(
        self, infra_git_repo: Path
    ) -> None:
        root = infra_git_repo
        target = root / c.Infra.MAKEFILE_FILENAME
        original = "existing generated makefile\n"
        target.write_text(original, encoding="utf-8")

        rejected = self._conform_with_rendered_makefile(
            root, "Probe verb help\n<<<<<<< incoming\ntrailing help"
        )

        tm.fail(rejected)
        tm.that(rejected.error, has="base/Makefile.j2")
        tm.that(rejected.error, has=str(target))
        tm.that(rejected.error, has=str(root))
        tm.that(target.read_text(encoding="utf-8"), eq=original)

        # The autouse fixture owns GITHUB_SHA isolation for the whole module.
        # A conform run must not restore a CI SHA that cannot belong to this
        # synthetic repository.
        tm.that(os.getenv(c.Infra.ENV_VAR_GITHUB_SHA), eq=None)
        # Withdraw only the declaration that carried the marker. The same real
        # renderer must now produce a clean artifact and apply it.
        u.Tests.write_standalone_workspace_manifest(root, config.Infra.name)
        request = u.Tests.conform_request(
            root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.APPLY,
        )
        applied = FlextInfraCodegenConform.execute_request(request)
        tm.ok(applied)
        tm.that(target.read_text(encoding="utf-8"), lacks="<<<<<<< ")
        fixed_point = FlextInfraCodegenConform.execute_request(
            request.model_copy(update={"mode": c.Infra.CodegenConformMode.CHECK})
        )
        tm.ok(fixed_point)
        tm.that(fixed_point.value.written_files, eq=())

    @pytest.mark.slow
    def test_setext_underline_is_accepted_as_ordinary_content(
        self, infra_git_repo: Path
    ) -> None:
        """A Markdown Setext underline is content, so conform must not reject it."""
        applied = self._conform_with_rendered_makefile(
            infra_git_repo, "Probe verb help\n# Title\n=======\ntrailing help"
        )

        tm.ok(applied)

    def test_diff3_ancestor_fence_is_rejected_before_target_changes(
        self, infra_git_repo: Path
    ) -> None:
        """A diff3 merge leaves an ancestor fence that must stop the plan."""
        target = infra_git_repo / c.Infra.MAKEFILE_FILENAME
        original = "existing generated makefile\n"
        target.write_text(original, encoding="utf-8")

        rejected = self._conform_with_rendered_makefile(
            infra_git_repo, "Probe verb help\n||||||| base\nancestor"
        )

        tm.fail(rejected)
        tm.that(rejected.error, has="||||||| base")
        tm.that(target.read_text(encoding="utf-8"), eq=original)

    @pytest.mark.slow
    def test_apply_recovers_declared_managed_pyproject_conflict(
        self, infra_git_repo: Path
    ) -> None:
        """Repair a committed managed block through the normal apply plan."""
        root = infra_git_repo
        distribution = u.Tests.repository_ref(config.Infra.name).distribution
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "{distribution}"\nversion = "0.12.0.dev0"\n'
            'requires-python = ">=3.13,<3.14"\n'
            "\n"
            "[tool.pytest.ini_options]\n"
            'addopts = ["--timeout=10"]\n',
            encoding="utf-8",
        )
        package_init = root / "src" / distribution.replace("-", "_") / "__init__.py"
        package_init.parent.mkdir(parents=True, exist_ok=True)
        package_init.write_text("", encoding="utf-8")

        applied = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )

        tm.ok(applied)
        rendered = (root / "pyproject.toml").read_text(encoding="utf-8")
        tm.that(rendered, lacks="<<<<<<<")
        addopts = u.Tests.toml_table_at(rendered, "tool", "pytest", "ini_options")[
            "addopts"
        ]
        tm.that(
            addopts,
            has=f"--timeout={config.Infra.tooling.tools.pytest.case_timeout_seconds}",
        )

    @pytest.mark.slow
    def test_branch_ancestry_accepts_active_merge_parent(self, tmp_path: Path) -> None:
        root = u.Tests.git_repository(tmp_path)
        baseline = u.Tests.git_capture(root, "rev-parse", "HEAD")
        _ = u.Tests.git_run(
            root, "update-ref", "refs/remotes/origin/0.12.0-dev", baseline
        )
        _ = u.Tests.git_run(
            root, "remote", "set-url", "origin", str(tmp_path / "missing")
        )
        empty_tree = u.Tests.git_capture(root, "mktree")
        divergent = u.Tests.git_capture(
            root, "commit-tree", empty_tree, "-m", "Create divergent local line"
        )
        _ = u.Tests.git_run(root, "checkout", "-B", "0.12.0-dev", divergent)
        divergent_check = tm.ok(
            u.Cli.run_raw(
                ["git", "merge-base", "--is-ancestor", baseline, divergent], cwd=root
            )
        )
        tm.that(divergent_check.outcome.raw_return_code, eq=1)
        service, request = _self_check_conform_service(root)

        before_merge = tm.ok(service.plan(request)).branch_ancestry[0]
        divergent_current = next(
            reference
            for reference in before_merge.references
            if reference.reference == "refs/heads/0.12.0-dev"
        )
        tm.that(divergent_current.ancestor, eq=False)

        merge_head = tm.ok(
            u.Cli.capture(["git", "rev-parse", "--git-path", "MERGE_HEAD"], cwd=root)
        )
        (root / merge_head).write_text(f"{baseline}\n", encoding="utf-8")
        during_merge = tm.ok(service.plan(request)).branch_ancestry[0]
        merging_current = next(
            reference
            for reference in during_merge.references
            if reference.reference == "refs/heads/0.12.0-dev"
        )

        tm.that(merging_current.ancestor, eq=True)

    def test_branch_ancestry_anchors_baseline_to_triggering_commit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A concurrent publisher on the lane must not fail a linear commit.

        flext-9ehwb (run 31218338222). ``refs/remotes/origin/<lane>`` is the
        remote's LIVE tip: ``actions/checkout`` fetches at job start, so the tip
        advances whenever another actor publishes while this run waits in the
        queue. Gating against it asks whether the commit already absorbed work
        published AFTER it was written -- false by construction for a perfectly
        linear commit, which then fails with "does not descend from".

        The baseline is therefore anchored to ``merge-base(live_tip,
        GITHUB_SHA)``: the lane point the triggering commit actually knew.
        Concurrent publishers move the tip; they never move that merge base.

        The repository here reproduces the race exactly: HEAD is linear on top
        of the lane, and the remote tip then advances by one unrelated commit.
        """
        root = u.Tests.git_repository(tmp_path)
        lane_point = u.Tests.git_capture(root, "rev-parse", "HEAD")
        _ = u.Tests.git_run(root, "checkout", "-B", "0.12.0-dev", lane_point)
        # Our commit: written linearly on top of the lane as it existed.
        (root / "ours.txt").write_text("ours\n", encoding="utf-8")
        _ = u.Tests.git_run(root, "add", "ours.txt")
        _ = u.Tests.git_run(root, "commit", "-m", "Our linear commit on the lane")
        triggering_sha = u.Tests.git_capture(root, "rev-parse", "HEAD")
        # A concurrent actor publishes to the same lane while our run queues,
        # so the fetched remote tip moves past the point we branched from.
        empty_tree = u.Tests.git_capture(root, "mktree")
        concurrent_tip = u.Tests.git_capture(
            root,
            "commit-tree",
            empty_tree,
            "-p",
            lane_point,
            "-m",
            "Concurrent publisher advances the lane",
        )
        _ = u.Tests.git_run(
            root, "update-ref", "refs/remotes/origin/0.12.0-dev", concurrent_tip
        )
        _ = u.Tests.git_run(
            root, "remote", "set-url", "origin", str(tmp_path / "missing")
        )
        # The live tip is genuinely NOT an ancestor of our commit: this is the
        # exact state the old gate rejected.
        live_tip_check = tm.ok(
            u.Cli.run_raw(
                ["git", "merge-base", "--is-ancestor", concurrent_tip, triggering_sha],
                cwd=root,
            )
        )
        tm.that(live_tip_check.outcome.raw_return_code, eq=1)

        service, request = _self_check_conform_service(root)

        monkeypatch.setenv(c.Infra.ENV_VAR_GITHUB_SHA, triggering_sha)
        anchored = tm.ok(service.plan(request)).branch_ancestry[0]

        current = next(
            reference
            for reference in anchored.references
            if reference.reference == "refs/heads/0.12.0-dev"
        )
        tm.that(current.ancestor, eq=True)
        tm.that(anchored.baseline_sha, eq=lane_point)

    def test_branch_ancestry_skips_triggering_sha_in_submodule_context(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GITHUB_SHA from the superproject must not break submodule ancestry.

        In CI, GITHUB_SHA is the superproject's PR merge commit, which does
            not exist inside a submodule's object database. ``git merge-base``
            then fails with exit 128 ("Not a valid commit name"), breaking
            ``gen check`` for every governed submodule (PR #187).

        When triggering_sha does not resolve locally the gate must skip the
        merge-base pin and fall back to the live baseline tip, the same
            behavior a local (non-CI) checkout would use.
        """
        root = u.Tests.git_repository(tmp_path)
        lane_point = u.Tests.git_capture(root, "rev-parse", "HEAD")
        _ = u.Tests.git_run(root, "checkout", "-B", "0.12.0-dev", lane_point)
        (root / "ours.txt").write_text("ours\n", encoding="utf-8")
        _ = u.Tests.git_run(root, "add", "ours.txt")
        _ = u.Tests.git_run(root, "commit", "-m", "Our commit on the lane")
        # GITHUB_SHA is a SHA that does NOT exist in this repo (simulating a
        # superproject merge commit visible only at the workspace root).
        foreign_sha = "9" * 40
        tm.that(
            u.Cli.run_raw(
                ["git", "cat-file", "-t", foreign_sha], cwd=root
            ).value.outcome.raw_return_code,
            eq=128,
        )
        monkeypatch.setenv(c.Infra.ENV_VAR_GITHUB_SHA, foreign_sha)
        service, request = _self_check_conform_service(root)

        anchored = tm.ok(service.plan(request)).branch_ancestry[0]
        tm.that(anchored.baseline_sha, eq=lane_point)

    def test_branch_ancestry_skips_bare_main_worktree_entry(
        self, tmp_path: Path
    ) -> None:
        """A bare main worktree (Gas Town rig .repo.git) must not fail the plan.

        `git worktree list --porcelain` lists the bare repository itself as a
        worktree entry carrying only the `bare` attribute — no HEAD line. The
        ancestry parser used to reject that block with "worktree has no HEAD";
        it must skip it and keep planning.
        """
        bare = tmp_path / "repo.git"
        tm.ok(u.Cli.run_checked(["git", "init", "-b", "dev", "--bare", str(bare)]))
        tm.ok(
            u.Cli.run_checked([
                "git",
                "-C",
                str(bare),
                "config",
                "user.email",
                "tests@flext.local",
            ])
        )
        tm.ok(
            u.Cli.run_checked([
                "git",
                "-C",
                str(bare),
                "config",
                "user.name",
                "Flext Tests",
            ])
        )
        empty_tree = tm.ok(u.Cli.capture(["git", "-C", str(bare), "mktree"]))
        seed = tm.ok(
            u.Cli.capture([
                "git",
                "-C",
                str(bare),
                "commit-tree",
                empty_tree,
                "-m",
                "seed",
            ])
        )
        checkout = tmp_path / "checkout"
        tm.ok(
            u.Cli.run_checked(
                ["git", "-C", str(bare), "worktree", "add", str(checkout), seed],
                cwd=tmp_path,
            )
        )
        tm.ok(
            u.Cli.run_checked([
                "git",
                "-C",
                str(checkout),
                "update-ref",
                "refs/remotes/origin/0.12.0-dev",
                seed,
            ])
        )
        repository = u.Tests.repository_ref("flext-infra").model_copy(
            update={"path": Path()}
        )
        workspace = m.Infra.WorkspaceSpec(
            name=repository.name,
            beads=u.Tests.beads_project(repository.name),
            repository=repository,
            project=u.Tests.project_spec(repository.name),
        )
        (checkout / "pyproject.toml").write_text(
            f"[project]\nname = '{repository.distribution}'\nversion = '0.1.0'\n",
            encoding="utf-8",
        )
        package = checkout / "src" / repository.distribution.replace("-", "_")
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        request = u.Tests.conform_request(
            checkout,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        service = FlextInfraCodegenConform(
            repository_root=checkout, request=request, initial_workspace=workspace
        )

        plan = tm.ok(service.plan(request))

        tm.that(
            any(
                entry.reference == "refs/remotes/origin/0.12.0-dev"
                for entry in plan.branch_ancestry[0].references
            ),
            eq=True,
        )

    # This end-to-end scenario scaffolds a project and runs its console entry
    # point in a fresh interpreter. The slow marker opts into the single
    # config-owned slow-item budget; tests must not restate that policy locally.
    @pytest.mark.slow
    @pytest.mark.parametrize("name", ["flext-demo", "flext-member"])
    def test_new_project_is_complete_and_idempotent(
        self, tmp_path: Path, name: str
    ) -> None:
        # Generation rewrites an internal_flext repository and nothing else, so
        # a scaffold that must come out complete declares that kind; the two
        # rows prove the result does not depend on the distribution name.
        root = tmp_path / name
        service = FlextInfraCodegenProjectNew(
            name=name,
            kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
            output_root=root,
            provider="flext-sh",
            license="MIT",
            author_name="FLEXT Team",
            author_email="team@flext.dev",
            upstream="flext_cli",
            year=2026,
            apply_changes=True,
        )
        first = service.execute()
        first_result = tm.ok(first)
        tm.that(bool(first_result.written_files), eq=True)
        tm.that(first_result.written_files.count(root / "README.md"), eq=1)
        tm.that(
            (root / "README.md").read_text(encoding="utf-8"),
            has=c.Infra.GENERATED_HEADER,
        )
        tm.that(
            (root / "docs/api-reference/generated/public-api.md").read_text(
                encoding="utf-8"
            ),
            has=f"::: {u.Infra.project_package_name(root)}\n",
        )
        tm.that(
            (root / "docs/api-reference/generated/modules/index.md").is_file(), eq=True
        )
        docs = tm.ok(
            FlextInfraDocGenerator(repository_root=root).generate(
                m.Infra.DocsGenerateRequest(repository_root=root, apply=False)
            )
        )
        tm.that(all(report.changed_files == 0 for report in docs), eq=True)
        tm.that(
            tuple(
                file.path
                for file in first_result.plan.files
                if u.Infra.codegen_file_requires_effect(file)
            ),
            eq=(),
        )
        makefile_plan = next(
            item
            for item in first_result.plan.files
            if item.path.name == c.Infra.MAKEFILE_FILENAME
        )
        tm.that(
            u.Tests.codegen_file_text(makefile_plan),
            has=f"MAKE_PROFILE := {c.Infra.MakeProfile.STANDALONE.value}",
        )
        tm.that(first_result.plan.request.root, eq=root.resolve())
        tm.that((root / "config" / "workspace.yaml").exists(), eq=False)
        tm.that((root / "config" / "beads.yaml").is_file(), eq=True)
        tm.that((root / "pyproject.toml").is_file(), eq=True)
        tm.that((root / ".env.example").is_file(), eq=True)
        package_name = name.replace("-", "_")
        pythonpath = os.pathsep.join(
            part
            for part in (str(root / "src"), os.environ.get("PYTHONPATH", ""))
            if part
        )
        process = u.Cli.capture(
            [sys.executable, "-m", package_name, "ping"],
            cwd=root,
            env={**os.environ, "PYTHONPATH": pythonpath},
            timeout=c.Infra.TIMEOUT_DEFAULT,
        )
        tm.ok(process)
        tm.that(process.value, eq="✅ pong")

    @pytest.mark.slow
    def test_generated_make_uses_unpinned_environment_uv(
        self, infra_git_repo: Path
    ) -> None:
        """Generated Make delegates uv selection to the caller environment."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(root, workspace, c.Infra.CodegenConformSurface.MAKEFILE)
        selected = u.Cli.run_raw(
            ["make", "-C", str(root), "--dry-run", "_builtin_status_diagnostics"],
            remove_env_keys=("MAKEFLAGS",),
        )

        selected_process = tm.ok(selected)
        selected_output = selected_process.stdout + selected_process.stderr
        tm.that(u.Cli.process_succeeded(selected_process.outcome), eq=True)
        tm.that(selected_output, has="uv --version")
        tm.that(selected_output, lacks="uv@")
        tm.that(selected_output, lacks="UV_VERSION")
        makefile = (root / "Makefile").read_text(encoding="utf-8")
        tm.that(makefile, has="UV ?= uv")
        tm.that(makefile, lacks="UV_VERSION")
        tm.that(makefile, lacks="uv@")
        tm.that(makefile, lacks="mise exec")

    @pytest.mark.slow
    def test_existing_manifest_converges_to_identical_tree(
        self, infra_git_repo: Path
    ) -> None:
        existing_root = infra_git_repo
        created = FlextInfraCodegenProjectNew(
            name="flext-demo",
            kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
            output_root=existing_root,
            provider="flext-sh",
            license="MIT",
            author_name="FLEXT Team",
            author_email="team@flext.dev",
            upstream="flext_cli",
            year=2026,
            apply_changes=True,
        ).execute()
        tm.ok(created)
        expected_tree = _project_tree(existing_root)
        tm.ok(
            u.Cli.atomic_write_text_file(
                existing_root / ".gitignore", "# committed managed drift\n"
            )
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                existing_root / "Makefile", "# committed managed drift\n"
            )
        )
        u.Tests.commit_git_changes(existing_root, "Seed committed drift")
        migrated = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                existing_root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )
        tm.ok(migrated)
        actual_tree = _project_tree(existing_root)
        assert actual_tree == expected_tree, _project_tree_diff(
            expected_tree, actual_tree
        )

    @pytest.mark.slow
    def test_python_root_outside_env_dirs_still_reaches_a_fixed_point(
        self, infra_git_repo: Path
    ) -> None:
        """The gen verb converges for a Python root beyond declarative env_dirs.

        Two derivations used to select the pyright execution environments: the
        dependency command discovered roots ON DISK, while conform planned them
        from declarative ``env_dirs``. A project owning a Python directory
        outside that list therefore oscillated between two writers. Conform is
        the sole generation owner, so it must discover and preserve the extra
        root by itself and immediately reach a fixed point.
        """
        root = infra_git_repo
        _seed_infra_package_tree(root)
        # The defect needs a Python root the declarative env_dirs never lists.
        extra_root = "tools"
        module = root / extra_root / "maintenance.py"
        module.parent.mkdir(parents=True, exist_ok=True)
        tm.ok(u.Cli.atomic_write_text_file(module, "VALUE = 1\n"))
        tm.that(extra_root in u.Infra.discover_python_dirs(root), eq=True)
        tm.that(
            extra_root in config.Infra.tooling.tools.pyright.path_rules.env_dirs,
            eq=False,
        )
        tm.ok(u.Cli.run_checked(["git", "add", "-A"], cwd=root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Seed python root beyond env_dirs"],
                cwd=root,
            )
        )

        applied = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )
        tm.ok(applied)

        fixed_point = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            )
        )
        tm.ok(fixed_point)
        tm.that(fixed_point.value.written_files, eq=())

    @pytest.mark.slow
    def test_empty_rendered_directory_is_not_a_python_root(
        self, infra_git_repo: Path
    ) -> None:
        root = infra_git_repo
        _seed_infra_package_tree(root)
        (root / "scripts").mkdir()

        result = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )

        tm.ok(result)
        tm.that(
            u.Tests.toml_table_at(
                (root / "pyproject.toml").read_text(encoding="utf-8"), "tool", "pyrefly"
            )["project-includes"],
            lacks="scripts/**/*.py*",
        )
        tm.that(
            u.Tests.toml_table_at(
                (root / "pyproject.toml").read_text(encoding="utf-8"), "tool", "pyright"
            )["include"],
            lacks="scripts",
        )

    # Why (suite budget): two conform apply cycles plus a check over a full
    # managed tree on a real git repo; the per-case wall only holds idle.
    @pytest.mark.slow
    def test_manifestless_existing_root_plans_artifacts_without_project_spec(
        self, infra_git_repo: Path
    ) -> None:
        root = infra_git_repo
        repository = u.Tests.repository_ref(
            config.Infra.name, role=c.Infra.MakeProfile.STANDALONE
        )
        local_repository = repository.model_copy(update={"path": Path()})
        create_only = {
            "LICENSE": "existing license\n",
            "README.md": "# Existing repository\n",
            "custom.mk": "_custom-status-diagnostics:\n\t@true\n",
        }
        _seed_infra_package_tree(root)
        for relative, content in create_only.items():
            tm.ok(u.Cli.atomic_write_text_file(root / relative, content))
        u.Tests.commit_git_changes(root, "Seed manifest-less tree")

        derived = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        tm.that(derived.repository, eq=local_repository)
        tm.that(derived.project, eq=None)

        request = u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.APPLY,
        )
        initial_plan = tm.ok(
            FlextInfraCodegenConform(repository_root=root).plan(request)
        )
        plans = {
            file.path.relative_to(root).as_posix(): file for file in initial_plan.files
        }
        env_plan = plans[".env.example"]
        tm.that(env_plan.owner, eq="codegen")
        tm.that(env_plan.policy, eq="create-only")
        tm.that(u.Infra.codegen_file_requires_effect(env_plan), eq=False)
        tm.that(tm.ok(u.Infra.codegen_file_before_state(env_plan)).content, eq=None)
        tm.that((root / ".env.example").exists(), eq=False)
        for required in ("Makefile", ".mise.toml", ".python-version", ".gitignore"):
            tm.that(u.Infra.codegen_file_requires_effect(plans[required]), eq=True)

        applied = FlextInfraCodegenConform.execute_request(request)
        tm.ok(applied)
        for relative, content in create_only.items():
            tm.that((root / relative).read_text(encoding="utf-8"), eq=content)
        tm.that((root / "Makefile").is_file(), eq=True)
        tm.that((root / ".mise.toml").is_file(), eq=True)
        tm.that((root / ".python-version").is_file(), eq=True)
        tm.that((root / ".gitignore").is_file(), eq=True)
        tm.that((root / ".env.example").exists(), eq=False)
        tm.that(root / ".env.example" in applied.value.written_files, eq=False)
        for name, mode in (("mise", 0o755), ("mise.cmd", 0o644)):
            tm.that((root / "bin" / name).stat().st_mode & 0o777, eq=mode)
        tm.ok(FlextInfraCodegenMiseArtifacts.validate_launchers(root))

        fixed_point = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            )
        )
        tm.ok(fixed_point)
        tm.that(fixed_point.value.written_files, eq=())

    def test_workspace_uv_plan_owns_root_lock_and_editable_repositories(
        self, tmp_path: Path
    ) -> None:
        """Keep workspace setup data complete without Make-side re-derivation."""
        root_repository = u.Tests.repository_ref("flext")
        member = u.Tests.repository_ref("flext-core", path=Path("flext-core"))
        workspace = m.Infra.WorkspaceSpec(
            name="flext",
            beads=u.Tests.beads_project("flext"),
            repository=root_repository,
            project=u.Tests.project_spec("flext"),
            subprojects=(member,),
        )
        root = tmp_path / "flext"
        request = u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned = FlextInfraCodegenConform(
            repository_root=root, request=request, initial_workspace=workspace
        ).plan(request)
        tm.ok(planned)
        environment = planned.value.uv_environments[0]
        tm.that(environment.environment_root, eq=root.resolve())
        tm.that(environment.lock_path, eq=root.resolve() / "uv.lock")
        tm.that(environment.groups, eq=("dev", "codegen", "workspace"))
        tm.that(
            tuple(item.name for item in environment.editable_repositories),
            eq=("flext-core",),
        )

    @pytest.mark.slow
    def test_repository_root_catalog_profile_preserves_platform_coverage(
        self, tmp_path: Path
    ) -> None:
        """Route an arbitrary workspace root through its typed catalog profile."""
        provider = u.Tests.provider()
        repository = u.Tests.repository_ref("arbitrary-root").model_copy(
            update={
                "name": "arbitrary-root",
                "distribution": "arbitrary-root",
                "url": f"{provider.base_url}/arbitrary-root.git",
                "path": Path(),
                "role": c.Infra.MakeProfile.WORKSPACE,
                "package": False,
                "editable": False,
            }
        )
        workspace = m.Infra.WorkspaceSpec(
            name="arbitrary-root",
            beads=u.Tests.beads_project("arbitrary-root"),
            repository=repository,
            project=u.Tests.project_spec("arbitrary-root"),
        )
        root = tmp_path / "arbitrary-root"
        request = u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        service = FlextInfraCodegenConform(
            repository_root=root, request=request, initial_workspace=workspace
        )

        first = tm.ok(service.plan(request))
        second = tm.ok(service.plan(request))
        first_pyproject = next(
            item for item in first.files if item.path.name == c.Infra.PYPROJECT_FILENAME
        )
        second_pyproject = next(
            item
            for item in second.files
            if item.path.name == c.Infra.PYPROJECT_FILENAME
        )
        rendered_pyproject = u.Tests.codegen_file_text(first_pyproject)
        report = u.Tests.toml_table_at(rendered_pyproject, "tool", "coverage", "report")
        addopts = u.Tests.toml_strings_at(
            rendered_pyproject, "tool", "pytest", "ini_options", "addopts"
        )
        pytest_policy = config.Infra.tooling.tools.pytest

        tm.that(
            u.Tests.codegen_file_text(second_pyproject),
            eq=u.Tests.codegen_file_text(first_pyproject),
        )
        tm.that(addopts, has=f"--timeout={pytest_policy.case_timeout_seconds}")
        tm.that(addopts, lacks="--session-timeout")
        tm.that(set(addopts) >= set(pytest_policy.standard_addopts), eq=True)
        tm.that(
            report["fail_under"],
            eq=config.Infra.tooling.tools.coverage.fail_under.platform,
        )

    @pytest.mark.slow
    def test_project_root_exports_only_declared_upstream_facets(
        self, tmp_path: Path
    ) -> None:
        repository = u.Tests.repository_ref("consumer")
        project = u.Tests.project_spec("consumer").model_copy(
            update={"upstream": "flext_cli"}
        )
        workspace = m.Infra.WorkspaceSpec(
            name="consumer",
            beads=u.Tests.beads_project("consumer"),
            repository=repository,
            project=project,
        )
        root = tmp_path / "consumer"
        request = u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )

        plan = tm.ok(
            FlextInfraCodegenConform(
                repository_root=root, request=request, initial_workspace=workspace
            ).plan(request)
        )
        package_root = next(
            item
            for item in plan.files
            if item.path == root / "src/consumer/__init__.py"
        )
        tm.that(u.Tests.codegen_file_text(package_root), lacks='"r"')

        declared_workspace = workspace.model_copy(
            update={"project": project.model_copy(update={"inherited_facets": ("r",)})}
        )
        declared_plan = tm.ok(
            FlextInfraCodegenConform(
                repository_root=root,
                request=request,
                initial_workspace=declared_workspace,
            ).plan(request)
        )
        declared_root = next(
            item
            for item in declared_plan.files
            if item.path == root / "src/consumer/__init__.py"
        )
        tm.that(u.Tests.codegen_file_text(declared_root), has='"r"')
        tm.that(
            u.Tests.codegen_file_text(declared_root), has="from flext_cli import r as r"
        )

    def test_make_context_accepts_manifest_without_project_metadata(
        self, tmp_path: Path
    ) -> None:
        """Build Make context from repository-owned data alone."""
        repository = u.Tests.repository_ref("consumer")
        workspace = m.Infra.WorkspaceSpec(
            name="consumer",
            beads=u.Tests.beads_project("consumer"),
            repository=repository,
        )
        target = _conform_target(
            tmp_path, repository, make_profile=c.Infra.MakeProfile.STANDALONE
        )
        tooling_runtime = tm.ok(
            FlextInfraPyprojectModernizer(
                repository_root=tmp_path, skip_check=True
            ).resolve_tooling_context(
                project_name=repository.distribution,
                package_name=repository.distribution.replace("-", "_"),
                path=tmp_path / "pyproject.toml",
                declared_python_dirs=("src",),
            )
        )
        context = FlextInfraCodegenConform.make_render_context(
            repository,
            target,
            workspace,
            config.Infra.codegen,
            tooling_runtime=tooling_runtime,
        )
        rendered = tm.ok(context)
        tm.that(isinstance(rendered, m.Infra.MakeRenderContext), eq=True)
        tm.that(isinstance(rendered, m.Infra.ProjectRenderContext), eq=False)
        tm.that(rendered.repository_root_rel, eq=".")

    # Why (suite budget): parametrized over both conform modes, each running a
    # full plan/apply cycle on a real git repo; 10s only holds on an idle CPU.
    @pytest.mark.slow
    @pytest.mark.parametrize("mode", tuple(c.Infra.CodegenConformMode))
    def test_public_cli_routes_check_and_apply_to_one_handler(
        self, infra_git_repo: Path, mode: c.Infra.CodegenConformMode
    ) -> None:
        """Execute one public mode without changing an already conform tree."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(root, workspace, c.Infra.CodegenConformSurface.MAKEFILE)
        u.Tests.commit_git_changes(root, "Seed generated project")
        route = next(
            route
            for route in CodegenRoutes.codegen_routes[c.Infra.CLI_GROUP_CODEGEN]
            if route.name == "conform"
        )
        request = u.Tests.conform_request(
            root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=mode,
        )
        tm.ok(route.handler(request))
        status = tm.ok(u.Cli.capture(["git", "status", "--porcelain"], cwd=root))
        tm.that(status, eq="")

    # Why (suite budget): dependencies-only apply+check runs two full conform
    # cycles on a real git repo; the per-case wall only holds on an idle CPU.
    @pytest.mark.slow
    def test_dependency_surface_excludes_unowned_managed_files(
        self, infra_git_repo: Path
    ) -> None:
        """Plan only dependency metadata when another managed surface is invalid."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(root, workspace, c.Infra.CodegenConformSurface.ALL)
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "custom.mk", ".PHONY: public-handler\npublic-handler:\n\t@true\n"
            )
        )
        u.Tests.commit_git_changes(root, "Seed generated project")
        request = u.Tests.conform_request(
            root,
            what=c.Infra.CodegenConformSurface.DEPENDENCIES,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned = FlextInfraCodegenConform(repository_root=root, request=request).plan(
            request
        )
        tm.ok(planned)
        tm.that(
            tuple(file.path.name for file in planned.value.files),
            eq=("pyproject.toml",),
        )
        tm.that(
            tuple(
                u.Infra.codegen_file_requires_effect(file)
                for file in planned.value.files
            ),
            eq=(False,),
        )
        exit_code = main([
            "codegen",
            "conform",
            "--root",
            str(root),
            "--what",
            "dependencies",
            "--scope",
            "self",
            "--mode",
            "check",
        ])
        tm.that(exit_code, eq=0)

    # Why (suite budget): full conform cycle plus subprocess make validation;
    # the default case timeout only holds on an idle machine.

    def test_invalid_public_custom_make_fails_without_side_effects(
        self, infra_git_repo: Path
    ) -> None:
        root = infra_git_repo
        custom = root / "custom.mk"
        content = ".PHONY: public-handler\npublic-handler:\n\t@true\n"
        tm.ok(u.Cli.atomic_write_text_file(custom, content))
        policy: m.Infra.CustomHandlerPolicy = (
            config.Infra.codegen.make.custom_handler_policies[
                c.Infra.MakeProfile.STANDALONE
            ]
        )
        result = FlextInfraCodegenConform.validate_custom_make(
            tm.ok(u.Cli.files_read_text(custom)), policy
        )
        tm.fail(result)
        rejection = Path(f"{custom}.rej")
        tm.that(
            result.error or "", has="custom.mk line 1 is not a private custom handler"
        )
        tm.that(rejection.exists(), eq=False)
        tm.that(custom.read_text(encoding="utf-8"), eq=content)

    @pytest.mark.slow
    def test_valid_private_custom_make_has_no_rejection(
        self, infra_git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        custom = root / "custom.mk"
        tm.ok(
            u.Cli.atomic_write_text_file(
                custom,
                (
                    ".PHONY: \\\n"
                    "\t_custom_check_demo \\\n"
                    "\t_custom_run_demo\n"
                    "_custom_check_demo:\n\t@true\n"
                    "_custom_run_demo:\n\t@true\n"
                ),
            )
        )
        result = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            initial_workspace=workspace,
        )
        tm.ok(result)
        tm.that("WARN:" in capsys.readouterr().out, eq=False)
        tm.that(Path(f"{custom}.rej").exists(), eq=False)

    def test_custom_make_rejects_unterminated_phony_continuation(self) -> None:
        """Fail closed when a multiline private-handler declaration is truncated."""
        policy: m.Infra.CustomHandlerPolicy = (
            config.Infra.codegen.make.custom_handler_policies[
                c.Infra.MakeProfile.STANDALONE
            ]
        )

        result = FlextInfraCodegenConform.validate_custom_make(
            ".PHONY: \\\n\t_custom_check_demo \\", policy
        )

        tm.fail(result, has="unterminated .PHONY continuation")

    @pytest.mark.slow
    def test_scaffold_make_help_documents_and_lists_custom_hooks(
        self, infra_git_repo: Path
    ) -> None:
        """Scaffold help lists the selector-free interface; hooks stay lifecycle-only."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(root, workspace, c.Infra.CodegenConformSurface.MAKEFILE)
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "custom.mk",
                ".PHONY: pre-check post-test-all _custom-check-myscan\n"
                "pre-check:\n\t@true\n"
                "post-test-all:\n\t@true\n"
                "_custom-check-myscan:\n\t@true\n",
            )
        )
        outcome = u.Cli.run_raw(
            ["make", "-C", str(root), "help"], remove_env_keys=("MAKEFLAGS",)
        )
        output = tm.ok(outcome)
        tm.that(output.stderr, eq="")
        tm.that(u.Cli.process_succeeded(output.outcome), eq=True)
        tm.that(
            output.stdout,
            has=["help", "setup", "check", "test", "fmt", "conform", "docs"],
        )
        tm.that(output.stdout, lacks="Custom hooks (custom.mk):")
        tm.that(output.stdout, lacks="WHAT")

    @pytest.mark.slow
    def test_scaffold_make_runs_pre_and_post_verb_hooks_in_order(
        self, infra_git_repo: Path
    ) -> None:
        """Generated dispatch runs pre-<verb>, custom handler, post-<verb> in order."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(root, workspace, c.Infra.CodegenConformSurface.MAKEFILE)
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "custom.mk",
                ".PHONY: pre-check post-check _custom-check\n"
                "pre-check:\n\t@echo HOOK_PRE\n"
                "_custom-check:\n\t@echo HANDLER_BODY\n"
                "post-check:\n\t@echo HOOK_POST\n",
            )
        )
        # `check` requires a provisioned interpreter, which `make setup` would
        # build. Stub it so this test stays about hook ordering.
        u.Tests.write_executable(
            root / ".venv" / "bin" / "python", "#!/bin/sh\nexit 0\n"
        )
        outcome = u.Cli.run_raw(["make", "-C", str(root), "check", "APPLY=Y"])
        output = tm.ok(outcome)
        tm.that(u.Cli.process_succeeded(output.outcome), eq=True)
        combined = output.stdout + output.stderr
        pre_at = combined.find("HOOK_PRE")
        body_at = combined.find("HANDLER_BODY")
        post_at = combined.find("HOOK_POST")
        tm.that(pre_at >= 0 and body_at >= 0 and post_at >= 0, eq=True)
        tm.that(pre_at < body_at, eq=True)
        tm.that(body_at < post_at, eq=True)

    def test_custom_make_accepts_pre_post_verb_hooks(
        self, infra_git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """custom.mk may append pre/post verb hooks (verb-wide and WHAT-scoped)."""
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        custom = root / "custom.mk"
        tm.ok(
            u.Cli.atomic_write_text_file(
                custom,
                ".PHONY: pre-check post-check pre-test-all post-test-all\n"
                "pre-check:\n\t@true\n"
                "post-check:\n\t@true\n"
                "pre-test-all:\n\t@true\n"
                "post-test-all:\n\t@true\n",
            )
        )
        result = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            ),
            initial_workspace=workspace,
        )
        tm.ok(result)
        tm.that("WARN:" in capsys.readouterr().out, eq=False)
        tm.that(Path(f"{custom}.rej").exists(), eq=False)

    @pytest.mark.slow
    def test_non_regular_custom_make_remains_fatal(self, infra_git_repo: Path) -> None:
        root = infra_git_repo
        workspace = _standalone_workspace(root)
        _apply_conform_surface(root, workspace, c.Infra.CodegenConformSurface.MAKEFILE)
        tm.ok(u.Cli.files_delete(root / "custom.mk"))
        (root / "custom.mk").mkdir()
        result = FlextInfraCodegenConform.execute_request(
            u.Tests.conform_request(
                root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            ),
            initial_workspace=workspace,
        )
        tm.fail(result)
        tm.that(result.error, has="not a regular file")
        tm.that(result.error, has=str(root / "custom.mk"))


class TestScriptDispatchMakefile:
    """Prove per-repo extra verbs and script-dispatch WHAT normalization."""

    @staticmethod
    def _render_root_makefile(
        tmp_path: Path,
        *,
        extra_verbs: tuple[m.Infra.MakeVerbSpec, ...],
        script_dispatch: m.Infra.ScriptDispatchSpec | None,
    ) -> str:
        # The engine is consumer-agnostic, so this fixture models a
        # neutral downstream root and takes its provider from the engine's own
        # configured provider catalog instead of naming a real consumer.
        provider = u.Tests.provider()
        root_repository = m.Infra.RepositoryRef(
            name="demo-root",
            distribution="demo-root",
            url=f"{provider.base_url}/demo-root.git",
            path=Path(),
            # Script dispatch is a generic capability: exercise it on standalone.
            role=c.Infra.MakeProfile.STANDALONE,
            provider=provider.name,
            kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
            codegen=c.Infra.CodegenKind.CONFORM,
            package=False,
            editable=False,
            read_only=False,
            extra_verbs=extra_verbs,
            script_dispatch=script_dispatch,
        )
        workspace = m.Infra.WorkspaceSpec(
            name="demo-root",
            beads=u.Tests.beads_project("demo-root"),
            repository=root_repository,
            project=u.Tests.project_spec("demo-root"),
            subprojects=(),
        )
        root = tmp_path / "demo-root"
        request = u.Tests.conform_request(
            root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned = FlextInfraCodegenConform(
            repository_root=root, request=request, initial_workspace=workspace
        ).plan(request)
        plan = tm.ok(planned)
        makefile = next(
            file for file in plan.files if file.path.name == c.Infra.MAKEFILE_FILENAME
        )
        rendered: str = u.Tests.codegen_file_text(makefile)
        return rendered

    def test_script_dispatch_repo_routes_extra_verbs_and_normalizes_what(
        self, tmp_path: Path
    ) -> None:
        """Extra verbs join PUBLIC_VERBS and dispatch through the declared dispatcher."""
        rendered = self._render_root_makefile(
            tmp_path,
            extra_verbs=(
                m.Infra.MakeVerbSpec(
                    name="incidente",
                    description="Dispatch incidente through the declared script dispatcher.",
                    requires_apply=True,
                ),
                m.Infra.MakeVerbSpec(
                    name="charts",
                    description="Dispatch charts through the declared script dispatcher.",
                    requires_apply=True,
                ),
            ),
            script_dispatch=m.Infra.ScriptDispatchSpec(
                dispatcher="scripts/dispatch.py",
                roots=("scripts", "apps/demo-app/scripts"),
            ),
        )
        # Extra verbs are public targets the dispatcher can reach.
        tm.that("incidente" in rendered, eq=True)
        tm.that("charts" in rendered, eq=True)
        # Each extra verb gets a _builtin-<verb> target that dispatches through
        # the repo's declared dispatcher.
        tm.that("_builtin-incidente:" in rendered, eq=True)
        tm.that("_builtin-charts:" in rendered, eq=True)
        # It forwards to the declared dispatcher through uv, not a raw builtin.
        tm.that("scripts/dispatch.py" in rendered, eq=True)
        # Script dispatch roots are recorded for operator visibility.
        tm.that("apps/demo-app/scripts" in rendered, eq=True)

    def test_dispatch_routes_custom_what_before_allowlist(self, tmp_path: Path) -> None:
        """Custom ``_custom_<verb>`` handlers bypass the builtin allowlist.

        ai-hub and other projects extend ``run`` / ``check`` via custom.mk. The
        continuous Makefile RUN_PUBLIC macro discovers those handlers and
        dispatches them instead of falling through to _builtin-<verb>.
        """
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        # RUN_PUBLIC checks CUSTOM_DECLARED_TARGETS first and calls _custom-$(1)
        # when it exists, falling back to _builtin-$(1).
        tm.that("define RUN_PUBLIC" in rendered, eq=True)
        tm.that("_custom-$(1)" in rendered, eq=True)
        tm.that("_builtin-$(1)" in rendered, eq=True)

    def test_repo_without_script_dispatch_omits_script_routing(
        self, tmp_path: Path
    ) -> None:
        """A repo with no script dispatch omits every script-routing projection."""
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        # No script routing leaks into non-opted-in repositories.
        tm.that("tr '-' '_'" in rendered, eq=False)
        tm.that("scripts/dispatch.py" in rendered, eq=False)

    def test_gen_replaces_codegen_as_the_single_conform_verb(
        self, tmp_path: Path
    ) -> None:
        """``make gen`` is THE conform verb; ``codegen`` no longer exists.

        The convergence spine fuses codegen+conform under the
        single short ``gen`` verb: one verb, one meaning. The old ``codegen``
        Make verb is fully replaced across config, rendered handlers, and the
        regeneration header.
        """
        make_config = config.Infra.codegen.make
        verb_names = {verb.name for verb in make_config.verbs}
        tm.that("gen" in verb_names, eq=True)
        tm.that("codegen" in verb_names, eq=False)
        gen = next(verb for verb in make_config.verbs if verb.name == "gen")
        # WHAT selectors were exterminated: one verb, one meaning, declared once.
        tm.that(hasattr(gen, "default_what"), eq=False)
        tm.that(gen.requires_apply, eq=True)
        tm.that("initialize" in verb_names, eq=True)
        tm.that(hasattr(make_config, "serialization"), eq=False)
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        public_line = next(
            line for line in rendered.splitlines() if line.startswith("PUBLIC_VERBS :=")
        )
        tm.that(" gen" in public_line, eq=True)
        tm.that(" codegen" in public_line, eq=False)
        tm.that("_DEFAULT_gen" in rendered, eq=False)
        tm.that("_builtin-gen: _builtin_gen_all" in rendered, eq=True)
        tm.that("_builtin-conform: _builtin_gen_check" in rendered, eq=True)
        tm.that("_builtin_gen_check:" in rendered, eq=True)
        tm.that("_builtin_gen_init:" in rendered, eq=True)
        tm.that("_builtin_gen_apply:" in rendered, eq=True)
        tm.that("_builtin_codegen_check" in rendered, eq=False)
        tm.that("_builtin_codegen_apply" in rendered, eq=False)
        builtin_line = next(
            line
            for line in rendered.splitlines()
            if line.startswith("BUILTIN_VERBS :=")
        )
        tm.that(" gen" in builtin_line, eq=True)
        tm.that(" codegen" in builtin_line, eq=False)
        phony_line = next(
            line
            for line in rendered.splitlines()
            if line.startswith(".PHONY:") and "_builtin_" in line
        )
        tm.that("_builtin_gen_check" in phony_line, eq=True)
        tm.that("_builtin_gen_init" in phony_line, eq=True)
        tm.that("_builtin_gen_apply" in phony_line, eq=True)
        # Both handlers drive the conform engine (CLI namespace is unchanged).
        gen_check_body = rendered.split("_builtin_gen_check:", 1)[1].split("\n\n", 1)[0]
        tm.that(gen_check_body.count("codegen conform"), eq=1)
        tm.that("--mode check" in gen_check_body, eq=True)
        tm.that(
            gen_check_body,
            has=["_builtin_require_environment", "$(PROJECT_FLEXT_INFRA)"],
        )
        tm.that(
            gen_check_body,
            lacks=["$(FLEXT_INFRA_BOOTSTRAP)", "codegen init", "deps modernize"],
        )
        tm.that(gen_check_body, lacks=["codegen init", "deps modernize"])
        # One public conform invocation owns the complete generation transaction.
        tm.that(
            gen_check_body,
            lacks=["codegen lazy-init", "docs generate", "_generated_docs"],
        )
        # The apply semantics live on _builtin_gen_all; _builtin_gen_apply aliases it.
        gen_all_body = rendered.split("_builtin_gen_all:", 1)[1].split("\n\n", 1)[0]
        tm.that(gen_all_body.count("codegen conform"), eq=1)
        tm.that("--mode apply" in gen_all_body, eq=True)
        tm.that("--mode check" in gen_all_body, eq=False)
        tm.that(gen_all_body, has="$(PROJECT_FLEXT_INFRA)")
        tm.that(
            gen_all_body,
            lacks=[
                "_builtin_require_environment",
                "$(FLEXT_INFRA_BOOTSTRAP)",
                "codegen init",
                "deps modernize",
            ],
        )
        tm.that("_require_apply" in gen_all_body, eq=True)
        tm.that(gen_all_body, lacks="MISE_GITHUB_CREDENTIAL_COMMAND")
        tm.that(
            gen_all_body,
            lacks=["codegen lazy-init", "docs generate", "_generated_docs"],
        )
        tm.that("define _generated_docs" in rendered, eq=False)
        gen_apply_body = rendered.split("_builtin_gen_apply:", 1)[1].split("\n\n", 1)[0]
        tm.that("_builtin_gen_all" in gen_apply_body, eq=True)
        gen_init_body = rendered.split("_builtin_gen_init:", 1)[1].split("\n\n", 1)[0]
        tm.that(gen_init_body.count("codegen init"), eq=2)
        tm.that(gen_init_body, lacks=["codegen conform", "REPOSITORY_ROOT", "bd"])
        # The regeneration contract published on every projection speaks gen.
        tm.that("# @flext-regenerate: make gen APPLY=Y" in rendered, eq=True)
        # The custom-surface policy names gen (not codegen) for hooks/handlers.
        handler_policies: dict[str, m.Infra.CustomHandlerPolicy] = dict(
            config.Infra.codegen.make.custom_handler_policies
        )
        for policy in handler_policies.values():
            tm.that("|gen|" in policy.target_pattern, eq=True)
            tm.that("|codegen|" in policy.target_pattern, eq=False)

    def test_make_gen_init_bypasses_runtime_and_topology_discovery(
        self, tmp_path: Path
    ) -> None:
        """Execute the public selector with process sentinels around its owner."""
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        root = tmp_path / "declared-target"
        package = root / "src" / "demo_root"
        package.mkdir(parents=True)
        makefile = root / c.Infra.MAKEFILE_FILENAME
        makefile.write_text(rendered, encoding="utf-8")
        (root / "custom.mk").write_text(
            "$(error init selector evaluated custom.mk)\n", encoding="utf-8"
        )

        calls = root / "init.calls"
        forbidden = root / "forbidden.calls"
        sentinel_bin = root / "sentinel-bin"
        for command in ("git", "bd", "mise", "uv", "sed", "sort", "tr"):
            u.Tests.write_executable(
                sentinel_bin / command,
                f"#!/bin/sh\nprintf '%s\\n' '{command}' >> '{forbidden}'\nexit 97\n",
            )
        driver = root / "init-owner"
        u.Tests.write_executable(
            driver,
            "#!/bin/sh\n"
            "set -eu\n"
            f"printf '%s\\n' \"$*\" >> '{calls}'\n"
            "test \"$1 $2\" = 'codegen init'\n"
            'case " $* " in\n'
            f"  *' --apply '*) printf '%s\\n' '# generated' > '{package / '__init__.py'}' ;;\n"
            f"  *' --check '*) test -f '{package / '__init__.py'}' ;;\n"
            "  *) exit 98 ;;\n"
            "esac\n",
        )
        environment = dict(os.environ)
        environment["PATH"] = f"{sentinel_bin}:{environment['PATH']}"

        invoked = u.Cli.run_raw(
            [
                "make",
                "--no-print-directory",
                "-f",
                str(makefile),
                "gen",
                "WHAT=init",
                "APPLY=Y",
                f"PROJECT_FLEXT_INFRA={driver}",
            ],
            cwd=root,
            env=environment,
        )

        tm.ok(invoked)
        tm.that(u.Cli.process_succeeded(invoked.value.outcome), eq=True)
        tm.that(forbidden.exists(), eq=False)
        tm.that(
            calls.read_text(encoding="utf-8").splitlines(),
            eq=[
                f"codegen init --repository-root {root} --apply",
                f"codegen init --repository-root {root} --check",
            ],
        )

    def test_work_lifecycle_is_not_projected(self, tmp_path: Path) -> None:
        """Gas City owns lanes; generated repositories expose no second lifecycle."""
        make_config = config.Infra.codegen.make
        verb_names = {verb.name for verb in make_config.verbs}
        tm.that("work" in verb_names, eq=False)
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        public_line = next(
            line for line in rendered.splitlines() if line.startswith("PUBLIC_VERBS :=")
        )
        tm.that(" work" in public_line, eq=False)
        tm.that(rendered, lacks="_builtin_work_")
        tm.that(rendered, lacks="workspace work")

    # A test asserting a downstream consumer's verbs from this
    # engine's catalog was removed. The engine is consumer-agnostic: a consumer
    # declares extra_verbs/script_dispatch in its own typed repository input. The
    # generic capability stays covered by the fixture-driven cases below.
    def test_script_dispatch_adds_scripts_to_lint_and_type_paths(
        self, tmp_path: Path
    ) -> None:
        """Opted-in repos scan scripts alongside src and tests."""
        rendered = self._render_root_makefile(
            tmp_path,
            extra_verbs=(
                m.Infra.MakeVerbSpec(
                    name="charts",
                    description="Dispatch charts through the declared script dispatcher.",
                    requires_apply=True,
                ),
                m.Infra.MakeVerbSpec(
                    name="chart-release",
                    description="Dispatch chart-release through the declared script dispatcher.",
                    requires_apply=True,
                ),
                m.Infra.MakeVerbSpec(
                    name="bead",
                    description="Dispatch bead through the declared script dispatcher.",
                    requires_apply=True,
                ),
            ),
            script_dispatch=m.Infra.ScriptDispatchSpec(
                dispatcher="scripts/dispatch.py", roots=("scripts",)
            ),
        )
        tm.that(
            "RUFF_PATHS := $(strip $(foreach d,src tests examples scripts,"
            "$(if $(wildcard $(PROJECT_ROOT)/$(d)/.),$(PROJECT_ROOT)/$(d),)))"
            in rendered,
            eq=True,
        )
        tm.that(
            "MYPY_PATHS := $(strip $(foreach d,src tests examples scripts,"
            "$(if $(wildcard $(PROJECT_ROOT)/$(d)/.),$(PROJECT_ROOT)/$(d),)))"
            in rendered,
            eq=True,
        )

    def test_repo_without_script_dispatch_retains_canonical_lint_and_type_paths(
        self, tmp_path: Path
    ) -> None:
        """A repo without script dispatch keeps src/tests/scripts paths and excludes scripts."""
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        tm.that(
            "RUFF_PATHS := $(strip $(foreach d,src tests examples,"
            "$(if $(wildcard $(PROJECT_ROOT)/$(d)/.),$(PROJECT_ROOT)/$(d),)))"
            in rendered,
            eq=True,
        )
        tm.that(
            "MYPY_PATHS := $(strip $(foreach d,src tests examples,"
            "$(if $(wildcard $(PROJECT_ROOT)/$(d)/.),$(PROJECT_ROOT)/$(d),)))"
            in rendered,
            eq=True,
        )
        tm.that("$(PROJECT_ROOT)/scripts" in rendered, eq=False)


__all__: list[str] = []
