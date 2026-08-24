"""Workspace conform progress feedback contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from flext_infra import c, m
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from flext_tests import tm
from tests import u


class TestsFlextInfraCodegenConformProgress:
    """Prove conform emits stage and template progress on stdout."""

    def test_plan_emits_stage_and_repository_progress(
        self, infra_git_repo: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A check-mode conform must report stage and per-repository progress."""
        root = infra_git_repo
        u.Tests.write_standalone_workspace_manifest(
            root, "flext-demo", upstream="flext_cli"
        )
        package_root = root / "src" / "flext_demo"
        tm.ok(u.Cli.ensure_dir(package_root))
        tm.ok(u.Cli.atomic_write_text_file(package_root / "__init__.py", ""))
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "pyproject.toml",
                (
                    "[project]\n"
                    'name = "flext-demo"\n'
                    'version = "0.1.0"\n'
                    'requires-python = ">=3.13,<3.14"\n'
                    "dependencies = []\n"
                ),
            )
        )
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        request = m.Infra.CodegenConformRequest(
            root=root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.APPLY,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
        )
        tm.ok(FlextInfraCodegenConform.execute_request(request, workspace))
        _ = capsys.readouterr()
        checked = FlextInfraCodegenConform.execute_request(
            request.model_copy(update={"mode": c.Infra.CodegenConformMode.CHECK})
        )
        tm.ok(checked)
        captured = capsys.readouterr().out
        tm.that("Codegen Conform" in captured, where=bool, msg=captured[-3000:])
        tm.that("stage=plan" in captured, where=bool, msg=captured[-3000:])
        tm.that(
            "stage=plan repositories=" in captured, where=bool, msg=captured[-3000:]
        )
        tm.that(
            "[1/" in captured and "conform" in captured,
            where=bool,
            msg=captured[-3000:],
        )
        tm.that(
            "stage=pyproject" in captured or "stage=templates" in captured,
            where=bool,
            msg=captured[-3000:],
        )
        tm.that(" template " in captured, where=bool, msg=captured[-3000:])
