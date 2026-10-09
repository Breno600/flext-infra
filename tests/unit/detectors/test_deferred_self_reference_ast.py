"""Behavior contract for the deferred-self-reference normalizer.

Detection is rule data (``ban-deferred-self-reference`` and
``ban-recursive-model``, with their ast-grep fixtures); this module covers the
semantic repair the mod phase applies.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pytest
from flext_tests import tm

from flext_infra import u


class TestsFlextInfraDeferredSelfReferenceNormalizer:
    """Behavior contract for the deferred-self-reference normalizer."""

    @staticmethod
    def test_public_normalizer_qualifies_sibling_annotations_without_reordering() -> (
        None
    ):
        """Sibling annotations use the owner while declaration order stays stable."""
        source = (
            "from __future__ import annotations\n\n"
            "class Models:\n"
            "    class Consumer:\n"
            "        dependency: Dependency\n\n"
            "        def runtime(self) -> object:\n"
            "            return Models.Dependency()\n\n"
            "    class Dependency:\n"
            "        pass\n"
        )
        normalized = u.Infra.normalize_deferred_self_references(source)
        tm.that(
            normalized.index("    class Consumer:"),
            lt=normalized.index("    class Dependency:"),
        )
        tm.that(normalized, has="dependency: Models.Dependency")
        tm.that(normalized, has="return Models.Dependency()")

    @staticmethod
    def test_public_normalizer_ignores_a_nested_models_own_return_type() -> None:
        """A method returning its enclosing nested model is not a graph edge."""
        source = (
            "class Models:\n"
            "    class Target:\n"
            "        @classmethod\n"
            "        def create(cls) -> Target:\n"
            "            return cls()\n\n"
            "    class Other:\n"
            "        pass\n"
        )
        tm.that(u.Infra.normalize_deferred_self_references(source), eq=source)

    @staticmethod
    def test_public_normalizer_restores_executable_nested_class_bases() -> None:
        """A nested base resolves from the active owner namespace at definition time."""
        source = (
            "class Models:\n"
            "    class Base:\n"
            "        pass\n\n"
            "    class Child(Models.Base):\n"
            "        pass\n"
        )
        normalized = u.Infra.normalize_deferred_self_references(source)
        tm.that(normalized, has="class Child(Base):")
        tm.that("class Child(Models.Base):" not in normalized, eq=True)

    @staticmethod
    def test_public_normalizer_rejects_ambiguous_owners_and_model_rebuild() -> None:
        """Unknown owner members and runtime schema repair fail loud."""
        ambiguous = (
            "class Models:\n"
            "    class First:\n"
            "        value: Models.Missing\n\n"
            "    class Second:\n"
            "        pass\n"
        )
        rebuild = "class Model:\n    pass\n\nModel.model_rebuild()\n"
        with pytest.raises(ValueError, match="ambiguous self-qualified annotation"):
            u.Infra.normalize_deferred_self_references(ambiguous)
        with pytest.raises(ValueError, match="model_rebuild is prohibited"):
            u.Infra.normalize_deferred_self_references(rebuild)

    @staticmethod
    def test_public_normalizer_preserves_inherited_owner_annotations() -> None:
        """An inherited public type need not be redeclared in the local facade."""
        source = (
            "from __future__ import annotations\n\n"
            "class Base:\n"
            "    class Target:\n"
            "        pass\n\n"
            "class Models(Base):\n"
            "    class Consumer:\n"
            "        value: Models.Target\n"
        )
        tm.that(u.Infra.normalize_deferred_self_references(source), eq=source)

    @staticmethod
    @pytest.mark.parametrize(
        "declaration",
        [
            '_Kind = Literal["one", "two"]',
            '_Kind: TypeAlias = Literal["one", "two"]',
            'type _Kind = Literal["one", "two"]',
        ],
    )
    def test_public_normalizer_accepts_declared_owner_aliases(
        declaration: str,
    ) -> None:
        """An existing qualified alias must not block unrelated sibling repairs."""
        source = (
            "from __future__ import annotations\n"
            "from typing import Annotated, Literal, TypeAlias\n\n"
            "class Models:\n"
            f"    {declaration}\n"
            "    class Dependency:\n"
            "        pass\n"
            "    class Consumer:\n"
            "        kind: Annotated[Models._Kind, 'category']\n"
            "        dependency: Dependency\n"
        )
        normalized = u.Infra.normalize_deferred_self_references(source)

        tm.that(
            normalized,
            eq=source.replace(
                "dependency: Dependency",
                "dependency: Models.Dependency",
            ),
        )
        tm.that(u.Infra.normalize_deferred_self_references(normalized), eq=normalized)

    @staticmethod
    def test_public_normalizer_does_not_qualify_bare_assignment_bindings() -> None:
        """Recognizing a member does not turn every class attribute into a type."""
        source = (
            "from __future__ import annotations\n\n"
            "class Models:\n"
            "    int = 1\n"
            "    class Consumer:\n"
            "        value: int\n"
        )

        tm.that(u.Infra.normalize_deferred_self_references(source), eq=source)

    @staticmethod
    @pytest.mark.parametrize(
        "declaration",
        ["_Kind: object", "class Other:\n        _Kind = str"],
    )
    def test_public_normalizer_rejects_unbound_or_foreign_owner_members(
        declaration: str,
    ) -> None:
        """An annotation-only slot or another class's member is not an owner binding."""
        source = (
            "from __future__ import annotations\n\n"
            "class Models:\n"
            f"    {declaration}\n"
            "    class Consumer:\n"
            "        kind: Models._Kind\n"
        )

        with pytest.raises(ValueError, match="ambiguous self-qualified annotation"):
            u.Infra.normalize_deferred_self_references(source)
