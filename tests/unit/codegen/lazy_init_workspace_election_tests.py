"""Repository-local projects retain their nearest facade re-export boundary."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import c, u


class TestsFlextInfraLazyInitWorkspaceElection:
    """A letter's source never depends on how many projects share the scan.

    A child project inherits ``r`` through a middle project that re-exports it
    from the declaring owner project. The three projects share one Git owner,
    so all are indexed and the owner is reachable through the middle project's
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
        packages: list[Path] = []
        for name in ("flext-ws-owner", "flext-ws-middle", "flext-ws-child"):
            repository_project = workspace / name
            packages.append(
                u.Tests.src_package(
                    repository_project,
                    name.replace("-", "_"),
                    pyproject=f'[project]\nname="{name}"\nversion="0.1.0"\n',
                )
            )
            u.Tests.write_project_beads_config(repository_project, name)
        owner, middle, child = packages
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

        u.Tests.initialize_git_repo(workspace)
        service = u.Tests.create_lazy_init_service(workspace)
        analysis = tm.ok(service.plan_files())
        child_plan = next(
            plan for plan in analysis.publications if plan.context.pkg_dir == child
        )
        tm.that(child_plan.lazy_map.get("r"), eq=(middle.name, "r"))
        tm.ok(u.Tests.materialize_lazy_init(service))
        tm.that(u.Tests.run_lazy_init(workspace, check_only=True), eq=0)
