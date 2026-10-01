"""Unit tests for the future-import enforcement transformer.

The other enforcement rewrites (open encoding, hardcoded version, redundant
inner namespace, compatibility aliases, typing Dict) are ast-grep rules applied
by ``make mod``; their behavior is proven by the codemod rule tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.transformers.future_import import FlextInfraRefactorFutureImport
from tests import t

if TYPE_CHECKING:
    from collections.abc import Sequence


class TestsFlextInfraTransformersEnforcementFixers:
    """Behavior contract for the future-import enforcement transformer."""

    def _transform(
        self, source: str, transformer: FlextInfraRefactorFutureImport
    ) -> t.Pair[str, Sequence[str]]:
        """Apply a stateless transformer to source text."""
        result: t.Pair[str, Sequence[str]] = transformer.apply_to_source(source)
        return result

    def test_future_import_already_present_is_unchanged(self) -> None:
        """Verify future import already present is unchanged."""
        for source in (
            "from __future__ import annotations\n\nx = 1\n",
            '"""Module."""\n\nfrom __future__ import annotations\n\n\nclass Owner:\n    pass\n',
            '"""Module."""\nfrom __future__ import annotations\nx = 1\n',
        ):
            code, changes = self._transform(source, FlextInfraRefactorFutureImport())
            tm.that(code, eq=source)
            tm.that(changes, eq=[])

    def test_future_import_inserted_at_top_when_absent(self) -> None:
        """Verify future import inserted at top when absent."""
        source = "x = 1\n"
        code, changes = self._transform(source, FlextInfraRefactorFutureImport())
        tm.that(code, eq="from __future__ import annotations\nx = 1\n")
        tm.that(changes, empty=False)

    def test_future_import_inserted_after_shebang_and_comments(self) -> None:
        """Verify future import inserted after shebang and comments."""
        source = (
            "#!/usr/bin/env python3\n"
            "# -*- coding: utf-8 -*-\n"
            "# leading comment\n"
            "\n"
            "x = 1\n"
        )
        code, changes = self._transform(source, FlextInfraRefactorFutureImport())
        expected = (
            "#!/usr/bin/env python3\n"
            "# -*- coding: utf-8 -*-\n"
            "# leading comment\n"
            "\n"
            "from __future__ import annotations\n"
            "x = 1\n"
        )
        tm.that(code, eq=expected)
        tm.that(changes, empty=False)

    def test_future_import_normalizes_duplicate_before_docstring(self) -> None:
        """Verify future import normalizes duplicate before docstring."""
        source = (
            "from __future__ import annotations\n"
            '"""Module docstring."""\n'
            "\n"
            "from __future__ import annotations\n"
            "\n"
            "import os\n"
        )
        code, changes = self._transform(source, FlextInfraRefactorFutureImport())
        expected = (
            '"""Module docstring."""\n'
            "\n"
            "from __future__ import annotations\n"
            "\n"
            "import os\n"
        )
        tm.that(code, eq=expected)
        tm.that(changes, empty=False)
