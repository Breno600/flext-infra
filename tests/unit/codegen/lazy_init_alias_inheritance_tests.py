"""Facade-parent alias inheritance elects the nearest re-exporting parent."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from flext_tests import tm

from tests import c, u


class TestsFlextInfraLazyInitAliasInheritance:
    """A letter comes from the nearest parent whose published ABI exports it.

    Regression coverage for flext-b3xmn and flext-2rizg: the generated
    ``__init__`` of a parent is read as its published export list whether the
    parent is indexed (workspace) or installed (standalone CI), so both scopes
    render the same bytes. An unresolvable declared parent fails loud.
    """

    def test_generated_parent_retains_operational_result_alias_in_child(
        self, tmp_path: Path
    ) -> None:
        """A generated parent cannot erase a declared result needed at bootstrap."""
        repository, child = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-bootstrap-result",
            package_name="flext_bootstrap_child",
        )
        parent = repository / c.Infra.DEFAULT_SRC_DIR / "flext_bootstrap_parent"
        parent.mkdir()
        (parent / c.Infra.INIT_PY).write_text(
            c.Infra.AUTOGEN_HEADERS[0] + "\n__all__ = []\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        u.Tests.write_lazy_init_namespace_module(
            parent / "constants.py", class_name="BootstrapParentConstants", alias="c"
        )
        parent_constants = parent / c.Infra.CONSTANTS_PY
        parent_constants.write_text(
            parent_constants.read_text(encoding=c.Cli.ENCODING_DEFAULT)
            + "\nimport re\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (parent / "result.py").write_text(
            "from flext_core import FlextResult\nr = FlextResult\n"
            "__all__ = ['FlextResult', 'r']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (child / "constants.py").write_text(
            "from flext_bootstrap_parent import c as parent_c\n"
            "class BootstrapChildConstants(parent_c):\n    pass\n"
            "c = BootstrapChildConstants\n__all__ = ['BootstrapChildConstants', 'c']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (child / "consumer.py").write_text(
            "from flext_bootstrap_child import r\n"
            "def execute():\n    return r.ok('bootstrap-ready')\n"
            "__all__ = ['execute']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tm.that(u.Tests.run_lazy_init(repository), eq=0)
        first = (child / c.Infra.INIT_PY).read_bytes()
        tm.that(u.Tests.run_lazy_init(repository), eq=0)
        tm.that((child / c.Infra.INIT_PY).read_bytes(), eq=first)
        probe_env = dict(os.environ)
        probe_env["PYTHONPATH"] = os.pathsep.join([
            str(repository / c.Infra.DEFAULT_SRC_DIR),
            *sys.path,
        ])
        probe = (
            "from flext_bootstrap_child.consumer import execute\n"
            "import flext_bootstrap_child as generated\n"
            "from flext_core import r\n"
            "print(generated.r is r)\n"
            "print('r' in generated.__all__)\n"
            "print('compile' in generated.__all__)\n"
            "print(execute().value)\n"
        )
        result = tm.ok(
            u.Cli.run([sys.executable, "-c", probe], env=probe_env, cwd=repository)
        )
        tm.that(
            result.stdout.splitlines(), eq=["True", "True", "False", "bootstrap-ready"]
        )

    def test_child_inherits_exactly_the_indexed_parent_letters(
        self, tmp_path: Path
    ) -> None:
        """An indexed parent's exact alias set is what the child inherits."""
        repository_root, child_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-test-inherit",
            package_name="flext_test_inherit_child",
        )
        parent_root = (
            repository_root / c.Infra.DEFAULT_SRC_DIR / "flext_test_inherit_parent"
        )
        parent_root.mkdir(parents=True)
        parent_root.joinpath(c.Infra.INIT_PY).write_text(
            "", encoding=c.Infra.ENCODING_DEFAULT
        )
        u.Tests.write_lazy_init_namespace_module(
            parent_root / "constants_ns.py",
            class_name="FlextTestInheritParentConstantsNs",
            alias="c",
        )
        u.Tests.write_lazy_init_namespace_module(
            parent_root / "models_ns.py",
            class_name="FlextTestInheritParentModelsNs",
            alias="m",
        )
        u.Tests.write_lazy_init_namespace_module(
            parent_root / "protocols_ns.py",
            class_name="FlextTestInheritParentProtocolsNs",
            alias="p",
        )
        child_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "from flext_test_inherit_parent import c\n\n"
            "class FlextTestInheritChildConstants(c):\n"
            "    pass\n\n"
            '__all__: list[str] = ["FlextTestInheritChildConstants"]\n',
            encoding=c.Infra.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = child_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )

        tm.that(
            generated.splitlines(),
            has="    from flext_test_inherit_parent import c, m, p",
        )
        tm.that(generated, lacks="from flext_test_inherit_parent import c, m, p, ")

    def test_external_parent_letters_come_from_the_nearest_exporter(
        self, tmp_path: Path
    ) -> None:
        """The nearest parent re-exporting a letter is its source.

        ``flext_cli`` is not indexed here; its generated ``__init__`` re-exports
        ``r`` from ``flext_core``. The child inherits ``r`` through
        ``flext_cli``, the nearest facade that publishes it. The ``cli``
        singleton is not a facade letter and stays in ``flext_cli``.
        """
        repository_root, child_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-test-external",
            package_name="flext_test_external_child",
        )
        child_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "from flext_cli import c as cli_c\n\n"
            "class FlextTestExternalChildConstants(cli_c):\n"
            "    pass\n\n"
            "c = FlextTestExternalChildConstants\n"
            '__all__: list[str] = ["FlextTestExternalChildConstants", "c"]\n',
            encoding=c.Infra.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = child_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )
        entries, _refs = u.Infra.module_mapping_assignment_source(
            generated, u.Infra.lazy_imports_name_source(generated)
        )
        sources = dict(entries)

        tm.that(sources.get("flext_cli", ()), has="r")
        tm.that(sources.get("flext_cli", ()), lacks="cli")
        tm.that(sources.get("flext_core", ()), lacks="r")
        tm.that(u.Tests.run_lazy_init(repository_root, check_only=True), eq=0)

    def test_dependency_groups_and_entry_points_are_never_inherited(
        self, tmp_path: Path
    ) -> None:
        """Dev/codegen dependencies and non-letter names stay out of the root.

        A dev or codegen dependency is a consumer, never a facade ancestor, and
        singletons or entry points (``cli``, ``main``, ``infra``, ``docs_main``)
        are declared and consumed only from their own namespace root.
        """
        repository_root, child_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-test-groups",
            package_name="flext_test_groups_child",
        )
        pyproject = repository_root / c.PYPROJECT_FILENAME
        pyproject.write_text(
            pyproject.read_text(encoding=c.Infra.ENCODING_DEFAULT)
            + '\n[dependency-groups]\ncodegen = ["flext-infra"]\n'
            'dev = ["flext-tests"]\n',
            encoding=c.Infra.ENCODING_DEFAULT,
        )
        child_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "from flext_cli import c as cli_c\n\n"
            "class FlextTestGroupsChildConstants(cli_c):\n"
            "    pass\n\n"
            "c = FlextTestGroupsChildConstants\n"
            '__all__: list[str] = ["FlextTestGroupsChildConstants", "c"]\n',
            encoding=c.Infra.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = child_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )
        entries, _refs = u.Infra.module_mapping_assignment_source(
            generated, u.Infra.lazy_imports_name_source(generated)
        )
        sources = dict(entries)
        inherited = {name for names in sources.values() for name in names}

        tm.that(sources, lacks="flext_tests")
        tm.that(sources, lacks="flext_infra")
        tm.that(sources.get("flext_cli", ()), has="r")
        for entry_point in ("cli", "main", "infra", "docs_main"):
            tm.that(inherited, lacks=entry_point)
        tm.that(u.Tests.run_lazy_init(repository_root, check_only=True), eq=0)

    def test_declared_parent_resolving_nowhere_fails_loud(self, tmp_path: Path) -> None:
        """A declared parent that resolves nowhere in the environment is a typed failure."""
        repository_root, child_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-test-ghost",
            package_name="flext_test_ghost_child",
        )
        child_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "from flext_ghost_parent_zzz import c\n\n"
            "class FlextTestGhostChildConstants(c):\n"
            "    pass\n\n"
            '__all__: list[str] = ["FlextTestGhostChildConstants"]\n',
            encoding=c.Infra.ENCODING_DEFAULT,
        )

        planned = u.Tests.plan_lazy_init(repository_root)

        tm.that(planned.failure, eq=True)
        tm.that(
            planned.error,
            contains=(
                "lazy-init: declared facade parent 'flext_ghost_parent_zzz'"
                " resolves nowhere in the active environment"
            ),
        )
