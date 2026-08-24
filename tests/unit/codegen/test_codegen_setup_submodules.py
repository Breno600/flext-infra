"""Behavioral proof for generated setup submodule bootstrapping."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from flext_infra import c, u
from flext_infra.codegen.project_new import FlextInfraCodegenProjectNew
from flext_tests import tm

# Why (suite budget): every scenario provisions a real scaffolded project
# template plus live git submodule topologies; the per-case wall only holds
# on an idle CPU, so the whole module declares the config-owned slow budget.
pytestmark = pytest.mark.slow


class TestsCodegenSetupSubmodules:
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

    @classmethod
    def _generated_project(cls, root: Path, template: Path) -> None:
        shutil.copytree(template, root)
        cls._git(root, "init", "-q", "-b", "main")
        cls._git(root, "config", "user.email", "tests@flext.local")
        cls._git(root, "config", "user.name", "FLEXT Tests")

    @staticmethod
    def _fake_uv(
        root: Path, expected_submodule_file: Path | None = None
    ) -> dict[str, str]:
        bin_dir = root / "fixture-bin"
        bin_dir.mkdir()
        (bin_dir / "uv").write_text(
            "#!/bin/sh\n"
            "set -eu\n"
            'if [ -n "${EXPECTED_SUBMODULE_FILE:-}" ] && '
            '[ ! -f "$EXPECTED_SUBMODULE_FILE" ]; then\n'
            '  printf "submodule missing before uv\\n" >&2\n'
            "  exit 70\n"
            "fi\n"
            'printf "%s\\n" "$*" >> "$UV_LOG"\n',
            encoding="utf-8",
        )
        (bin_dir / "uv").chmod(0o755)
        environment = {
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "UV": str(bin_dir / "uv"),
            "UV_LOG": str(root / "uv.log"),
            "GIT_ALLOW_PROTOCOL": "file",
        }
        if expected_submodule_file is not None:
            environment["EXPECTED_SUBMODULE_FILE"] = str(expected_submodule_file)
        return environment

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
    ) -> tuple[Path, dict[str, str]]:
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
        return project, cls._fake_uv(project)

    def test_virgin_recursive_submodules_initialize_before_environment(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        nested = tmp_path / "nested"
        child = tmp_path / "child"
        self._commit_repository(nested, "nested-dev", "nested")
        self._commit_repository(child, "child-dev", "child")
        self._add_submodule(child, nested, "nested", "nested-dev")

        source = tmp_path / "source"
        self._commit_repository(source, "source-dev", "source")
        self._add_submodule(source, child, "child", "child-dev")

        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(project, source, "vendor/source", "source-dev")
        self._git(project, "submodule", "deinit", "-q", "-f", "--all")
        nested_marker = project / "vendor/source/child/nested/marker.txt"

        tm.ok(
            u.Cli.capture(
                ["make", "setup"],
                cwd=project,
                env=self._fake_uv(project, nested_marker),
            )
        )

        tm.that(
            self._git(project / "vendor/source", "branch", "--show-current"),
            eq="source-dev",
        )
        tm.that(
            self._git(
                project / "vendor/source/child/nested", "branch", "--show-current"
            ),
            eq="nested-dev",
        )

    def test_setup_is_repeatable_with_managed_submodule(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        """Idempotent setup succeeds twice when the submodule is already valid."""
        source = tmp_path / "source"
        self._commit_repository(source, "declared-dev", "source")
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        self._add_submodule(project, source, "vendor/source", "declared-dev")
        environment = self._fake_uv(project)

        tm.ok(u.Cli.capture(["make", "setup"], cwd=project, env=environment))
        tm.ok(u.Cli.capture(["make", "setup"], cwd=project, env=environment))

    def test_submodule_setup_uses_conditional_fetch(self) -> None:
        """Generated setup skips fetch when cached origin refs already validate."""
        template = (
            Path(__file__).resolve().parents[3]
            / "src"
            / "flext_infra"
            / "templates"
            / "project"
            / "base"
            / "submodule_setup_recipe.j2"
        )
        content = template.read_text(encoding="utf-8")

        tm.that(content, has="need_fetch=1")
        tm.that(content, has='if [ "$$need_fetch" -eq 1 ]')
        tm.that(content, has='merge-base --is-ancestor "$$remote_ref" HEAD')

    def test_setup_is_repeatable_without_gitmodules(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        project = tmp_path / "project"
        self._generated_project(project, generated_project_template)
        environment = self._fake_uv(project)

        tm.ok(u.Cli.capture(["make", "setup"], cwd=project, env=environment))
        tm.ok(u.Cli.capture(["make", "setup"], cwd=project, env=environment))

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

        tm.ok(u.Cli.capture(["make", "setup"], cwd=project, env=self._fake_uv(project)))

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

        tm.ok(u.Cli.capture(["make", "setup"], cwd=project, env=self._fake_uv(project)))

        tm.that(marker.read_text(encoding="utf-8"), eq="foreign wip")
        tm.that(
            self._git(project, "config", "--get", "submodule.vendor/upstream.url"),
            eq=configured_url,
        )

    @pytest.mark.parametrize("member_branch", ["declared-dev", "feature/lane"])
    def test_accepted_branch_provisions_the_environment(
        self, tmp_path: Path, generated_project_template: Path, member_branch: str
    ) -> None:
        """Declared branch and superproject lane branch are both accepted."""
        project, environment = self._branch_scenario(
            tmp_path,
            generated_project_template,
            superproject_branch="feature/lane",
            member_branch=member_branch,
        )

        result = tm.ok(u.Cli.run_raw(["make", "setup"], cwd=project, env=environment))

        tm.that(result.exit_code, eq=0)
        tm.that(result.stderr, lacks="conflicting branch")
        tm.that(
            self._git(project / "vendor/source", "branch", "--show-current"),
            eq=member_branch,
        )
        tm.that((project / "uv.log").is_file(), eq=True)

    def test_conflicting_branch_fails_before_environment(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        """A branch that is neither the declared one nor the lane is still refused."""
        project, environment = self._branch_scenario(
            tmp_path,
            generated_project_template,
            superproject_branch="feature/lane",
            member_branch="local-work",
        )

        result = tm.ok(u.Cli.run_raw(["make", "setup"], cwd=project, env=environment))

        tm.that(result.exit_code, eq=2)
        tm.that(result.stderr, has="conflicting branch")
        tm.that(result.stderr, has="expected declared-dev or feature/lane")
        tm.that(
            self._git(project / "vendor/source", "branch", "--show-current"),
            eq="local-work",
        )
        tm.that((project / "uv.log").exists(), eq=False)

    def test_lane_branch_keeps_head_and_dirty_work(
        self, tmp_path: Path, generated_project_template: Path
    ) -> None:
        """A member on the superproject lane branch provisions without any fetch."""
        project, environment = self._branch_scenario(
            tmp_path,
            generated_project_template,
            superproject_branch="feature/lane",
            member_branch="feature/lane",
        )
        checkout = project / "vendor/source"
        dirty = checkout / "marker.txt"
        dirty.write_text("lane wip", encoding="utf-8")
        head = self._git(checkout, "rev-parse", "HEAD")

        result = tm.ok(u.Cli.run_raw(["make", "setup"], cwd=project, env=environment))

        tm.that(result.exit_code, eq=0)
        tm.that(result.stderr, lacks="fetch origin")
        tm.that(self._git(checkout, "branch", "--show-current"), eq="feature/lane")
        tm.that(self._git(checkout, "rev-parse", "HEAD"), eq=head)
        tm.that(dirty.read_text(encoding="utf-8"), eq="lane wip")
        tm.that((project / "uv.log").is_file(), eq=True)

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
        environment = self._fake_uv(project)

        result = tm.ok(u.Cli.run_raw(["make", "setup"], cwd=project, env=environment))

        tm.that(result.exit_code, eq=2)
        tm.that(result.stderr, has="diverges from recorded gitlink")
        tm.that(result.stderr, lacks="fetch origin")
        tm.that(self._git(checkout, "branch", "--show-current"), eq="feature/lane")
        tm.that((project / "uv.log").exists(), eq=False)

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
        environment = self._fake_uv(project)

        result = tm.ok(u.Cli.run_raw(["make", "setup"], cwd=project, env=environment))

        tm.that(result.exit_code, eq=0)
        tm.that(marker.read_text(encoding="utf-8"), eq="local change")
        tm.that((project / "uv.log").is_file(), eq=True)

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

        tm.ok(u.Cli.capture(["make", "setup"], cwd=project, env=self._fake_uv(project)))

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

        tm.ok(u.Cli.capture(["make", "setup"], cwd=project, env=self._fake_uv(project)))

        tm.that(self._git(checkout, "branch", "--show-current"), eq="fork-local")
        tm.that(self._git(checkout, "rev-parse", "HEAD"), eq=head)
        tm.that(marker.read_text(encoding="utf-8"), eq="third-party wip")

    def test_same_branch_declaration_uses_superproject_branch(
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

        tm.ok(u.Cli.capture(["make", "setup"], cwd=project, env=self._fake_uv(project)))

        tm.that(
            self._git(project / "vendor/source", "branch", "--show-current"), eq="main"
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
        environment = self._fake_uv(project)

        result = tm.ok(u.Cli.run_raw(["make", "setup"], cwd=project, env=environment))

        tm.that(result.exit_code, eq=0)
        tm.that(dirty.read_text(encoding="utf-8"), eq="preserve me")
        tm.that(self._git(checkout, "branch", "--show-current"), eq="declared-dev")


@pytest.fixture(scope="module")
def generated_project_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("setup-submodules") / "project"
    tm.ok(
        FlextInfraCodegenProjectNew(
            name="flext-demo",
            kind=c.Infra.ProjectKind.EXTERNAL,
            output_root=root,
            provider="flext-sh",
            license="MIT",
            author_name="FLEXT Team",
            author_email="team@flext.dev",
            upstream="flext_cli",
            year=2026,
            apply_changes=True,
        ).execute()
    )
    return root


__all__: tuple[str, ...] = ()
