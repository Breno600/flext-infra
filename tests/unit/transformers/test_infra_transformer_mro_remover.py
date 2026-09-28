"""Unit tests for the redundant-inner-namespace remover (ENFORCE-048).

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.transformers.mro_remover import FlextInfraRefactorMroRemover

if TYPE_CHECKING:
    from collections.abc import Sequence

    from tests import t


class TestsFlextInfraTransformersMroRemover:
    """Behavior contract for FlextInfraRefactorMroRemover."""

    def _transform(self, source: str) -> t.Pair[str, Sequence[str]]:
        """Apply the MRO remover to source text."""
        transformer = FlextInfraRefactorMroRemover()
        result: t.Pair[str, Sequence[str]] = transformer.apply_to_source(source)
        return result

    def test_empty_inner_class_reinheriting_outer_is_removed(self) -> None:
        source = "class Outer:\n    class Cli(Outer):\n        pass\n"
        code, changes = self._transform(source)
        tm.that(code, lacks="class Cli")
        tm.that(len(changes), eq=1)

    def test_removal_keeps_the_outer_body_valid(self) -> None:
        source = "class Outer:\n    class Cli(Outer):\n        ...\n"
        code, _changes = self._transform(source)
        compile(code, "<mro-remover>", "exec")

    def test_docstring_only_inner_class_is_removed(self) -> None:
        source = 'class Outer:\n    class Cli(Outer):\n        """Namespace."""\n'
        code, changes = self._transform(source)
        tm.that(code, lacks="class Cli")
        tm.that(len(changes), eq=1)

    def test_inner_class_with_members_is_kept(self) -> None:
        source = "class Outer:\n    class Cli(Outer):\n        VALUE = 1\n"
        code, changes = self._transform(source)
        tm.that(code, eq=source)
        tm.that(not changes, eq=True)

    def test_inner_class_with_a_different_first_base_is_kept(self) -> None:
        source = "class Outer:\n    class Cli(Other):\n        pass\n"
        code, changes = self._transform(source)
        tm.that(code, eq=source)
        tm.that(not changes, eq=True)

    def test_top_level_class_is_never_removed(self) -> None:
        source = "class Outer(Base):\n    pass\n"
        code, changes = self._transform(source)
        tm.that(code, eq=source)
        tm.that(not changes, eq=True)

    def test_surviving_siblings_keep_their_formatting(self) -> None:
        source = (
            "class Outer:\n"
            "    class Cli(Outer):\n"
            "        pass\n"
            "\n"
            "    class Real(Base):\n"
            "        VALUE = 2\n"
        )
        code, _changes = self._transform(source)
        tm.that(code, lacks="class Cli")
        tm.that(code, has="    class Real(Base):\n        VALUE = 2\n")
