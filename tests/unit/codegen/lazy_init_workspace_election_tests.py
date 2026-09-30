"""Workspace-mode lazy-init elects the same nearest parent as standalone mode."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, u


class TestsFlextInfraLazyInitWorkspaceElection:
    """A repository-local planner never borrows a sibling checkout's facade."""

    @staticmethod
    def _write_constants(package_root: Path, *, parent: str, class_name: str) -> None:
        package_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            f"from {parent} import c as parent_c\n\n"
            f"class {class_name}(parent_c):\n"
            "    pass\n\n"
            f"c = {class_name}\n"
            f'__all__: list[str] = ["{class_name}", "c"]\n',
            encoding=c.Infra.ENCODING_DEFAULT,
        )

    def test_workspace_plan_does_not_resolve_an_uninstalled_sibling_parent(
        self, tmp_path: Path
    ) -> None:
        """A child needs its declared parent installed in its own environment."""
        workspace = tmp_path / "workspace"
        _owner_repo, owner = u.Tests.create_lazy_init_workspace(
            workspace, project_name="flext-ws-owner", package_name="flext_ws_owner"
        )
        _middle_repo, middle = u.Tests.create_lazy_init_workspace(
            workspace, project_name="flext-ws-middle", package_name="flext_ws_middle"
        )
        child_repo, child = u.Tests.create_lazy_init_workspace(
            workspace, project_name="flext-ws-child", package_name="flext_ws_child"
        )
        u.Tests.write_lazy_init_namespace_module(
            owner / c.Infra.CONSTANTS_PY, class_name="FlextWsOwnerConstants", alias="c"
        )
        u.Tests.write_lazy_init_namespace_module(
            owner / "result.py", class_name="FlextWsOwnerResult", alias="r"
        )
        self._write_constants(
            middle, parent="flext_ws_owner", class_name="FlextWsMiddleConstants"
        )
        self._write_constants(
            child, parent="flext_ws_middle", class_name="FlextWsChildConstants"
        )

        child_init = child / c.Infra.INIT_PY
        before = child_init.read_bytes()
        tm.that(tm.ok(u.Tests.plan_lazy_init(workspace)).files, eq=())
        with pytest.raises(
            ValueError,
            match="declared facade parent 'flext_ws_middle' resolves nowhere",
        ):
            u.Tests.plan_lazy_init(child_repo)
        tm.that(child_init.read_bytes(), eq=before)
