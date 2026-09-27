"""Behavioral proof for generated setup submodule bootstrapping."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import p, u as test_u

# Why (suite budget): every scenario provisions a real scaffolded project
# template plus live git submodule topologies; the per-case wall only holds
# on an idle CPU, so the whole module declares the config-owned slow budget.
pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenSetupSubmodules:
    @pytest.fixture(scope="module")
    def generated_project_template(
        self, tmp_path_factory: pytest.TempPathFactory
    ) -> Path:
        root = tmp_path_factory.mktemp("setup-submodules") / "project"
        repository = test_u.Tests.repository_ref(
            "flext-demo", role=c.Infra.MakeProfile.STANDALONE
        )
        beads = test_u.Tests.beads_project(repository.distribution)
        test_u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            repository.distribution,
            workspace=beads.workspace,
            database=beads.database,
            issue_prefix=beads.issue_prefix,
        )
        workspace = test_u.Tests.workspace_spec(
            repository, project=test_u.Tests.project_spec(repository.name)
        )
        request = test_u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        plan = tm.ok(
            FlextInfraCodegenConform(
                repository_root=root, request=request, initial_workspace=workspace
            ).plan(request)
        )
        # Setup consumes generated environment declarations and tracked Mise
        # seeds; documentation publication belongs to the conform tests.
        for filename in (c.Infra.MAKEFILE_FILENAME, c.Infra.ENVRC_FILENAME):
            planned = next(file for file in plan.files if file.path.name == filename)
            tm.ok(
                u.Cli.atomic_write_text_file(
                    root / filename, test_u.Tests.codegen_file_text(planned)
                )
            )
        self._package(root, repository.distribution)
        return root

    @staticmethod
    def _package(root: Path, distribution: str) -> None:
        build = config.Infra.codegen.scaffold.build
        test_u.Tests.src_package(
            root,
            distribution.replace("-", "_"),
            pyproject=(
                "[build-system]\n"
                f"build-backend = {tm.ok(u.Cli.json_dumps(build.backend))}\n"
                f"requires = {tm.ok(u.Cli.json_dumps(list(build.requirements)))}\n"
                "[project]\n"
                f'name = "{distribution}"\nversion = "0.1.0"\n'
                f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\n'
                "dependencies = []\n"
            ),
        )

    @staticmethod
    def _git(root: Path, *arguments: str) -> str:
        return tm.ok(u.Cli.capture(["git", *arguments], cwd=root)).strip()

    @classmethod
    def _commit_repository(cls, root: Path, branch: str, marker: str) -> None:
        root.mkdir(parents=True, exist_ok=True)
        cls._git(root, "init", "-q", "-b", branch)
        cls._git(root, "config", "user.email", "tests@flext.local")
        cls._git(root, "config", "user.name", "FLEXT Tests")
        (root / "marker.txt").write_text(marker, encoding="utf-8")
        cls._git(root, "add", "marker.txt")
        cls._git(root, "commit", "-q", "-m", marker)
        # A scenario repository publishes its integration line exactly as a
        # real clone would; the branch is a Git fact, never a checkout guess.
        cls._git(root, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")

    @classmethod
    def _generated_project(cls, root: Path, template: Path) -> None:
        # Each scenario initializes its own topology and origin.
        shutil.copytree(template, root, ignore=shutil.ignore_patterns(c.Infra.GIT_DIR))
        test_u.Tests.initialize_git_repo(root)

    @staticmethod
    def _setup(root: Path, *, expected_return_code: int = 0) -> p.Cli.CommandOutput:
        result = tm.ok(
            test_u.Tests.run_isolated_make(
                ["setup"], cwd=root, env={"GIT_ALLOW_PROTOCOL": "file"}
            )
        )
        tm.that(
            result.outcome.raw_return_code,
            eq=expected_return_code,
            msg=f"{result.stdout}\n{result.stderr}",
        )
        tm.that(
            (root / c.Infra.VENV_BIN_REL / "python").is_file(),
            eq=expected_return_code == 0,
        )
        tm.that((root / ".venv").is_symlink(), eq=False)
        return result

    @classmethod
    def _add_submodule(
        cls,
        superproject: Path,
        repository: Path,
        path: str,
        branch: str,
        *,
        managed: bool = True,
    ) -> None:
        cls._git(
            superproject,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            "-f",
            "-b",
            branch,
            str(repository),
            path,
        )
        cls._git(
            superproject,
            "config",
            "-f",
            ".gitmodules",
            f"submodule.{path}.flext-managed",
            str(managed).lower(),
        )
        cls._git(superproject / path, "config", "user.email", "tests@flext.local")
        cls._git(superproject / path, "config", "user.name", "FLEXT Tests")
        cls._git(superproject, "add", "-f", ".gitmodules", path)
        cls._git(superproject, "commit", "-q", "-m", f"Add {path}")

    @classmethod
    def _branch_scenario(
        cls,
        tmp_path: Path,
        template: Path,
        *,
        superproject_branch: str,
        member_branch: str,
    ) -> Path:
        """Provision a project whose member sits on the requested branch."""
        source = tmp_path / "source"
        cls._commit_repository(source, "declared-dev", "source")
        project = tmp_path / "project"
        cls._generated_project(project, template)
        cls._add_submodule(project, source, "vendor/source", "declared-dev")
        if superproject_branch != "main":
            cls._git(project, "switch", "-q", "-c", superproject_branch)
        if member_branch != "declared-dev":
            cls._git(project / "vendor/source", "switch", "-q", "-c", member_branch)
        return project

    def test_virgin_submodule_initializes_only_direct_owner_before_environment(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        nested = tmp_path / "nested"
        child = tmp_path / "child"
        self._commit_repository(nested, "nested-dev", "nested")
        self._commit_repository(child, "child-dev", "child")
        self._add_submodule(child, nested, "nested", "nested-dev")

        source = tmp_path / "source"
        self._commit_repository(source, "source-dev", "source")
        self._package(source, source.name)
        self._git(source, "add", "pyproject.toml", "src")
        self._git(source, "commit", "-q", "-m", "Declare the submodule package")
        self._add_submodule(source, child, "child", "child-dev")

        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(project, source, "vendor/source", "source-dev")
        pyproject = project / c.Infra.PYPROJECT_FILENAME
        dependency = f"{source.name} @ {(project / 'vendor/source').as_uri()}"
        pyproject.write_text(
            pyproject.read_text(encoding="utf-8")
            + f"\n[dependency-groups]\nsubmodule = [{tm.ok(u.Cli.json_dumps(dependency))}]\n",
            encoding="utf-8",
        )
        (project / config.Infra.codegen.make.custom_handler_policy.filename).write_text(
            ".PHONY: post-setup\npost-setup:\n"
            f'\t@"$(RUNTIME_PYTHON)" -I -c "import {source.name}; '
            f"print('installed dependency:', {source.name}.__name__)" + '"\n',
            encoding="utf-8",
        )
        self._git(project, "submodule", "deinit", "-q", "-f", "--all")
        direct_marker = project / "vendor/source/marker.txt"
        nested_marker = project / "vendor/source/child/nested/marker.txt"

        result = self._setup(project)
        tm.that(result.stdout, has=f"installed dependency: {source.name}")
        tm.that(direct_marker.is_file(), eq=True)

        checkout = project / "vendor/source"
        tm.that(self._git(checkout, "branch", "--show-current"), eq="")
        tm.that(
            self._git(checkout, "rev-parse", "HEAD"),
            eq=self._git(project, "rev-parse", "HEAD:vendor/source"),
        )
        tm.that(nested_marker.exists(), eq=False)

    def test_setup_is_repeatable_with_managed_submodule(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        """Idempotent setup succeeds twice when the submodule is already valid."""
        source = tmp_path / "source"
        self._commit_repository(source, "declared-dev", "source")
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(project, source, "vendor/source", "declared-dev")

        self._setup(project)
        self._setup(project)

    def test_setup_is_repeatable_without_gitmodules(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)

        self._setup(project)
        self._setup(project)

    def test_content_only_submodule_is_never_initialized(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        """A checkout without the config-owned marker remains untouched."""
        source = tmp_path / "source"
        self._commit_repository(source, "upstream", "foreign")
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(
            project, source, "vendor/upstream", "upstream", managed=False
        )
        self._git(project, "submodule", "deinit", "-q", "-f", "--all")

        self._setup(project)

        tm.that((project / "vendor/upstream/marker.txt").exists(), eq=False)

    def test_content_only_submodule_config_and_wip_are_never_mutated(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        """Setup neither synchronizes nor validates an immutable checkout."""
        source = tmp_path / "source"
        self._commit_repository(source, "upstream", "foreign")
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(
            project, source, "vendor/upstream", "upstream", managed=False
        )
        checkout = project / "vendor/upstream"
        marker = checkout / "marker.txt"
        marker.write_text("foreign wip", encoding="utf-8")
        configured_url = self._git(
            project, "config", "--get", "submodule.vendor/upstream.url"
        )
        self._git(
            project,
            "config",
            "-f",
            ".gitmodules",
            "submodule.vendor/upstream.url",
            "https://example.test/foreign.git",
        )

        self._setup(project)

        tm.that(marker.read_text(encoding="utf-8"), eq="foreign wip")
        tm.that(
            self._git(project, "config", "--get", "submodule.vendor/upstream.url"),
            eq=configured_url,
        )

    @pytest.mark.parametrize(
        "member_branch", ["declared-dev", "feature/lane", "local-work"]
    )
    def test_accepted_branch_provisions_the_environment(
        self, tmp_path: Path, generated_project_template: Path, member_branch: str
    ) -> None:
        """Any named lane containing the recorded gitlink is accepted."""
        project = self._branch_scenario(
            tmp_path,
            generated_project_template,
            superproject_branch="feature/lane",
            member_branch=member_branch,
        )

        result = self._setup(project)

        tm.that(u.Cli.process_succeeded(result.outcome), eq=True)
        tm.that(result.stderr, lacks="conflicting branch")
        tm.that(
            self._git(project / "vendor/source", "branch", "--show-current"),
            eq=member_branch,
        )

    def test_branch_without_recorded_gitlink_fails_before_environment(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        """Commit ancestry, rather than a branch-name allowlist, is the boundary."""
        project = self._branch_scenario(
            tmp_path,
            generated_project_template,
            superproject_branch="feature/lane",
            member_branch="declared-dev",
        )
        checkout = project / "vendor/source"
        self._git(checkout, "switch", "-q", "--orphan", "divergent")
        (checkout / "marker.txt").write_text("divergent", encoding="utf-8")
        self._git(checkout, "add", "marker.txt")
        self._git(checkout, "commit", "-q", "-m", "divergent")

        result = self._setup(project, expected_return_code=2)

        tm.that(result.outcome.raw_return_code, eq=2)
        tm.that(result.stderr, has="does not contain recorded gitlink")
        tm.that(
            self._git(project / "vendor/source", "branch", "--show-current"),
            eq="divergent",
        )

    def test_lane_branch_keeps_head_and_dirty_work(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        """A member on the superproject lane branch provisions without any fetch."""
        project = self._branch_scenario(
            tmp_path,
            generated_project_template,
            superproject_branch="feature/lane",
            member_branch="feature/lane",
        )
        checkout = project / "vendor/source"
        dirty = checkout / "marker.txt"
        dirty.write_text("lane wip", encoding="utf-8")
        head = self._git(checkout, "rev-parse", "HEAD")
        (tmp_path / "source").rename(tmp_path / "offline-source")

        result = self._setup(project)

        tm.that(u.Cli.process_succeeded(result.outcome), eq=True)
        tm.that(result.stderr, lacks="fetch origin")
        tm.that(self._git(checkout, "branch", "--show-current"), eq="feature/lane")
        tm.that(self._git(checkout, "rev-parse", "HEAD"), eq=head)
        tm.that(dirty.read_text(encoding="utf-8"), eq="lane wip")

    def test_lane_branch_without_recorded_gitlink_fails(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        """The gitlink ancestry guarantee survives the lane branch acceptance."""
        source = tmp_path / "source"
        self._commit_repository(source, "declared-dev", "source")
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(project, source, "vendor/source", "declared-dev")
        checkout = project / "vendor/source"
        pinned_parent = self._git(checkout, "rev-parse", "HEAD")
        (checkout / "advanced.txt").write_text("pinned", encoding="utf-8")
        self._git(checkout, "add", "advanced.txt")
        self._git(checkout, "commit", "-q", "-m", "Advance the pin")
        self._git(project, "add", "-f", "vendor/source")
        self._git(project, "commit", "-q", "-m", "Pin the advanced commit")
        self._git(project, "switch", "-q", "-c", "feature/lane")
        self._git(checkout, "switch", "-q", "-c", "feature/lane", pinned_parent)

        result = self._setup(project, expected_return_code=2)

        tm.that(result.outcome.raw_return_code, eq=2)
        # Root cause: the checkout's own lane branch name is explicitly not a
        # safety boundary (submodule_setup_recipe.j2 header comment) — only
        # exact gitlink containment is. The failure names the *declared*
        # branch from .gitmodules ("declared-dev"), not whatever local lane
        # the submodule happens to be checked out on ("feature/lane").
        tm.that(
            result.stderr, has="branch declared-dev does not contain recorded gitlink"
        )
        tm.that(result.stderr, lacks="fetch origin")
        tm.that(self._git(checkout, "branch", "--show-current"), eq="feature/lane")

    def test_local_changes_are_preserved_on_declared_branch(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        source = tmp_path / "source"
        self._commit_repository(source, "declared-dev", "source")
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(project, source, "vendor/source", "declared-dev")
        marker = project / "vendor/source/marker.txt"
        marker.write_text("local change", encoding="utf-8")

        result = self._setup(project)

        tm.that(u.Cli.process_succeeded(result.outcome), eq=True)
        tm.that(marker.read_text(encoding="utf-8"), eq="local change")

    def test_declared_branch_ahead_of_gitlink_is_preserved(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        source = tmp_path / "source"
        self._commit_repository(source, "declared-dev", "source")
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(project, source, "vendor/source", "declared-dev")
        checkout = project / "vendor/source"
        advanced_marker = checkout / "advanced.txt"
        advanced_marker.write_text("fix forward", encoding="utf-8")
        self._git(checkout, "add", "advanced.txt")
        self._git(checkout, "commit", "-q", "-m", "Advance declared branch")
        advanced_head = self._git(checkout, "rev-parse", "HEAD")

        self._setup(project)

        tm.that(self._git(checkout, "branch", "--show-current"), eq="declared-dev")
        tm.that(self._git(checkout, "rev-parse", "HEAD"), eq=advanced_head)
        tm.that(advanced_marker.read_text(encoding="utf-8"), eq="fix forward")

    def test_unmanaged_third_party_submodule_is_never_mutated(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        source = tmp_path / "third-party-source"
        self._commit_repository(source, "vendor-main", "vendor")
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(
            project, source, "vendor/third-party", "vendor-main", managed=False
        )
        checkout = project / "vendor/third-party"
        self._git(checkout, "switch", "-q", "-c", "fork-local")
        marker = checkout / "fork.patch"
        marker.write_text("third-party wip", encoding="utf-8")
        head = self._git(checkout, "rev-parse", "HEAD")

        self._setup(project)

        tm.that(self._git(checkout, "branch", "--show-current"), eq="fork-local")
        tm.that(self._git(checkout, "rev-parse", "HEAD"), eq=head)
        tm.that(marker.read_text(encoding="utf-8"), eq="third-party wip")

    def test_same_branch_declaration_initializes_recorded_gitlink(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        source = tmp_path / "source"
        self._commit_repository(source, "main", "source")
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(project, source, "vendor/source", "main")
        self._git(
            project,
            "config",
            "-f",
            ".gitmodules",
            "submodule.vendor/source.branch",
            ".",
        )
        self._git(project, "add", ".gitmodules")
        self._git(project, "commit", "-q", "-m", "Track superproject branch")
        self._git(project, "submodule", "deinit", "-q", "-f", "--all")

        self._setup(project)

        checkout = project / "vendor/source"
        tm.that(self._git(checkout, "branch", "--show-current"), eq="")
        tm.that(
            self._git(checkout, "rev-parse", "HEAD"),
            eq=self._git(project, "rev-parse", "HEAD:vendor/source"),
        )

    def test_setup_succeeds_when_gitlink_is_ahead_of_origin(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        """Present pin matching HEAD must verify even when origin lags the pin."""
        source = tmp_path / "source"
        self._commit_repository(source, "declared-dev", "source")
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(project, source, "vendor/source", "declared-dev")
        checkout = project / "vendor/source"
        ahead = checkout / "ahead.txt"
        ahead.write_text("local ahead of origin", encoding="utf-8")
        self._git(checkout, "add", "ahead.txt")
        self._git(checkout, "commit", "-q", "-m", "ahead of origin")
        # Advance the superproject gitlink to the local tip without pushing origin.
        self._git(project, "add", "-f", "vendor/source")
        self._git(project, "commit", "-q", "-m", "pin ahead of origin")
        dirty = checkout / "dirty.txt"
        dirty.write_text("preserve me", encoding="utf-8")

        result = self._setup(project)

        tm.that(u.Cli.process_succeeded(result.outcome), eq=True)
        tm.that(dirty.read_text(encoding="utf-8"), eq="preserve me")
        tm.that(self._git(checkout, "branch", "--show-current"), eq="declared-dev")


__all__: list[str] = ["TestsFlextInfraCodegenSetupSubmodules"]
