"""Workspace conform progress feedback contract."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, infra, m
from tests import u


class TestsFlextInfraCodegenConformProgress:
    """Prove conform emits stage and repository progress on stdout."""

    def test_plan_emits_stage_and_repository_progress(
        self,
        infra_git_repo: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A check-mode conform must report stage and per-repository progress."""
        root = infra_git_repo
        # The check pass re-detects the checkout, so the manifest must declare
        # the identity the fixture's Git origin carries.
        workspace = u.Tests.standalone_workspace(root, config.Infra.name)
        request = m.Infra.CodegenConformRequest(
            root=root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.APPLY,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
        )
        tm.ok(infra.codegen_conform(request, workspace))
        _ = capsys.readouterr()
        checked = infra.codegen_conform(
            request.model_copy(update={"mode": c.Infra.CodegenConformMode.CHECK}),
        )
        tm.ok(checked)
        captured = capsys.readouterr().out
        tm.that("Codegen Conform" in captured, where=bool, msg=captured[-3000:])
        tm.that("stage=plan" in captured, where=bool, msg=captured[-3000:])
        tm.that(
            "stage=plan repositories=" in captured,
            where=bool,
            msg=captured[-3000:],
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
