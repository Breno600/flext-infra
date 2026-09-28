"""Public runtime evidence for declaration-driven facade repair."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import (
    FlextInfraNamespaceValidator,
    FlextInfraRuntimeAliasDetector,
    infra,
)
from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraRuntimeAliasDeclarations:
    """Keep derived internal declarations tied to real parent classes."""

    @staticmethod
    def _workspace(tmp_path: Path) -> t.Pair[Path, Path]:
        repository, package = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-declarations",
            package_name="flext_declarations",
        )
        (package / "owner.py").write_text(
            "class Parent:\n    class Domain:\n        pass\n\n"
            "capability = Parent\n"
            "__all__ = ['Parent', 'capability']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        return repository, package

    def test_inherited_alias_is_not_a_published_api_binding(
        self, tmp_path: Path
    ) -> None:
        """An API class can inherit a service facade without exporting its alias."""
        repository, package = self._workspace(tmp_path)
        source = package / "api.py"
        source.write_text(
            "from flext_declarations.owner import Parent\n"
            "class Api(Parent):\n    pass\n"
            "__all__ = ['Api']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        with infra.rope_workspace(repository) as rope:
            resource = tm.not_none(rope.resource(source))
            tm.that(
                u.Infra.published_facade_owner(rope.rope_project, resource), none=True
            )
            tm.that(
                u.Infra.publication_policy(
                    source, rope_project=rope.rope_project
                ).expected_alias,
                none=True,
            )

    def test_repair_preserves_actual_mro_and_publishes_local_owner(
        self, tmp_path: Path
    ) -> None:
        # Letters derive only on facade surfaces (ADR-018 tiering), so the
        # drifted module lives in the package root, not an arbitrary tier.
        repository, package = self._workspace(tmp_path)
        source = package / "facets.py"
        source.write_text(
            "from flext_declarations.owner import Parent as Renamed\n\n"
            "class Local(Renamed):\n"
            "    capability = 'nested data must survive'\n\n"
            "__all__: list[str] = [\n    'Local',\n]\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        with infra.rope_workspace(repository) as rope:
            policy = rope.convention(source).module_policy
            findings = FlextInfraRuntimeAliasDetector.detect_file(
                m.Infra.DetectorContext(
                    file_path=source, rope_project=rope.rope_project
                ),
                policy=policy,
            )
            tm.that(len(findings), eq=1)
            tm.that(policy.expected_family, eq="Local")
            tm.that(policy.expected_alias, eq="capability")
            repaired = u.Infra.ensure_runtime_alias(
                source.read_text(encoding=c.Cli.ENCODING_DEFAULT),
                alias=findings[0].alias,
                target_name="Local",
            )
        source.write_text(repaired, encoding=c.Cli.ENCODING_DEFAULT)
        with tm.scope(
            python_paths=[str(repository), str(repository / c.Infra.DEFAULT_SRC_DIR)]
        ):
            module = importlib.import_module("flext_declarations.facets")
            parent = importlib.import_module("flext_declarations.owner")
            tm.that(module.capability is module.Local, eq=True)
            tm.that(module.Local.__bases__, eq=(parent.Parent,))
            tm.that(module.Local.Domain is parent.Parent.Domain, eq=True)
            tm.that(module.Local.capability, eq="nested data must survive")
            tm.that(all(hasattr(module, name) for name in module.__all__), eq=True)
        with infra.rope_workspace(repository) as rope:
            policy = rope.convention(source).module_policy
            tm.that(
                FlextInfraRuntimeAliasDetector.detect_file(
                    m.Infra.DetectorContext(
                        file_path=source, rope_project=rope.rope_project
                    ),
                    policy=policy,
                ),
                eq=[],
            )
            resource = tm.not_none(rope.resource(source))
            layout = tm.not_none(rope.layout(repository))
            tm.that(
                FlextInfraNamespaceValidator.check_structure(
                    u.Infra.resolve_pymodule(rope.rope_project, resource).get_ast(),
                    source.relative_to(repository),
                    class_stem=layout.class_stem,
                    source=repaired,
                    policy=policy,
                ),
                empty=True,
            )
        tm.that(
            u.Infra.ensure_runtime_alias(
                repaired, alias="capability", target_name="Local"
            ),
            eq=repaired,
        )

    def test_ambiguous_parent_aliases_fail_at_semantic_owner(
        self, tmp_path: Path
    ) -> None:
        repository, package = self._workspace(tmp_path)
        (package / "other.py").write_text(
            "class Other:\n    pass\n\n"
            "another = Other\n__all__ = ['Other', 'another']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        # Ambiguity is only declared on a facade surface where the letter
        # must publish (ADR-018 tiering); off-facade modules derive nothing.
        source = package / "facets.py"
        source.write_text(
            "from flext_declarations.owner import Parent\n"
            "from flext_declarations.other import Other\n"
            "class Local(Parent, Other):\n    pass\n"
            "__all__ = ['Local']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        with (
            infra.rope_workspace(repository) as rope,
            pytest.raises(ValueError, match="ambiguous facade declaration"),
        ):
            rope.convention(source)

    def test_explicit_alias_does_not_evaluate_unpublished_imports(
        self, tmp_path: Path
    ) -> None:
        """Local ownership needs neither unrelated imports nor inherited lookup."""
        repository, package = self._workspace(tmp_path)
        initializer = package / c.Infra.INIT_PY
        conflicted = (
            c.Infra.AUTOGEN_HEADERS[0] + "\n<<<<<<< HEAD\n=======\n>>>>>>> incoming\n"
        )
        initializer.write_text(conflicted, encoding=c.Cli.ENCODING_DEFAULT)
        source = package / "facets.py"
        source.write_text(
            "from flext_declarations import Parent, unrelated\n"
            "class Local(Parent):\n    pass\n"
            "capability = Local\n"
            "__all__ = ['Local', 'capability', 'unrelated']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        with infra.rope_workspace(repository) as rope:
            resource = tm.not_none(rope.resource(source))
            tm.that(
                u.Infra.declared_facade_owner(rope.rope_project, resource),
                eq=("capability", "Local"),
            )
            tm.that(
                u.Infra.publication_policy(
                    source, rope_project=rope.rope_project
                ).expected_alias,
                eq="capability",
            )
        tm.that(initializer.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=conflicted)

    def test_local_classes_exclude_imports_and_instance_exports(
        self, tmp_path: Path
    ) -> None:
        """A public API instance and imported bindings are not local class aliases."""
        repository, package = self._workspace(tmp_path)
        (package / c.Infra.INIT_PY).write_text(
            c.Infra.AUTOGEN_HEADERS[0] + "\n<<<<<<< HEAD\n=======\n>>>>>>> incoming\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        source = package / "api.py"
        source.write_text(
            "from typing import TYPE_CHECKING\n"
            "import flext_declarations as imported_package\n"
            "if TYPE_CHECKING:\n    from flext_declarations import p, u\n"
            "class Api:\n    pass\n"
            "api = Api()\n__all__ = ['Api', 'api']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        with infra.rope_workspace(repository) as rope:
            resource = tm.not_none(rope.resource(source))
            tm.that(
                u.Infra.resolve_module_classes(rope.rope_project, resource), eq=("Api",)
            )
            tm.that(
                u.Infra.declared_facade_owner(rope.rope_project, resource), none=True
            )

    def test_api_does_not_republish_inherited_service_alias(
        self, tmp_path: Path
    ) -> None:
        """A root service alias does not become an alias of its API subclass."""
        repository, package = self._workspace(tmp_path)
        (package / c.Infra.INIT_PY).write_text(
            "from .owner import Parent as s\n__all__ = ['s']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        source = package / "api.py"
        source.write_text(
            "from flext_declarations import s\n"
            "class Api(s):\n    pass\n"
            "__all__ = ['Api']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        with infra.rope_workspace(repository) as rope:
            resource = tm.not_none(rope.resource(source))
            tm.that(
                u.Infra.published_facade_owner(rope.rope_project, resource), none=True
            )
            tm.that(
                u.Infra.publication_policy(
                    source, rope_project=rope.rope_project
                ).expected_alias,
                none=True,
            )

    def test_publication_preserves_inherited_settings_without_inventing_alias(
        self, tmp_path: Path
    ) -> None:
        """Generation propagates a declared settings class without resolving its root."""
        repository, package = self._workspace(tmp_path)
        (package / c.Infra.INIT_PY).write_text(
            c.Infra.AUTOGEN_HEADERS[0] + "\n<<<<<<< HEAD\n=======\n>>>>>>> incoming\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tier = repository / "tests"
        tier.mkdir(exist_ok=True)
        source = tier / "settings.py"
        source.write_text(
            "from flext_declarations import Settings\n"
            "class LocalSettings(Settings):\n    pass\n"
            "__all__ = ['LocalSettings']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        with infra.rope_workspace(repository) as rope:
            policy = u.Infra.publication_policy(source, rope_project=rope.rope_project)
            tm.that(policy.expected_family, eq="LocalSettings")
            tm.that(policy.expected_alias, none=True)
            resource = tm.not_none(rope.resource(source))
            tm.that(
                u.Infra.resolve_declared_module_imports(rope.rope_project, resource)[
                    "Settings"
                ],
                eq="flext_declarations.Settings",
            )

    def test_nested_module_does_not_claim_a_facade_letter(self, tmp_path: Path) -> None:
        repository, _ = self._workspace(tmp_path)
        nested = repository / "workflows" / "nested"
        nested.mkdir(parents=True)
        source = nested / "constants.py"
        source.write_text(
            "from flext_declarations.owner import Parent\n"
            "class Local(Parent):\n    pass\n__all__ = ['Local']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        with infra.rope_workspace(repository) as rope:
            policy = rope.convention(source).module_policy
            tm.that(policy.expected_alias, none=True)
            tm.that(
                FlextInfraRuntimeAliasDetector.detect_file(
                    m.Infra.DetectorContext(
                        file_path=source, rope_project=rope.rope_project
                    ),
                    policy=policy,
                ),
                eq=[],
            )

    def test_repair_rejects_a_shared_statement_span(self) -> None:
        """A repair cannot erase another declaration sharing its physical line."""
        source = (
            "class Local:\n    pass\n"
            "capability = None; retained = 1\n"
            "__all__ = ['Local', 'capability']\n"
        )
        with pytest.raises(ValueError, match="shares a source line"):
            u.Infra.ensure_runtime_alias(
                source, alias="capability", target_name="Local"
            )
