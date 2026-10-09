"""Public utility evidence for semantic private-import cutovers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, infra, m, p, t, u


@dataclasses.dataclass(frozen=True)
class FacadeNaming:
    """The resolved facade identity of one public/private module pair."""

    private_module: str
    private_class: str
    root_class: str
    nested_class: str
    alias: str
    root_bases: str = ""

    @classmethod
    def from_family(
        cls,
        family: str,
        leaf: str,
        nested_class: str,
        alias: str,
    ) -> FacadeNaming:
        """Derive every name from the sampled family naming contract.

        Returns:
            The resulting ``FacadeNaming``.

        """
        return cls(
            private_module=f"flext_sample._{family}.{leaf}",
            private_class=f"FlextSample{family.title()}{leaf.title()}",
            root_class=f"FlextSample{family.title()}",
            nested_class=nested_class,
            alias=alias,
        )


class TestsFlextInfraPrivateImportCutover:
    """Exercise private-import automation only through ``u.Infra``."""

    def test_earlier_semantic_move_retires_stale_preflight_import(
        self,
        tmp_path: Path,
    ) -> None:
        """Test earlier semantic move retires stale preflight import."""
        consumer, statement, _ = self._facade_case(
            tmp_path,
            FacadeNaming.from_family("constants", "profile", "Profile", "c"),
        )
        sources = {consumer: "from flext_sample import c\nvalue = c.Profile.Value\n"}
        tm.that(self._edits(tmp_path, sources, consumer, statement), empty=True)

    @pytest.mark.parametrize("bad_source_reachable", [False, True])
    def test_installed_import_validation_follows_public_reachability(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
        *,
        bad_source_reachable: bool,
    ) -> None:
        """An invalid import blocks only a cutover that reaches its module."""
        consumer, statement, facade_sources = self._facade_case(
            tmp_path,
            FacadeNaming.from_family("constants", "profile", "Profile", "c"),
        )
        package = installed_dependency_path / "flext_sample"
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="utf-8")
        invalid_import = "from ..outside import Invalid\n"
        facade_source = next(iter(facade_sources.values()))
        (package / "constants.py").write_text(
            facade_source + (invalid_import if bad_source_reachable else ""),
            encoding="utf-8",
        )
        private = package / "_constants/profile.py"
        private.parent.mkdir()
        private.write_text(
            "class FlextSampleConstantsProfile:\n    Value = str\n",
            encoding="utf-8",
        )
        unrelated = package / "unrelated.py"
        unrelated.write_text(invalid_import, encoding="utf-8")
        sources = {
            consumer: f"{statement}\nprofile = FlextSampleConstantsProfile.Value\n",
        }

        if bad_source_reachable:
            # flext-core's result factory catches broad runtime errors only
            # ("no IO, no import"): an invalid reachable import escapes raw.
            with pytest.raises(
                ImportError,
                match="attempted relative import beyond top-level",
            ):
                self._plan(tmp_path, sources, consumer, statement)
            return
        edits = self._edits(tmp_path, sources, consumer, statement)

        tm.that(tuple(edit.file_path for edit in edits), eq=(consumer,))
        tm.that(edits[0].updated_source, has="from flext_sample import c")
        tm.that(edits[0].updated_source, has="profile = c.Profile.Value")
        tm.that(unrelated.read_text(encoding="utf-8"), eq=invalid_import)

    def _seed_sample_dependency(
        self,
        package: Path,
        facade_sources: t.MappingKV[Path, str],
        *,
        case: str,
        depth: int,
    ) -> dict[Path, str]:
        """Materialize the installed sample dependency package for one case.

        Deep cases bridge the private facade through real subclasses and
        rewire every facade reference to the outermost bridge class.

        Returns:
            Every seeded dependency path and its written source.

        """
        dependency_sources = {
            package / path.name: source for path, source in facade_sources.items()
        }
        dependency_sources[package / "__init__.py"] = (
            "raise RuntimeError('discovery must not execute dependency code')\n"
        )
        dependency_sources[package / "_constants/profile.py"] = (
            "class FlextSampleConstantsProfile:\n    Value = str\n"
        )
        if case == "ambiguous":
            dependency_sources[package / "other.py"] = self._facade_source(
                naming=FacadeNaming(
                    private_module="flext_sample._constants.profile",
                    private_class="FlextSampleConstantsProfile",
                    root_class="OtherConstants",
                    nested_class="Other",
                    alias="c",
                ),
            )
        previous_module = "flext_sample._constants.profile"
        previous_class = "FlextSampleConstantsProfile"
        for level in range(depth):
            module_name = f"bridge_{level}"
            class_name = f"FlextSampleConstantsBridge{level}"
            previous_leaf = previous_module.rsplit(".", maxsplit=1)[-1]
            dependency_sources[package / f"_constants/{module_name}.py"] = (
                f"from .{previous_leaf} import {previous_class}\n"
                f"class {class_name}({previous_class}):\n    pass\n"
            )
            previous_module = f"flext_sample._constants.{module_name}"
            previous_class = class_name
        if depth:
            for path in tuple(dependency_sources):
                if path.parent == package and path.name != "__init__.py":
                    dependency_sources[path] = (
                        dependency_sources[path]
                        .replace("flext_sample._constants.profile", previous_module)
                        .replace("FlextSampleConstantsProfile", previous_class)
                    )
        for path, source in dependency_sources.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        return dependency_sources

    @pytest.mark.parametrize("case", ["unique", "ambiguous", "shadowed"])
    @pytest.mark.parametrize("depth", [0, 2])
    def test_installed_facades_are_read_only_discovery_inputs(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
        case: str,
        depth: int,
    ) -> None:
        """Test installed facades are read only discovery inputs."""
        consumer, statement, facade_sources = self._facade_case(
            tmp_path,
            FacadeNaming.from_family("constants", "profile", "Profile", "c"),
        )
        package = installed_dependency_path / "flext_sample"
        package.mkdir()
        dependency_sources = self._seed_sample_dependency(
            package,
            facade_sources,
            case=case,
            depth=depth,
        )
        sources = {
            consumer: f"{statement}\nprofile = FlextSampleConstantsProfile.Value\n",
        }
        if case == "shadowed":
            sources[consumer] += "c = 1\n"
        if case == "unique":
            edits = self._edits(tmp_path, sources, consumer, statement)
            tm.that(tuple(edit.file_path for edit in edits), eq=(consumer,))
            tm.that(edits[0].updated_source, has="from flext_sample import c")
            tm.that(edits[0].updated_source, has="profile = c.Profile.Value")
        elif case == "shadowed":
            tm.fail(self._plan(tmp_path, sources, consumer, statement), has=case)
        else:
            with pytest.raises(ValueError, match=case):
                self._plan(tmp_path, sources, consumer, statement)
        for path, source in dependency_sources.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)
        tm.that(tuple(sources), eq=(consumer,))

    @pytest.mark.parametrize("root_export", [False, True])
    def test_installed_declared_reexports_preserve_binding(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
        *,
        root_export: bool,
    ) -> None:
        """Test installed declared reexports preserve binding."""
        consumer, statement, sources = self._declared_export_case(
            tmp_path,
            package_import=True,
            root_export=root_export,
            renamed=True,
        )
        consumer_sources = {consumer: sources.pop(consumer)}
        dependency_sources = {
            installed_dependency_path
            / path.relative_to(tmp_path / "sample/src"): source
            for path, source in sources.items()
        }
        package_init = installed_dependency_path / "sample/__init__.py"
        dependency_sources[package_init] = dependency_sources.get(package_init, "") + (
            "raise RuntimeError('discovery must not execute dependency code')\n"
        )
        for path, source in dependency_sources.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")

        edits = self._edits(tmp_path, consumer_sources, consumer, statement)

        module = "sample" if root_export else "sample.api"
        tm.that(tuple(edit.file_path for edit in edits), eq=(consumer,))
        tm.that(
            edits[0].updated_source,
            has=f"from {module} import PublicClient as BoundClient",
        )
        tm.that(edits[0].updated_source, has="instance = BoundClient()")
        for path, source in dependency_sources.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)

    @pytest.mark.parametrize(
        ("declaration", "expected"),
        [
            (
                (
                    "class Facade:\n"
                    "    class Base:\n        pass\n"
                    "    class Leaf(Base):\n        pass\n"
                ),
                "",
            ),
            (
                (
                    "class Facade:\n"
                    "    class Base:\n        pass\n"
                    "    class Branch(Base):\n"
                    "        class Leaf(Base):\n            pass\n"
                ),
                "c.Branch.Leaf",
            ),
            (
                (
                    "class Facade:\n"
                    "    class Branch:\n"
                    "        class Base:\n            pass\n"
                    "        class Leaf(Base):\n            pass\n"
                ),
                "",
            ),
            (
                "class Facade:\n    class Leaf(private.Target):\n        pass\n",
                "c.Leaf",
            ),
            (
                (
                    "class Facade:\n"
                    "    class private:\n"
                    "        class Target:\n            pass\n"
                    "    class Leaf(private.Target):\n        pass\n"
                ),
                "",
            ),
            (
                (
                    "class Facade:\n"
                    "    class Left(Base):\n        pass\n"
                    "    class Right(Base):\n        pass\n"
                ),
                "ambiguous",
            ),
        ],
        ids=[
            "sibling-shadow",
            "grandchild-module-binding",
            "grandchild-local-shadow",
            "qualified-module-base",
            "qualified-local-shadow",
            "ambiguous-siblings",
        ],
    )
    def test_installed_facade_bases_follow_declaration_scope(
        self,
        tmp_path: Path,
        installed_dependency_path: Path,
        declaration: str,
        expected: str,
    ) -> None:
        """Test installed facade bases follow declaration scope."""
        package = installed_dependency_path / "lexical_sample"
        dependency_sources = {
            package / "__init__.py": (
                "raise RuntimeError('discovery must not execute dependency code')\n"
            ),
            package / "_private.py": "class Target:\n    Value = str\n",
            package / "constants.py": (
                "from lexical_sample._private import Target as Base\n"
                "import lexical_sample._private as private\n"
                f"{declaration}\nc = Facade\n"
            ),
        }
        for path, source in dependency_sources.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        consumer = tmp_path / "consumer/src/consumer/service.py"
        statement = "from lexical_sample._private import Target"
        sources = {consumer: f"{statement}\nvalue = Target.Value\n"}

        if expected.startswith("c."):
            edits = self._edits(tmp_path, sources, consumer, statement)
            tm.that(tuple(edit.file_path for edit in edits), eq=(consumer,))
            tm.that(edits[0].updated_source, has="from lexical_sample import c")
            tm.that(edits[0].updated_source, has=f"value = {expected}.Value")
            tm.that(edits[0].updated_source, lacks=statement)
        else:
            with pytest.raises(
                ValueError,
                match=expected or "no public facade exposes",
            ):
                self._plan(tmp_path, sources, consumer, statement)
        for path, source in dependency_sources.items():
            tm.that(path.read_text(encoding="utf-8"), eq=source)

    @staticmethod
    def _declared_export_case(
        root: Path,
        *,
        package_import: bool = False,
        root_export: bool = False,
        renamed: bool = False,
    ) -> t.Triple[Path, str, t.MutableMappingKV[Path, str]]:
        package = root / "sample/src/sample"
        public_name = "PublicClient" if renamed else "Client"
        sources = {
            package / "_private/client.py": "class Client:\n    pass\n",
            package / "_private/__init__.py": (
                "from typing import TYPE_CHECKING\n"
                "from flext_core.lazy import "
                "build_lazy_import_map, install_lazy_exports\n"
                "if TYPE_CHECKING:\n    from .client import Client\n"
                "__all__ = ('Client',)\n"
                "_LAZY_IMPORTS = build_lazy_import_map({'.client': ('Client',)})\n"
                "install_lazy_exports("
                "__name__, globals(), _LAZY_IMPORTS, public_exports=__all__)\n"
            ),
            package / "api.py": (
                f"from ._private.client import Client as {public_name}\n"
                f"__all__ = ('{public_name}',)\n"
            ),
        }
        if root_export:
            sources[package / "__init__.py"] = (
                f"from .api import {public_name}\n__all__ = ('{public_name}',)\n"
            )
        module = "sample._private" if package_import else "sample._private.client"
        statement = f"from {module} import Client as BoundClient"
        consumer = root / "consumer/src/consumer/service.py"
        sources[consumer] = (
            f"{statement}\ninstance = BoundClient()\n"
            "def local(BoundClient: str) -> str:\n    return BoundClient\n"
        )
        return consumer, statement, sources

    @pytest.mark.parametrize("package_import", [False, True])
    @pytest.mark.parametrize("root_export", [False, True])
    @pytest.mark.parametrize("renamed", [False, True])
    def test_declared_reexports_preserve_identity_binding_and_shadowing(
        self,
        tmp_path: Path,
        *,
        package_import: bool,
        root_export: bool,
        renamed: bool,
    ) -> None:
        """Test declared reexports preserve identity binding and shadowing."""
        consumer, statement, sources = self._declared_export_case(
            tmp_path,
            package_import=package_import,
            root_export=root_export,
            renamed=renamed,
        )

        updated = self._updated_source(tmp_path, sources, consumer, statement)

        module = "sample" if root_export else "sample.api"
        public_name = "PublicClient" if renamed else "Client"
        tm.that(updated, has=f"from {module} import {public_name} as BoundClient")
        tm.that(updated, has="instance = BoundClient()")
        tm.that(
            updated,
            has="def local(BoundClient: str) -> str:\n    return BoundClient",
        )
        tm.that(updated, lacks=statement)

    def test_declared_reexport_rename_keeps_an_unaliased_consumer_binding(
        self,
        tmp_path: Path,
    ) -> None:
        """Test declared reexport rename keeps an unaliased consumer binding."""
        consumer, statement, sources = self._declared_export_case(
            tmp_path,
            renamed=True,
        )
        unaliased = statement.replace(" as BoundClient", "")
        sources[consumer] = f"{unaliased}\ninstance = Client()\n"

        updated = self._updated_source(tmp_path, sources, consumer, unaliased)

        tm.that(updated, has="from sample.api import PublicClient as Client")
        tm.that(updated, has="instance = Client()")

    def test_declared_reexport_retains_type_checking_boundary(
        self,
        tmp_path: Path,
    ) -> None:
        """Test declared reexport retains type checking boundary."""
        consumer, statement, sources = self._declared_export_case(tmp_path)
        sources[consumer] = (
            "from __future__ import annotations\nfrom typing import TYPE_CHECKING\n"
            f"if TYPE_CHECKING:\n    {statement}\nvalue: BoundClient\n"
        )

        updated = self._updated_source(tmp_path, sources, consumer, statement)

        tm.that(
            updated,
            has="if TYPE_CHECKING:\n    from sample.api import Client as BoundClient",
        )
        tm.that(updated, has="value: BoundClient")

    def test_unrelated_export_cycle_does_not_block_a_proven_public_import(
        self,
        tmp_path: Path,
    ) -> None:
        """Test unrelated export cycle does not block a proven public import."""
        consumer, statement, sources = self._declared_export_case(tmp_path)
        package = tmp_path / "sample/src/sample"
        sources[package / "left.py"] = "from .right import Loop\n__all__ = ('Loop',)\n"
        sources[package / "right.py"] = "from .left import Loop\n__all__ = ('Loop',)\n"

        updated = self._updated_source(tmp_path, sources, consumer, statement)

        tm.that(updated, has="from sample.api import Client as BoundClient")

    @pytest.mark.parametrize("case", ["unexposed", "homonym", "ambiguous", "shadowed"])
    def test_declared_export_resolution_rejects_unproven_or_ambiguous_targets(
        self,
        tmp_path: Path,
        case: str,
    ) -> None:
        """Test declared export resolution rejects unproven or ambiguous targets."""
        consumer, statement, sources = self._declared_export_case(tmp_path)
        package = tmp_path / "sample/src/sample"
        if case == "unexposed":
            sources[package / "api.py"] = "from ._private.client import Client\n"
        elif case == "homonym":
            sources[package / "api.py"] = (
                "class Client:\n    pass\n__all__ = ('Client',)\n"
            )
        elif case == "ambiguous":
            sources[package / "other.py"] = sources[package / "api.py"]
        else:
            sources[package / "api.py"] += "Client = object\n"
        # A shadowed re-export is rebound at runtime (``Client = object``), so
        # the facade does not expose the private class at all.
        expected = (
            "no public facade exposes"
            if case in {"unexposed", "homonym", "shadowed"}
            else "ambiguous"
        )

        with pytest.raises(ValueError, match=expected):
            self._plan(tmp_path, sources, consumer, statement)

    @staticmethod
    def _finding(file_path: Path, text: str) -> m.Infra.ModScanFinding:
        """Build one authenticated-shape semantic finding.

        Returns:
            The resulting ``m.Infra.ModScanFinding``.

        """
        return m.Infra.ModScanFinding(
            rule_file="ban-private-import.yml",
            rule_id="ban-private-import",
            repository="flext-sample",
            file=file_path,
            range={},
            text=text,
            actionable=False,
            classification=c.Infra.ModScanFindingClass.DETECTION_ONLY,
            payload={},
        )

    @staticmethod
    def _facade_source(*, naming: FacadeNaming) -> str:
        """Build one public facade module that nests the private class.

        Returns:
            The resulting ``str``.

        """
        return (
            f"from {naming.private_module} import {naming.private_class}\n\n"
            f"class {naming.root_class}{naming.root_bases}:\n"
            f"    class {naming.nested_class}({naming.private_class}):\n"
            "        pass\n\n"
            f"{naming.alias} = {naming.root_class}\n"
        )

    @classmethod
    def _facade_case(
        cls,
        tmp_path: Path,
        naming: FacadeNaming,
        *,
        import_alias: str = "",
    ) -> t.Triple[Path, str, t.MutableMappingKV[Path, str]]:
        """Derive the consumer path, private import, and facade source of one family.

        Returns:
            The resulting ``t.Triple[Path, str, t.MutableMappingKV[Path, str]]``.

        """
        binding = (
            f"{naming.private_class} as {import_alias}"
            if import_alias
            else naming.private_class
        )
        family_dir = naming.private_module.split(".")[1].removeprefix("_")
        sources = {
            tmp_path / f"flext-sample/src/flext_sample/{family_dir}.py": (
                cls._facade_source(naming=naming)
            ),
        }
        consumer_path = tmp_path / "flext-consumer/src/flext_consumer/service.py"
        return consumer_path, f"from {naming.private_module} import {binding}", sources

    @classmethod
    def _plan(
        cls,
        tmp_path: Path,
        sources: t.MappingKV[Path, str],
        consumer_path: Path,
        *private_imports: str,
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan the cutover for every private import reported in the consumer.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]``.

        """
        with infra.rope_workspace(tmp_path) as rope:
            return u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.PRIVATE_IMPORT,
                rope_workspace=rope,
                sources=sources,
                findings=tuple(
                    cls._finding(consumer_path.relative_to(tmp_path), private_import)
                    for private_import in private_imports
                ),
            )

    @classmethod
    def _edits(
        cls,
        tmp_path: Path,
        sources: t.MappingKV[Path, str],
        consumer_path: Path,
        *private_imports: str,
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        """Return the successful plan's edits.

        Returns:
            The successful plan's edits.

        """
        planned = cls._plan(tmp_path, sources, consumer_path, *private_imports)
        tm.ok(planned)
        return planned.value

    @classmethod
    def _updated_source(
        cls,
        tmp_path: Path,
        sources: t.MappingKV[Path, str],
        consumer_path: Path,
        *private_imports: str,
    ) -> str:
        """Return the single planned edit's rewritten consumer source.

        Returns:
            The single planned edit's rewritten consumer source.

        """
        return cls._edits(tmp_path, sources, consumer_path, *private_imports)[
            0
        ].updated_source

    def test_rewires_unique_public_facade_binding(self, tmp_path: Path) -> None:
        """Derive the nested facade path and remove the private import atomically."""
        consumer_path, private_import, sources = self._facade_case(
            tmp_path,
            FacadeNaming.from_family("utilities", "managers", "Sample", "u"),
        )
        sources[consumer_path] = (
            "from flext_sample import p\n"
            f"{private_import}\n\n"
            "manager: FlextSampleUtilitiesManagers.ServiceManagers\n"
        )

        edits = self._edits(tmp_path, sources, consumer_path, private_import)
        tm.that(len(edits), eq=1)
        updated = edits[0].updated_source

        tm.that(
            "from flext_sample import p, u" in updated
            or "from flext_sample import u" in updated,
            eq=True,
        )
        tm.that(updated, has="manager: u.Sample.ServiceManagers")
        tm.that(updated, lacks=private_import)
        tm.that(updated, lacks="FlextSampleUtilitiesManagers.ServiceManagers")

    def test_prefers_nested_facade_over_its_root_ancestor(self, tmp_path: Path) -> None:
        """Select the deepest public namespace when the root shares its base."""
        consumer_path, private_import, sources = self._facade_case(
            tmp_path,
            dataclasses.replace(
                FacadeNaming.from_family("utilities", "managers", "Sample", "u"),
                root_bases="(FlextSampleUtilitiesManagers)",
            ),
        )
        sources[consumer_path] = (
            f"{private_import}\n\n"
            "manager = FlextSampleUtilitiesManagers.ServiceManagers\n"
        )

        updated = self._updated_source(tmp_path, sources, consumer_path, private_import)

        tm.that(updated, has="manager = u.Sample.ServiceManagers")
        tm.that(updated, lacks=private_import)

    def test_rewrites_only_the_imported_alias_binding(self, tmp_path: Path) -> None:
        """Keep a homonymous local binding outside the authenticated cutover."""
        consumer_path, private_import, sources = self._facade_case(
            tmp_path,
            FacadeNaming.from_family(
                "utilities",
                "managers",
                "Sample",
                "u",
            ),
            import_alias="managers",
        )
        sources[consumer_path] = (
            f"{private_import}\n\n"
            "manager = managers.ServiceManagers\n\n"
            "def identity(managers: str) -> str:\n"
            "    return managers\n"
        )

        updated = self._updated_source(tmp_path, sources, consumer_path, private_import)

        tm.that(updated, has="manager = u.Sample.ServiceManagers")
        tm.that(updated, has="def identity(managers: str) -> str:")
        tm.that(updated, has="    return managers")
        tm.that(updated, lacks=private_import)

    def test_rejects_shadowed_public_facade_alias(self, tmp_path: Path) -> None:
        """Fail before effects when a local binding would capture the facade alias."""
        consumer_path, private_import, sources = self._facade_case(
            tmp_path,
            FacadeNaming.from_family("utilities", "managers", "Sample", "u"),
        )
        sources[consumer_path] = (
            f"{private_import}\n\n"
            "def select(u: str) -> str:\n"
            "    return FlextSampleUtilitiesManagers.ServiceManagers or u\n"
        )

        tm.fail(
            self._plan(tmp_path, sources, consumer_path, private_import),
            has="public facade alias u is shadowed",
        )

    def test_accepts_alias_owned_by_removed_private_import(
        self,
        tmp_path: Path,
    ) -> None:
        """Replace the old import binding with its public facade atomically."""
        consumer_path, private_import, sources = self._facade_case(
            tmp_path,
            FacadeNaming.from_family(
                "models",
                "base",
                "Metadata",
                "m",
            ),
            import_alias="m",
        )
        sources[consumer_path] = f"{private_import}\n\nmetadata = m.Metadata()\n"

        updated = self._updated_source(tmp_path, sources, consumer_path, private_import)

        tm.that(updated, has="from flext_sample import m")
        tm.that(updated, has="metadata = m.Metadata()")
        tm.that(updated, lacks=private_import)

    def test_preserves_type_checking_boundary_for_public_facade(
        self,
        tmp_path: Path,
    ) -> None:
        """Keep a type-only facade import in the original type-only boundary."""
        consumer_path, private_import, sources = self._facade_case(
            tmp_path,
            FacadeNaming.from_family(
                "models",
                "base",
                "Metadata",
                "m",
            ),
            import_alias="m",
        )
        sources[consumer_path] = (
            "from __future__ import annotations\n\n"
            "from typing import TYPE_CHECKING\n\n"
            "if TYPE_CHECKING:\n"
            f"    {private_import}\n\n"
            "metadata: m.Metadata\n"
        )

        updated = self._updated_source(tmp_path, sources, consumer_path, private_import)

        tm.that(updated, has="if TYPE_CHECKING:\n    from flext_sample import m")
        tm.that(updated, lacks="\nfrom flext_sample import m\n")
        tm.that(updated, lacks=private_import)

    def test_preserves_multiple_type_only_facades_from_one_package(
        self,
        tmp_path: Path,
    ) -> None:
        """Rewire every type facade without promoting imports to runtime."""
        package_path = tmp_path / "flext-sample/src/flext_sample"
        consumer_path = tmp_path / "flext-consumer/src/flext_consumer/service.py"
        layers = (
            ("models", "m", "FlextSampleModelsBase", "Model"),
            ("protocols", "p", "FlextSampleProtocolsBase", "Protocol"),
            ("typings", "t", "FlextSampleTypesBase", "Type"),
        )
        sources: t.MutableMappingKV[Path, str] = {}
        private_imports: list[str] = []
        annotations: list[str] = []
        for layer, alias, private_class, nested_class in layers:
            private_module = f"flext_sample._{layer}.base"
            private_imports.append(
                f"from {private_module} import {private_class} as {alias}b",
            )
            sources[package_path / f"{layer}.py"] = self._facade_source(
                naming=FacadeNaming(
                    private_module=private_module,
                    private_class=private_class,
                    root_class=f"FlextSample{layer.title()}",
                    nested_class=nested_class,
                    alias=alias,
                ),
            )
            annotations.append(f"value_{alias}: {alias}b.Member")
        sources[consumer_path] = (
            "from __future__ import annotations\n\n"
            "from typing import TYPE_CHECKING\n\n"
            "if TYPE_CHECKING:\n    "
            + "\n    ".join(private_imports)
            + "\n\n"
            + "\n".join(annotations)
            + "\n"
        )

        updated = self._updated_source(
            tmp_path,
            sources,
            consumer_path,
            *private_imports,
        )

        tm.that(updated, has="    from flext_sample import m, p, t")
        tm.that(updated.count("from flext_sample import"), eq=1)
        for _layer, alias, _private_class, nested_class in layers:
            tm.that(updated, has=f"value_{alias}: {alias}.{nested_class}.Member")
            tm.that(updated, lacks=f"\nfrom flext_sample import {alias}\n")
        for private_import in private_imports:
            tm.that(updated, lacks=private_import)

    def test_discovers_operational_facade_from_live_source(
        self,
        tmp_path: Path,
    ) -> None:
        """Rewire an operational family without a registered family-to-alias map."""
        consumer_path, private_import, sources = self._facade_case(
            tmp_path,
            FacadeNaming.from_family(
                "exceptions",
                "base",
                "Invalid",
                "e",
            ),
            import_alias="eb",
        )
        sources[consumer_path] = f"{private_import}\n\nerror: eb.Code\n"

        updated = self._updated_source(tmp_path, sources, consumer_path, private_import)

        tm.that(updated, has="from flext_sample import e")
        tm.that(updated, has="error: e.Invalid.Code")
        tm.that(updated, lacks=private_import)

    def test_replaces_public_long_alias_during_private_cutover(
        self,
        tmp_path: Path,
    ) -> None:
        """Delete the long public alias while wiring the canonical facade."""
        consumer_path, private_import, sources = self._facade_case(
            tmp_path,
            FacadeNaming.from_family(
                "models",
                "pydantic",
                "Pydantic",
                "m",
            ),
            import_alias="mp",
        )
        sources[consumer_path] = (
            "from __future__ import annotations\n\n"
            f"{private_import}\n\n"
            "from typing import TYPE_CHECKING\n\n"
            "if TYPE_CHECKING:\n"
            "    from flext_sample import FlextSampleModels as m\n\n"
            "value: m.Metadata\n"
            "model: mp.BaseModel\n"
        )

        updated = self._updated_source(tmp_path, sources, consumer_path, private_import)

        tm.that(updated.count("from flext_sample import m"), eq=1)
        tm.that(updated, lacks="FlextSampleModels as m")
        tm.that(updated, lacks=private_import)
        tm.that(updated, has="model: m.Pydantic.BaseModel")

    def test_preserves_valid_relative_private_import(self, tmp_path: Path) -> None:
        """Leave an already-relative same-owner import outside the finding set."""
        consumer_path = tmp_path / "flext-sample/src/flext_sample/service.py"
        relative_import = (
            "from ._models.pydantic import FlextSampleModelsPydantic as mp"
        )

        edits = self._edits(
            tmp_path,
            {consumer_path: f"{relative_import}\n\nmodel = mp.BaseModel\n"},
            consumer_path,
        )

        tm.that(edits, eq=())
