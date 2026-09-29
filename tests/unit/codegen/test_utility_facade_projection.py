"""Public evidence for discovery-driven utility-facade projection."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, u


class TestsFlextInfraUtilityFacadeProjection:
    """Exercise consumer-driven owner projection only through ``u.Infra``."""

    @staticmethod
    def _write(path: Path, source: str) -> None:
        """Create one fixture source through the canonical atomic writer."""
        path.parent.mkdir(parents=True, exist_ok=True)
        tm.ok(u.Cli.atomic_write_text_file(path, source))

    @pytest.mark.parametrize(
        ("import_statement", "consumer_name"),
        [
            ("from flext_sample import u", "batch_apply.py"),
            ("from .. import u", "batch_apply.py"),
            ("from ..utilities import u", "batch_apply.py"),
            ("from .. import u", "__init__.py"),
            ("from ..utilities import u", "__init__.py"),
        ],
    )
    def test_projects_only_uniquely_discovered_missing_owner(
        self, tmp_path: Path, import_statement: str, consumer_name: str
    ) -> None:
        """Derive the required owner from the executable public consumer."""
        package = tmp_path / "src" / "flext_sample"
        conflicted = (
            c.Infra.AUTOGEN_HEADERS[0] + "\n<<<<<<< HEAD\n=======\n>>>>>>> incoming\n"
        )
        self._write(package / "__init__.py", conflicted)
        self._write(
            package / "codemod" / consumer_name,
            import_statement + "\n\nu.Sample.plan_cutover()\n",
        )
        self._write(
            package / "_utilities" / "semantic_cutover.py",
            "class FlextSampleUtilitiesSemanticCutover:\n"
            "    @staticmethod\n"
            "    def plan_cutover() -> None:\n"
            "        pass\n",
        )
        facade = package / "utilities.py"
        self._write(
            facade,
            "from upstream import u\n"
            "from flext_sample._utilities.existing import Existing\n\n"
            "class FlextSampleUtilities(u):\n"
            "    class Sample(\n"
            "        Existing,\n"
            "    ):\n"
            "        pass\n\n"
            "u = FlextSampleUtilities\n",
        )
        updated = u.Infra.render_utility_facade(package)

        tm.that(updated is not None, eq=True)
        assert updated is not None
        tm.that(updated, has="from flext_sample._utilities.semantic_cutover import (")
        tm.that(updated.count("FlextSampleUtilitiesSemanticCutover"), eq=2)
        tm.that(
            "FlextSampleUtilitiesSemanticCutover" not in facade.read_text(), eq=True
        )
        tm.that((package / "__init__.py").read_text(), eq=conflicted)

    def test_unresolved_consumer_import_fails_before_projection(
        self, tmp_path: Path
    ) -> None:
        """Unknown provenance is an error, never an empty owner selection."""
        package = tmp_path / "src" / "flext_sample"
        self._write(package / "__init__.py", "")
        self._write(package / "_utilities" / "owner.py", "class Owner:\n    pass\n")
        self._write(
            package / "utilities.py", "class Facade:\n    class Sample:\n        pass\n"
        )
        self._write(
            package / "consumer.py",
            "from nonexistent_facade_owner import u\nu.Sample.required()\n",
        )
        with pytest.raises(ValueError, match="unresolved imported module"):
            u.Infra.render_utility_facade(package)

    def test_rejects_ambiguous_method_ownership(self, tmp_path: Path) -> None:
        """Fail before projection when two local owners claim one method."""
        package = tmp_path / "src" / "flext_sample"
        self._write(package / "__init__.py", "")
        self._write(
            package / "codemod" / "batch_apply.py",
            "from flext_sample import u\n\nu.Sample.plan_cutover()\n",
        )
        for module, class_name in (("first", "First"), ("second", "Second")):
            self._write(
                package / "_utilities" / f"{module}.py",
                f"class {class_name}:\n"
                "    @staticmethod\n"
                "    def plan_cutover() -> None:\n"
                "        pass\n",
            )
        facade = package / "utilities.py"
        original = (
            "from upstream import u\n\n"
            "class FlextSampleUtilities(u):\n"
            "    class Sample(u):\n"
            "        pass\n"
        )
        self._write(facade, original)

        with pytest.raises(ValueError, match=r"ambiguous u\.Sample owner"):
            u.Infra.render_utility_facade(package)
        tm.that(facade.read_text(), eq=original)

    def test_rejects_owners_without_a_public_facade(self, tmp_path: Path) -> None:
        """Utility owners without a facade have no public surface at all."""
        package = tmp_path / "src" / "flext_sample"
        self._write(package / "_utilities" / "owner.py", "class Owner:\n    pass\n")

        with pytest.raises(ValueError, match="have no public facade"):
            u.Infra.render_utility_facade(package)

    def test_empty_owner_directory_needs_no_facade(self, tmp_path: Path) -> None:
        """A preflight-created empty directory is not a private implementation."""
        package = tmp_path / "src" / "flext_sample"
        (package / "_utilities").mkdir(parents=True)
        tm.that(u.Infra.render_utility_facade(package), eq=None)

    @pytest.mark.parametrize("generated", [True, False])
    def test_initializer_ownership_controls_consumer_parsing(
        self, tmp_path: Path, *, generated: bool
    ) -> None:
        """Only generated propagation is excluded from authored consumer analysis."""
        package = tmp_path / "src" / "flext_sample"
        self._write(package / "_utilities" / "owner.py", "class Owner:\n    pass\n")
        original = (
            "from flext_sample._utilities.owner import Owner\n"
            "class Facade:\n    class Domain(Owner):\n        pass\n"
            "u = Facade\n__all__ = ['Facade', 'u']\n"
        )
        self._write(package / "utilities.py", original)
        conflicted = (
            c.Infra.AUTOGEN_HEADERS[0] + "\n" if generated else ""
        ) + "<<<<<<< HEAD\n=======\n>>>>>>> incoming\n"
        initializer = package / c.Infra.INIT_PY
        self._write(initializer, conflicted)

        if generated:
            tm.that(u.Infra.render_utility_facade(package), eq=original)
        else:
            with pytest.raises(SyntaxError):
                u.Infra.render_utility_facade(package)
        tm.that(initializer.read_text(), eq=conflicted)

    def test_facade_without_local_owners_is_complete(self, tmp_path: Path) -> None:
        """A pure re-export facade with no owners directory needs no projection."""
        package = tmp_path / "src" / "flext_sample"
        self._write(package / "utilities.py", "class Owner:\n    pass\n")

        tm.that(u.Infra.render_utility_facade(package), eq=None)

    def test_rejects_unsupported_facade_base_expression(self, tmp_path: Path) -> None:
        """Reject dynamic bases instead of converting them to an empty owner."""
        package = tmp_path / "src" / "flext_sample"
        self._write(
            package / "codemod" / "batch_apply.py",
            "from flext_sample import u\n\nu.Sample.plan_cutover()\n",
        )
        # The facade and its private family exist together in a real package;
        # without the owner directory the renderer stops at the incomplete
        # artifact check and never reaches the base expression under test.
        self._write(
            package / "_utilities" / "semantic_cutover.py",
            "class FlextSampleUtilitiesSemanticCutover:\n"
            "    @staticmethod\n"
            "    def plan_cutover() -> None:\n"
            "        pass\n",
        )
        self._write(
            package / "utilities.py",
            "from upstream import u\n\n"
            "class FlextSampleUtilities(u):\n"
            "    class Sample(owner_factory()):\n"
            "        pass\n",
        )

        with pytest.raises(ValueError, match="unsupported utility facade base"):
            u.Infra.render_utility_facade(package)

    @pytest.mark.parametrize("multiline", [False, True])
    def test_protocol_annotation_projects_owner_and_converges(
        self, tmp_path: Path, *, multiline: bool
    ) -> None:
        """An owned annotation supplies its protocol without changing other code."""
        package = tmp_path / "src" / "flext_sample"
        self._write(package / "__init__.py", "")
        self._write(
            package / "_models" / "payload.py",
            "from flext_sample import p\n"
            "def consume(value: p.Sample.Payload) -> None:\n    pass\n"
            "def foreign(value: p.Other.Unused) -> None:\n    pass\n",
        )
        self._write(
            package / "_protocols" / "payload.py",
            "class PayloadOwner:\n    class Payload:\n        pass\n",
        )
        self._write(
            package / "_protocols" / "unused.py",
            "class UnusedOwner:\n    class Unused:\n        pass\n",
        )
        self._write(package.parent / "foreign_package" / "__init__.py", "p = 0\n")
        self._write(
            package / "foreign_consumer.py",
            "from foreign_package import p\n"
            "def foreign(value: p.Sample.Unused) -> None:\n    pass\n",
        )
        self._write(
            package / "shadowed_consumer.py",
            "from flext_sample import p\n"
            "def parameter(p):\n    return p.Sample.Unused\n"
            "def assigned():\n    p = 0\n    return p.Sample.Unused\n",
        )
        facade = package / "protocols.py"
        header = (
            "    class Sample(\n        p,\n    ):\n"
            if multiline
            else ("    class Sample(p):\n")
        )
        original = (
            "from upstream import p\n\nclass FlextSampleProtocols(p):\n"
            + header
            + "        preserved = 'unchanged'\n\np = FlextSampleProtocols\n"
        )
        self._write(facade, original)

        updated = u.Infra.render_utility_facade(package, family="p")

        assert updated is not None
        ast.parse(updated)
        tm.that(updated, has="from flext_sample._protocols.payload import (")
        tm.that(updated.count("PayloadOwner"), eq=2)
        tm.that("UnusedOwner" in updated, eq=False)
        tm.that(updated, has="        preserved = 'unchanged'")
        tm.that(facade.read_text(), eq=original)
        self._write(facade, updated)
        tm.that(u.Infra.render_utility_facade(package, family="p"), eq=updated)
