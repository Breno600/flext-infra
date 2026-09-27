"""Real cold-workspace upgrades materialize gitlinks before Python resolution."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_core import r
from tests import c, m, t, u

pytestmark = [pytest.mark.slow, pytest.mark.remote]


class TestsFlextInfraCodegenUpgWorkspace:
    """Upgrade a real workspace with an indexed, uninitialized member."""

    def test_upg_materializes_member_before_resolving_workspace_lock(
        self, tmp_path: Path
    ) -> None:
        root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.WORKSPACE, bootstrap=True
        )
        member = u.Tests.repository_ref("fixture-member", path=Path("fixture-member"))
        source = tmp_path / "member-origin"
        u.Tests.WorktreeFixture.write_python_project(source, member.distribution)
        u.Tests.initialize_git_repo(source)
        branch = u.Tests.checkout_integration(source)
        u.Tests.git_bootstrap(
            root,
            (
                "-c",
                "protocol.file.allow=always",
                "submodule",
                "add",
                "-b",
                branch,
                str(source),
                member.path.as_posix(),
            ),
        )
        u.Tests.git_bootstrap(
            root,
            (
                "config",
                "-f",
                c.Infra.GITMODULES,
                f"submodule.{member.path.as_posix()}.flext-managed",
                "true",
            ),
        )
        u.Tests.git_bootstrap(root, ("add", c.Infra.GITMODULES, member.path.as_posix()))
        u.Tests.git_bootstrap(root, ("commit", "-m", "Declare real workspace member"))
        gitlink = tm.ok(
            u.Cli.capture(
                [c.Infra.GIT, "rev-parse", f"HEAD:{member.path.as_posix()}"], cwd=root
            )
        ).strip()
        repository = u.Tests.repository_ref(
            root.name, role=c.Infra.MakeProfile.WORKSPACE
        )
        workspace = u.Tests.workspace_spec(
            repository,
            project=u.Tests.project_spec(repository.name),
            subprojects=(member,),
        )
        plan = u.Tests.conform_plan(root, workspace)
        artifacts = tuple(
            artifact
            for artifact in plan.files
            if artifact.path
            in {root / c.Infra.MAKEFILE_FILENAME, root / c.PYPROJECT_FILENAME}
        )
        tm.that(len(artifacts), eq=2)
        tm.ok(
            u.Tests.materialize_codegen_plans(
                r[tuple[m.Infra.CodegenFilePlan, ...]].ok(artifacts)
            )
        )
        u.Tests.git_bootstrap(root, ("submodule", "deinit", "--force", "--all"))
        checkout = root / member.path
        tm.that((checkout / c.PYPROJECT_FILENAME).exists(), eq=False)
        tm.that((root / c.Infra.UV_LOCK_FILENAME).exists(), eq=False)

        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "upg"],
                cwd=root,
                env={"GIT_ALLOW_PROTOCOL": "file:https:ssh"},
            )
        )

        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tm.that((checkout / c.PYPROJECT_FILENAME).is_file(), eq=True)
        tm.that(
            tm.ok(
                u.Cli.capture([c.Infra.GIT, "rev-parse", "HEAD"], cwd=checkout)
            ).strip(),
            eq=gitlink,
        )
        locked = u.Tests.toml_payload((root / c.Infra.UV_LOCK_FILENAME).read_text())
        packages = t.Cli.JSON_LIST_ADAPTER.validate_python(locked["package"])
        tm.that(
            tuple(
                t.Cli.JSON_MAPPING_ADAPTER.validate_python(item)["name"]
                for item in packages
            ),
            has=member.distribution,
        )
        tm.that((root / ".venv" / "pyvenv.cfg").is_file(), eq=True)
        tm.that((checkout / ".venv").exists(), eq=False)
        pin = (root / c.Infra.MISE_VERSION_PIN_FILENAME).read_text().strip()
        tm.that(process.stdout, has=f"mise setup receipt={pin}")
