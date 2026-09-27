"""Public contract tests for canonical lazy-init artifact rendering."""

from __future__ import annotations

from importlib import import_module
from importlib.util import resolve_name
from pathlib import Path
from types import MappingProxyType

import pytest
from flext_tests import tm

import flext_core
from flext_infra import c, m, t, u
from flext_infra.codegen.codegen_generation import FlextInfraCodegenGeneration


class TestsFlextInfraCodegenGeneration:
    """Validate observable generated Python artifacts without legacy internals."""

    @staticmethod
    def _plan(
        current_pkg: str,
        exports: t.StrSequence,
        lazy_map: t.LazyAliasMap,
        *,
        eager_dunders: t.MappingKV[str, t.StrPair] | None = None,
        child_packages: t.StrSequence = (),
        type_checking_map: t.LazyAliasMap | None = None,
    ) -> m.Infra.LazyInitPlan:
        """Build one validated render plan for a synthetic package path."""
        package_dir = Path.cwd() / current_pkg.replace(".", "/")
        return m.Infra.LazyInitPlan(
            context=m.Infra.LazyInitPackageContext(
                pkg_dir=package_dir,
                init_path=package_dir / c.Infra.INIT_PY,
                current_pkg=current_pkg,
                surface=current_pkg.split(".", maxsplit=1)[0],
                importable=True,
            ),
            action=c.Infra.LazyInitAction.WRITE,
            exports=exports,
            lazy_map=MappingProxyType(dict(lazy_map)),
            type_checking_map=MappingProxyType(
                dict(lazy_map if type_checking_map is None else type_checking_map)
            ),
            eager_dunders=MappingProxyType(dict(eager_dunders or {})),
            child_packages_for_lazy=child_packages,
            excluded_lazy_names=("internal_only",),
        )

    def test_root_initializer_is_the_lazy_ssot(self) -> None:
        """Public roots render one importable initializer with a literal ABI."""
        plan = self._plan(
            "demo_pkg",
            ("Demo", "r", "__version__"),
            MappingProxyType({
                "Demo": ("demo_pkg.api", "Demo"),
                "r": ("flext_core", "r"),
            }),
            eager_dunders={"__version__": ("demo_pkg.__version__", "__version__")},
            child_packages=("demo_pkg.services",),
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(content, lacks="_LAZY_MODULES")
        tm.that(content, lacks="_LAZY_ALIAS_GROUPS")
        # _LAZY_IMPORTS is the canonical metadata binding flext_core reads
        # (lazy.merge child inheritance + runtime_alias_names).
        tm.that(content, contains="_LAZY_IMPORTS = MappingProxyType(")
        tm.that(content, contains="MappingProxyType(")
        tm.that(content, contains="build_lazy_import_map(")
        tm.that(content, contains='".api": ("Demo",)')
        tm.that(content, contains="from .__version__ import __version__ as __version__")
        tm.that(
            content, contains='__all__: tuple[str, ...] = ("Demo", "__version__", "r")'
        )
        tm.that(content, contains="if TYPE_CHECKING:")
        tm.that(content, contains="    from .api import Demo")
        tm.that(content, contains="install_lazy_exports(")
        tm.that(content, lacks="__unit__")

    def test_export_width_is_a_real_formatter_fixed_point(self, tmp_path: Path) -> None:
        """The rendered tuple annotation owns the compact-line width budget."""
        names = ("FlextInfraCleanService", "FlextInfraPythonVersionEnforcer")
        plan = self._plan(
            "demo_pkg", names, {name: ("demo_pkg.owner", name) for name in names}
        )
        rendered = FlextInfraCodegenGeneration.render_init(plan)
        target = tmp_path / "__init__.py"
        target.write_text(rendered, encoding="utf-8")
        formatted = u.Cli.run([
            "ruff",
            "format",
            "--config",
            str(Path.cwd() / "pyproject.toml"),
            str(target),
        ])
        assert formatted.success, formatted.error
        assert target.read_text(encoding="utf-8") == rendered

    def test_sibling_private_exports_use_relative_owners(self) -> None:
        """Static and lazy imports resolve the same private sibling module."""
        plan = self._plan(
            "demo_pkg.servers._rfc",
            ("BaseConstants",),
            {"BaseConstants": ("demo_pkg.servers._base.constants", "BaseConstants")},
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(content, has="from .._base.constants import BaseConstants")
        tm.that(content, has='".._base.constants": ("BaseConstants",)')
        tm.that(content, lacks="from demo_pkg.servers._base.constants import")

    def test_generated_runtime_surfaces_import_without_bootstrap_cycles(self) -> None:
        lazy_parts = import_module("flext_core._lazy_parts")
        typings = import_module("flext_core._typings")
        infra_utilities = import_module("flext_infra._utilities")

        tm.that(lazy_parts.__all__, eq=())
        tm.that(typings.__all__, eq=())
        tm.that(flext_core.__all__, has="c")
        tm.that(dir(flext_core), has="c")
        tm.that(flext_core.c.__name__, eq="FlextConstants")
        tm.that(
            infra_utilities.FlextInfraUtilitiesRopeCore.__name__,
            eq="FlextInfraUtilitiesRopeCore",
        )

    @pytest.mark.parametrize(
        ("owner", "rendered_owner"),
        [
            ("demo_pkg.servers._base.constants", ".._base.constants"),
            ("demo_pkg._shared.constants", "..._shared.constants"),
            ("demo_pkg.servers", ".."),
            ("demo_pkg", "..."),
            ("demo_pkg.servers._rfc", "."),
            ("demo_pkg.servers._rfc.constants", ".constants"),
            (".._base.constants", ".._base.constants"),
            ("upstream_pkg.constants", "upstream_pkg.constants"),
        ],
    )
    def test_generated_imports_preserve_owner_resolution(
        self, owner: str, rendered_owner: str
    ) -> None:
        """Static imports and lazy targets resolve to the same declared owner."""
        package = "demo_pkg.servers._rfc"
        plan = self._plan(
            package, ("Demo",), MappingProxyType({"Demo": (owner, "Demo")})
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(content, contains=f"from {rendered_owner} import Demo")
        tm.that(content, contains=f'"{rendered_owner}": ("Demo",)')
        tm.that(resolve_name(rendered_owner, package), eq=resolve_name(owner, package))

    def test_root_initializer_contains_static_and_lazy_contracts(self) -> None:
        """Public root initializer keeps typing and runtime targets aligned."""
        plan = self._plan(
            "demo_pkg", ("Demo",), MappingProxyType({"Demo": ("demo_pkg.api", "Demo")})
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(content, contains="if TYPE_CHECKING:")
        tm.that(content, contains="    from .api import Demo")
        runtime_prefix = content.split("if TYPE_CHECKING:", maxsplit=1)[0]
        tm.that(runtime_prefix, lacks="from .api import Demo")
        tm.that(content, contains='".api": ("Demo",)')
        tm.that(content, contains="install_lazy_exports(")
        tm.that(content, lacks="__unit__")

    def test_nested_package_initializer_is_static(self) -> None:
        plan = self._plan(
            "flext_core._lazy_parts",
            ("FlextLazy",),
            MappingProxyType({
                "FlextLazy": ("flext_core._lazy_parts.flextlazy_part_02", "FlextLazy")
            }),
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(content, lacks="from flext_core.lazy import")
        tm.that(content, contains="__all__: tuple[str, ...] = ()")

    def test_root_initializer_rejects_private_entries_outside_all(self) -> None:
        """Render no package attribute that is absent from the public contract."""
        plan = self._plan(
            "demo_pkg",
            ("Demo",),
            MappingProxyType({
                "Demo": ("demo_pkg.api", "Demo"),
                "DemoConversion": ("demo_pkg._utilities.conversion", "DemoConversion"),
            }),
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(content, lacks="from ._utilities.conversion import DemoConversion")
        tm.that(content, lacks="DemoConversion")
        tm.that(content, contains='__all__: tuple[str, ...] = ("Demo",)')

    def test_root_type_checking_uses_compact_relative_local_imports(self) -> None:
        """Emit relative declarations as explicit public re-exports."""
        plan = self._plan(
            "flext_cli",
            ("FlextCliSettings", "settings"),
            MappingProxyType({
                "FlextCliSettings": ("flext_cli._settings", "FlextCliSettings"),
                "settings": ("flext_cli._settings", "settings"),
            }),
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(content, contains="from ._settings import FlextCliSettings, settings")
        tm.that(content, lacks="from flext_cli._settings import")
        tm.that(content, lacks="    _ = (")

    def test_public_nested_package_preserves_lazy_exports(self) -> None:
        plan = self._plan(
            "demo_pkg.services",
            ("Demo", "Nested"),
            MappingProxyType({
                "Demo": ("demo_pkg.services.demo", "Demo"),
                "Nested": ("demo_pkg.services.nested.item", "Nested"),
            }),
        )

        init_content = FlextInfraCodegenGeneration.render_init(plan)

        compile(init_content, "__init__.py", "exec")
        tm.that(init_content, contains="from flext_core.lazy import")
        tm.that(init_content, contains='__all__: tuple[str, ...] = ("Demo", "Nested")')
        tm.that(init_content, contains="install_lazy_exports")

    def test_private_fixture_package_initializer_is_side_effect_free(self) -> None:
        """Keep pytest plugin siblings unloaded until pytest registers them."""
        plan = self._plan(
            "demo_pkg._fixtures",
            ("DemoFixture",),
            MappingProxyType({
                "DemoFixture": ("demo_pkg._fixtures.settings", "DemoFixture")
            }),
        )

        init_content = FlextInfraCodegenGeneration.render_init(plan)

        compile(init_content, "__init__.py", "exec")
        tm.that(init_content, contains="from .settings import DemoFixture")
        tm.that(init_content, contains='__all__: tuple[str, ...] = ("DemoFixture",)')
        tm.that(init_content, contains="install_lazy_exports")

    def test_lazy_bootstrap_package_initializer_is_side_effect_free(self) -> None:
        """Keep the lazy runtime importable while its implementation initializes."""
        plan = self._plan(
            "flext_core._lazy_parts",
            ("FlextLazy",),
            MappingProxyType({
                "FlextLazy": ("flext_core._lazy_parts.flextlazy_part_02", "FlextLazy")
            }),
        )

        init_content = FlextInfraCodegenGeneration.render_init(plan)

        compile(init_content, "__init__.py", "exec")
        tm.that(init_content, contains="__all__: tuple[str, ...] = ()")
        tm.that(init_content, lacks="from flext_core.lazy import")
        tm.that(init_content, lacks="install_lazy_exports")

    def test_lazy_typings_bootstrap_initializer_is_side_effect_free(self) -> None:
        """Keep the lazy runtime's typing dependency free of import callbacks."""
        plan = self._plan(
            "flext_core._typings",
            ("FlextTypesLazy",),
            MappingProxyType({
                "FlextTypesLazy": ("flext_core._typings.lazy", "FlextTypesLazy")
            }),
        )

        init_content = FlextInfraCodegenGeneration.render_init(plan)

        compile(init_content, "__init__.py", "exec")
        tm.that(init_content, contains="__all__: tuple[str, ...] = ()")
        tm.that(init_content, lacks="from flext_core.lazy import")
        tm.that(init_content, lacks="install_lazy_exports")

    def test_normal_package_initializer_keeps_full_lazy_map(self) -> None:
        """Keep ordinary package boundaries backed by the lazy runtime."""
        plan = self._plan(
            "flext_core._models",
            ("FlextModel",),
            MappingProxyType({"FlextModel": ("flext_core._models.base", "FlextModel")}),
        )

        init_content = FlextInfraCodegenGeneration.render_init(plan)

        compile(init_content, "__init__.py", "exec")
        tm.that(init_content, contains="from flext_core.lazy import")
        tm.that(init_content, contains='".base": ("FlextModel",)')
        tm.that(init_content, contains="install_lazy_exports(")

    def test_tests_root_renders_only_its_facade_contract(self) -> None:
        """Render test facades without importing collected test classes."""
        plan = self._plan(
            "tests",
            (
                "TestsDemoConstants",
                "TestsDemoModels",
                "TestsDemoProtocols",
                "TestsDemoServiceBase",
                "TestsDemoSettings",
                "TestsDemoTypes",
                "TestsDemoUtilities",
                "c",
                "m",
                "p",
                "s",
                "t",
                "tm",
                "u",
            ),
            MappingProxyType({
                "TestsDemoCase": ("tests.unit.test_demo", "TestsDemoCase"),
                "TestsDemoConstants": ("tests.constants", "TestsDemoConstants"),
                "TestsDemoModels": ("tests.models", "TestsDemoModels"),
                "TestsDemoProtocols": ("tests.protocols", "TestsDemoProtocols"),
                "TestsDemoServiceBase": ("tests.base", "TestsDemoServiceBase"),
                "TestsDemoSettings": ("tests.settings", "TestsDemoSettings"),
                "TestsDemoTypes": ("tests.typings", "TestsDemoTypes"),
                "TestsDemoUtilities": ("tests.utilities", "TestsDemoUtilities"),
                "c": ("tests.constants", "c"),
                "m": ("tests.models", "m"),
                "p": ("tests.protocols", "p"),
                "s": ("tests.base", "s"),
                "t": ("tests.typings", "t"),
                "tm": ("flext_tests", "tm"),
                "u": ("tests.utilities", "u"),
            }),
        )

        init_content = FlextInfraCodegenGeneration.render_init(plan)

        compile(init_content, "__init__.py", "exec")
        tm.that(init_content, contains="from flext_tests import tm")
        tm.that(init_content, contains='".constants": ("TestsDemoConstants", "c"),')
        tm.that(init_content, contains='".utilities": ("TestsDemoUtilities", "u"),')
        import_block = init_content.split(
            "from flext_core.lazy import build_lazy_import_map, install_lazy_exports\n",
            maxsplit=1,
        )[1]
        import_block = import_block.split("install_lazy_exports(", maxsplit=1)[0]
        module_offsets = tuple(
            import_block.index(module)
            for module in (
                "from flext_tests import tm",
                "from .base import",
                "from .constants import",
                "from .models import",
                "from .protocols import",
                "from .settings import",
                "from .typings import",
                "from .utilities import",
            )
        )
        tm.that(module_offsets, eq=tuple(sorted(module_offsets)))
        tm.that(import_block, contains="from flext_tests import tm\n")
        tm.that(init_content, contains="if TYPE_CHECKING:")
        tm.that(init_content, contains="install_lazy_exports")
        tm.that(init_content, lacks="TestsDemoCase")
        tm.that(init_content, lacks=".unit.test_demo")
        tm.that(init_content, lacks="TestsDemoCase")
        tm.that(init_content, lacks=".unit.test_demo")

    def test_root_type_checking_alias_uses_named_local_facade(self) -> None:
        """Static analyzers receive the local facade class behind short aliases."""
        plan = self._plan(
            "demo_pkg",
            ("FlextDemoProtocols", "p"),
            MappingProxyType({
                "FlextDemoProtocols": ("demo_pkg.protocols", "FlextDemoProtocols"),
                "p": ("demo_pkg.protocols", "p"),
            }),
            type_checking_map={
                "FlextDemoProtocols": ("demo_pkg.protocols", "FlextDemoProtocols"),
                "p": ("demo_pkg.protocols", "FlextDemoProtocols"),
            },
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(
            content,
            contains="from .protocols import FlextDemoProtocols, FlextDemoProtocols as p",
        )
        tm.that(content, contains="FlextDemoProtocols as p")

    def test_root_service_alias_uses_typed_service_base(self) -> None:
        """Bind ``s`` to the concrete project service base for static analysis."""
        plan = self._plan(
            "demo_pkg",
            ("FlextDemoServiceBase", "s"),
            MappingProxyType({
                "FlextDemoServiceBase": ("demo_pkg.base", "FlextDemoServiceBase"),
                "s": ("demo_pkg.base", "s"),
            }),
            type_checking_map={
                "FlextDemoServiceBase": ("demo_pkg.base", "FlextDemoServiceBase"),
                "s": ("demo_pkg.base", "FlextDemoServiceBase"),
            },
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(
            content,
            contains="from .base import FlextDemoServiceBase, FlextDemoServiceBase as s",
        )
        tm.that(content, contains="FlextDemoServiceBase as s")

    def test_type_checking_renderer_keeps_explicit_aliases(self) -> None:
        """Static imports bind aliases to their facade types explicitly."""
        lines = FlextInfraCodegenGeneration.generate_type_checking({
            "module": [("c", "FlextConstants"), ("m", "FlextModels")]
        })

        tm.that(
            "\n".join(lines),
            contains=(
                "if TYPE_CHECKING:\n"
                "    from flext_core import FlextTypes\n"
                "    from module import FlextConstants as c, FlextModels as m"
            ),
        )

    def test_root_type_checking_sections_follow_known_first_party_policy(self) -> None:
        """Base first-party namespaces render in the ruff first-party section.

        The generated TYPE_CHECKING block must mirror the project's ruff isort
        sections. The config-owned base namespace (flext_core, the declared
        upstream) is first-party, so it is separated from a third-party
        absolute import by the blank line ruff requires (I001).
        """
        plan = self._plan(
            "demo_pkg",
            ("cli_c", "core_d"),
            MappingProxyType({
                "cli_c": ("flext_cli", "c"),
                "core_d": ("flext_core", "d"),
            }),
        )

        init_content = FlextInfraCodegenGeneration.render_init(plan)

        compile(init_content, "__init__.py", "exec")
        tm.that(
            init_content,
            contains=(
                "if TYPE_CHECKING:\n"
                "    from flext_cli import c as cli_c\n"
                "\n"
                "    from flext_core import d as core_d\n"
            ),
        )

    def test_root_type_checking_keeps_the_project_package_first_party(self) -> None:
        """Roots outside the source tree import the project package first-party.

        ``examples``/``scripts`` initializers import the distribution package
        absolutely, and the project's known-first-party lists it, so it must
        share its section instead of gaining a spurious blank line.
        """
        plan = self._plan(
            "demo_root",
            ("cli_c", "core_d", "project_p"),
            MappingProxyType({
                "cli_c": ("flext_cli", "c"),
                "core_d": ("flext_core", "d"),
                "project_p": ("flext_infra", "p"),
            }),
        )

        init_content = FlextInfraCodegenGeneration.render_init(plan)

        compile(init_content, "__init__.py", "exec")
        tm.that(
            init_content,
            contains=(
                "if TYPE_CHECKING:\n"
                "    from flext_cli import c as cli_c\n"
                "\n"
                "    from flext_core import d as core_d\n"
                "    from flext_infra import p as project_p\n"
            ),
        )

    def test_project_package_name_reads_manifest_not_directory_name(
        self, tmp_path: Path
    ) -> None:
        """Worktree checkouts keep the manifest's package name.

        A project root directory named after a git branch (``0.12.0-dev``)
        must not leak into isort sectioning: the distribution package is
        declared by the manifest, never proxied from the directory name,
        so a wrapper root renders the project import in the first-party
        section below the third-party block.
        """
        project_root = tmp_path / "0.12.0-dev"
        wrapper_root = project_root / "examples"
        wrapper_root.mkdir(parents=True)
        (project_root / c.Infra.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "demo-worktree-pkg"\nversion = "1.0.0"\n',
            encoding="utf-8",
        )
        plan = m.Infra.LazyInitPlan(
            context=m.Infra.LazyInitPackageContext(
                pkg_dir=wrapper_root,
                init_path=wrapper_root / c.Infra.INIT_PY,
                current_pkg="examples",
                surface="examples",
                importable=True,
            ),
            action=c.Infra.LazyInitAction.WRITE,
            exports=("cli_c", "project_p"),
            lazy_map=MappingProxyType({
                "cli_c": ("flext_cli", "c"),
                "project_p": ("demo_worktree_pkg", "p"),
            }),
            type_checking_map=MappingProxyType({
                "cli_c": ("flext_cli", "c"),
                "project_p": ("demo_worktree_pkg", "p"),
            }),
            eager_dunders=MappingProxyType({}),
            child_packages_for_lazy=(),
            excluded_lazy_names=("internal_only",),
        )

        init_content = FlextInfraCodegenGeneration.render_init(plan)

        compile(init_content, "__init__.py", "exec")
        tm.that(
            init_content,
            contains=(
                "if TYPE_CHECKING:\n"
                "    from flext_cli import c as cli_c\n"
                "\n"
                "    from demo_worktree_pkg import p as project_p\n"
            ),
        )


__all__: list[str] = ["TestsFlextInfraCodegenGeneration"]
