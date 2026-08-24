"""Workspace-root submodule setup behavior through generated Make surfaces."""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, m, u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_tests import tm
from tests import u as test_u

_MEMBER_BRANCH = "0.12.0-dev"
_FILE_PROTOCOL_CONFIG = ("-c", "protocol.file.allow=always")
# Local bare origins are reached over the file transport, which Git refuses by
# default for submodule clones. The allowance belongs to the fixture topology,
# never to the developer environment the suite happens to inherit.
_FILE_PROTOCOL_ENV = {"GIT_ALLOW_PROTOCOL": "file"}


def _render_workspace_root_makefile(tmp_path: Path) -> str:
    root_repository = test_u.Tests.repository_ref("flext")
    member = test_u.Tests.repository_ref(
        "flext-core", role=c.Infra.RepositoryRole.WORKSPACE_MEMBER
    )
    workspace = m.Infra.WorkspaceSpec(
        version=c.Infra.WORKSPACE_MANIFEST_VERSION,
        name="flext",
        repository=root_repository,
        project=m.Infra.ProjectSpec(
            package_name="flext",
            class_stem="Flext",
            namespace="Flext",
            constant_name="flext",
            namespace_attribute="flext",
            alias="flext",
            environment_prefix="FLEXT_",
            description="FLEXT workspace",
            version="0.12.0.dev0",
            license="MIT",
            author_name="FLEXT Team",
            author_email="team@flext.dev",
            upstream="flext_cli",
            homepage="https://github.com/flext-sh/flext",
            documentation="https://github.com/flext-sh/flext",
            workspace_root_rel=".",
            year=2026,
        ),
        members=(member,),
    )
    root = tmp_path / "render-root"
    request = m.Infra.CodegenConformRequest(
        root=root,
        scope=c.Infra.CodegenConformScope.SELF,
        mode=c.Infra.CodegenConformMode.CHECK,
    )
    planned = FlextInfraCodegenConform(
        workspace_root=root, request=request, initial_workspace=workspace
    ).plan(request)
    plan = tm.ok(planned)
    makefile: m.Infra.CodegenFilePlan = next(
        file for file in plan.files if file.path.name == c.Infra.MAKEFILE_FILENAME
    )
    return makefile.rendered


def _create_member_origin(tmp_path: Path) -> Path:
    member = tmp_path / "member-source"
    member.mkdir()
    (member / "pyproject.toml").write_text(
        "[project]\nname = 'flext-core'\nversion = '0.1.0'\n"
        'requires-python = ">=3.13,<3.14"\ndependencies = []\n',
        encoding="utf-8",
    )
    pkg = member / "src" / "flext_core"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(
        "from __future__ import annotations\n\n__all__: list[str] = []\n",
        encoding="utf-8",
    )
    test_u.Tests.initialize_git_repo(member)
    test_u.Tests.git_bootstrap(member, ("checkout", "-b", _MEMBER_BRANCH))
    test_u.Tests.git_bootstrap(member, ("checkout", c.Infra.GIT_MAIN))
    remote_root = tmp_path / "member-remote"
    remote_root.mkdir()
    origin = test_u.Tests.configure_local_origin(member, remote_root)
    tm.ok(
        u.Infra.git_push_upstream(
            m.Infra.GitPushRequest(
                repo_root=member, remote=c.Infra.GIT_ORIGIN, branch=_MEMBER_BRANCH
            )
        )
    )
    test_u.Tests.git_bootstrap(
        origin, ("symbolic-ref", c.Infra.GIT_HEAD, f"refs/heads/{_MEMBER_BRANCH}")
    )
    return origin


def _create_uninitialized_workspace(tmp_path: Path, makefile: str) -> Path:
    member_origin = _create_member_origin(tmp_path)
    source = tmp_path / "workspace-source"
    source.mkdir()
    (source / "Makefile").write_text(makefile, encoding="utf-8")
    (source / "pyproject.toml").write_text(
        "[project]\nname = 'flext'\nversion = '0.1.0'\n"
        "[tool.uv.workspace]\nmembers = ['flext-core']\n",
        encoding="utf-8",
    )
    test_u.Tests.initialize_git_repo(source)
    test_u.Tests.git_bootstrap(
        source,
        (
            *_FILE_PROTOCOL_CONFIG,
            "submodule",
            "add",
            "-q",
            "-b",
            _MEMBER_BRANCH,
            str(member_origin),
            "flext-core",
        ),
    )
    test_u.Tests.commit_git_changes(source, "Declare workspace member")
    test_u.Tests.git_bootstrap(source, ("checkout", "-b", _MEMBER_BRANCH))
    test_u.Tests.git_bootstrap(source, ("checkout", c.Infra.GIT_MAIN))
    remote_root = tmp_path / "workspace-remote"
    remote_root.mkdir()
    workspace_origin = test_u.Tests.configure_local_origin(source, remote_root)
    tm.ok(
        u.Infra.git_push_upstream(
            m.Infra.GitPushRequest(
                repo_root=source, remote=c.Infra.GIT_ORIGIN, branch=_MEMBER_BRANCH
            )
        )
    )
    test_u.Tests.git_bootstrap(
        workspace_origin,
        ("symbolic-ref", c.Infra.GIT_HEAD, f"refs/heads/{_MEMBER_BRANCH}"),
    )
    checkout = tmp_path / "workspace-checkout"
    checkout.mkdir()
    test_u.Tests.git_bootstrap(
        checkout, ("clone", "-q", str(workspace_origin), str(checkout))
    )
    return checkout


class TestsWorkspaceRootSetupSubmodules:
    def test_generated_setup_orders_submodules_before_first_uv(
        self, tmp_path: Path
    ) -> None:
        rendered = _render_workspace_root_makefile(tmp_path)

        # The generated setup expresses the ordering as a Make prerequisite:
        # every _builtin_setup_environment profile branch depends on
        # _builtin_setup_submodules, whose recipe runs the per-module
        # `submodule update --init` before any `$(UV) sync --project` can run.
        prerequisite = "_builtin_setup_environment: _builtin_setup_submodules"
        update_at = rendered.index("submodule update --init")
        first_uv_at = rendered.index("$(UV) sync --project")

        tm.that(rendered.count(prerequisite), eq=3)
        tm.that(update_at < rendered.index(prerequisite), eq=True)
        # The only uv sync lives in SETUP_ENVIRONMENT_RECIPE, which is reachable
        # solely through the prerequisite-guarded _builtin_setup_environment.
        env_recipe_at = rendered.index("SETUP_ENVIRONMENT_RECIPE = ")
        tm.that(env_recipe_at < first_uv_at, eq=True)

    def test_make_setup_initializes_local_submodule_before_environment(
        self, tmp_path: Path
    ) -> None:
        """Generated workspace-root setup initializes declared submodules first."""
        rendered = _render_workspace_root_makefile(tmp_path)
        workspace = _create_uninitialized_workspace(tmp_path, rendered)
        outcome = u.Cli.run_raw(
            ["make", "_builtin_setup_submodules"],
            cwd=workspace,
            env=_FILE_PROTOCOL_ENV,
            remove_env_keys=test_u.Tests.isolated_git_keys(),
        )
        process = outcome.value
        transcript = process.stdout + process.stderr

        tm.that(process.exit_code, eq=0, msg=transcript)
        tm.that(transcript, has="Submodule path 'flext-core'")
        tm.that((workspace / "flext-core" / "pyproject.toml").is_file(), eq=True)
