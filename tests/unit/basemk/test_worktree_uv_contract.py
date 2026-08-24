"""External-worktree contract for generated uv project resolution."""

from __future__ import annotations

import os
import shutil
from typing import TYPE_CHECKING

from flext_infra.basemk.generator import FlextInfraBaseMkGenerator
from flext_tests import tm
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


def _run(command: list[str], cwd: Path) -> None:
    result = u.Cli.run_raw(command, cwd=cwd)
    tm.that(result.success, eq=True)


class TestsFlextInfraBasemkWorktreeUvContract:
    """Resolve uv sources and environments against the active worktree."""

    def test_external_worktree_uses_lane_project_and_environment(
        self, tmp_path: Path
    ) -> None:
        canonical_root = tmp_path / "canonical" / "consumer"
        lane_root = tmp_path / "lanes" / "consumer-feature"
        canonical_root.mkdir(parents=True)
        lane_root.parent.mkdir(parents=True)
        _run(["git", "init", "-q"], canonical_root)
        _run(["git", "config", "user.email", "tests@flext.sh"], canonical_root)
        _run(["git", "config", "user.name", "FLEXT Tests"], canonical_root)
        (canonical_root / "tracked.txt").write_text("fixture\n", encoding="utf-8")
        (canonical_root / "pyproject.toml").write_text(
            (
                "[project]\n"
                'name = "lane-probe"\n'
                'version = "0.1.0"\n'
                'requires-python = ">=3.13"\n'
            ),
            encoding="utf-8",
        )
        (canonical_root / "lane_probe.py").write_text(
            'VALUE = "canonical"\n', encoding="utf-8"
        )
        _run(
            ["git", "add", "tracked.txt", "pyproject.toml", "lane_probe.py"],
            canonical_root,
        )
        _run(["git", "commit", "-q", "-m", "fixture"], canonical_root)
        _run(
            ["git", "worktree", "add", "-q", str(lane_root), "-b", "feature"],
            canonical_root,
        )
        (lane_root / "lane_probe.py").write_text('VALUE = "lane"\n', encoding="utf-8")

        rendered = tm.ok(FlextInfraBaseMkGenerator().generate_basemk())
        (lane_root / "base.mk").write_text(rendered, encoding="utf-8")
        (lane_root / "Makefile").write_text(
            "include base.mk\n"
            "print-uv-roots:\n"
            '\t@printf \'%s\\n%s\\n\' "$(UV_PROJECT)" "$(UV_PROJECT_ENVIRONMENT)"\n'
            "print-runtime-source:\n"
            '\t@PYTHONPATH="$(UV_PROJECT)" $(UV) run --project "$(UV_PROJECT)" '
            "--no-sync python -c 'import lane_probe; print(lane_probe.VALUE)'\n",
            encoding="utf-8",
        )

        active_env = os.environ.copy()
        inherited_keys = (
            "FLEXT_ROOT",
            "FLEXT_STANDALONE",
            "FLEXT_WORKSPACE_ROOT",
            "UV_PROJECT",
            "UV_PROJECT_ENVIRONMENT",
            "VIRTUAL_ENV",
            "WORKSPACE_ROOT",
        )
        for key in inherited_keys:
            active_env.pop(key, None)
        uv_executable = shutil.which("uv")
        tm.that(uv_executable, none=False)
        active_env.update({
            "MAKEFLAGS": "",
            "MAKEOVERRIDES": "",
            "UV": str(uv_executable),
        })
        result = u.Cli.run_raw(
            ["make", "print-uv-roots"],
            cwd=lane_root,
            env=active_env,
            remove_env_keys=inherited_keys,
        )

        output = [
            line
            for line in tm.ok(result).stdout.splitlines()
            if line.startswith(str(tmp_path))
        ]
        tm.that(output, eq=[str(lane_root), str(lane_root / ".venv")])

        runtime = u.Cli.run_raw(
            ["make", "print-runtime-source"],
            cwd=lane_root,
            env=active_env,
            remove_env_keys=inherited_keys,
        )

        runtime_lines = tm.ok(runtime).stdout.splitlines()
        tm.that("lane" in runtime_lines, eq=True)
        tm.that("canonical" in runtime_lines, eq=False)


__all__: tuple[str, ...] = ()
