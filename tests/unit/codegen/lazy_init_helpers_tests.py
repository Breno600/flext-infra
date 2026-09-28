"""Behavior tests for public lazy-init generation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, t, u


class TestsFlextInfraLazyInitHelpers:
    """Validate lazy-init through the public service surface only."""

    @staticmethod
    def _workspace(tmp_path: Path) -> t.Pair[Path, Path]:
        workspace: t.Pair[Path, Path] = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        return workspace

    @staticmethod
    def _generated_init(package_root: Path) -> str:
        return package_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )

    def test_discover_package_from_standard_roots(self) -> None:
        """Resolve package names consistently for every supported source shape."""
        tm.that(
            u.Infra.package_name(Path("/workspace/src/test_pkg/__init__.py")),
            eq="test_pkg",
        )
        tm.that(
            u.Infra.package_name(Path("/workspace/tests/unit/__init__.py")),
            eq="tests.unit",
        )
        tm.that(
            u.Infra.package_name(Path("/workspace/examples/tests/__init__.py")),
            eq="examples.tests",
        )

    def test_root_generation_uses_real_classes_and_aliases(
        self, tmp_path: Path
    ) -> None:
        """Publish real root declarations through the inline lazy contract."""
        repository_root, package_root = self._workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py",
            class_name="FlextDemoModels",
            alias="m",
            docstring="Models.",
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        init_content = self._generated_init(package_root)
        exports_content = self._generated_init(package_root)

        tm.that(init_content, has="build_lazy_import_map, install_lazy_exports")
        # _LAZY_IMPORTS is the canonical metadata binding flext_core reads.
        tm.that(init_content, has="_LAZY_IMPORTS = MappingProxyType(")
        tm.that(exports_content, has='"FlextDemoModels"')
        tm.that(exports_content, has='"m"')

    def test_non_flext_root_replaces_manual_initializer_with_generated_contract(
        self, tmp_path: Path
    ) -> None:
        """Generate every governed src root regardless of its package prefix."""
        # External consumers such as ai_hub are
        # first-class FLEXT packages; prefix-specific planning created dual truth.
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="ai-hub", package_name="ai_hub"
        )
        package_root.joinpath(c.Infra.INIT_PY).write_text(
            '"""Stale manual initializer."""\n', encoding=c.Cli.ENCODING_DEFAULT
        )
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py",
            class_name="AiHubModels",
            alias="m",
            docstring="AI Hub models.",
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = self._generated_init(package_root)

        tm.that(generated, has="AUTO-GENERATED FILE")
        tm.that(generated, has='"AiHubModels"')
        tm.that(generated, has='"m"')
        tm.that(generated, lacks="Stale manual initializer")

    def test_private_modules_do_not_export_from_root(self, tmp_path: Path) -> None:
        """Keep private sibling modules outside the public package contract."""
        repository_root, package_root = self._workspace(tmp_path)
        (package_root / "_internal.py").write_text(
            "from __future__ import annotations\n\nclass FlextDemoInternal:\n    pass\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        tm.that(self._generated_init(package_root), lacks="FlextDemoInternal")

    def test_root_regeneration_preserves_declared_abi_only(
        self, tmp_path: Path
    ) -> None:
        """Keep module-local public helpers outside the package-root ABI."""
        repository_root, package_root = self._workspace(tmp_path)
        package_root.joinpath(c.Infra.INIT_PY).write_text(
            '__all__: tuple[str, ...] = ("FlextDemoConstants", "FlextDemoLazy", "c")\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        package_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "class FlextDemoConstants:\n"
            '    """Canonical constants facade."""\n\n'
            "class FlextDemoConstantsEnforcement:\n"
            '    """Module-local composition class."""\n\n'
            "c = FlextDemoConstants\n\n"
            '__all__ = ("FlextDemoConstants", '
            '"FlextDemoConstantsEnforcement", "c")\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        package_root.joinpath("lazy.py").write_text(
            "class FlextDemoLazy:\n"
            '    """Canonical lazy facade."""\n\n'
            "class FlextDemoLazyAttribute:\n"
            '    """Module-local implementation type."""\n\n'
            "def lazy_attribute() -> None:\n"
            '    """Module-local helper."""\n\n'
            '__all__ = ("FlextDemoLazy", "FlextDemoLazyAttribute", '
            '"lazy_attribute")\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = self._generated_init(package_root)
        has_all, exports = u.Tests.extract_lazy_init_exports(generated)

        tm.that(has_all, eq=True)
        tm.that(exports, eq=("FlextDemoConstants", "FlextDemoLazy", "c"))
        tm.that(generated, lacks="FlextDemoConstantsEnforcement")
        tm.that(generated, lacks="FlextDemoLazyAttribute")
        tm.that(generated, lacks="lazy_attribute")

    def test_root_regeneration_prunes_contract_name_without_owner(
        self, tmp_path: Path
    ) -> None:
        """Remove stale projected names that have no current source owner."""
        repository_root, package_root = self._workspace(tmp_path)
        declared_contract = (
            '__all__: tuple[str, ...] = ("FlextDemoModels", "FlextDemoMissing", "m")\n'
        )
        package_root.joinpath(c.Infra.INIT_PY).write_text(
            declared_contract, encoding=c.Cli.ENCODING_DEFAULT
        )
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextDemoModels", alias="m"
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = self._generated_init(package_root)

        # The prior projection is never an ABI
        # owner; regeneration converges it to declarations that still exist.
        tm.that(generated, has='"FlextDemoModels"')
        tm.that(generated, has='"m"')
        tm.that(generated, lacks="FlextDemoMissing")
        tm.that(generated, ne=declared_contract)

    def test_private_child_packages_do_not_widen_root_api(self, tmp_path: Path) -> None:
        """Keep private child declarations outside the public root contract."""
        repository_root, package_root = self._workspace(tmp_path)
        child_dir = package_root / "_enforcement"
        child_dir.mkdir()
        (child_dir / c.Infra.INIT_PY).write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        (child_dir / "engine.py").write_text(
            "class FlextDemoEnforcementEngine:\n"
            '    """Internal engine."""\n\n'
            '__all__ = ["FlextDemoEnforcementEngine"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        exports_content = self._generated_init(package_root)
        public_exports = exports_content.split(
            "__all__: tuple[str, ...] =", maxsplit=1
        )[1]

        # Private child classes never become root ABI.
        tm.that(exports_content, lacks="FlextDemoEnforcementEngine")
        tm.that(public_exports, lacks="FlextDemoEnforcementEngine")
        tm.that(public_exports, lacks='"_enforcement"')

    def test_regeneration_prunes_stale_private_direct_imports(
        self, tmp_path: Path
    ) -> None:
        """Derive root attributes from public facades, never a stale init literal."""
        repository_root, package_root = self._workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextDemoModels", alias="m"
        )
        utilities_dir = package_root / "_utilities"
        utilities_dir.mkdir()
        utilities_dir.joinpath(c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        conversion_path = utilities_dir / "conversion.py"
        conversion_path.write_text(
            "class FlextDemoConversion:\n"
            '    """Supported direct root import."""\n\n'
            '__all__ = ["FlextDemoConversion"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = self._generated_init(package_root)
        tm.that(generated, lacks="_DIRECT_IMPORTS")
        tm.that(generated, lacks="FlextDemoConversion")

        extra_path = utilities_dir / "extra.py"
        extra_path.write_text(
            "class FlextDemoExtra:\n"
            '    """New internal name outside the frozen contract."""\n\n'
            '__all__ = ["FlextDemoExtra"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        tm.that(self._generated_init(package_root), lacks="FlextDemoExtra")

        conversion_path.unlink()
        check_service = u.Tests.create_lazy_init_service(repository_root)
        tm.that(check_service.plan_files().success, eq=True)
        tm.that(self._generated_init(package_root), eq=generated)

    def test_private_subpackage_facade_never_becomes_root_public(
        self, tmp_path: Path
    ) -> None:
        """Keep even a final implementation facade private below the root."""
        repository_root, package_root = self._workspace(tmp_path)
        models_dir = package_root / "_models"
        parts_dir = models_dir / "_base_parts"
        parts_dir.mkdir(parents=True)
        for package_dir in (models_dir, parts_dir):
            package_dir.joinpath(c.Infra.INIT_PY).write_text(
                "", encoding=c.Cli.ENCODING_DEFAULT
            )
        parts_dir.joinpath("flextdemomodelsbase_part_01.py").write_text(
            "class FlextDemoModelsBase:\n"
            '    """Private implementation part."""\n\n'
            '__all__ = ["FlextDemoModelsBase"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        models_dir.joinpath("base.py").write_text(
            "from ._base_parts.flextdemomodelsbase_part_01 import "
            "FlextDemoModelsBase as FlextDemoModelsBasePart01\n\n"
            "class FlextDemoModelsBase(FlextDemoModelsBasePart01):\n"
            '    """Public facade."""\n\n'
            '__all__ = ["FlextDemoModelsBase"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = self._generated_init(package_root)

        tm.that(generated, lacks="FlextDemoModelsBase")
        tm.that(generated, lacks="._models.base")
        tm.that(generated, lacks="._models._base_parts.flextdemomodelsbase_part_01")

    def test_explicit_all_exports_keep_public_aliases_only(
        self, tmp_path: Path
    ) -> None:
        """Respect an explicit module export contract without leaking siblings."""
        repository_root, package_root = self._workspace(tmp_path)
        (package_root / "api.py").write_text(
            "from __future__ import annotations\n\n"
            "class FlextDemo:\n"
            "    pass\n\n"
            "demo = FlextDemo()\n"
            "hidden = FlextDemo()\n\n"
            '__all__: list[str] = ["FlextDemo", "demo"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        exports_content = self._generated_init(package_root)

        tm.that(exports_content, has='"FlextDemo"')
        tm.that(exports_content, has='"demo"')
        tm.that(exports_content, lacks="hidden")

    def test_child_packages_never_widen_the_public_root(self, tmp_path: Path) -> None:
        """Keep every child-package declaration behind its owning facade."""
        repository_root, package_root = self._workspace(tmp_path)
        child_dir = package_root / "services"
        child_dir.mkdir()
        (child_dir / c.Infra.INIT_PY).write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        (child_dir / "service.py").write_text(
            "from __future__ import annotations\n\n"
            "class FlextDemoService:\n"
            "    pass\n\n"
            '__all__: list[str] = ["FlextDemoService"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (child_dir / "colors.py").write_text(
            'from __future__ import annotations\n\nBLUE = "blue"\n\n__all__: list[str] = ["BLUE"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (child_dir / "cli.py").write_text(
            'from __future__ import annotations\n\ndef main() -> str:\n    return "ok"\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        u.Tests.write_lazy_init_namespace_module(
            child_dir / "models.py",
            class_name="FlextDemoServicesModels",
            alias="m",
            docstring="Models.",
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        exports_content = self._generated_init(package_root)

        tm.that(exports_content, has="FlextDemoService")
        tm.that(exports_content, has='"BLUE"')
        tm.that(exports_content, has="FlextDemoServicesModels")
        tm.that(exports_content, lacks='"main"')
        tm.that(exports_content, has='"m"')

    def test_generated_constants_owner_never_widens_parent_map(
        self, tmp_path: Path
    ) -> None:
        repository_root, package_root = self._workspace(tmp_path)
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="FlextDemoModels", alias="m"
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        first = self._generated_init(package_root)
        tm.that(u.Tests.run_lazy_init(repository_root, check_only=True), eq=0)

        tm.that(self._generated_init(package_root), eq=first)
        tm.that(first, lacks='"._constants"')

    def test_tests_root_facade_is_generated_lazily(self, tmp_path: Path) -> None:
        """Generate the tests root facade with local publics and inherited aliases."""
        repository_root, _package_root = self._workspace(tmp_path)
        tests_root = repository_root / c.Infra.DIR_TESTS
        tests_root.mkdir()
        tests_root.joinpath(c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        tests_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "class TestsFlextDemoConstants:\n"
            "    pass\n\n"
            "c = TestsFlextDemoConstants\n\n"
            '__all__: list[str] = ["TestsFlextDemoConstants", "c"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        child_dir = tests_root / "unit"
        child_dir.mkdir()
        (child_dir / c.Infra.INIT_PY).write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        (child_dir / "child.py").write_text(
            "from __future__ import annotations\n\n"
            "class Child:\n"
            "    pass\n\n"
            '__all__: list[str] = ["Child"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        init_content = tests_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )
        # Lazy inits cover EVERY python surface (src, tests, examples,
        # scripts): the tests root is a generated PEP 562 facade too.
        tm.that(init_content, has="_LAZY_IMPORTS = MappingProxyType(")
        tm.that(init_content, has='"TestsFlextDemoConstants"')
        tm.that(tests_root.joinpath("__unit__.py").exists(), eq=False)
        compile(init_content, "tests/__init__.py", "exec")
        check_service = u.Tests.create_lazy_init_service(repository_root)
        tm.that(
            tuple(
                plan
                for plan in tm.ok(check_service.plan_files()).files
                if u.Infra.codegen_file_requires_effect(plan)
            ),
            empty=True,
        )
        tm.that(check_service.modified_files, empty=True)

    def test_root_aliases_follow_transitive_parent_exports_from_source(
        self, tmp_path: Path
    ) -> None:
        """Order inherited aliases by the canonical facade dependency chain."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-meltano", package_name="flext_meltano"
        )
        core_root = tmp_path / "flext-core" / c.Infra.DEFAULT_SRC_DIR / "flext_core"
        core_root.mkdir(parents=True)
        core_root.parent.parent.joinpath(c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "flext-core"\nversion = "0.1.0"\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        core_root.joinpath(c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        u.Tests.write_lazy_init_namespace_module(
            core_root / "result.py",
            class_name="FlextCoreResult",
            alias="r",
            docstring="Result.",
        )
        core_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "class FlextCoreConstants:\n"
            "    pass\n\n"
            '__all__: list[str] = ["FlextCoreConstants"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        cli_root = tmp_path / "flext-cli" / c.Infra.DEFAULT_SRC_DIR / "flext_cli"
        cli_root.mkdir(parents=True)
        cli_root.parent.parent.joinpath(c.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "flext-cli"\nversion = "0.1.0"\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        cli_root.joinpath(c.Infra.INIT_PY).write_text(
            '__all__: list[str] = ["c", "r"]\n', encoding=c.Cli.ENCODING_DEFAULT
        )
        cli_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "from flext_core import FlextCoreConstants\n\n"
            "class FlextCliConstants(FlextCoreConstants):\n"
            "    pass\n\n"
            '__all__: list[str] = ["FlextCliConstants"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        package_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "from flext_cli import c\n\n"
            "class FlextMeltanoConstants(c):\n"
            "    pass\n\n"
            '__all__: list[str] = ["FlextMeltanoConstants"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        init_content = self._generated_init(package_root)
        exports_content = self._generated_init(package_root)

        tm.that(init_content, lacks="_LAZY_MODULES")
        tm.that(exports_content, has='"flext_cli": (')
        tm.that(init_content, has="__all__: tuple[str, ...]")
        tm.that(init_content, has="install_lazy_exports(")
        tm.that(init_content, lacks="__unit__")
        tm.that(init_content, lacks="_root_typing_parts")
        ruff_ordered_aliases = ("c", "d", "e", "h", "m", "p", "r", "s", "t", "u", "x")
        for alias_name in ruff_ordered_aliases:
            tm.that(init_content, has=f'    "{alias_name}",')
        has_all, public_exports = u.Tests.extract_lazy_init_exports(init_content)
        tm.that(has_all, eq=True)
        # __all__ follows RUF022; dependency order remains
        # exclusively in the static facade imports.
        alias_positions = tuple(
            public_exports.index(alias) for alias in ruff_ordered_aliases
        )
        tm.that(alias_positions, eq=tuple(sorted(alias_positions)))
        # ADR-018 p.1: the owner of a letter is the module that DECLARES it in
        # its own ``__all__``. This facade extends the parent's ``c`` but
        # declares only its class, so every letter here is inherited from the
        # nearest declaring facade — ``c`` included. Extending a letter is not
        # declaring it; the B1 fix writes the declaration when the module means
        # to own it, and until then the generator propagates, never infers.
        tm.that(
            init_content.splitlines(),
            has="    from flext_cli import c, d, e, h, m, p, r, s, t, u, x",
        )
        tm.that(init_content, lacks="FlextMeltanoConstants as c")
        tm.that(exports_content, has='"flext_cli": (')
        tm.that(exports_content, has='".constants": (')

    def test_existing_root_composes_public_parent_aliases(self, tmp_path: Path) -> None:
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        u.Tests.write_project_beads_config(repository_root, "flext-demo")
        package_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "from flext_cli import c\n\n"
            "class FlextDemoConstants(c):\n"
            "    pass\n\n"
            '__all__: list[str] = ["FlextDemoConstants", "c"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = self._generated_init(package_root)
        exports = self._generated_init(package_root)
        tm.that(exports, has='"flext_cli": (')
        tm.that(generated, has='    "r",')
        tm.that(generated, has='    "c",')

    def test_generated_parent_initializer_is_not_an_alias_owner(
        self, tmp_path: Path
    ) -> None:
        """Ignore stale aliases that exist only in a generated parent projection."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-child", package_name="flext_child"
        )
        parent_root = repository_root / c.Infra.DEFAULT_SRC_DIR / "flext_parent"
        parent_root.mkdir(parents=True)
        parent_root.joinpath(c.Infra.INIT_PY).write_text(
            f'{c.Infra.AUTOGEN_HEADER}\n__all__ = ("x",)\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        parent_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "class FlextParentConstants:\n"
            "    pass\n\n"
            '__all__ = ("FlextParentConstants",)\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        package_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from flext_parent import c\n\n"
            "class FlextChildConstants(c):\n"
            "    pass\n\n"
            '__all__ = ("FlextChildConstants",)\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        service = u.Tests.create_lazy_init_service(repository_root).model_copy(
            update={"target_module": "flext_child"}
        )
        planned = tm.ok(service.plan_files()).files
        generated = next(
            u.Tests.codegen_file_text(plan)
            for plan in planned
            if plan.path == package_root.joinpath(c.Infra.INIT_PY).resolve()
        )

        tm.that(generated, lacks='"x"')
        tm.that(generated, lacks='"flext_parent": ("x",)')

    def test_installed_parent_alias_uses_the_nearest_actual_owner(
        self, tmp_path: Path
    ) -> None:
        """An installed parent re-exporting a letter serves it, not its owner.

        Each installed package has the published FLEXT shape (ADR-018 p.1-2):
        a facade module declares its letter in its own ``__all__`` and the
        package initializer only propagates it. The child inherits ``r``
        through ``nearest_parent``, which re-exports it from the declaring
        ``owner_parent``; the election names the nearest re-exporting parent
        (operator ruling 2026-09-23). Every installed module raises on import,
        so the planner can only read them by path.
        """
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-child", package_name="flext_child"
        )
        installed_root = tmp_path / "installed"
        guard = 'raise RuntimeError("must not import")\n'
        sys.path.insert(0, str(installed_root))
        try:
            nearest = installed_root / "nearest_parent"
            owner = installed_root / "owner_parent"
            nearest.mkdir(parents=True)
            owner.mkdir(parents=True)
            owner.joinpath("result.py").write_text(
                "class OwnerParentResult:\n    pass\n\n"
                "r = OwnerParentResult\n"
                f'__all__ = ("OwnerParentResult", "r")\n{guard}',
                encoding=c.Cli.ENCODING_DEFAULT,
            )
            owner.joinpath(c.Infra.INIT_PY).write_text(
                "from .result import OwnerParentResult, r\n\n"
                f'__all__ = ("OwnerParentResult", "r")\n{guard}',
                encoding=c.Cli.ENCODING_DEFAULT,
            )
            nearest.joinpath(c.Infra.CONSTANTS_PY).write_text(
                "class NearestParentConstants:\n    pass\n\n"
                "c = NearestParentConstants\n"
                f'__all__ = ("NearestParentConstants", "c")\n{guard}',
                encoding=c.Cli.ENCODING_DEFAULT,
            )
            nearest.joinpath(c.Infra.INIT_PY).write_text(
                "from owner_parent import r\n\n"
                "from .constants import NearestParentConstants, c\n\n"
                f'__all__ = ("NearestParentConstants", "c", "r")\n{guard}',
                encoding=c.Cli.ENCODING_DEFAULT,
            )
            package_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
                "from nearest_parent import NearestParentConstants\n\n"
                "class FlextChildConstants(NearestParentConstants):\n"
                "    pass\n\n"
                "c = FlextChildConstants\n"
                '__all__ = ("FlextChildConstants", "c")\n',
                encoding=c.Cli.ENCODING_DEFAULT,
            )

            tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
            generated = self._generated_init(package_root)
            entries, _refs = u.Infra.module_mapping_assignment_source(
                generated, u.Infra.lazy_imports_name_source(generated)
            )
            sources = dict(entries)

            tm.that(sources.get("nearest_parent", ()), has="r")
            tm.that(sources, lacks="owner_parent")
            tm.that(u.Tests.run_lazy_init(repository_root, check_only=True), eq=0)
        finally:
            sys.path.remove(str(installed_root))

    def test_non_flext_root_derives_inherited_aliases_beyond_stale_all(
        self, tmp_path: Path
    ) -> None:
        """Derive the root ABI from facade owners, never the prior projection."""
        # ai_hub's stale __all__ omitted r and became a second SSOT;
        # regeneration must follow the declared composition parent.
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="ai-hub", package_name="ai_hub"
        )
        package_root.joinpath(c.Infra.INIT_PY).write_text(
            '__all__: tuple[str, ...] = ("AiHubModels", "m")\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        u.Tests.write_lazy_init_namespace_module(
            package_root / "models.py", class_name="AiHubModels", alias="m"
        )
        package_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "from flext_infra import c\n\n"
            "class AiHubConstants(c):\n"
            "    pass\n\n"
            '__all__ = ("AiHubConstants", "c")\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = self._generated_init(package_root)
        has_all, public_exports = u.Tests.extract_lazy_init_exports(generated)

        tm.that(has_all, eq=True)
        for alias_name in ("c", "d", "e", "h", "m", "p", "r", "s", "t", "u", "x"):
            tm.that(public_exports, has=alias_name)
        tm.that(generated, has="from flext_infra import d, e, h, p, r, s, t, u, x")

    def test_root_keeps_declared_public_git_and_work_services(
        self, tmp_path: Path
    ) -> None:
        """Publish service owners declared by root namespace configuration."""
        repository_root, package_root = self._workspace(tmp_path)
        package_root.joinpath("git.py").write_text(
            "class FlextDemoGitService:\n"
            '    """Public Git service."""\n\n'
            '__all__ = ("FlextDemoGitService",)\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        package_root.joinpath("work.py").write_text(
            "class FlextDemoWorkService:\n"
            '    """Public work service."""\n\n'
            '__all__ = ("FlextDemoWorkService",)\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        generated = self._generated_init(package_root)
        exports = self._generated_init(package_root)

        tm.that(generated, has='"FlextDemoGitService"')
        tm.that(generated, has='"FlextDemoWorkService"')
        tm.that(exports, has='".git": ("FlextDemoGitService",)')
        tm.that(exports, has='".work": ("FlextDemoWorkService",)')

    def test_nested_tests_namespace_uses_public_test_facades(
        self, tmp_path: Path
    ) -> None:
        """Generate nested test namespaces with their local publics."""
        repository_root, package_root = self._workspace(tmp_path)
        package_root.joinpath(c.Infra.RESULT_PY).write_text(
            "from __future__ import annotations\n\nclass FlextDemoResult:\n    pass\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tests_unit_root = repository_root / c.Infra.DIR_TESTS / "unit"
        tests_unit_root.mkdir(parents=True)
        tests_unit_root.joinpath(c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        # `__all__` is the publication contract on EVERY surface — a module
        # that declares nothing publishes nothing, in tests exactly as in src.
        # The fixture declares its publics like every other module here does,
        # so what this test proves is the tests-namespace routing, not the
        # unrelated question of undeclared symbols.
        tests_unit_root.joinpath(c.Infra.CONSTANTS_PY).write_text(
            "from __future__ import annotations\n\n"
            "class TestsFlextDemoUnitConstants:\n"
            "    pass\n\n"
            "c = TestsFlextDemoUnitConstants\n\n"
            '__all__: list[str] = ["TestsFlextDemoUnitConstants", "c"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tests_unit_root.joinpath(c.Infra.MODELS_PY).write_text(
            "from __future__ import annotations\n\n"
            "class TestsFlextDemoUnitModels:\n"
            "    pass\n\n"
            "m = TestsFlextDemoUnitModels\n\n"
            '__all__: list[str] = ["TestsFlextDemoUnitModels", "m"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        init_content = tests_unit_root.joinpath(c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )
        for public_name in ("c", "m"):
            tm.that(init_content, has=f'"{public_name}"')
        for undeclared_name in set(c.Infra.TEST_RUNTIME_ALIAS_TARGETS) - {"c", "m"}:
            tm.that(init_content, lacks=f'"{undeclared_name}"')
        tm.that(init_content, lacks="FlextDemoResult")
        tm.that(tests_unit_root.joinpath("__unit__.py").exists(), eq=False)

    def test_root_rejects_symbols_from_deep_descendant_packages(
        self, tmp_path: Path
    ) -> None:
        """Keep deeply nested declarations behind their package facade."""
        repository_root, package_root = self._workspace(tmp_path)
        deep_dir = package_root / "services" / "http"
        deep_dir.mkdir(parents=True)
        (package_root / "services" / c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        deep_dir.joinpath(c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        deep_dir.joinpath("transport.py").write_text(
            "from __future__ import annotations\n\n"
            "class FlextDemoHttpTransport:\n"
            "    pass\n\n"
            '__all__: list[str] = ["FlextDemoHttpTransport"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        exports_content = self._generated_init(package_root)

        tm.that(exports_content, has="FlextDemoHttpTransport")
        tm.that(exports_content, has='"services"')

    def test_independent_packages_accept_same_export_name_without_warnings(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A public name belongs to its package, not to a workspace-wide census."""
        repository_root, package_root = self._workspace(tmp_path)
        other_package = package_root.with_name("independent_package")
        other_package.mkdir()
        other_package.joinpath(c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        for package in (package_root, other_package):
            package.joinpath("holder.py").write_text(
                "class SharedPackageDeclaration:\n    pass\n\n"
                '__all__ = ["SharedPackageDeclaration"]\n',
                encoding=c.Cli.ENCODING_DEFAULT,
            )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        tm.that(u.Tests.run_lazy_init(repository_root, check_only=True), eq=0)
        captured = capsys.readouterr()
        tm.that(captured.out + captured.err, lacks="WARN:")

    def test_unpublished_module_homonyms_do_not_compete_for_exports(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Independent implementation declarations need no global renaming."""
        repository_root, package_root = self._workspace(tmp_path)
        for module in ("first", "second"):
            package_root.joinpath(f"{module}.py").write_text(
                "class ModuleLocalDeclaration:\n    pass\n\n__all__: list[str] = []\n",
                encoding=c.Cli.ENCODING_DEFAULT,
            )

        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        tm.that(u.Tests.run_lazy_init(repository_root, check_only=True), eq=0)
        captured = capsys.readouterr()
        tm.that(captured.out + captured.err, lacks="WARN:")

    def test_duplicate_public_export_fails_before_generation(
        self, tmp_path: Path
    ) -> None:
        """Two owners of one public name stop the phase before any file plan.

        Both modules declare the same public name, so nothing can decide which
        one owns it. Picking the first, the last, or merging them would make
        the disagreement invisible exactly where it matters, so planning
        refuses and names the collision instead of generating a facade.
        """
        repository_root, package_root = self._workspace(tmp_path)
        before = self._generated_init(package_root)
        (package_root / "api.py").write_text(
            "from __future__ import annotations\n\nclass Shared:\n    pass\n\n"
            '__all__: list[str] = ["Shared"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        (package_root / "service.py").write_text(
            "from __future__ import annotations\n\nclass Shared:\n    pass\n\n"
            '__all__: list[str] = ["Shared"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        planned = u.Tests.plan_lazy_init(repository_root)

        tm.that(planned.failure, eq=True)
        tm.that(planned.error, has="ambiguous")
        # The refusal is PRE-EFFECT: the facade on disk is untouched and never
        # gained the contested name.
        after = self._generated_init(package_root)
        tm.that(after, eq=before)
        tm.that(after, lacks="Shared")

    def test_duplicate_facade_letter_fails_before_generation(
        self, tmp_path: Path
    ) -> None:
        """Two same-level owners of one facade letter stop the phase pre-effect.

        The letter channel is governed exactly like every public name: when two
        modules of one package both declare the same letter, nothing can decide
        which one owns it, so planning refuses loudly and names the collision
        instead of silently electing a winner behind the disagreement.
        """
        repository_root, package_root = self._workspace(tmp_path)
        before = self._generated_init(package_root)
        for module_name, class_name in (
            ("constants", "AlphaConstants"),
            ("culture", "CultureConstants"),
        ):
            (package_root / f"{module_name}.py").write_text(
                "from __future__ import annotations\n\n"
                f"class {class_name}:\n    pass\n\n"
                f"c = {class_name}\n\n"
                f'__all__: list[str] = ["{class_name}", "c"]\n',
                encoding=c.Cli.ENCODING_DEFAULT,
            )

        planned = u.Tests.plan_lazy_init(repository_root)

        tm.that(planned.failure, eq=True)
        tm.that(planned.error, has="ambiguous")
        # The refusal is PRE-EFFECT: no facade gains either contested owner.
        after = self._generated_init(package_root)
        tm.that(after, eq=before)
        tm.that(after, lacks="AlphaConstants")
        tm.that(after, lacks="CultureConstants")
        tm.that(after, lacks='"c"')
