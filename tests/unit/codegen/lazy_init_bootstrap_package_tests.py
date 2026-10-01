"""Tests that lazy-init never generates a bootstrap into its own import chain.

The bootstrap-owning distribution's initializers open with
``from flext_core.lazy import ...``. That module imports ``._lazy_parts`` at
module scope, which reaches ``._typings`` and the remaining private facets.
Writing a generated bootstrap into any of those packages therefore re-enters a
module that is still initializing and raises ``cannot import name
'build_lazy_import_map' from partially initialized module``. The private
surface of the bootstrap-owning distribution keeps side-effect-free
initializers; every other distribution imports the helpers from the
``flext_core`` root, which publishes them.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from flext_tests import tm

from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraLazyInitBootstrapPackage:
    """The bootstrap import chain is never generated into a cycle."""

    @staticmethod
    def _write_bootstrap_owner(package_root: Path, subpackage: str) -> Path:
        """Create a private facet of the bootstrap-owning distribution.

        Returns:
            The resulting ``Path``.

        """
        facet_dir = package_root / subpackage
        facet_dir.mkdir()
        (facet_dir / c.Infra.INIT_PY).write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        symbol_name = (
            f"Flext{subpackage.removeprefix('_').title().replace('_', '')}Part"
        )
        (facet_dir / "part.py").write_text(
            '"""Bootstrap implementation detail."""\n\n'
            f"class {symbol_name}:\n"
            '    """Bootstrap owner."""\n\n'
            f'__all__ = ["{symbol_name}"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        return facet_dir

    def test_bootstrap_owner_private_facets_stay_side_effect_free(
        self,
        tmp_path: Path,
    ) -> None:
        """Private facets of the bootstrap owner never import the bootstrap."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name=c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE.replace("_", "-"),
            package_name=c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE,
        )
        lazy_parts = self._write_bootstrap_owner(package_root, "_lazy_parts")
        typings = self._write_bootstrap_owner(package_root, "_typings")

        result = u.Tests.run_lazy_init(repository_root)

        tm.that(result, eq=0)
        for facet in (lazy_parts, typings):
            init_content = (facet / c.Infra.INIT_PY).read_text(
                encoding=c.Cli.ENCODING_DEFAULT,
            )
            tm.that(init_content, lacks=f"from {c.Infra.LAZY_BOOTSTRAP_MODULE} import")
            tm.that(init_content, lacks="install_lazy_exports")

    def test_generated_bootstrap_owner_facet_is_preserved_not_removed(
        self,
        tmp_path: Path,
    ) -> None:
        """A generated facet initializer stays a generated facet initializer.

        The generator OWNS files carrying the autogen header: it re-renders
        them to the canonical form and retires obsolete ones, and it never
        preserves a previous byte-for-byte body. What must hold for the
        bootstrap chain is observed here, per the runtime contract: the run
        succeeds, the facet survives as a package initializer, it remains
        codegen-owned, and it still imports nothing from the bootstrap.
        """
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name=c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE.replace("_", "-"),
            package_name=c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE,
        )
        lazy_parts = self._write_bootstrap_owner(package_root, "_lazy_parts")
        generated_stub = f'{c.Infra.AUTOGEN_HEADER}\n"""Lazy Parts package."""\n'
        init_path = lazy_parts / c.Infra.INIT_PY
        init_path.write_text(generated_stub, encoding=c.Cli.ENCODING_DEFAULT)

        result = u.Tests.run_lazy_init(repository_root)

        tm.that(result, eq=0)
        tm.that(init_path.is_file(), eq=True)
        rendered = init_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        tm.that(rendered.startswith(c.Infra.AUTOGEN_HEADER), eq=True)
        tm.that(rendered, lacks=f"from {c.Infra.LAZY_BOOTSTRAP_MODULE} import")
        tm.that(rendered, lacks="install_lazy_exports")

    def test_other_distributions_import_the_helpers_from_the_bootstrap_root(
        self,
        tmp_path: Path,
    ) -> None:
        """Packages outside the bootstrap owner import the published helpers."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        consumer_facet = self._write_bootstrap_owner(package_root, "_models")

        result = u.Tests.run_lazy_init(repository_root)

        init_content = (consumer_facet / c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tm.that(result, eq=0)
        tm.that(
            init_content,
            contains=(
                f"from {c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE} import "
                f"{', '.join(c.Infra.LAZY_BOOTSTRAP_HELPERS)}"
            ),
        )
        tm.that(init_content, lacks=f"from {c.Infra.LAZY_BOOTSTRAP_MODULE} import")
        tm.that(init_content, contains="FlextModelsPart")

    def test_bootstrap_root_publishes_the_helpers_it_owns(
        self,
        tmp_path: Path,
    ) -> None:
        """The bootstrap root imports its helpers directly and publishes them."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name=c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE.replace("_", "-"),
            package_name=c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE,
        )

        result = u.Tests.run_lazy_init(repository_root)

        root_init = (package_root / c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        published = next(
            ast.literal_eval(node.value)
            for node in ast.parse(root_init).body
            if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
            and node.value is not None
        )
        tm.that(result, eq=0)
        tm.that(root_init, contains=f"from {c.Infra.LAZY_BOOTSTRAP_MODULE} import")
        tm.that(set(c.Infra.LAZY_BOOTSTRAP_HELPERS) <= set(published), eq=True)
