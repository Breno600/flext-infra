"""Public behavior tests for the Rope workspace DSL service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

import flext_infra
from flext_infra.workspace.rope import FlextInfraRopeWorkspace
from tests import c, m, t, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraInfraRopeService:
    """Validate the public Rope workspace DSL through public methods only."""

    def _demo_module(
        self, tmp_path: Path, module_name: str, source: str
    ) -> t.Pair[Path, Path]:
        """Create one flext-demo workspace and write ``source`` into its module."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / module_name
        module_path.write_text(source, encoding="utf-8")
        return repository_root, module_path

    def _paired_namespace_projects(
        self, root: Path
    ) -> tuple[Path, Path, Path, Path, Path]:
        """Declare two sibling namespace projects and return their roots and modules."""
        project_root, package_root = u.Tests.create_lazy_init_workspace(
            root, project_name="flext-infra", package_name="flext_infra"
        )
        sibling_root, sibling_package_root = u.Tests.create_lazy_init_workspace(
            root, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "models.py"
        u.Tests.write_lazy_init_namespace_module(
            module_path, class_name="FlextInfraModels", alias="m", docstring="Models."
        )
        sibling_module_path = sibling_package_root / "models.py"
        u.Tests.write_lazy_init_namespace_module(
            sibling_module_path,
            class_name="FlextDemoModels",
            alias="m",
            docstring="Models.",
        )
        return (
            project_root,
            package_root,
            module_path,
            sibling_root,
            sibling_module_path,
        )

    def _module_exports(
        self, repository_root: Path, module_path: Path, options: t.JsonMapping
    ) -> t.VariadicTuple[str]:
        """Read one module's public export contract through the Rope workspace."""
        with flext_infra.infra.rope_workspace(repository_root) as rope:
            return tuple(
                rope.exports(
                    module_path,
                    export_options=m.Infra.ExportOptions.model_validate(options),
                )
            )

    def _module_objects_by_name(
        self, repository_root: Path, module_path: Path
    ) -> t.MutableMappingKV[str, m.Infra.Object]:
        """Index one module's non-local objects by their declared name."""
        with flext_infra.infra.rope_workspace(repository_root) as rope:
            return {
                item.name: item
                for item in rope.objects(module_path, include_local_scopes=False)
            }

    @pytest.mark.parametrize(
        ("source", "symbol", "documented"),
        [
            ("from .sibling import Public\n", "Public", False),
            ('class Public:\n    """Public contract."""\n', "Public", True),
            ("class Public:\n    pass\n", "Public", False),
        ],
    )
    def test_source_docstrings_only_resolve_local_definitions(
        self, source: str, symbol: str, *, documented: bool
    ) -> None:
        """Relative reexports require repository context, not source-only lookup."""
        tm.that(u.Infra.symbol_has_docstring_source(source, symbol), eq=documented)

    def test_open_workspace_materializes_snapshot(self, tmp_path: Path) -> None:
        """Public service class exposes one typed workspace snapshot."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        module_path = package_root / "models.py"
        u.Tests.write_lazy_init_namespace_module(
            module_path, class_name="FlextTestsModels", alias="m", docstring="Models."
        )

        rope = FlextInfraRopeWorkspace.open_workspace(repository_root)
        try:
            snapshot_result = rope.execute()
            tm.ok(snapshot_result)
            snapshot = snapshot_result.unwrap()
            tm.that(snapshot.repository_root, eq=repository_root.resolve())
            tm.that(snapshot.workspace_index.package_dirs, has=package_root)
            tm.that(rope.module(module_path), none=False)
            tm.that(rope.package(package_root), none=False)
            exports = rope.exports(
                module_path,
                export_options=m.Infra.ExportOptions.model_validate({
                    "allow_assignments": True
                }),
            )
            tm.that(exports, has="FlextTestsModels")
            tm.that(exports, has="m")
        finally:
            rope.close()

    def test_script_guard_bindings_are_not_exports(self, tmp_path: Path) -> None:
        """A name bound under ``if __name__ == "__main__":`` is not a module export.

        flext-core's examples bound ``result`` and ``msg`` in their script
        blocks; the regenerated package facade re-exported them and every
        importer failed with a missing module attribute.
        """
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        module_path = package_root / "demo.py"
        module_path.write_text(
            '"""Demo."""\n\n'
            "LIMIT = 3\n\n\n"
            "def run() -> int:\n"
            '    """Run."""\n'
            "    return LIMIT\n\n\n"
            'if __name__ == "__main__":\n'
            "    result = run()\n"
            "    if result != LIMIT:\n"
            '        msg = "unexpected"\n'
            "        raise RuntimeError(msg)\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        rope = FlextInfraRopeWorkspace.open_workspace(repository_root)
        try:
            exports = rope.exports(
                module_path,
                export_options=m.Infra.ExportOptions.model_validate({
                    "allow_assignments": True,
                    "allow_functions": True,
                }),
            )
        finally:
            rope.close()

        tm.that(exports, has=["LIMIT", "run"], lacks=["result", "msg"])

    def test_source_exports_preserve_explicit_public_contract(
        self, tmp_path: Path
    ) -> None:
        """Explicit ``__all__`` remains authoritative over implicit symbols."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        module_path = package_root / "public.py"
        module_path.write_text(
            '"""Public contract."""\n\n'
            "from elsewhere import Imported\n\n"
            'PUBLIC = "public"\n'
            'PRIVATE = "private"\n'
            '__all__ = ("PUBLIC",)\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        exports = self._module_exports(
            repository_root,
            module_path,
            {"allow_assignments": True, "allow_functions": True},
        )

        tm.that(exports, eq=("PUBLIC",))

    def test_source_exports_include_conditional_module_assignments(
        self, tmp_path: Path
    ) -> None:
        """Module-control-flow assignments remain visible outside script guards."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        module_path = package_root / "conditional.py"
        module_path.write_text(
            '"""Conditional contract."""\n\n'
            "if TYPE_CHECKING:\n"
            '    MODE = "typing"\n'
            "else:\n"
            '    MODE = "runtime"\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        exports = self._module_exports(
            repository_root, module_path, {"allow_assignments": True}
        )

        tm.that(exports, eq=("MODE",))

    def test_open_workspace_indexes_declared_wrapper_packages(
        self, tmp_path: Path
    ) -> None:
        """Expose examples modules for explicitly targeted semantic codegen."""
        repository_root, _package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        examples_root = repository_root / c.Infra.DIR_EXAMPLES
        examples_root.mkdir()
        examples_root.joinpath(c.Infra.INIT_PY).write_text(
            "", encoding=c.Cli.ENCODING_DEFAULT
        )
        module_path = examples_root / "demo.py"
        module_path.write_text(
            'class ExamplesDemo:\n    """Example boundary."""\n\n'
            '__all__ = ["ExamplesDemo"]\n',
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        with FlextInfraRopeWorkspace.open_workspace(repository_root) as rope:
            tm.that(rope.workspace_index.package_dirs, has=examples_root)
            module = rope.module(module_path)
            tm.that(module, none=False)
            tm.that(
                module.module_name if module is not None else "", eq="examples.demo"
            )

    def test_public_facade_opens_rope_workspace(self, tmp_path: Path) -> None:
        """Public facade returns the same ergonomic Rope workspace DSL."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        module_path = package_root / "models.py"
        u.Tests.write_lazy_init_namespace_module(
            module_path, class_name="FlextTestsModels", alias="m", docstring="Models."
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            state = rope.semantic(module_path)
            tm.that(
                any(
                    class_info.name == "FlextTestsModels"
                    for class_info in state.class_infos
                ),
                eq=True,
            )

    @pytest.mark.parametrize(
        ("family_alias", "module_name"), tuple(c.Infra.FAMILY_PUBLIC_MODULES.items())
    )
    def test_class_nesting_cutover_uses_declared_family_owner(
        self, tmp_path: Path, family_alias: str, module_name: str
    ) -> None:
        """Plan every facade family from semantic objects and its declared owner."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        owner_name = (
            f"{u.derive_class_stem(repository_root.name)}"
            f"{c.Infra.FAMILY_SUFFIXES[family_alias]}"
        )
        extra_class_name = f"{owner_name}Member"
        module_path = package_root / f"{module_name}.py"
        u.Tests.write_lazy_init_namespace_module(
            module_path,
            class_name=owner_name,
            alias=family_alias,
            extra_class_names=(extra_class_name,),
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            owner = rope.convention(module_path).module_policy.expected_family
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources={module_path: module_path.read_text(encoding="utf-8")},
            )

        tm.ok(planned)
        tm.that(len(planned.value), eq=1)
        tm.that(planned.value[0].file_path, eq=module_path.resolve())
        tm.that(
            planned.value[0].changes, eq=(f"nested {extra_class_name} under {owner}",)
        )

    def test_open_workspace_keeps_the_requested_repository_boundary(
        self, tmp_path: Path
    ) -> None:
        """Only an explicit workspace call includes declared sibling repositories."""
        monorepo_root = tmp_path / "repo"
        monorepo_root.mkdir()
        u.Tests.declare_workspace_projects(monorepo_root, ("flext-infra", "flext-demo"))
        (
            repository_root,
            package_root,
            module_path,
            sibling_root,
            sibling_module_path,
        ) = self._paired_namespace_projects(monorepo_root)

        for call_root in (monorepo_root, repository_root, package_root):
            workspace_scope = call_root == monorepo_root
            expected_root = monorepo_root if workspace_scope else repository_root
            expected_projects = {repository_root.resolve()}
            if workspace_scope:
                expected_projects.add(sibling_root.resolve())
            with flext_infra.infra.rope_workspace(call_root) as rope:
                tm.that(rope.rope_repository_root, eq=expected_root.resolve())
                tm.that(
                    {entry.project_root for entry in rope.modules()},
                    eq=expected_projects,
                )
                tm.that(rope.module(module_path), none=False)
                tm.that(rope.module(sibling_module_path), none=not workspace_scope)

    def test_open_standalone_keeps_local_project_scope(self, tmp_path: Path) -> None:
        """Without a workspace context, sibling projects remain outside Rope."""
        projects_root = tmp_path / "projects"
        projects_root.mkdir()
        project_root, package_root, module_path, sibling_root, sibling_module_path = (
            self._paired_namespace_projects(projects_root)
        )

        with flext_infra.infra.rope_workspace(package_root) as rope:
            tm.that(rope.rope_repository_root, eq=project_root.resolve())
            tm.that(
                {entry.project_root for entry in rope.modules()},
                eq={project_root.resolve()},
            )
            tm.that(rope.module(module_path), none=False)
            tm.that(rope.module(sibling_module_path), none=True)
            tm.that(sibling_root in rope.rope_repository_root.parents, eq=False)

    def test_unrelated_ancestor_workspace_does_not_capture_project(
        self, tmp_path: Path
    ) -> None:
        """An ancestor workspace owns only the projects it declares."""
        ancestor = tmp_path / "ancestor"
        ancestor.mkdir()
        declared_root, _ = u.Tests.create_lazy_init_workspace(
            ancestor, project_name="declared", package_name="declared"
        )
        project_root, package_root = u.Tests.create_lazy_init_workspace(
            ancestor / "scratch", project_name="standalone", package_name="standalone"
        )
        u.Tests.declare_workspace_projects(ancestor, (declared_root.name,))

        with flext_infra.infra.rope_workspace(package_root) as rope:
            tm.that(rope.rope_repository_root, eq=project_root.resolve())

    def test_unowned_ancestor_src_does_not_expand_rope_scope(
        self, tmp_path: Path
    ) -> None:
        """Ignore an ancestor source directory that owns no repository."""
        unowned_parent = tmp_path / "unowned"
        scratch = unowned_parent / "scratch"
        (unowned_parent / c.Infra.DEFAULT_SRC_DIR).mkdir(parents=True)
        scratch.mkdir()

        with flext_infra.infra.rope_workspace(scratch) as rope:
            tm.that(rope.rope_repository_root, eq=scratch.resolve())
            tm.that(rope.modules(), eq=())

    def test_workspace_exports_fixture_functions_when_requested(
        self, tmp_path: Path
    ) -> None:
        """Fixture modules can publish pytest fixtures through the Rope DSL."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        fixtures_dir = package_root / "_fixtures"
        fixtures_dir.mkdir()
        fixture_module = fixtures_dir / "settings.py"
        fixture_module.write_text(
            "from __future__ import annotations\n\n"
            "def reset_settings() -> None:\n"
            "    return None\n\n"
            "def settings_factory() -> None:\n"
            "    return None\n",
            encoding="utf-8",
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            exports = rope.exports(
                fixture_module,
                export_options=m.Infra.ExportOptions.model_validate({
                    "allow_functions": True
                }),
            )

        tm.that(exports, has="reset_settings")
        tm.that(exports, has="settings_factory")

    def test_workspace_dsl_centralizes_project_and_module_conventions(
        self, tmp_path: Path
    ) -> None:
        """Public Rope DSL centralizes project discovery and module naming rules."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "models.py"
        u.Tests.write_lazy_init_namespace_module(
            module_path, class_name="FlextDemoModels", alias="m", docstring="Models."
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            projects = rope.projects()
            tm.that(len(projects), eq=1)
            tm.that(projects[0].name, eq="flext-demo")

            layout = rope.layout(repository_root)
            layout = tm.not_none(layout)
            tm.that(layout.project_name, eq="flext-demo")
            tm.that(layout.package_name, eq="flext_demo")
            tm.that(layout.package_alias, eq="demo")
            tm.that(layout.class_stem, eq="FlextDemo")
            tm.that(layout.package_dir, eq=package_root)
            tm.that(layout.runtime_aliases, eq=("m",))

            convention = rope.convention(module_path)
            tm.that(convention.module_name, eq="flext_demo.models")
            tm.that(convention.package_name, eq="flext_demo")
            tm.that(convention.package_context.current_pkg, eq="flext_demo")
            tm.that(convention.module_policy.expected_alias, eq="m")
            project_layout = tm.not_none(convention.project_layout)
            tm.that(project_layout.class_stem, eq="FlextDemo")

    def test_api_module_alias_comes_only_from_declared_exports(
        self, tmp_path: Path
    ) -> None:
        """A root ``api.py`` without a declared alias never gets a synthesized one."""
        repository_root, api_path = self._demo_module(
            tmp_path,
            c.Infra.API_PY,
            '"""Api."""\n\n__all__: list[str] = ["FlextDemo"]\n\n'
            "class FlextDemo:\n    pass\n",
        )
        with flext_infra.infra.rope_workspace(repository_root) as rope:
            layout = tm.not_none(rope.layout(repository_root))
            policy = rope.convention(api_path).module_policy
        tm.that(policy.expected_alias, none=True)
        tm.that(layout.package_alias, ne=policy.expected_alias)

    def test_workspace_dsl_exposes_direct_modules_source_and_objects(
        self, tmp_path: Path
    ) -> None:
        """Public Rope DSL returns direct module inventory through census objects."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "models.py"
        module_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "VALUE = 1\n\n"
                "class FlextDemoModels:\n"
                "    FLAG = VALUE\n\n"
                "    def build(self, payload: int) -> int:\n"
                "        local = payload + VALUE\n\n"
                "        def nested(extra: int) -> int:\n"
                "            return local + extra\n\n"
                "        return nested(1)\n\n"
                "m = FlextDemoModels\n"
            ),
            encoding="utf-8",
        )
        with flext_infra.infra.rope_workspace(repository_root) as rope:
            tm.that(
                any(entry.file_path == module_path for entry in rope.modules()), eq=True
            )
            tm.that(rope.source(module_path), has="class FlextDemoModels")
            objects = {
                (item.scope_path, item.kind): item for item in rope.objects(module_path)
            }
            tm.that(objects.get(("VALUE", "constant")), none=False)
            tm.that(objects.get(("FlextDemoModels", "class")), none=False)
            tm.that(objects.get(("FlextDemoModels.build", "method")), none=False)
            tm.that(
                objects.get(("FlextDemoModels.build.payload", "parameter")), none=False
            )
            tm.that(objects.get(("FlextDemoModels.build.local", "local")), none=False)
            tm.that(
                objects.get(("FlextDemoModels.build.nested", "function")), none=False
            )

    def test_workspace_dsl_reload_refreshes_cached_objects(
        self, tmp_path: Path
    ) -> None:
        """Reload drops Rope caches and reflects updated module objects."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "service.py"
        module_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "def first() -> int:\n"
                "    return 1\n"
            ),
            encoding="utf-8",
        )
        with flext_infra.infra.rope_workspace(repository_root) as rope:
            tm.that({item.name for item in rope.objects(module_path)}, eq={"first"})
            module_path.write_text(
                (
                    "from __future__ import annotations\n\n"
                    "def first() -> int:\n"
                    "    return 1\n\n"
                    "def second() -> int:\n"
                    "    return first()\n"
                ),
                encoding="utf-8",
            )
            rope.reload()
            tm.that(
                {item.name for item in rope.objects(module_path)},
                eq={"first", "second"},
            )

    def test_workspace_refresh_invalidates_source_and_semantic_snapshots(
        self, tmp_path: Path
    ) -> None:
        """Refresh exposes file changes after preserving stable session snapshots."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "service.py"
        original_source = "class Original:\n    pass\n"
        changed_source = "class Changed:\n    pass\n"
        module_path.write_text(original_source, encoding=c.Cli.ENCODING_DEFAULT)

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            original_semantic = rope.semantic(module_path)
            tm.that(rope.source(module_path), eq=original_source)
            tm.that(
                tuple(item.name for item in original_semantic.class_infos),
                eq=("Original",),
            )

            module_path.write_text(changed_source, encoding=c.Cli.ENCODING_DEFAULT)
            tm.that(rope.source(module_path), eq=changed_source)
            tm.that(
                tuple(item.name for item in rope.semantic(module_path).class_infos),
                eq=("Original",),
            )
            tm.that(
                tuple(item.name for item in rope.objects(module_path)), eq=("Original",)
            )

            rope.refresh()
            tm.that(
                tuple(item.name for item in rope.objects(module_path)), eq=("Changed",)
            )

    def test_workspace_refresh_can_preserve_reverted_name_indexes(
        self, tmp_path: Path
    ) -> None:
        """Refresh can retain the text index after preview-style reverted writes."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "service.py"
        original_source = (
            "from __future__ import annotations\n\ndef first() -> int:\n    return 1\n"
        )
        changed_source = (
            "from __future__ import annotations\n\n"
            "def first() -> int:\n"
            "    return 1\n\n"
            "def second() -> int:\n"
            "    return first()\n"
        )
        module_path.write_text(original_source, encoding="utf-8")

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            original_index = rope.name_index()
            tm.that(original_index, has="first")
            tm.that(original_index, lacks="second")

            module_path.write_text(changed_source, encoding="utf-8")
            module_path.write_text(original_source, encoding="utf-8")
            rope.refresh(preserve_indexes=True)

            preserved_index = rope.name_index()
            tm.that(preserved_index is original_index, eq=True)
            tm.that(preserved_index, lacks="second")

            module_path.write_text(changed_source, encoding="utf-8")
            rope.refresh()

            rebuilt_index = rope.name_index()
            tm.that(rebuilt_index is not original_index, eq=True)
            tm.that(rebuilt_index, has="second")

    def test_workspace_objects_raise_on_unparseable_module(
        self, tmp_path: Path
    ) -> None:
        """Unparseable module sources surface instead of an empty module."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "service.py"
        module_path.write_text("def first(:\n", encoding=c.Cli.ENCODING_DEFAULT)

        with (
            flext_infra.infra.rope_workspace(repository_root) as rope,
            pytest.raises(SyntaxError) as parse_error,
        ):
            rope.objects(module_path)

        tm.that(parse_error.value.filename, eq=str(module_path.resolve()))

    def test_workspace_name_index_raises_on_module_read_error(
        self, tmp_path: Path
    ) -> None:
        """Name index failures surface instead of dropping unreadable modules."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "service.py"
        module_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "def public() -> int:\n"
                "    return 1\n"
            ),
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            _ = rope.workspace_index
            module_path.unlink()
            with pytest.raises(
                RuntimeError, match=r"rope name index failed to read .*service\.py"
            ):
                rope.name_index()

    def test_workspace_objects_raise_on_indexed_resource_lookup_error(
        self, tmp_path: Path
    ) -> None:
        """Indexed reference lookup fails when a module resource vanishes."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        service_path = package_root / "service.py"
        service_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "def public() -> int:\n"
                "    return 1\n"
            ),
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        consumer_path = package_root / "consumer.py"
        consumer_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "from flext_demo.service import public\n\n"
                "def consume() -> int:\n"
                "    return public()\n"
            ),
            encoding=c.Cli.ENCODING_DEFAULT,
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            _ = rope.name_index()
            consumer_path.unlink()
            with pytest.raises(
                RuntimeError,
                match=(
                    r"rope search resource unavailable for indexed path "
                    r".*consumer\.py"
                ),
            ):
                rope.objects(service_path, include_local_scopes=False)

    def test_workspace_dsl_ignores_test_references(self, tmp_path: Path) -> None:
        """Tests remain outside production reachability."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "service.py"
        module_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "def only_for_tests(value: int) -> int:\n"
                "    return value + 1\n"
            ),
            encoding="utf-8",
        )
        test_path = repository_root / "tests" / "test_service.py"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "from flext_demo.service import only_for_tests\n\n"
                "def test_only_for_tests_returns_incremented_value() -> None:\n"
                "    assert only_for_tests(1) == 2\n"
            ),
            encoding="utf-8",
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            objects = {
                item.scope_path: item
                for item in rope.objects(module_path, include_local_scopes=False)
            }

        candidate = objects["only_for_tests"]
        tm.that(candidate.references_count, eq=0)
        tm.that(candidate.runtime_references_count, eq=0)
        tm.that(candidate.script_references_count, eq=0)

    def test_workspace_dsl_does_not_classify_legacy_root_facade(
        self, tmp_path: Path
    ) -> None:
        """Legacy root facade declarations are ordinary objects."""
        repository_root, module_path = self._demo_module(
            tmp_path,
            "models.py",
            "from __future__ import annotations\n\n"
            "class FlextDemoModels:\n"
            "    pass\n\n"
            "m = FlextDemoModels\n",
        )

        objects = self._module_objects_by_name(repository_root, module_path)

        tm.that(objects["FlextDemoModels"].is_facade_member, eq=False)
        tm.that(objects["m"].is_facade_member, eq=False)

    def test_workspace_dsl_skips_reference_scan_for_private_names(
        self, tmp_path: Path
    ) -> None:
        """Private and dunder names expose zero production references."""
        repository_root, module_path = self._demo_module(
            tmp_path,
            "service.py",
            "from __future__ import annotations\n\n"
            '__all__: list[str] = ["public"]\n\n'
            "def public() -> int:\n"
            "    return 1\n",
        )

        objects = self._module_objects_by_name(repository_root, module_path)

        tm.that(objects, has="__all__")
        tm.that(objects["__all__"].references_count, eq=0)
        tm.that(objects, has="public")

    def test_workspace_dsl_ignores_example_importers_for_generic_names(
        self, tmp_path: Path
    ) -> None:
        """Examples remain outside production reachability."""
        repository_root, _package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        examples_dir = repository_root / c.Infra.DIR_EXAMPLES
        examples_dir.mkdir(parents=True, exist_ok=True)
        (examples_dir / c.Infra.INIT_PY).write_text(
            "from __future__ import annotations\n", encoding="utf-8"
        )
        producer_path = examples_dir / "producer.py"
        consumer_path = examples_dir / "consumer.py"
        producer_path.write_text(
            ("from __future__ import annotations\n\ndef run() -> int:\n    return 1\n"),
            encoding="utf-8",
        )
        consumer_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "from examples.producer import run\n\n"
                "VALUE = run()\n"
            ),
            encoding="utf-8",
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            objects = {
                item.scope_path: item
                for item in rope.objects(producer_path, include_local_scopes=False)
            }

        candidate = objects["run"]
        tm.that(candidate.references_count, eq=0)
        tm.that(candidate.runtime_references_count, eq=0)
        tm.that(candidate.script_references_count, eq=0)

    def test_workspace_dsl_ignores_example_base_class_references(
        self, tmp_path: Path
    ) -> None:
        """Example inheritance remains outside production reachability."""
        repository_root, _package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        examples_dir = repository_root / c.Infra.DIR_EXAMPLES
        models_dir = examples_dir / "_models"
        models_dir.mkdir(parents=True, exist_ok=True)
        (examples_dir / c.Infra.INIT_PY).write_text(
            "from __future__ import annotations\n", encoding="utf-8"
        )
        (models_dir / c.Infra.INIT_PY).write_text(
            "from __future__ import annotations\n", encoding="utf-8"
        )
        shared_path = models_dir / "shared.py"
        shared_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "class ExampleSharedPerson:\n"
                "    pass\n"
            ),
            encoding="utf-8",
        )
        facade_path = examples_dir / "models.py"
        facade_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "from examples._models.shared import ExampleSharedPerson\n\n"
                "class ExamplesModels:\n"
                "    class Person(ExampleSharedPerson):\n"
                "        pass\n"
            ),
            encoding="utf-8",
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            objects = {
                item.scope_path: item
                for item in rope.objects(shared_path, include_local_scopes=False)
            }

        candidate = objects["ExampleSharedPerson"]
        tm.that(candidate.references_count, eq=0)
        tm.that(candidate.runtime_references_count, eq=0)
        tm.that(candidate.script_references_count, eq=0)

    def test_workspace_dsl_tracks_same_file_references(self, tmp_path: Path) -> None:
        """Same-file uses must block the unused fast-path shortcut."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "service.py"
        module_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "class ExampleService:\n"
                "    pass\n\n"
                "DEFAULT_SERVICE = ExampleService()\n"
            ),
            encoding="utf-8",
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            objects = {
                item.scope_path: item
                for item in rope.objects(module_path, include_local_scopes=False)
            }

        candidate = objects["ExampleService"]
        tm.that(candidate.references_count, eq=1)
        tm.that(candidate.runtime_references_count, eq=1)
        tm.that(candidate.script_references_count, eq=0)
        tm.that(
            {site.file_path for site in candidate.runtime_reference_sites},
            eq={str(module_path)},
        )
        tm.that([site.line for site in candidate.runtime_reference_sites], eq=[6])
