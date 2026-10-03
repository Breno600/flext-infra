"""Public conformance contract for declared Python distribution roots.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import pytest
from flext_tests import tm

from flext_infra import c, main as infra_main
from tests import t, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDepsModernizerPackaging:
    """Conformance contract for declared Python distribution roots."""

    @staticmethod
    def _declared_roots() -> t.Pair[t.NonEmptyStr, t.NonEmptyStr]:
        """Derive arbitrary valid roots from the typed project fixture owner.

        Returns:
            The resulting ``t.Pair[t.NonEmptyStr, t.NonEmptyStr]``.

        """
        package_name = u.Tests.project_spec("flext-packaging-fixture").package_name
        return f"{package_name}_entry", f"{package_name}_client"

    def _prepare_project(
        self,
        root: Path,
        *,
        materialize_module: bool,
        materialize_package: bool,
    ) -> t.Pair[t.NonEmptyStr, t.NonEmptyStr]:
        """Materialize one provider-governed project through shared typed fixtures.

        Returns:
            The resulting ``t.Pair[t.NonEmptyStr, t.NonEmptyStr]``.

        """
        _ = u.Tests.standalone_workspace(root, "flext-packaging-fixture")
        root_module, root_package = self._declared_roots()
        source_root = root / c.Infra.DEFAULT_SRC_DIR
        if materialize_module:
            tm.ok(
                u.Cli.atomic_write_text_file(
                    source_root / f"{root_module}.py",
                    "VALUE = 1\n",
                ),
            )
        if materialize_package:
            # The declared root keeps its initializer, and the distribution
            # root package gets a real module with declared exports: the
            # planner only emits a WRITE plan (the public export contract the
            # fresh-import validation demands) for a root that publishes at
            # least one local module.
            tm.ok(
                u.Cli.atomic_write_text_file(
                    source_root / root_package / c.Infra.INIT_PY,
                    '"""Fixture."""\n',
                ),
            )
            module_root = source_root / "flext_packaging_fixture"
            tm.ok(
                u.Cli.atomic_write_text_file(
                    module_root / "core.py",
                    'VALUE = 1\n\n__all__: list[str] = ["VALUE"]\n',
                ),
            )
            tm.ok(
                u.Cli.atomic_write_text_file(
                    module_root / c.Infra.INIT_PY,
                    '"""Fixture package."""\n',
                ),
            )
        _ = u.Tests.write_standalone_workspace_manifest(
            root,
            "flext-packaging-fixture",
            root_modules=[root_module],
            root_packages=[root_package],
            # The fixture package ships no cli module, so it declares none.
            cli_module=False,
        )
        u.Tests.git_bootstrap(
            root,
            (
                "remote",
                "set-url",
                c.Infra.GIT_ORIGIN,
                u.Tests.repository_ref("flext-packaging-fixture").url,
            ),
        )
        u.Tests.copy_tracked_mise_seeds(root)
        return root_module, root_package

    @staticmethod
    @pytest.mark.slow
    def _conform_self(infra_git_repo: Path) -> int:
        """Run codegen conform self-apply through the public CLI entrypoint.

        Returns:
            The resulting ``int``.

        """
        return infra_main([
            c.Infra.CLI_GROUP_CODEGEN,
            "conform",
            "--root",
            str(infra_git_repo),
            "--scope",
            c.Infra.CodegenConformScope.SELF.value,
            "--mode",
            c.Infra.CodegenConformMode.APPLY.value,
        ])

    @pytest.mark.slow
    def test_conform_packages_every_declared_python_root(
        self,
        infra_git_repo: Path,
    ) -> None:
        """The public generator emits matching bounded wheel and sdist targets."""
        root_module, root_package = self._prepare_project(
            infra_git_repo,
            materialize_module=True,
            materialize_package=True,
        )

        applied = self._conform_self(infra_git_repo)

        tm.that(applied, eq=0)
        manifest = (infra_git_repo / c.PYPROJECT_FILENAME).read_text(encoding="utf-8")
        wheel = u.Tests.toml_table_at(
            manifest,
            c.Infra.TOOL,
            "hatch",
            "build",
            "targets",
            "wheel",
        )
        sdist = u.Tests.toml_table_at(
            manifest,
            c.Infra.TOOL,
            "hatch",
            "build",
            "targets",
            "sdist",
        )
        primary_package = u.Tests.project_spec("flext-packaging-fixture").package_name
        package_paths = {
            f"{c.Infra.DEFAULT_SRC_DIR}/{primary_package}",
            f"{c.Infra.DEFAULT_SRC_DIR}/{root_package}",
        }
        module_path = f"{c.Infra.DEFAULT_SRC_DIR}/{root_module}.py"
        tm.that(
            set(u.Tests.toml_list(wheel["include"])),
            eq={f"/{path}/**" for path in package_paths},
        )
        tm.that(
            u.Tests.toml_mapping(wheel["force-include"]),
            has=module_path,
            msg=manifest,
        )
        tm.that(
            u.Tests.toml_mapping(wheel["force-include"])[module_path],
            eq=f"{root_module}.py",
        )
        included = set(u.Tests.toml_list(sdist["include"]))
        tm.that({f"/{path}/**" for path in package_paths} <= included, eq=True)
        tm.that(u.Tests.toml_mapping(sdist["force-include"]), has=module_path)
        tm.that(
            u.Tests.toml_mapping(sdist["force-include"])[module_path],
            eq=module_path,
        )

        manifest_path = infra_git_repo / c.PYPROJECT_FILENAME
        header = "[tool.hatch.build.targets.sdist.force-include]\n"
        # The stale entry must really be injected, or ``lacks`` below passes
        # vacuously on an unchanged manifest.
        tm.that(manifest.count(header), eq=1)
        tm.ok(
            u.Cli.atomic_write_text_file(
                manifest_path,
                manifest.replace(header, header + '"stale.txt" = "stale.txt"\n'),
            ),
        )
        tm.that(self._conform_self(infra_git_repo), eq=0)
        repaired = u.Tests.toml_table_at(
            manifest_path.read_text(encoding="utf-8"),
            c.Infra.TOOL,
            "hatch",
            "build",
            "targets",
            "sdist",
        )
        tm.that(u.Tests.toml_mapping(repaired["force-include"]), lacks="stale.txt")

        fixed_point = infra_main([
            c.Infra.CLI_GROUP_CODEGEN,
            "conform",
            "--root",
            str(infra_git_repo),
            "--scope",
            c.Infra.CodegenConformScope.SELF.value,
            "--mode",
            c.Infra.CodegenConformMode.CHECK.value,
        ])
        tm.that(fixed_point, eq=0)

    @pytest.mark.slow
    @pytest.mark.parametrize("missing_kind", ["module", "package"])
    def test_conform_rejects_missing_declared_python_root(
        self,
        infra_git_repo: Path,
        missing_kind: Literal["module", "package"],
    ) -> None:
        """A declaration never produces a phantom wheel or sdist path."""
        _ = self._prepare_project(
            infra_git_repo,
            materialize_module=missing_kind != "module",
            materialize_package=missing_kind != "package",
        )
        before = (infra_git_repo / c.PYPROJECT_FILENAME).read_bytes()

        with pytest.raises(FileNotFoundError, match=f"root {missing_kind}"):
            self._conform_self(infra_git_repo)
        tm.that((infra_git_repo / c.PYPROJECT_FILENAME).read_bytes(), eq=before)
