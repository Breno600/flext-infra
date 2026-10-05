"""Public conform contract for the declared Hatch custom build hook.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra.codegen import FlextInfraCodegenConform
from tests import c, m, t, u
from tests.unit.codegen.conform_support import TestsFlextInfraConformSupport

pytestmark = [pytest.mark.slow]


class TestsFlextInfraCodegenConformHatchHook:
    """Prove the manifest-declared Hatch hook is the only hook projection."""

    @staticmethod
    def _hook_workspace(hook_path: str | Path | None) -> m.Infra.WorkspaceSpec:
        """Build one standalone project whose manifest owns the Hatch hook.

        Returns:
            The resulting ``m.Infra.WorkspaceSpec``.

        """
        repository = u.Tests.repository_ref("hook-project").model_copy(
            update={"role": c.Infra.MakeProfile.STANDALONE},
        )
        project_payload = u.Tests.project_spec("hook-project").model_dump()
        project_payload["hatch_build_hook_path"] = hook_path
        return u.Tests.workspace_spec(
            repository,
            project=m.Infra.ProjectSpec.model_validate(project_payload),
        )

    @staticmethod
    def _planned_hook_pyproject(
        root: Path,
        hook_path: str | Path | None,
    ) -> t.Triple[
        FlextInfraCodegenConform,
        m.Infra.CodegenConformRequest,
        m.Infra.CodegenFilePlan,
    ]:
        """Plan the canonical pyproject through the public conform owner.

        Returns:
            The resulting ``t.Triple[FlextInfraCodegenConform,
                m.Infra.CodegenConformRequest, m.Infra.CodegenFilePlan]``.

        """
        u.Tests.seed_locked_taplo(root.parent)
        service, request = TestsFlextInfraConformSupport.check_conform_service(
            root,
            TestsFlextInfraCodegenConformHatchHook._hook_workspace(hook_path),
            what=c.Infra.CodegenConformSurface.PYPROJECT,
        )
        plan = tm.ok(service.plan(request))
        pyproject = next(
            item for item in plan.files if item.path.name == c.PYPROJECT_FILENAME
        )
        return service, request, pyproject

    # NOTE (multi-agent, flext-get3j): these tests exercise the public conform
    # owner so no test-only template path can mask declaration or propagation drift.
    def test_declared_hatch_build_hook_renders_before_wheel_target(
        self,
        tmp_path: Path,
    ) -> None:
        """Test declared hatch build hook renders before wheel target."""
        _, _, pyproject = self._planned_hook_pyproject(
            tmp_path / "declared",
            Path("scripts/hatch_build.py"),
        )
        rendered = u.Tests.codegen_file_text(pyproject)

        tm.that(
            u.Tests.toml_table_at(
                rendered,
                "tool",
                "hatch",
                "build",
                "hooks",
                "custom",
            )["path"],
            eq="scripts/hatch_build.py",
        )
        tm.that(
            rendered.index("[tool.hatch.build.hooks.custom]")
            < rendered.index("[tool.hatch.build.targets.wheel]"),
            eq=True,
        )

    def test_absent_hatch_build_hook_emits_no_custom_hook_table(
        self,
        tmp_path: Path,
    ) -> None:
        """Test absent hatch build hook emits no custom hook table."""
        _, _, pyproject = self._planned_hook_pyproject(tmp_path / "absent", None)

        tm.that(
            u.Tests.codegen_file_text(pyproject),
            lacks="[tool.hatch.build.hooks.custom]",
        )

    @staticmethod
    @pytest.mark.parametrize(
        "unsafe_path",
        [
            "/scripts/hatch_build.py",
            ".",
            "..",
            "../scripts/hatch_build.py",
            "scripts/../hatch_build.py",
            r"scripts\hatch_build.py",
            "C:/scripts/hatch_build.py",
            r"\\server\share\hatch_build.py",
        ],
    )
    def test_hatch_build_hook_rejects_unsafe_paths(unsafe_path: str) -> None:
        """Test hatch build hook rejects unsafe paths."""
        payload = u.Tests.project_spec("unsafe-hook").model_dump()
        payload["hatch_build_hook_path"] = unsafe_path

        with pytest.raises(c.ValidationError, match="safe project-relative path"):
            m.Infra.ProjectSpec.model_validate(payload)

    def test_hatch_build_hook_conform_reaches_pyproject_fixed_point(
        self,
        tmp_path: Path,
    ) -> None:
        """Test hatch build hook conform reaches pyproject fixed point."""
        root = tmp_path / "fixed-point"
        service, request, first = self._planned_hook_pyproject(
            root,
            Path("scripts/hatch_build.py"),
        )
        root.mkdir(parents=True, exist_ok=True)
        # Publish exactly what the plan declares: bytes and permission bits, so
        # the fixed point never depends on the process umask.
        published = root / c.PYPROJECT_FILENAME
        published.write_bytes(tm.not_none(first.desired_content))
        published.chmod(tm.not_none(first.desired_mode))

        second_plan = tm.ok(service.plan(request))
        second = next(
            item for item in second_plan.files if item.path.name == c.PYPROJECT_FILENAME
        )

        tm.that(u.Tests.codegen_file_text(second), eq=u.Tests.codegen_file_text(first))
        tm.that(u.Infra.codegen_file_requires_effect(second), eq=False)
