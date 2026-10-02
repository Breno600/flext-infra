"""Public contract tests for canonical lazy-init artifact rendering.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

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
        eager_dunders: t.LazyAliasMap | None = None,
        child_packages: t.StrSequence = (),
    ) -> m.Infra.LazyInitPlan:
        """Build one validated render plan for a synthetic package path.

        Returns:
            The resulting ``m.Infra.LazyInitPlan``.

        """
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
            eager_dunders=MappingProxyType(dict(eager_dunders or {})),
            inline_constants=MappingProxyType({}),
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
            eager_dunders=MappingProxyType({
                "__version__": ("demo_pkg.__version__", "__version__"),
            }),
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
        tm.that(content, contains="from demo_pkg.__version__ import __version__\n")
        tm.that(
            content,
            contains='__all__: tuple[str, ...] = ("Demo", "__version__", "r")',
        )
        tm.that(content, contains="if TYPE_CHECKING:")
        tm.that(content, contains="    from demo_pkg.api import Demo")
        tm.that(content, contains="install_lazy_exports(")
        tm.that(content, lacks="__unit__")

    def test_export_width_is_a_real_formatter_fixed_point(self, tmp_path: Path) -> None:
        """The rendered tuple annotation owns the compact-line width budget."""
        names = ("FlextInfraCleanService", "FlextInfraPythonVersionEnforcer")
        plan = self._plan(
            "demo_pkg",
            names,
            {name: ("demo_pkg.owner", name) for name in names},
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

    def test_sibling_private_exports_import_their_absolute_owner(self) -> None:
        """The static import names the absolute owner; the lazy key stays compact."""
        plan = self._plan(
            "demo_pkg.servers._rfc",
            ("BaseConstants",),
            {"BaseConstants": ("demo_pkg.servers._base.constants", "BaseConstants")},
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(
            content,
            has="from demo_pkg.servers._base.constants import BaseConstants",
        )
        tm.that(content, has='".._base.constants": ("BaseConstants",)')
        tm.that(content, lacks="from .._base.constants import")

    @staticmethod
    def test_generated_runtime_surfaces_import_without_bootstrap_cycles() -> None:
        """Test generated runtime surfaces import without bootstrap cycles."""
        tm.that(flext_core.__all__, has="c")
        tm.that(dir(flext_core), has="c")
        tm.that(flext_core.c.__name__, eq="FlextConstants")
        tm.that(u.Infra.init_rope_project, none=False)

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
        self,
        owner: str,
        rendered_owner: str,
    ) -> None:
        """The static import names the absolute owner the compact lazy key resolves to."""
        package = "demo_pkg.servers._rfc"
        plan = self._plan(
            package,
            ("Demo",),
            MappingProxyType({"Demo": (owner, "Demo")}),
        )
        absolute_owner = resolve_name(owner, package)

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(content, contains=f"from {absolute_owner} import Demo")
        tm.that(content, contains=f'"{rendered_owner}": ("Demo",)')
        tm.that(resolve_name(rendered_owner, package), eq=absolute_owner)

    def test_root_initializer_contains_static_and_lazy_contracts(self) -> None:
        """Public root initializer keeps typing and runtime targets aligned."""
        plan = self._plan(
            "demo_pkg",
            ("Demo",),
            MappingProxyType({"Demo": ("demo_pkg.api", "Demo")}),
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(content, contains="if TYPE_CHECKING:")
        tm.that(content, contains="    from demo_pkg.api import Demo")
        runtime_prefix = content.split("if TYPE_CHECKING:", maxsplit=1)[0]
        tm.that(runtime_prefix, lacks="from demo_pkg.api import Demo")
        tm.that(content, contains='".api": ("Demo",)')
        tm.that(content, contains="install_lazy_exports(")
        tm.that(content, lacks="__unit__")

    def test_nested_package_initializer_is_static(self) -> None:
        """Test nested package initializer is static."""
        plan = self._plan(
            "flext_core._lazy_parts",
            ("FlextLazy",),
            MappingProxyType({
                "FlextLazy": ("flext_core._lazy_parts.flextlazy_part_02", "FlextLazy"),
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
        tm.that(
            content,
            lacks="from demo_pkg._utilities.conversion import DemoConversion",
        )
        tm.that(content, lacks="DemoConversion")
        tm.that(content, contains='__all__: tuple[str, ...] = ("Demo",)')

    def test_root_type_checking_imports_local_declarations_absolutely(self) -> None:
        """Emit local declarations as absolute public re-exports."""
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
        tm.that(
            content,
            contains="from flext_cli._settings import FlextCliSettings, settings",
        )
        tm.that(content, lacks="from ._settings import")
        tm.that(content, lacks="    _ = (")

    def test_public_nested_package_preserves_lazy_exports(self) -> None:
        """Test public nested package preserves lazy exports."""
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
        tm.that(
            init_content,
            contains=(
                f"from {c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE} import "
                f"{', '.join(c.Infra.LAZY_BOOTSTRAP_HELPERS)}"
            ),
        )
        tm.that(init_content, contains='__all__: tuple[str, ...] = ("Demo", "Nested")')
        tm.that(init_content, contains="install_lazy_exports")

    def test_private_fixture_package_initializer_is_side_effect_free(self) -> None:
        """Keep pytest plugin siblings unloaded until pytest registers them."""
        plan = self._plan(
            "demo_pkg._fixtures",
            ("DemoFixture",),
            MappingProxyType({
                "DemoFixture": ("demo_pkg._fixtures.settings", "DemoFixture"),
            }),
        )

        init_content = FlextInfraCodegenGeneration.render_init(plan)

        compile(init_content, "__init__.py", "exec")
        tm.that(
            init_content,
            contains="from demo_pkg._fixtures.settings import DemoFixture",
        )
        tm.that(init_content, contains='__all__: tuple[str, ...] = ("DemoFixture",)')
        tm.that(init_content, contains="install_lazy_exports")

    def test_lazy_bootstrap_package_initializer_is_side_effect_free(self) -> None:
        """Keep the lazy runtime importable while its implementation initializes."""
        plan = self._plan(
            "flext_core._lazy_parts",
            ("FlextLazy",),
            MappingProxyType({
                "FlextLazy": ("flext_core._lazy_parts.flextlazy_part_02", "FlextLazy"),
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
                "FlextTypesLazy": ("flext_core._typings.lazy", "FlextTypesLazy"),
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
            (
                f"from {c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE} import "
                f"{', '.join(c.Infra.LAZY_BOOTSTRAP_HELPERS)}\n"
            ),
            maxsplit=1,
        )[1]
        import_block = import_block.split("install_lazy_exports(", maxsplit=1)[0]
        module_offsets = tuple(
            import_block.index(module)
            for module in (
                "from flext_tests import tm",
                "from tests.base import",
                "from tests.constants import",
                "from tests.models import",
                "from tests.protocols import",
                "from tests.settings import",
                "from tests.typings import",
                "from tests.utilities import",
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

    def test_root_type_checking_imports_the_declared_letter(self) -> None:
        """Static imports name the letter the facade module declares."""
        plan = self._plan(
            "demo_pkg",
            ("FlextDemoProtocols", "p"),
            MappingProxyType({
                "FlextDemoProtocols": ("demo_pkg.protocols", "FlextDemoProtocols"),
                "p": ("demo_pkg.protocols", "p"),
            }),
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(
            content,
            contains="from demo_pkg.protocols import FlextDemoProtocols, p",
        )
        tm.that(content, lacks="FlextDemoProtocols as p")

    def test_root_service_letter_is_the_declared_service_letter(self) -> None:
        """The service letter is imported as the base module declares it."""
        plan = self._plan(
            "demo_pkg",
            ("FlextDemoServiceBase", "s"),
            MappingProxyType({
                "FlextDemoServiceBase": ("demo_pkg.base", "FlextDemoServiceBase"),
                "s": ("demo_pkg.base", "s"),
            }),
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        compile(content, "__init__.py", "exec")
        tm.that(content, contains="from demo_pkg.base import FlextDemoServiceBase, s")
        tm.that(content, lacks="FlextDemoServiceBase as s")

    @staticmethod
    def test_type_checking_renderer_keeps_declared_letters() -> None:
        """Static imports keep each letter under the name its module declares."""
        lines = FlextInfraCodegenGeneration.generate_type_checking({
            "module": [("c", "c"), ("m", "m")],
        })

        tm.that(
            "\n".join(lines),
            contains=(
                "if TYPE_CHECKING:\n"
                "    from flext_core import FlextTypes\n"
                "    from module import c, m"
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

    @pytest.mark.parametrize(
        "isort_table",
        ["", "[tool.ruff.lint.isort]\nknown-first-party = []\n"],
    )
    def test_project_package_name_reads_manifest_not_directory_name(
        self,
        tmp_path: Path,
        isort_table: str,
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
        (project_root / c.PYPROJECT_FILENAME).write_text(
            f'[project]\nname = "demo-worktree-pkg"\nversion = "1.0.0"\nauthors = [{{ name = "Fixture Author" }}]\n{isort_table}',
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
            eager_dunders=MappingProxyType({}),
            inline_constants=MappingProxyType({}),
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

    @pytest.mark.parametrize("declared_empty", [False, True])
    def test_empty_first_party_policy_does_not_discover_extra_namespaces(
        self,
        tmp_path: Path,
        *,
        declared_empty: bool,
    ) -> None:
        """An explicit empty list and an absent table remain distinct inputs."""
        additional = tmp_path / "src" / "fixture_extra_namespace"
        additional.mkdir(parents=True)
        (additional / c.Infra.INIT_PY).write_text("", encoding="utf-8")
        wrapper = tmp_path / "examples"
        wrapper.mkdir()
        table = (
            "[tool.ruff.lint.isort]\nknown-first-party = []\n" if declared_empty else ""
        )
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            f'[project]\nname = "configured-workspace"\nversion = "1.0.0"\nauthors = [{{ name = "Fixture Author" }}]\n{table}',
            encoding="utf-8",
        )
        plan = self._plan(
            "examples",
            ("extra", "external"),
            MappingProxyType({
                "extra": ("fixture_extra_namespace", "value"),
                "external": ("zz_external_fixture", "value"),
            }),
        )
        plan = plan.model_copy(
            update={
                "context": plan.context.model_copy(
                    update={"pkg_dir": wrapper, "init_path": wrapper / c.Infra.INIT_PY},
                ),
            },
        )
        rendered = FlextInfraCodegenGeneration.render_init(plan)
        expected = (
            "    from fixture_extra_namespace import value as extra\n"
            "    from zz_external_fixture import value as external\n"
            if declared_empty
            else (
                "    from zz_external_fixture import value as external\n\n"
                "    from fixture_extra_namespace import value as extra\n"
            )
        )
        tm.that(rendered, has=expected)

    @pytest.mark.parametrize("projected", ['"namespace"', '["valid", 3]', "false"])
    def test_malformed_first_party_names_fail_at_the_render_boundary(
        self,
        tmp_path: Path,
        projected: str,
    ) -> None:
        """Invalid Ruff configuration cannot become a derived namespace list."""
        package = tmp_path / "src" / "sample"
        package.mkdir(parents=True)
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "sample"\nversion = "1.0.0"\n'
            f"[tool.ruff.lint.isort]\nknown-first-party = {projected}\n",
            encoding="utf-8",
        )
        plan = self._plan("sample", (), MappingProxyType({}))
        plan = plan.model_copy(
            update={
                "context": plan.context.model_copy(
                    update={"pkg_dir": package, "init_path": package / c.Infra.INIT_PY},
                ),
            },
        )

        with pytest.raises(m.ValidationError):
            FlextInfraCodegenGeneration.render_init(plan)

    def test_runtime_imports_are_one_isort_section_with_the_lazy_helpers(
        self,
    ) -> None:
        """The helpers import sorts inside the first-party block it belongs to.

        In the bootstrap root the helpers live in a sibling module of the
        ``__version__`` import; both are first-party, so Ruff isort keeps them
        in one block ordered by module. A separate helpers block was rewritten
        by ``make fix`` after every ``make gen``.
        """
        root = c.Infra.LAZY_BOOTSTRAP_ROOT_PACKAGE
        plan = self._plan(
            root,
            ("FlextLazy", "__version__"),
            MappingProxyType({
                "FlextLazy": (c.Infra.LAZY_BOOTSTRAP_MODULE, "FlextLazy"),
            }),
            eager_dunders=MappingProxyType({
                "__version__": (f"{root}.__version__", "__version__"),
            }),
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        helpers = ", ".join(c.Infra.LAZY_BOOTSTRAP_HELPERS)
        tm.that(
            content,
            contains=(
                f"from {root}.__version__ import __version__\n"
                f"from {c.Infra.LAZY_BOOTSTRAP_MODULE} import {helpers}\n"
            ),
        )

    def test_expanded_single_entry_mapping_keeps_its_trailing_comma(self) -> None:
        """An exploded one-entry mapping carries the comma COM812 requires.

        The entry fits one line while the inline mapping does not, which is
        the shape whose comma-less rendering ``make fix`` rewrote.
        """
        plan = self._plan(
            "demo_pkg",
            ("FlextDemoGeneratedFacade",),
            MappingProxyType({
                "FlextDemoGeneratedFacade": (
                    "demo_pkg._generated_parts.facade_part_04",
                    "FlextDemoGeneratedFacade",
                ),
            }),
        )

        content = FlextInfraCodegenGeneration.render_init(plan)

        tm.that(content, contains='("FlextDemoGeneratedFacade",),\n        }),')
