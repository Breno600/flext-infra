"""Workspace-root member matrix lifecycle behavior."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from flext_infra import FlextInfraWorkService, FlextInfraWorktreeService, c, m
from flext_tests import tm
from tests import u as test_u
from tests.unit.workspace.test_work_service import (
    TestsFlextInfraWorkService as _WorkFixture,
)

_metadata = _WorkFixture._metadata  # ruff: ignore[private-member-access]
_repository = _WorkFixture._repository  # ruff: ignore[private-member-access]
_member = _WorkFixture._member  # ruff: ignore[private-member-access]
_install_bd_shim = _WorkFixture._install_bd_shim  # ruff: ignore[private-member-access]
_install_gh_shim = _WorkFixture._install_gh_shim  # ruff: ignore[private-member-access]
_set_metadata = _WorkFixture._set_metadata  # ruff: ignore[private-member-access]
_attach_bare_origin = _WorkFixture._attach_bare_origin  # ruff: ignore[private-member-access]


def _matrix(tmp_path: Path, bead_id: str) -> m.Infra.WorkLaneMatrix:
    metadata = _metadata(tmp_path, bead_id)
    return m.Infra.WorkLaneMatrix.model_validate_json(metadata["matrix"])


def _workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    bead_id: str,
    *,
    issue_type: str | None = None,
) -> tuple[Path, Path]:
    repository = _repository(tmp_path)
    member = _member(tmp_path, repository, "member")
    with (repository / ".gitignore").open("a", encoding="utf-8") as stream:
        stream.write(".reports/\n")
    with (repository / "pyproject.toml").open("a", encoding="utf-8") as stream:
        stream.write('\n[tool.uv.workspace]\nmembers = ["member"]\n')
    tm.ok(
        test_u.Cli.run_checked(
            [
                c.Infra.GIT,
                "config",
                "-f",
                c.Infra.GITMODULES,
                "submodule.member.url",
                "https://github.com/flext-sh/member.git",
            ],
            cwd=repository,
        )
    )
    tm.ok(
        test_u.Cli.run_checked(
            [
                c.Infra.GIT,
                "config",
                "url." + str(tmp_path / "member-source") + ".insteadOf",
                "https://github.com/flext-sh/member.git",
            ],
            cwd=repository,
        )
    )
    tm.ok(
        test_u.Cli.run_checked(
            [
                c.Infra.GIT,
                "config",
                "submodule.member.url",
                str(tmp_path / "member-source"),
            ],
            cwd=repository,
        )
    )
    manifest = repository / "config" / "workspace.yaml"
    workspace = m.Infra.WorkspaceSpec.model_validate(
        test_u.Cli.yaml_load_mapping(manifest)
    )
    member_ref = test_u.Tests.repository_ref("member").model_copy(
        update={
            "path": Path("member"),
            "url": "https://github.com/flext-sh/member.git",
            "branch": "0.12.0-dev",
            "package": False,
            "editable": False,
        }
    )
    tm.ok(
        test_u.Cli.yaml_dump(
            manifest,
            workspace.model_copy(update={"members": (member_ref,)}).model_dump(
                mode="json", exclude_none=True
            ),
        )
    )
    (repository / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.1.0"\n'
        'description = "A standard PEP 621 description string"\n\n'
        '[tool.uv.workspace]\nmembers = ["member"]\n',
        encoding="utf-8",
    )
    (member / "Makefile").write_text(
        ".PHONY: setup\n"
        "setup:\n"
        "\t@mkdir -p .venv/bin\n"
        "\t@printf '#!/bin/sh\\n' > .venv/bin/python\n"
        "\t@chmod +x .venv/bin/python\n",
        encoding="utf-8",
    )
    (member / ".gitignore").write_text(".venv/\n", encoding="utf-8")
    tm.ok(
        test_u.Cli.run_checked(
            [c.Infra.GIT, "add", "Makefile", ".gitignore"], cwd=member
        )
    )
    tm.ok(
        test_u.Cli.run_checked(
            [c.Infra.GIT, "commit", "-m", "add setup surface"], cwd=member
        )
    )
    tm.ok(
        test_u.Cli.run_checked(
            [
                c.Infra.GIT,
                "config",
                "-f",
                ".gitmodules",
                "submodule.member.url",
                "https://github.com/flext-sh/member.git",
            ],
            cwd=repository,
        )
    )
    tm.ok(
        test_u.Cli.run_checked(
            [
                c.Infra.GIT,
                "config",
                "-f",
                ".gitmodules",
                "submodule.member.branch",
                "0.12.0-dev",
            ],
            cwd=repository,
        )
    )
    tm.ok(
        test_u.Cli.run_checked(
            [c.Infra.GIT, "add", ".gitmodules", "member"], cwd=repository
        )
    )
    tm.ok(
        test_u.Cli.run_checked(
            [
                c.Infra.GIT,
                "config",
                "submodule.member.url",
                str(tmp_path / "member-source"),
            ],
            cwd=repository,
        )
    )
    tm.ok(
        test_u.Cli.run_checked(
            [c.Infra.GIT, "commit", "-am", "attach member"], cwd=repository
        )
    )
    issue_types = {bead_id: issue_type} if issue_type is not None else None
    shim_dir = _install_bd_shim(tmp_path, bead_id, issue_types=issue_types)
    _install_gh_shim(
        tmp_path, pr_list='[{"number": "41", "url": "https://example.test/pr/41"}]'
    )
    gh = tmp_path / "bin" / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "import json, sys\n"
        "args = sys.argv[1:]\n"
        "is_member = Path.cwd().name == 'member'\n"
        "number = '42' if is_member else '41'\n"
        "url = f'https://example.test/pr/{number}'\n"
        "if args[:2] == ['pr', 'list']:\n"
        "    print(json.dumps([{'number': number, 'url': url}]))\n"
        "elif args[:2] == ['pr', 'create']:\n"
        "    print(url)\n"
        "elif args[:2] == ['pr', 'view']:\n"
        "    print(json.dumps({'state': 'MERGED', 'mergedAt': '2026-08-03T00:00:00Z', 'headRefName': ''}))\n"
        "else:\n"
        "    raise SystemExit(f'unsupported gh args: {args}')\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return repository, member


def _start_from_member(member: Path, bead_id: str) -> str:
    return tm.ok(
        FlextInfraWorkService(
            workspace_root=member,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.FEATURE,
            name="member-matrix",
            base="HEAD",
            apply_changes=True,
        ).execute()
    )


def test_member_start_upgrades_legacy_scalar_metadata_to_workspace_matrix(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bead_id = "mro-member-start"
    repository, member = _workspace(tmp_path, monkeypatch, bead_id)
    branch = "feature/member-matrix"
    lane = tm.ok(
        FlextInfraWorktreeService(
            workspace_root=repository,
            operation=c.Infra.WorktreeOperation.ADD,
            branch=branch,
            base="HEAD",
            apply_changes=True,
        ).execute()
    )
    _set_metadata(
        tmp_path,
        bead_id,
        {
            "branch": branch,
            "worktree": lane,
            "integration_base": "HEAD",
            "head_oid": tm.ok(
                test_u.Infra.git_repository_head(
                    m.Infra.GitRepoRequest(repo_root=Path(lane))
                )
            ).oid,
        },
    )

    _start_from_member(member, bead_id)

    matrix = _matrix(tmp_path, bead_id)
    assert tuple(entry.project for entry in matrix.entries) == (".", "member")
    assert all(entry.branch == branch for entry in matrix.entries)
    assert all(entry.state == "started" for entry in matrix.entries)


def test_epic_start_preserves_legacy_workspace_matrix_during_upgrade(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bead_id = "mro-legacy-epic"
    repository, member = _workspace(tmp_path, monkeypatch, bead_id, issue_type="epic")
    branch = "epic/tracker-governance"
    lane = Path(
        tm.ok(
            FlextInfraWorktreeService(
                workspace_root=repository,
                operation=c.Infra.WorktreeOperation.ADD,
                branch=branch,
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
    )
    root_head = tm.ok(
        test_u.Infra.git_repository_head(m.Infra.GitRepoRequest(repo_root=lane))
    ).oid
    member_head = tm.ok(
        test_u.Infra.git_repository_head(
            m.Infra.GitRepoRequest(repo_root=lane / "member")
        )
    ).oid
    legacy_matrix = m.Infra.WorkLaneMatrix(
        entries=(
            m.Infra.WorkLaneEntry(
                project=".", branch=branch, head_oid=root_head, state="started"
            ),
            m.Infra.WorkLaneEntry(
                project="member",
                branch=branch,
                head_oid=member_head,
                pr_number="41",
                pr_url="https://example.test/pr/41",
                state="landed",
            ),
        )
    )
    _set_metadata(
        tmp_path,
        bead_id,
        {
            "integration_base": "HEAD",
            "kind": "epic",
            "matrix": legacy_matrix.model_dump_json(),
            "slug": "tracker-governance",
            "worktree": str(lane),
        },
    )

    tm.ok(
        FlextInfraWorkService(
            workspace_root=member,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            name="tracker-governance",
            base="HEAD",
            apply_changes=True,
        ).execute()
    )

    upgraded = _matrix(tmp_path, bead_id)
    assert upgraded.entries == legacy_matrix.entries


def test_land_publishes_every_workspace_matrix_branch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bead_id = "mro-member-land"
    repository, member = _workspace(tmp_path, monkeypatch, bead_id)
    origin = _attach_bare_origin(tmp_path, repository)
    _start_from_member(member, bead_id)

    tm.ok(
        FlextInfraWorkService(
            workspace_root=member,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
    )

    matrix = _matrix(tmp_path, bead_id)
    prs = {entry.project: (entry.pr_number, entry.pr_url) for entry in matrix.entries}
    assert prs == {
        ".": ("41", "https://example.test/pr/41"),
        "member": ("42", "https://example.test/pr/42"),
    }
    root = next(entry for entry in matrix.entries if entry.project == ".")
    pushed = tm.ok(
        test_u.Infra.git_rev_parse(
            m.Infra.GitCommitishRequest(
                repo_root=repository, commitish=f"refs/remotes/origin/{root.branch}"
            )
        )
    ).oid
    assert pushed == root.head_oid
    assert origin.is_dir()


def test_finish_removes_every_workspace_matrix_checkout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bead_id = "mro-member-finish"
    repository, member = _workspace(tmp_path, monkeypatch, bead_id)
    _attach_bare_origin(tmp_path, repository)
    _start_from_member(member, bead_id)
    tm.ok(
        FlextInfraWorkService(
            workspace_root=member,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
    )
    before = _matrix(tmp_path, bead_id)
    lane = Path(_metadata(tmp_path, bead_id)["worktree"])

    tm.ok(
        FlextInfraWorkService(
            workspace_root=member,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
    )

    after = _matrix(tmp_path, bead_id)
    assert not lane.exists()
    assert tuple(entry.project for entry in after.entries) == tuple(
        entry.project for entry in before.entries
    )
    assert all(entry.state == "removed" for entry in after.entries)


__all__: tuple[str, ...] = ()
