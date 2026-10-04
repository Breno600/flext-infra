"""Workspace-mode lazy-init evaluates each repository, never the members.

Operator ruling 2026-09-29: a workspace root consumes its declared members as
installed libraries and never fans a verb out across them. The fixture declares
three member repositories through ``.gitmodules`` — the shape that used to make
the workspace root plan every member and elect cross-repository re-export
parents (ruling 2026-09-23). That scenario is gone by contract: each member
evaluates only itself, a self-scoped plan refuses loud when a declared facade
parent is another repository that the active environment has not installed,
and the workspace root plans nothing — zero effects is the contract, not a
regression.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, u


class TestsFlextInfraLazyInitWorkspaceElection:
    """Workspace planning uses declared sibling source without publishing it."""

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

    def test_workspace_plan_uses_declared_sibling_without_installing_it(
        self,
        tmp_path: Path,
    ) -> None:
        """Members self-scope; cross-repo parents refuse loud; the root plans zero."""
        workspace = tmp_path / "workspace"
        owner_repo, owner = u.Tests.create_lazy_init_workspace(
            workspace,
            project_name="flext-ws-owner",
            package_name="flext_ws_owner",
        )
        middle_repo, middle = u.Tests.create_lazy_init_workspace(
            workspace,
            project_name="flext-ws-middle",
            package_name="flext_ws_middle",
        )
        child_repo, child = u.Tests.create_lazy_init_workspace(
            workspace,
            project_name="flext-ws-child",
            package_name="flext_ws_child",
        )
        workspace.joinpath(c.Infra.GITMODULES).write_text(
            "".join(
                f'[submodule "{name}"]\n\tpath = {name}\n'
                for name in ("flext-ws-owner", "flext-ws-middle", "flext-ws-child")
            ),
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        u.Tests.write_lazy_init_namespace_module(
            owner / c.Infra.CONSTANTS_PY,
            class_name="FlextWsOwnerConstants",
            alias="c",
        )
        u.Tests.write_lazy_init_namespace_module(
            owner / "result.py",
            class_name="FlextWsOwnerResult",
            alias="r",
        )
        self._write_constants(
            middle,
            parent="flext_ws_owner",
            class_name="FlextWsMiddleConstants",
        )
        self._write_constants(
            child,
            parent="flext_ws_middle",
            class_name="FlextWsChildConstants",
        )

        # The owner has no cross-repository parent: two self-scoped planning
        # cycles reach the fixed point (the second is a no-op receipt), and the
        # generated facade exports only the owner's own namespace.
        tm.that(u.Tests.run_lazy_init(owner_repo), eq=0)
        tm.that(u.Tests.run_lazy_init(owner_repo), eq=0)
        tm.that(u.Tests.run_lazy_init(owner_repo, check_only=True), eq=0)
        generated = owner.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        entries, _refs = u.Infra.lazy_import_mapping_source(generated)

        tm.that(dict(entries).get(".constants", ()), has="c")

        # The middle declares its facade parent in ANOTHER repository. Self
        # scope never indexes a sibling: with the parent not installed in the
        # active environment the plan refuses loud instead of silently
        # resolving through a declared submodule's checkout.
        with pytest.raises(ValueError, match="resolves nowhere"):
            _ = u.Tests.run_lazy_init(middle_repo)

        # The workspace root owns no package dirs at all: its members are
        # declared submodules, consumed as installed libraries, and its
        # planning receipt is empty by contract.
        tm.that(u.Tests.run_lazy_init(workspace), eq=0)
        tm.that(u.Tests.run_lazy_init(workspace, check_only=True), eq=0)
        _ = (child, child_repo)
