"""Real Git + shim bd behavior for make work saga."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING

import flext_infra
import pytest
from flext_infra import FlextInfraWorkService, FlextInfraWorktreeService, config
from flext_tests import tm

from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path as PathType


class TestsFlextInfraWorkService:
    """Public work saga owns bead/branch/worktree registration."""

    @staticmethod
    def _repository(tmp_path: PathType) -> PathType:
        venv_name = config.Infra.tooling.tools.pyright.path_rules.venv_name
        repository = tmp_path / "repository"
        repository.mkdir()
        (repository / "README.md").write_text("fixture\n", encoding="utf-8")
        (repository / "pyproject.toml").write_text(
            '[project]\nname = "fixture"\nversion = "0.1.0"\n'
            'description = "A standard PEP 621 description string"\n',
            encoding="utf-8",
        )
        (repository / "Makefile").write_text(
            ".PHONY: setup\n"
            "setup:\n"
            '\t@grep -q "^\\[project\\]" "$(CURDIR)/pyproject.toml"\n'
            f"\t@mkdir -p {venv_name}/bin\n"
            f"\t@printf '#!/bin/sh\\n' > {venv_name}/bin/python\n"
            f"\t@chmod +x {venv_name}/bin/python\n"
            '\t@printf "setting up %s\\n" "$(CURDIR)"\n',
            encoding="utf-8",
        )
        (repository / ".gitignore").write_text(
            f"{venv_name}\n.reports/\n", encoding="utf-8"
        )
        # Why (mro-tvc03): the ledger is resolved from the typed workspace
        # manifest, so a fixture that only drops .beads/config.yaml no longer
        # declares a tracker. Emit the manifest the runtime actually reads.
        repository_ref = u.Tests.repository_ref("fixture").model_copy(
            update={"path": Path(), "package": False, "editable": False}
        )
        tm.ok(
            u.Cli.yaml_dump(
                repository / "config" / "workspace.yaml",
                m.Infra.WorkspaceSpec(
                    version=c.Infra.WORKSPACE_MANIFEST_VERSION,
                    name=repository_ref.distribution,
                    repository=repository_ref,
                    ledger_id="mro",
                    # Tracker owner declares both identifiers (mro-cdzxf).
                    ledger_prefix="mro",
                ).model_dump(mode="json", exclude_none=True),
            )
        )
        u.Tests.initialize_git_repo(repository)
        return repository

    @staticmethod
    def _member(tmp_path: PathType, workspace: PathType, name: str) -> PathType:
        """Attach a real Git submodule the governing workspace owns."""
        # Why (mro-tvc03): membership is Git topology, not a nested directory.
        # Only a real submodule makes the checkout report its superproject, and
        # that report is what routes the ledger to the governing workspace.
        source = tmp_path / f"{name}-source"
        source.mkdir(parents=True)
        (source / "pyproject.toml").write_text(
            f'[project]\nname = "{name}"\nversion = "0.1.0"\n'
            'description = "A standard PEP 621 description string"\n',
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(source)
        tm.ok(
            u.Cli.run_checked(
                [
                    c.Infra.GIT,
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "add",
                    str(source),
                    name,
                ],
                cwd=workspace,
            )
        )
        return workspace / name

    @staticmethod
    def _install_bd_shim(
        tmp_path: PathType,
        *bead_ids: str,
        update_fails: bool = False,
        issue_types: dict[str, str] | None = None,
        parents: dict[str, str] | None = None,
    ) -> PathType:
        store = tmp_path / "beads-store.json"
        store.write_text(
            json.dumps({
                bead_id: {
                    "id": bead_id,
                    "status": "open",
                    "issue_type": (issue_types or {}).get(bead_id),
                    "parent": (parents or {}).get(bead_id),
                    "assignee": None,
                    "metadata": {},
                    "labels": [],
                }
                for bead_id in bead_ids
            }),
            encoding="utf-8",
        )
        shim_dir = tmp_path / "bin"
        shim_dir.mkdir()
        shim = shim_dir / "bd"
        shim.write_text(
            "#!/usr/bin/env python3\n"
            "from __future__ import annotations\n"
            "import json, sys\n"
            f"STORE = {str(store)!r}\n"
            "args = sys.argv[1:]\n"
            "while args:\n"
            "    if args[0] == '-C' and len(args) > 1:\n"
            "        args = args[2:]\n"
            "        continue\n"
            "    if args[0] in {'--json', '--quiet', '-q', '-v', '--verbose'}:\n"
            "        args = args[1:]\n"
            "        continue\n"
            "    break\n"
            "store = json.loads(open(STORE, encoding='utf-8').read())\n"
            "bead_id = args[1] if len(args) > 1 else ''\n"
            "if args[:1] == ['show'] and '--json' in args:\n"
            "    if bead_id not in store:\n"
            "        raise SystemExit(f'no issue found matching {bead_id}')\n"
            "    print(json.dumps(store[bead_id]))\n"
            "    raise SystemExit(0)\n"
            "if args[:1] == ['list'] and '--json' in args:\n"
            "    print(json.dumps(list(store.values())))\n"
            "    raise SystemExit(0)\n"
            "if args[:1] == ['update']:\n"
            f"    if {update_fails!r}:\n"
            "        raise SystemExit('bd update refused')\n"
            "    if bead_id not in store:\n"
            "        raise SystemExit(f'no issue found matching {bead_id}')\n"
            "    data = store[bead_id]\n"
            "    i = 2\n"
            "    while i < len(args):\n"
            "        if args[i] == '--set-metadata':\n"
            "            key, value = args[i + 1].split('=', 1)\n"
            "            data.setdefault('metadata', {})[key] = value\n"
            "            i += 2\n"
            "            continue\n"
            "        if args[i] == '--unset-metadata':\n"
            "            data.setdefault('metadata', {}).pop(args[i + 1], None)\n"
            "            i += 2\n"
            "            continue\n"
            "        if args[i] == '--add-label':\n"
            "            labels = data.setdefault('labels', [])\n"
            "            if args[i + 1] not in labels:\n"
            "                labels.append(args[i + 1])\n"
            "            i += 2\n"
            "            continue\n"
            "        if args[i] == '--append-notes':\n"
            "            notes = data.setdefault('notes', [])\n"
            "            notes.append(args[i + 1])\n"
            "            i += 2\n"
            "            continue\n"
            "        if args[i] == '--claim':\n"
            "            data['assignee'] = 'worker'\n"
            "            i += 1\n"
            "            continue\n"
            "        i += 1\n"
            "    store[bead_id] = data\n"
            "    open(STORE, 'w', encoding='utf-8').write(json.dumps(store))\n"
            "    print('updated')\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(f'unsupported bd args: {args}')\n",
            encoding="utf-8",
        )
        shim.chmod(0o755)
        return shim_dir

    @staticmethod
    def _install_gh_shim(
        tmp_path: PathType,
        *,
        pr_list: str = "[]",
        pr_view: str = (
            '{"state": "MERGED", "mergedAt": "2026-08-03T00:00:00Z", "headRefName": ""}'
        ),
    ) -> PathType:
        shim_dir = tmp_path / "bin"
        shim_dir.mkdir(exist_ok=True)
        shim = shim_dir / "gh"
        shim.write_text(
            "#!/usr/bin/env python3\n"
            "from __future__ import annotations\n"
            "import sys\n"
            f"PR_LIST = {pr_list!r}\n"
            f"PR_VIEW = {pr_view!r}\n"
            "args = sys.argv[1:]\n"
            "if args[:2] == ['pr', 'list']:\n"
            "    print(PR_LIST)\n"
            "    raise SystemExit(0)\n"
            "if args[:2] == ['pr', 'create']:\n"
            "    print('https://example.test/pr/1')\n"
            "    raise SystemExit(0)\n"
            "if args[:2] == ['pr', 'view']:\n"
            "    print(PR_VIEW)\n"
            "    raise SystemExit(0)\n"
            "raise SystemExit(f'unsupported gh args: {args}')\n",
            encoding="utf-8",
        )
        shim.chmod(0o755)
        return shim_dir

    @staticmethod
    def _attach_bare_origin(tmp_path: PathType, repository: PathType) -> PathType:
        """Replace the self-referencing fixture remote with a pushable origin."""
        origin = tmp_path / "origin.git"
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "init", "--bare", str(origin)], cwd=tmp_path
            )
        )
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "remote", "set-url", "origin", str(origin)],
                cwd=repository,
            )
        )
        tm.ok(
            u.Cli.run_checked([c.Infra.GIT, "push", "origin", "main"], cwd=repository)
        )
        return origin

    @staticmethod
    def _record(tmp_path: PathType, bead_id: str) -> dict[str, dict[str, str]]:
        """Return the bead record the bd shim persisted."""
        store: dict[str, dict[str, dict[str, str]]] = json.loads(
            (tmp_path / "beads-store.json").read_text(encoding="utf-8")
        )
        return store[bead_id]

    @staticmethod
    def _set_record(
        tmp_path: PathType, bead_id: str, record: dict[str, dict[str, str]]
    ) -> None:
        """Persist one bead record back into the bd shim store."""
        path = tmp_path / "beads-store.json"
        store: dict[str, dict[str, dict[str, str]]] = json.loads(
            path.read_text(encoding="utf-8")
        )
        store[bead_id] = record
        path.write_text(json.dumps(store), encoding="utf-8")

    @classmethod
    def _set_metadata(
        cls, tmp_path: PathType, bead_id: str, metadata: dict[str, str]
    ) -> None:
        """Replace the lane metadata of one bead."""
        record = cls._record(tmp_path, bead_id)
        record["metadata"] = metadata
        cls._set_record(tmp_path, bead_id, record)

    @classmethod
    def _metadata(cls, tmp_path: PathType, bead_id: str) -> dict[str, str]:
        """Return the lane metadata the bd shim persisted."""
        return cls._record(tmp_path, bead_id)["metadata"]

    @classmethod
    def _update_root_matrix_entry(
        cls, tmp_path: PathType, bead_id: str, **updates: str
    ) -> None:
        record = cls._record(tmp_path, bead_id)
        metadata = record["metadata"]
        matrix = m.Infra.WorkLaneMatrix.model_validate_json(metadata["matrix"])
        metadata["matrix"] = matrix.model_copy(
            update={
                "entries": tuple(
                    entry.model_copy(update=updates) if entry.project == "." else entry
                    for entry in matrix.entries
                )
            }
        ).model_dump_json()
        metadata.update(updates)
        cls._set_record(tmp_path, bead_id, record)

    @staticmethod
    def _commit_in(lane: PathType, message: str) -> None:
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "commit", "--allow-empty", "-m", message], cwd=lane
            )
        )

    def test_start_registers_lane_and_status_reports_metadata(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-work"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="example-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(started, has="BRANCH=feature/example-lane")
        tm.that(started, has="WORKTREE=")
        status = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.STATUS,
                bead=bead_id,
                apply_changes=False,
            ).execute()
        )
        tm.that(status, has="metadata.branch: feature/example-lane")
        tm.that(status, has="metadata.worktree:")

    def test_start_rejects_matrixless_ready_before_mutation(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-matrixless-ready"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="matrixless-ready",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, bead_id)
        record["metadata"].pop("matrix")
        self._set_record(tmp_path, bead_id, record)
        before_record = self._record(tmp_path, bead_id)
        before_worktrees = tm.ok(
            FlextInfraWorktreeService(
                workspace_root=repository, operation=c.Infra.WorktreeOperation.LIST
            ).execute()
        )

        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.FEATURE,
            name="matrixless-ready",
            base="HEAD",
            apply_changes=True,
        ).execute()

        tm.fail(result, has="ready lane start requires matrix metadata")
        assert self._record(tmp_path, bead_id) == before_record
        assert (
            tm.ok(
                FlextInfraWorktreeService(
                    workspace_root=repository, operation=c.Infra.WorktreeOperation.LIST
                ).execute()
            )
            == before_worktrees
        )

    def test_status_renders_matrixless_ready_without_matrix_lines(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-matrixless-status"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        workspace = m.Infra.WorkspaceSpec.model_validate(
            u.Cli.yaml_load_mapping(repository / "config" / "workspace.yaml")
        )
        provider = next(
            item
            for item in config.Infra.codegen.providers
            if item.name == workspace.repository.provider
        )
        self._set_metadata(
            tmp_path,
            bead_id,
            {
                "branch": "feature/matrixless-status",
                "namespace": "feature",
                "worktree": str(tmp_path / "matrixless-status"),
                "kind": "feature",
                "slug": "matrixless-status",
                "integration_base": u.Infra.resolve_integration_branch(
                    workspace, provider
                ),
                "head_oid": "abc",
                "provisioning": "ready",
                "role": "plain",
            },
        )

        status = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.STATUS,
                bead=bead_id,
                apply_changes=False,
            ).execute()
        )

        tm.that(status, has="metadata.branch: feature/matrixless-status")
        assert "matrix:" not in status

    def test_finish_refuses_primary_checkout(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-primary"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        self._set_metadata(
            tmp_path,
            bead_id,
            {
                "branch": "feature/primary-abuse",
                "namespace": "feature",
                "worktree": str(repository),
                "kind": "feature",
                "slug": "primary-abuse",
                "integration_base": "HEAD",
                "head_oid": tm.ok(
                    u.Infra.git_repository_head(
                        m.Infra.GitRepoRequest(repo_root=repository)
                    )
                ).oid,
                "provisioning": "ready",
                "role": "plain",
            },
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="refuses the primary worktree")

    def test_start_requires_bead(self, tmp_path: PathType) -> None:
        repository = self._repository(tmp_path)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            kind=c.Infra.WorkKind.FEATURE,
            name="no-bead",
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(result, has="requires --bead")

    def test_beads_resolve_reads_the_governing_workspace_manifest(
        self, tmp_path: PathType
    ) -> None:
        """The governing manifest owns the ledger for the workspace and members."""
        workspace = self._repository(tmp_path)
        member = self._member(tmp_path, workspace, "member")

        resolved = tm.ok(u.Infra.beads_resolve_root(member))
        assert str(resolved) == str(workspace.resolve())
        resolved_workspace = tm.ok(u.Infra.beads_resolve_root(workspace))
        assert str(resolved_workspace) == str(workspace.resolve())

    def test_beads_resolve_ignores_a_member_local_tracker_file(
        self, tmp_path: PathType
    ) -> None:
        """A member never outranks the governing workspace it belongs to.

        mro-tvc03: resolution used to walk candidates positionally and return
        the first `.beads/config.yaml` it found, so a member carrying that file
        captured the lane and `bd` bound to the wrong ledger. Ownership is a
        typed declaration on the governing manifest, never a file on disk.
        """
        workspace = self._repository(tmp_path)
        member = self._member(tmp_path, workspace, "member")
        member_beads = member / ".beads"
        member_beads.mkdir()
        (member_beads / "config.yaml").write_text(
            'issue-prefix: "member-local"\n', encoding="utf-8"
        )

        resolved = tm.ok(u.Infra.beads_resolve_root(member))
        assert str(resolved) == str(workspace.resolve())

    def test_finish_removes_lane_and_updates_metadata(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(started, has="BRANCH=bugfix/finish-lane")
        record = self._record(tmp_path, bead_id)
        lane = record["metadata"]["worktree"]
        head = record["metadata"]["head_oid"]
        matrix = m.Infra.WorkLaneMatrix.model_validate_json(
            record["metadata"]["matrix"]
        )
        record["metadata"]["matrix"] = matrix.model_copy(
            update={
                "entries": tuple(
                    entry.model_copy(update={"pr_number": "1"})
                    if entry.project == "."
                    else entry
                    for entry in matrix.entries
                )
            }
        ).model_dump_json()
        record["metadata"]["pr_number"] = "1"
        self._set_record(tmp_path, bead_id, record)
        finished = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.FINISH,
                bead=bead_id,
                apply_changes=True,
            ).execute()
        )
        tm.that(finished, has="FINISHED BRANCH=bugfix/finish-lane")
        assert not Path(lane).exists()
        updated = self._metadata(tmp_path, bead_id)
        assert updated["worktree"] == "removed"
        assert updated["head_oid"] == head

    def test_finish_cas_mismatch_fails(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-cas"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="cas-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        self._update_root_matrix_entry(
            tmp_path, bead_id, head_oid="0" * 40, pr_number="1"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="CAS failed")

    def test_land_refuses_permanent_branch(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-perm"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        self._set_metadata(
            tmp_path,
            bead_id,
            {
                "branch": "main",
                "worktree": str(tmp_path / "fake-lane"),
                "kind": "feature",
                "slug": "main",
                "integration_base": "HEAD",
                "head_oid": "a" * 40,
                "provisioning": "ready",
                "role": "plain",
            },
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="metadata.ready.namespace")

    def test_land_requires_head_oid(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-oid"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-oid",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, bead_id)
        record["metadata"]["head_oid"] = ""
        self._set_record(tmp_path, bead_id, record)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="metadata.ready.head_oid")

    def test_land_refuses_metadata_worktree_mismatch(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-bind"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-bind",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        poison = tmp_path / "poison-tree"
        poison.mkdir()
        (poison / "README.md").write_text("poison\n", encoding="utf-8")
        u.Tests.initialize_git_repo(poison)
        record = self._record(tmp_path, bead_id)
        record["metadata"]["worktree"] = str(poison)
        self._set_record(tmp_path, bead_id, record)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="does not match registered lane")

    def test_finish_requires_head_oid(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-oid"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-oid",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, bead_id)
        record["metadata"]["head_oid"] = ""
        record["metadata"]["pr_number"] = "1"
        self._set_record(tmp_path, bead_id, record)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="metadata.ready.head_oid")

    def test_finish_refuses_permanent_branch_via_config_integration(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        # Why (mro-tvc03): the manifest is the tracker SSOT the fixture already
        # wrote, so the integration branch is ADDED to it. Overwriting the file
        # with a fragment produced a manifest without version/name/repository
        # and the lane could no longer resolve its own ledger.
        manifest = repository / "config" / "workspace.yaml"
        declared = u.Cli.yaml_load_mapping(manifest)
        tm.ok(
            u.Cli.yaml_dump(
                manifest,
                {
                    **declared,
                    "integration": {"provider": "flext-sh", "branch": "0.12.0-dev"},
                },
            )
        )
        bead_id = "mro-test-finish-perm"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        self._set_metadata(
            tmp_path,
            bead_id,
            {
                "branch": "0.12.0-dev",
                "worktree": str(tmp_path / "fake-lane"),
                "kind": "feature",
                "slug": "integration",
                "integration_base": "0.12.0-dev",
                "head_oid": "a" * 40,
                "provisioning": "ready",
                "role": "plain",
            },
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="metadata.ready.namespace")

    def test_finish_accepts_already_removed(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-removed"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        self._set_metadata(
            tmp_path,
            bead_id,
            {
                "branch": "bugfix/gone",
                "namespace": "bugfix",
                "worktree": "removed",
                "kind": "bugfix",
                "slug": "gone",
                "integration_base": "HEAD",
                "head_oid": "a" * 40,
                "provisioning": "ready",
                "role": "plain",
            },
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.that(tm.ok(result), has="receipt.worktree=removed")

    def test_status_reports_after_start(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-status-detail"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="status-detail",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        status = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.STATUS,
                bead=bead_id,
                apply_changes=False,
            ).execute()
        )
        tm.that(status, has="branch: feature/status-detail")
        tm.that(status, has="primary_checkout:")

    def test_finish_refuses_metadata_worktree_mismatch(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-bind"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-bind",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        poison = tmp_path / "poison-finish"
        poison.mkdir()
        (poison / "README.md").write_text("poison\n", encoding="utf-8")
        u.Tests.initialize_git_repo(poison)
        record = self._record(tmp_path, bead_id)
        record["metadata"]["worktree"] = str(poison)
        record["metadata"]["pr_number"] = "1"
        self._set_record(tmp_path, bead_id, record)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="does not match registered lane")

    def test_start_rejects_invalid_slug(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-bad-slug"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.FEATURE,
            name="Not_Kebab",
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(result, has="kebab-case required")

    def test_start_rejects_forbidden_slug(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-forbidden-slug"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.FEATURE,
            name="temp",
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(result, has="forbidden work slug")

    def test_start_requires_apply(self, tmp_path: PathType) -> None:
        repository = self._repository(tmp_path)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead="mro-test-start-apply",
            kind=c.Infra.WorkKind.FEATURE,
            name="needs-apply",
            base="HEAD",
            apply_changes=False,
        ).execute()
        tm.fail(result, has="requires --apply")

    def test_land_requires_apply(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-apply"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=False,
        ).execute()
        tm.fail(result, has="requires --apply")

    def test_land_cas_mismatch_fails(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-cas"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-cas",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        self._update_root_matrix_entry(tmp_path, bead_id, head_oid="0" * 40)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="CAS failed")

    def test_land_refuses_dirty_lane(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-land-dirty"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="land-dirty",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        lane = Path(self._metadata(tmp_path, bead_id)["worktree"])
        (lane / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="clean lane worktree")

    def test_makefile_j2_exposes_work_builtins_on_workspace(self) -> None:
        template = (
            Path(flext_infra.__file__).resolve().parent
            / "templates"
            / "project"
            / "base"
            / "Makefile.j2"
        ).read_text(encoding="utf-8")
        tm.that(template, has="override WORKSPACE := $(WORKSPACE_ROOT)/$(PROJECT)")
        tm.that(template, has="_builtin_work_status:")
        tm.that(template, has="_builtin_work_start:")
        tm.that(template, has="_builtin_work_land:")
        tm.that(template, has="_builtin_work_finish:")
        tm.that(
            template, has='workspace work --workspace "$(WORKSPACE)" --operation status'
        )
        tm.that(
            template, has='workspace work --workspace "$(WORKSPACE)" --operation land'
        )
        tm.that(template, has='$(if $(strip $(KIND)),--kind "$(KIND)")')
        tm.that(template, lacks='--kind "$(KIND)" --name')
        tm.that(template, has='--epic "$(EPIC)"')

    def test_finish_refuses_missing_lane(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-missing"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-missing",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, bead_id)
        lane = Path(record["metadata"]["worktree"])
        record["metadata"]["pr_number"] = "1"
        self._set_record(tmp_path, bead_id, record)
        for child in sorted(lane.rglob("*"), reverse=True):
            if child.is_file() or child.is_symlink():
                child.unlink()
            elif child.is_dir():
                child.rmdir()
        lane.rmdir()
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="lane worktree missing")
        assert self._metadata(tmp_path, bead_id)["worktree"] != "removed"

    def test_finish_fails_when_pr_list_errors(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-gh-fail"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="finish-gh-fail",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        gh = shim_dir / "gh"
        gh.write_text(
            "#!/usr/bin/env python3"
            + chr(10)
            + "import sys"
            + chr(10)
            + "raise SystemExit('gh unavailable')"
            + chr(10),
            encoding="utf-8",
        )
        gh.chmod(0o755)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="gh unavailable")

    def test_finish_refuses_pr_head_mismatch(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-pr-head"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-pr-head",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        self._update_root_matrix_entry(tmp_path, bead_id, pr_number="9")
        gh = shim_dir / "gh"
        gh.write_text(
            "#!/usr/bin/env python3"
            + chr(10)
            + "import json, sys"
            + chr(10)
            + "print(json.dumps({'state': 'MERGED', 'mergedAt': '2026-08-03T00:00:00Z', 'headRefName': 'feature/other'}))"
            + chr(10),
            encoding="utf-8",
        )
        gh.chmod(0o755)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="does not match lane branch")

    def test_land_refuses_integration_base_drift(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        # Why (mro-tvc03): add the integration branch to the manifest the
        # fixture already declared; replacing it with a fragment removed the
        # tracker identity the lane resolves its ledger from.
        manifest = repository / "config" / "workspace.yaml"
        declared = u.Cli.yaml_load_mapping(manifest)
        tm.ok(
            u.Cli.yaml_dump(
                manifest,
                {
                    **declared,
                    "integration": {"provider": "flext-sh", "branch": "0.12.0-dev"},
                },
            )
        )
        bead_id = "mro-test-land-base-drift"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-base-drift",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, bead_id)
        record["metadata"]["integration_base"] = "attacker-base"
        self._set_record(tmp_path, bead_id, record)
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="integration_base drift")

    def test_start_idempotent_same_lane_refreshes_head(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Re-running start on a bound bead refreshes CAS instead of failing."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-start-idempotent"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        first = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="idempotent-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(first, has="receipt.operation=start")
        lane = Path(self._metadata(tmp_path, bead_id)["worktree"])
        stale_head = self._metadata(tmp_path, bead_id)["head_oid"]
        self._commit_in(lane, "lane work")
        second = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="idempotent-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        refreshed = self._metadata(tmp_path, bead_id)
        assert refreshed["worktree"] == str(lane)
        assert refreshed["head_oid"] != stale_head
        tm.that(second, has=f"receipt.head_oid={refreshed['head_oid']}")
        tm.that(second, has=f"receipt.worktree={lane}")
        assert lane.is_dir()

    def test_start_recovers_existing_lane_without_metadata(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A lane registered by an interrupted start is adopted, not rejected."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-start-recover"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        orphan = tm.ok(
            FlextInfraWorktreeService(
                workspace_root=repository,
                operation=c.Infra.WorktreeOperation.ADD,
                branch="feature/recover-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        assert self._metadata(tmp_path, bead_id) == {}
        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="recover-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(started, has=f"receipt.worktree={orphan}")
        tm.that(started, has="receipt.branch=feature/recover-lane")
        assert self._metadata(tmp_path, bead_id)["worktree"] == orphan

    def test_start_rolls_back_lane_when_beads_update_fails(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A lane the saga cannot register on its bead must not survive."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-start-rollback"
        shim_dir = self._install_bd_shim(tmp_path, bead_id, update_fails=True)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.FEATURE,
            name="rollback-lane",
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(result, has="bd update refused")
        tm.fail(result, has="rolled back")
        orphaned = FlextInfraWorktreeService.registered_lane(
            repository, "feature/rollback-lane"
        )
        tm.fail(orphaned, has="is not registered")

    def test_land_happy_path_push_and_pr_updates_metadata(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Land pushes the lane, records the PR, and emits a land receipt."""
        repository = self._repository(tmp_path)
        self._attach_bare_origin(tmp_path, repository)
        bead_id = "mro-test-land-happy"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(
            tmp_path, pr_list='[{"number": "7", "url": "https://example.test/pr/7"}]'
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-happy",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        landed = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.LAND,
                bead=bead_id,
                apply_changes=True,
            ).execute()
        )
        metadata = self._metadata(tmp_path, bead_id)
        tm.that(landed, has="receipt.operation=land")
        tm.that(landed, has="receipt.pr=7")
        tm.that(landed, has="receipt.base=main")
        tm.that(landed, has=f"receipt.head_oid={metadata['head_oid']}")
        assert metadata["pr_number"] == "7"
        assert metadata["pr_url"] == "https://example.test/pr/7"
        pushed = tm.ok(
            u.Infra.git_rev_parse(
                m.Infra.GitCommitishRequest(
                    repo_root=repository,
                    commitish="refs/remotes/origin/feature/land-happy",
                )
            )
        ).oid
        assert pushed == metadata["head_oid"]

    def test_land_allows_ancestor_cas(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Lane commits made after start are a fast-forward, not a CAS conflict."""
        repository = self._repository(tmp_path)
        self._attach_bare_origin(tmp_path, repository)
        bead_id = "mro-test-land-ancestor"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(
            tmp_path, pr_list='[{"number": "3", "url": "https://example.test/pr/3"}]'
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-ancestor",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        recorded = self._metadata(tmp_path, bead_id)["head_oid"]
        lane = Path(self._metadata(tmp_path, bead_id)["worktree"])
        self._commit_in(lane, "lane advance")
        landed = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.LAND,
                bead=bead_id,
                apply_changes=True,
            ).execute()
        )
        advanced = self._metadata(tmp_path, bead_id)["head_oid"]
        assert advanced != recorded
        tm.that(landed, has=f"receipt.head_oid={advanced}")

    def test_land_push_rejection_reports_shas(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rejected push names both SHAs so the operator can judge divergence."""
        repository = self._repository(tmp_path)
        self._attach_bare_origin(tmp_path, repository)
        bead_id = "mro-test-land-reject"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="land-reject",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        lane = Path(self._metadata(tmp_path, bead_id)["worktree"])
        self._commit_in(repository, "remote advance")
        remote_oid = tm.ok(
            u.Infra.git_repository_head(m.Infra.GitRepoRequest(repo_root=repository))
        ).oid
        tm.ok(
            u.Cli.run_checked(
                [c.Infra.GIT, "push", "origin", "HEAD:refs/heads/feature/land-reject"],
                cwd=repository,
            )
        )
        tm.ok(u.Cli.run_checked([c.Infra.GIT, "fetch", "origin"], cwd=lane))
        self._commit_in(lane, "lane diverge")
        local_oid = tm.ok(
            u.Infra.git_repository_head(m.Infra.GitRepoRequest(repo_root=lane))
        ).oid
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.LAND,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has=f"local={local_oid.strip()}")
        tm.fail(result, has=f"remote={remote_oid.strip()}")

    def test_finish_refuses_open_pr_state(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An open PR still owns the lane, so finish must refuse to retire it."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-open"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(
            tmp_path, pr_view='{"state": "OPEN", "mergedAt": null, "headRefName": ""}'
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-open",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        self._update_root_matrix_entry(tmp_path, bead_id, pr_number="5")
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="requires merged PR #5; state=OPEN")

    def test_finish_refuses_closed_unmerged_pr(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A closed-without-merge PR abandoned the work; the lane stays."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-closed"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(
            tmp_path, pr_view='{"state": "CLOSED", "mergedAt": null, "headRefName": ""}'
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-closed",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        self._update_root_matrix_entry(tmp_path, bead_id, pr_number="6")
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="requires merged PR #6; state=CLOSED")
        assert self._metadata(tmp_path, bead_id)["worktree"] != "removed"

    def test_finish_refuses_open_pr_without_pr_number(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Without a recorded PR the branch query is the only merge evidence."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-finish-open-query"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(tmp_path, pr_list='[{"number": "8"}]')
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.BUGFIX,
                name="finish-open-query",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=bead_id,
            apply_changes=True,
        ).execute()
        tm.fail(result, has="refuses open PR on bugfix/finish-open-query")

    def test_start_status_land_finish_idempotent_status_twice(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The full lane lifecycle runs once, and status never mutates it."""
        repository = self._repository(tmp_path)
        self._attach_bare_origin(tmp_path, repository)
        bead_id = "mro-test-lifecycle"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        self._install_gh_shim(
            tmp_path, pr_list='[{"number": "9", "url": "https://example.test/pr/9"}]'
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="lifecycle-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(started, has="receipt.operation=start")
        status_service = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.STATUS,
            bead=bead_id,
            apply_changes=False,
        )
        first_status = tm.ok(status_service.execute())
        second_status = tm.ok(status_service.execute())
        assert first_status == second_status
        landed = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.LAND,
                bead=bead_id,
                apply_changes=True,
            ).execute()
        )
        tm.that(landed, has="receipt.operation=land")
        finished = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.FINISH,
                bead=bead_id,
                apply_changes=True,
            ).execute()
        )
        tm.that(finished, has="receipt.operation=finish")
        tm.that(finished, has="receipt.pr=9")
        tm.that(finished, has="receipt.branch=feature/lifecycle-lane")
        assert self._metadata(tmp_path, bead_id)["worktree"] == "removed"

    def test_makefile_j2_help_scopes_apply_to_mutating_work_selectors(self) -> None:
        """Help must not demand APPLY=Y for the read-only default selector."""
        template = (
            Path(flext_infra.__file__).resolve().parent
            / "templates"
            / "project"
            / "base"
            / "Makefile.j2"
        ).read_text(encoding="utf-8")
        tm.that(
            template,
            has="{{ verb.default_what }} is read-only; other WHATs require APPLY=Y",
        )

    def test_makefile_j2_exposes_the_public_epic_selector(self) -> None:
        """One public selector nests a child lane, and it names a bead id."""
        template = (
            Path(flext_infra.__file__).resolve().parent
            / "templates"
            / "project"
            / "base"
            / "Makefile.j2"
        ).read_text(encoding="utf-8")
        tm.that(template, has='--base "$(BASE)" --epic "$(EPIC)" --apply')
        tm.that(template, has='$(if $(strip $(KIND)),--kind "$(KIND)")')
        tm.that(
            template,
            has="'EPIC' 'registered epic bead id; nests work start as its child lane'",
        )
        tm.that(
            template,
            has="'KIND' 'optional feature|bugfix|hotfix|release; omitted derives from Bead issue_type'",
        )

    @pytest.mark.parametrize(
        ("issue_type", "expected_branch"),
        [
            ("epic", "epic/derived-kind"),
            ("feature", "feature/derived-kind"),
            ("bug", "bugfix/derived-kind"),
        ],
    )
    def test_start_derives_kind_from_issue_type(
        self,
        tmp_path: PathType,
        monkeypatch: pytest.MonkeyPatch,
        issue_type: str,
        expected_branch: str,
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = f"mro-{issue_type}-kind"
        shim_dir = self._install_bd_shim(
            tmp_path, bead_id, issue_types={bead_id: issue_type}
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                name="derived-kind",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.that(started, has=f"BRANCH={expected_branch}")

    def test_start_refuses_explicit_gitflow_kind_for_epic_issue(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-epic-explicit-kind"
        shim_dir = self._install_bd_shim(
            tmp_path, bead_id, issue_types={bead_id: "epic"}
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )

        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            kind=c.Infra.WorkKind.FEATURE,
            name="epic-explicit-kind",
            base="HEAD",
            apply_changes=True,
        ).execute()

        tm.fail(result, has="epic issue derives the epic branch namespace")

    def test_start_refuses_missing_issue_type_without_kind_override(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repository = self._repository(tmp_path)
        bead_id = "mro-missing-kind"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=bead_id,
            name="missing-kind",
            base="HEAD",
            apply_changes=True,
        ).execute()
        tm.fail(result, has="missing issue_type")

    def _started_epic_lane(
        self,
        tmp_path: PathType,
        repository: PathType,
        epic_bead: str,
        child_bead: str,
        *,
        child_name: str = "child-one",
    ) -> tuple[PathType, PathType]:
        """Start one epic lane and one child lane nested below it."""
        store_path = tmp_path / "beads-store.json"
        store = json.loads(store_path.read_text(encoding="utf-8"))
        store[epic_bead]["issue_type"] = "epic"
        store[child_bead]["parent"] = epic_bead
        store_path.write_text(json.dumps(store), encoding="utf-8")
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=epic_bead,
                name="epic-alpha",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=child_bead,
                kind=c.Infra.WorkKind.FEATURE,
                name=child_name,
                epic=epic_bead,
                apply_changes=True,
            ).execute()
        )
        return (
            Path(self._metadata(tmp_path, epic_bead)["worktree"]),
            Path(self._metadata(tmp_path, child_bead)["worktree"]),
        )

    def test_start_child_nests_under_the_registered_epic(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A child lane derives its base and its container from its epic."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic"
        child_bead = "mro-test-child"
        shim_dir = self._install_bd_shim(
            tmp_path,
            epic_bead,
            child_bead,
            issue_types={epic_bead: "epic", child_bead: "task"},
            parents={child_bead: epic_bead},
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=epic_bead,
                name="epic-alpha",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        epic_lane = Path(self._metadata(tmp_path, epic_bead)["worktree"])

        started = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=child_bead,
                kind=c.Infra.WorkKind.FEATURE,
                name="child-one",
                epic=epic_bead,
                apply_changes=True,
            ).execute()
        )

        tm.that(started, has=f"EPIC={epic_bead}")
        tm.that(started, has="BASE=epic/epic-alpha")
        child = self._metadata(tmp_path, child_bead)
        tm.that(child["role"], eq=c.Infra.WorkLaneRole.CHILD.value)
        tm.that(child["epic_bead"], eq=epic_bead)
        tm.that(child["epic_branch"], eq="epic/epic-alpha")
        tm.that(child["epic_worktree"], eq=str(epic_lane))
        tm.that(child["child_slug"], eq="child-one")
        tm.that(child["integration_base"], eq="epic/epic-alpha")
        container = epic_lane / c.Infra.WORKTREES_DIRNAME
        tm.that(Path(child["worktree"]), eq=container / "child-one")
        tm.that(
            self._metadata(tmp_path, epic_bead)["role"],
            eq=c.Infra.WorkLaneRole.EPIC.value,
        )
        tm.that(
            tm.ok(FlextInfraWorktreeService.registered_children(repository, epic_lane)),
            eq=(Path(child["worktree"]),),
        )

    def test_start_child_refuses_a_literal_base_beside_its_epic(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The epic alone decides where a child branches from."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic-base"
        child_bead = "mro-test-child-base"
        shim_dir = self._install_bd_shim(
            tmp_path,
            epic_bead,
            child_bead,
            issue_types={epic_bead: "epic", child_bead: "task"},
            parents={child_bead: epic_bead},
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=epic_bead,
                name="epic-alpha",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )

        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=child_bead,
            kind=c.Infra.WorkKind.FEATURE,
            name="child-one",
            epic=epic_bead,
            base="HEAD",
            apply_changes=True,
        ).execute()

        tm.fail(result, has="drop --base")

    def test_start_child_refuses_an_epic_that_owns_no_lane(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A child never precedes the epic lane it must nest under."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic-absent"
        child_bead = "mro-test-child-absent"
        shim_dir = self._install_bd_shim(
            tmp_path,
            epic_bead,
            child_bead,
            issue_types={epic_bead: "epic", child_bead: "task"},
            parents={child_bead: epic_bead},
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )

        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.START,
            bead=child_bead,
            kind=c.Infra.WorkKind.FEATURE,
            name="child-one",
            epic=epic_bead,
            apply_changes=True,
        ).execute()

        tm.fail(result, has=f"epic bead {epic_bead} lane is not ready")

    def test_status_reports_the_registered_epic_topology(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Status proves the recorded topology against Git's registry."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic-status"
        child_bead = "mro-test-child-status"
        shim_dir = self._install_bd_shim(
            tmp_path,
            epic_bead,
            child_bead,
            issue_types={epic_bead: "epic", child_bead: "feature"},
            parents={child_bead: epic_bead},
        )
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        epic_lane, child_lane = self._started_epic_lane(
            tmp_path, repository, epic_bead, child_bead
        )

        epic_status = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.STATUS,
                bead=epic_bead,
                apply_changes=False,
            ).execute()
        )
        child_status = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.STATUS,
                bead=child_bead,
                apply_changes=False,
            ).execute()
        )

        tm.that(epic_status, has=f"epic_topology: epic children=1 {child_lane}")
        tm.that(child_status, has=f"epic_topology: child of {epic_lane}")

    def test_status_of_a_plain_lane_reports_no_epic_topology(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A lane without an epic keeps the exact status it always had."""
        repository = self._repository(tmp_path)
        bead_id = "mro-test-plain-status"
        shim_dir = self._install_bd_shim(tmp_path, bead_id)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=bead_id,
                kind=c.Infra.WorkKind.FEATURE,
                name="plain-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )

        status = tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.STATUS,
                bead=bead_id,
                apply_changes=False,
            ).execute()
        )

        assert "epic_topology" not in status
        assert "metadata.role" not in status

    # Why (suite budget): builds an epic lane plus a nested child worktree with
    # real git submodule scans; the per-case wall only holds on an idle CPU.
    @pytest.mark.slow
    def test_finish_refuses_the_epic_until_its_child_is_finished(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A child lane pins its epic lane, and finishing the child frees it."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic-finish"
        child_bead = "mro-test-child-finish"
        shim_dir = self._install_bd_shim(tmp_path, epic_bead, child_bead)
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        epic_lane, child_lane = self._started_epic_lane(
            tmp_path, repository, epic_bead, child_bead
        )
        for bead_id, pr_number in ((epic_bead, "1"), (child_bead, "2")):
            self._update_root_matrix_entry(tmp_path, bead_id, pr_number=pr_number)

        refused = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=epic_bead,
            apply_changes=True,
        ).execute()

        tm.fail(refused, has="while children are registered")
        tm.fail(refused, has=str(child_lane))
        tm.that(epic_lane.is_dir(), where=bool)

        tm.that(
            tm.ok(
                FlextInfraWorkService(
                    workspace_root=repository,
                    operation=c.Infra.WorkOperation.FINISH,
                    bead=child_bead,
                    apply_changes=True,
                ).execute()
            ),
            has="FINISHED BRANCH=feature/child-one",
        )
        tm.that(
            tm.ok(
                FlextInfraWorkService(
                    workspace_root=repository,
                    operation=c.Infra.WorkOperation.FINISH,
                    bead=epic_bead,
                    apply_changes=True,
                ).execute()
            ),
            has="FINISHED BRANCH=epic/epic-alpha",
        )
        assert not epic_lane.exists()

    def test_finish_refuses_a_child_lane_outside_its_epic_namespace(
        self, tmp_path: PathType, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Recorded child metadata never overrides the real lane topology."""
        repository = self._repository(tmp_path)
        epic_bead = "mro-test-epic-escape"
        child_bead = "mro-test-child-escape"
        shim_dir = self._install_bd_shim(
            tmp_path,
            epic_bead,
            child_bead,
            issue_types={epic_bead: "epic", child_bead: "feature"},
            parents={child_bead: epic_bead},
        )
        self._install_gh_shim(tmp_path)
        monkeypatch.setenv(
            "PATH", f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        )
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=epic_bead,
                name="epic-alpha",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        epic_lane = Path(self._metadata(tmp_path, epic_bead)["worktree"])
        tm.ok(
            FlextInfraWorkService(
                workspace_root=repository,
                operation=c.Infra.WorkOperation.START,
                bead=child_bead,
                kind=c.Infra.WorkKind.FEATURE,
                name="outside-lane",
                base="HEAD",
                apply_changes=True,
            ).execute()
        )
        record = self._record(tmp_path, child_bead)
        record["metadata"] |= {
            "role": c.Infra.WorkLaneRole.CHILD.value,
            "epic_bead": epic_bead,
            "epic_branch": "epic/epic-alpha",
            "epic_worktree": str(epic_lane),
            "child_slug": "outside-lane",
        }
        self._set_record(tmp_path, child_bead, record)

        result = FlextInfraWorkService(
            workspace_root=repository,
            operation=c.Infra.WorkOperation.FINISH,
            bead=child_bead,
            apply_changes=True,
        ).execute()

        tm.fail(result, has="is not nested under epic lane")
        tm.fail(result, has=str(epic_lane))
