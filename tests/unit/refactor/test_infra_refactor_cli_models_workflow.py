"""CLI workflow tests for refactor namespace automation."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main as infra_main
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRefactorInfraRefactorCliModelsWorkflow:
    """Behavior contract for test_infra_refactor_cli_models_workflow."""

    def test_namespace_enforce_cli_fails_on_manual_protocol_violation(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.mk_project(
            tmp_path, "workspace", pyproject="[project]\nname='sample'\n", with_src=True
        )
        module_dir = workspace / "src" / "sample_pkg"
        module_dir.mkdir(parents=True)
        (workspace / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
        (module_dir / "service.py").write_text(
            "from __future__ import annotations\n"
            "from typing import Protocol\n\n"
            "class External(Protocol):\n"
            "    def call(self) -> str:\n"
            "        ...\n",
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(workspace)
        buffer = StringIO()
        cli_args = [
            "namespace-enforce",
            f"--repository-root={workspace!s}",
            "--dry-run",
        ]
        with redirect_stdout(buffer):
            result = infra_main(["refactor", *cli_args])
        tm.that(result, ne=0)

    def test_wrapper_root_namespace_cli_dry_run_succeeds(self, tmp_path: Path) -> None:
        workspace = u.Tests.mk_project(
            tmp_path, "workspace", pyproject="[project]\nname='sample'\n", with_src=True
        )
        scripts_dir = workspace / "scripts"
        scripts_dir.mkdir(parents=True)
        (workspace / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
        source_file = scripts_dir / "sample.py"
        source_file.write_text(
            "from tests import c\n"
            "\n"
            "def test_contract() -> None:\n"
            "    _ = c.Core.Tests.ERR_OK_FAILED\n",
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(workspace)

        with redirect_stdout(StringIO()):
            result = infra_main([
                "refactor",
                "wrapper-root-namespace",
                f"--repository-root={workspace!s}",
                "--dry-run",
            ])

        tm.that(result, eq=0)
        tm.that(source_file.read_text(encoding="utf-8"), has="c.Core.Tests")

    def test_wrapper_root_namespace_cli_check_fails_when_changes_are_needed(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.mk_project(
            tmp_path, "workspace", pyproject="[project]\nname='sample'\n", with_src=True
        )
        scripts_dir = workspace / "scripts"
        scripts_dir.mkdir(parents=True)
        (workspace / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
        (scripts_dir / "sample.py").write_text(
            "from tests import m\n"
            "\n"
            "def test_contract() -> None:\n"
            "    _ = m.Core.Tests.Testobject\n",
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(workspace)

        result = infra_main([
            "refactor",
            "wrapper-root-namespace",
            f"--repository-root={workspace!s}",
            "--check",
        ])

        tm.that(result, ne=0)

    def test_wrapper_root_namespace_cli_apply_rewrites_file(
        self, tmp_path: Path
    ) -> None:
        workspace = u.Tests.mk_project(
            tmp_path, "workspace", pyproject="[project]\nname='sample'\n", with_src=True
        )
        scripts_dir = workspace / "scripts"
        scripts_dir.mkdir(parents=True)
        (workspace / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
        source_file = scripts_dir / "sample.py"
        source_file.write_text(
            "from tests import t\n"
            "\n"
            "def test_contract() -> None:\n"
            "    _ = t.Core.Tests.Testobject\n",
            encoding="utf-8",
        )
        u.Tests.initialize_git_repo(workspace)

        result = infra_main([
            "refactor",
            "wrapper-root-namespace",
            f"--repository-root={workspace!s}",
            "--apply",
        ])

        tm.that(result, eq=0)
        updated = source_file.read_text(encoding="utf-8")
        tm.that(updated, has="from tests import t")
        tm.that(updated, has="t.Tests.Testobject")
        tm.that(updated, lacks="Core.Tests")
