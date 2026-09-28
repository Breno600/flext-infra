"""Real Git + shim bd behavior for make work saga."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

from flext_tests import tm

from tests import c, m, t, u

if TYPE_CHECKING:
    from pathlib import Path as PathType


class WorkServiceFixture:
    """Shared real-Git and command-fixture support; contains no tests."""

    """Public work saga owns bead/branch/worktree registration."""

    @staticmethod
    def _repository(tmp_path: PathType) -> PathType:
        venv_name = c.Infra.ENVIRONMENT_DIRECTORY
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
            u.Cli.json_dumps({
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
            }).unwrap(),
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
        path.write_text(
            u.Cli.json_dumps(t.Cli.JSON_VALUE_ADAPTER.validate_python(store)).unwrap(),
            encoding="utf-8",
        )

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


__all__: list[str] = ["WorkServiceFixture"]
