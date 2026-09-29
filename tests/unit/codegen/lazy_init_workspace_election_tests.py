"""Workspace-mode lazy-init elects the same nearest parent as standalone mode."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import c, u


class TestsFlextInfraLazyInitWorkspaceElection:
    """A letter's source never depends on how many projects share the scan.

    A child project inherits ``r`` through a middle project that re-exports it
    from the declaring owner project. Planned from the workspace root, every
    project is indexed, so the owner is reachable through the middle project's
    facade chain; the election must still name the nearest re-exporting parent
    (the middle project), exactly as a standalone checkout of the child does
    (operator ruling 2026-09-23).
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
        self, tmp_path: Path
    ) -> None:
        """The child's ``r`` comes from the middle project, never the owner."""
        workspace = tmp_path / "workspace"
        _owner_repo, owner = u.Tests.create_lazy_init_workspace(
            workspace, project_name="flext-ws-owner", package_name="flext_ws_owner"
        )
        _middle_repo, middle = u.Tests.create_lazy_init_workspace(
            workspace, project_name="flext-ws-middle", package_name="flext_ws_middle"
        )
        _child_repo, child = u.Tests.create_lazy_init_workspace(
            workspace, project_name="flext-ws-child", package_name="flext_ws_child"
        )
        workspace.joinpath(c.Infra.GITMODULES).write_text(
            "".join(
                f'[submodule "{name}"]\n\tpath = {name}\n'
                for name in ("flext-ws-owner", "flext-ws-middle", "flext-ws-child")
            ),
            encoding=c.Infra.ENCODING_DEFAULT,
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

        tm.that(u.Tests.run_lazy_init(workspace), eq=0)
        tm.that(u.Tests.run_lazy_init(workspace), eq=0)
        generated = child.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )
        entries, _refs = u.Infra.module_mapping_assignment_source(
            generated, u.Infra.lazy_imports_name_source(generated)
        )
        sources = dict(entries)

        tm.that(sources.get("flext_ws_middle", ()), has="r")
        tm.that(sources, lacks="flext_ws_owner")
        tm.that(u.Tests.run_lazy_init(workspace, check_only=True), eq=0)
