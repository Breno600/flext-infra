"""Runtime behavior tests for generated lazy package artifacts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import infra
from tests import c, t, u


class TestsFlextInfraLazyInitRuntime:
    """Exercise generated roots through Python's real import machinery."""

    @staticmethod
    def test_pytest_private_source_is_not_reintroduced_by_typing_projection(
        tmp_path: Path,
    ) -> None:
        """Test pytest private source is not reintroduced by typing projection."""
        repository, _ = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-fixtures",
            package_name="flext_fixtures",
        )
        package = repository / "tests" / "unit"
        package.mkdir(parents=True, exist_ok=True)
        (package / c.Infra.INIT_PY).write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        (package / "support.py").write_text(
            "class PublishedSupport:\n    pass\n__all__ = ['PublishedSupport']\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        conftest = package / "conftest.py"
        private_source = "pytest_plugins = []\n__all__ = ['pytest_plugins']\n"
        conftest.write_text(private_source, encoding=c.Cli.ENCODING_DEFAULT)

        tm.that(u.Tests.run_lazy_init(repository), eq=0)

        generated = (package / c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tm.that(generated, has="PublishedSupport")
        tm.that(generated, lacks="pytest_plugins")
        tm.that(conftest.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=private_source)

    @staticmethod
    def _generate_package(tmp_path: Path) -> t.Pair[Path, Path]:
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-lazy-demo",
            package_name="flext_lazy_demo",
        )
        package_root.joinpath("api.py").write_text(
            "from pathlib import Path\n"
            "COUNTER = Path(__file__).with_name('imports.txt')\n"
            "COUNTER.write_text("
            "COUNTER.read_text() + 'x' if COUNTER.exists() else 'x')\n"
            "class FlextDemo:\n    pass\n"
            "primary = FlextDemo\n"
            "__all__ = ('FlextDemo', 'primary')\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        return repository_root, package_root

    def test_generated_root_preserves_lazy_runtime_contract(
        self,
        tmp_path: Path,
    ) -> None:
        """Test generated root preserves lazy runtime contract."""
        repository_root, package_root = self._generate_package(tmp_path)
        with tm.scope(python_paths=[str(repository_root / c.Infra.DEFAULT_SRC_DIR)]):
            package = importlib.import_module("flext_lazy_demo")

            tm.that("flext_lazy_demo.api" in sys.modules, eq=False)
            tm.that(package.__all__, eq=("FlextDemo", "primary"))
            tm.that(dir(package), eq=list(package.__all__))
            first = package.FlextDemo
            second = package.FlextDemo
            tm.that(first is second, eq=True)
            tm.that(package.primary is first, eq=True)
            tm.that(package_root.joinpath("imports.txt").read_text(), eq="x")

    @staticmethod
    def test_generated_root_never_invents_undeclared_api_alias(
        tmp_path: Path,
    ) -> None:
        """Test generated root never invents undeclared api alias."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-bare",
            package_name="flext_bare",
        )
        package_root.joinpath("api.py").write_text(
            "class FlextBare:\n    pass\n__all__ = ('FlextBare',)\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        with tm.scope(python_paths=[str(repository_root / c.Infra.DEFAULT_SRC_DIR)]):
            package = importlib.import_module("flext_bare")
            tm.that(package.__all__, eq=("FlextBare",))
            tm.that(
                [name for name in package.__all__ if not hasattr(package, name)],
                eq=[],
            )

    @staticmethod
    def test_generated_model_alias_preserves_mro_and_pydantic_roundtrip(
        tmp_path: Path,
    ) -> None:
        """Resolve deferred annotations through the generated public model alias."""
        repository, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-runtime-model",
            package_name="flext_runtime_model",
        )
        package_root.joinpath("models.py").write_text(
            "from __future__ import annotations\n"
            "from flext_core import FlextModels\n"
            "class FlextRuntimeModels(FlextModels):\n"
            "    class Payload(FlextModels.ContractModel):\n"
            '        count: int = FlextModels.Field(description="Payload count.")\n'
            "m = FlextRuntimeModels\n"
            "__all__ = ('FlextRuntimeModels', 'm')\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tm.that(u.Tests.run_lazy_init(repository), eq=0)
        probe = (
            "import sys\n"
            "from flext_core import FlextModels, e\n"
            "import flext_runtime_model as package\n"
            "print('flext_runtime_model.models' not in sys.modules)\n"
            "models = package.m\n"
            "print(models is package.FlextRuntimeModels is package.m)\n"
            "print(issubclass(models, FlextModels))\n"
            "payload = models.Payload.model_validate({'count': 7})\n"
            "print(payload.count == 7)\n"
            "print(models.Payload.model_validate_json(payload.model_dump_json())"
            " == payload)\n"
            "try:\n"
            "    models.Payload.model_validate({'count': 'invalid'})\n"
            "except e.PydanticValidationError as error:\n"
            "    print('count' in str(error))\n"
            "print(dir(package) == list(package.__all__))\n"
        )
        tm.that(
            u.Tests.run_lazy_init_probe(
                probe,
                python_paths=(str(repository / c.Infra.DEFAULT_SRC_DIR),),
            ),
            eq=["True"] * 7,
        )

    @staticmethod
    @pytest.mark.parametrize("same_named_export", [False, True])
    def test_child_package_preserves_export_ownership(
        tmp_path: Path,
        *,
        same_named_export: bool,
    ) -> None:
        """Child packages resolve as modules; competing public owners fail loud."""
        repository, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-child-runtime",
            package_name="flext_child_runtime",
        )
        child = package_root / "child"
        child.mkdir()
        (child / c.Infra.INIT_PY).write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        (child / "api.py").write_text(
            "class PublishedChild:\n    pass\n"
            + (
                "child = PublishedChild\n__all__ = ('PublishedChild', 'child')\n"
                if same_named_export
                else "__all__ = ('PublishedChild',)\n"
            ),
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        if same_named_export:
            with pytest.raises(RuntimeError, match="ownership is ambiguous"):
                u.Tests.run_lazy_init(repository)
            return
        tm.that(u.Tests.run_lazy_init(repository), eq=0)
        probe = (
            "import flext_child_runtime as package\n"
            "import flext_child_runtime.child as child\n"
            "print(package.child is child)\n"
            "print(package.PublishedChild is child.PublishedChild)\n"
        )
        tm.that(
            u.Tests.run_lazy_init_probe(
                probe,
                python_paths=(str(repository / c.Infra.DEFAULT_SRC_DIR),),
            ),
            eq=["True", "True"],
        )

    @staticmethod
    def test_empty_package_preserves_its_unmanaged_initializer(tmp_path: Path) -> None:
        """No published declarations means no generated root contract is invented."""
        repository, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-empty-runtime",
            package_name="flext_empty_runtime",
        )
        package_root.joinpath("api.py").write_text(
            "__all__ = ()\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        initializer = package_root / c.Infra.INIT_PY
        original = initializer.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        tm.that(u.Tests.run_lazy_init(repository), eq=0)
        tm.that(initializer.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=original)
        probe = (
            "import flext_empty_runtime as package\n"
            "print(not hasattr(package, '__all__'))\n"
            "try:\n"
            "    package.undeclared\n"
            "except AttributeError as error:\n"
            "    print('undeclared' in str(error))\n"
        )
        tm.that(
            u.Tests.run_lazy_init_probe(
                probe,
                python_paths=(str(repository / c.Infra.DEFAULT_SRC_DIR),),
            ),
            eq=["True", "True"],
        )

    @staticmethod
    def test_generated_root_preserves_import_failures(tmp_path: Path) -> None:
        """Test generated root preserves import failures."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-failure",
            package_name="flext_failure",
        )
        package_root.joinpath("api.py").write_text(
            "raise ModuleNotFoundError('missing runtime dependency')\n"
            "class FlextDemo:\n    pass\n"
            "__all__ = ('FlextDemo',)\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        tm.that(u.Tests.run_lazy_init(repository_root), eq=0)
        with tm.scope(python_paths=[str(repository_root / c.Infra.DEFAULT_SRC_DIR)]):
            package = importlib.import_module("flext_failure")

            with pytest.raises(ModuleNotFoundError, match="missing runtime dependency"):
                _ = package.FlextDemo

    @staticmethod
    def test_conflicted_generated_initializer_is_rebuilt_from_declarations(
        tmp_path: Path,
    ) -> None:
        """Generated bytes are outputs, including while a merge is unresolved."""
        repository, package = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-rebuilt",
            package_name="flext_rebuilt",
        )
        declaration = package / "models.py"
        u.Tests.write_lazy_init_namespace_module(
            declaration,
            class_name="FlextRebuiltModels",
            alias="m",
            docstring="Models.",
        )
        tm.that(u.Tests.run_lazy_init(repository), eq=0)
        initializer = package / c.Infra.INIT_PY
        canonical = initializer.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        conflicted = canonical + (
            "\n<<<<<<< HEAD\n__all__ = ['stale']\n"
            "=======\n__all__ = ['obsolete']\n>>>>>>> incoming\n"
        )
        initializer.write_text(conflicted, encoding=c.Cli.ENCODING_DEFAULT)
        with infra.rope_workspace(repository) as rope:
            layout = tm.not_none(rope.layout(repository))
            tm.that(layout.runtime_aliases, eq=("m",))
        tm.that(initializer.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=conflicted)

        tm.that(u.Tests.run_lazy_init(repository), eq=0)

        tm.that(initializer.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=canonical)
        with tm.scope(python_paths=[str(repository / c.Infra.DEFAULT_SRC_DIR)]):
            generated = importlib.import_module("flext_rebuilt")
            declared = importlib.import_module("flext_rebuilt.models")
            tm.that(generated.m is declared.FlextRebuiltModels, eq=True)
            tm.that(
                all(hasattr(generated, name) for name in generated.__all__),
                eq=True,
            )
        declaration.write_text(
            "<<<<<<< HEAD\n=======\n>>>>>>> incoming\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        with infra.rope_workspace(repository) as rope, pytest.raises(SyntaxError):
            rope.layout(repository)

    @staticmethod
    def test_internal_facade_requires_its_local_declaration(
        tmp_path: Path,
    ) -> None:
        """An undeclared letter propagates the declaring root's binding.

        Operator ruling (tier-alias propagation): a module declaring the
        letter wins. A facet that declares no letter inherits the root's
        declared letter, and the generator never rewrites the facet to
        substitute a local class for it.
        """
        repository, package = u.Tests.create_lazy_init_workspace(
            tmp_path,
            project_name="flext-local",
            package_name="flext_local",
        )
        package.joinpath("constants.py").write_text(
            "class Parent:\n    class Domain:\n        pass\n"
            "c = Parent\n__all__ = ('Parent', 'c')\n",
            encoding=c.Cli.ENCODING_DEFAULT,
        )
        examples = repository / "examples"
        examples.mkdir()
        examples.joinpath("__init__.py").write_text("", encoding=c.Cli.ENCODING_DEFAULT)
        facet = examples / "constants.py"
        facet_source = (
            "from flext_local.constants import Parent\n"
            "class Local(Parent):\n    pass\n__all__ = ('Local',)\n"
        )
        facet.write_text(facet_source, encoding=c.Cli.ENCODING_DEFAULT)
        tm.that(u.Tests.run_lazy_init(repository), eq=0)
        # The facet declares no letter, so the generator leaves it untouched:
        # no runtime-alias repair may invent a local binding for one.
        tm.that(facet.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=facet_source)
        exports = u.Infra.public_export_names_source(
            examples.joinpath("__init__.py").read_text(encoding=c.Cli.ENCODING_DEFAULT),
        )
        tm.that("c" in exports, eq=True)
        probe = (
            "import examples as generated\n"
            "import examples.constants as local\n"
            "import flext_local.constants as parent\n"
            "print('c' in generated.__all__)\n"
            "print(generated.c is parent.c)\n"
            "print(generated.c is parent.Parent)\n"
            "print(generated.c is local.Local)\n"
            "print(all(hasattr(generated, name) for name in generated.__all__))\n"
        )
        tm.that(
            u.Tests.run_lazy_init_probe(
                probe,
                python_paths=(
                    str(repository),
                    str(repository / c.Infra.DEFAULT_SRC_DIR),
                    *sys.path,
                ),
                cwd=repository,
            ),
            eq=["True", "True", "True", "False", "True"],
        )
