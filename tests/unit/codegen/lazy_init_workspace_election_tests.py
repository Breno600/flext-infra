"""Workspace-mode lazy-init elects the same nearest parent as standalone mode."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, u


class TestsFlextInfraLazyInitWorkspaceElection:
    """A letter's source never depends on how many projects share the scan.

    A child project inherits ``r`` through a middle project that re-exports it
    from the declaring owner project. Each Git checkout publishes its own
    initializer. The next project's real import path reads that published ABI,
    so the child must elect the nearest re-exporting parent.
    """

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

    def test_workspace_plan_elects_nearest_reexporting_parent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The child's ``r`` comes from the middle project, never the owner."""
        workspace = tmp_path / "workspace"
        owner_repo, owner = u.Tests.create_lazy_init_workspace(
            workspace, project_name="flext-ws-owner", package_name="flext_ws_owner"
        )
        middle_repo, middle = u.Tests.create_lazy_init_workspace(
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

        for repository in (owner_repo, middle_repo, child_repo):
            monkeypatch.syspath_prepend(str(repository / c.Infra.DEFAULT_SRC_DIR))
        for repository in (owner_repo, middle_repo, child_repo):
            tm.that(u.Tests.run_lazy_init(repository), eq=0)
            tm.that(u.Tests.run_lazy_init(repository, check_only=True), eq=0)
        generated = child.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )
        entries, _refs = u.Infra.module_mapping_assignment_source(
            generated, u.Infra.lazy_imports_name_source(generated)
        )
        sources = dict(entries)

        tm.that(sources.get("flext_ws_middle", ()), has="r")
        tm.that(sources, lacks="flext_ws_owner")
        tm.that(u.Tests.run_lazy_init(child_repo, check_only=True), eq=0)
