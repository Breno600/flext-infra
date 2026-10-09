"""Plan the module-layout moves the catalog's layout rules report.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from collections import defaultdict
from typing import TYPE_CHECKING

from flext_infra import m, t
from flext_infra._utilities._semantic_cutover.edits import (
    FlextInfraUtilitiesSemanticCutoverEdits,
)
from flext_infra._utilities.lint_recipes import FlextInfraUtilitiesLintRecipes
from flext_infra._utilities.rope_source import FlextInfraUtilitiesRopeSource

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesSemanticCutoverModuleLayout(
    FlextInfraUtilitiesSemanticCutoverEdits,
):
    """Close each reported module with its exports and its docstring notice."""

    @classmethod
    def _plan_module_end(
        cls,
        root: Path,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Move each reported top-level statement after the module's last one.

        A finding names its statement by the text the rule matched, so the
        statement is found again in the working source after earlier phases.

        Returns:
            One edit per module whose reported statements do not close it.

        """
        selected: MutableMapping[Path, set[str]] = defaultdict(set)
        for finding in findings:
            selected[(root / finding.file).resolve()].add(finding.text)

        def rewrite(path: Path, source: str) -> t.Infra.TransformResult:
            body = ast.parse(source, filename=str(path)).body
            moving = [
                node
                for node in body
                if ast.get_source_segment(source, node) in selected[path]
            ]
            if not moving or moving == body[-len(moving) :]:
                return source, ()
            updated = FlextInfraUtilitiesRopeSource.statements_at_module_end(
                source,
                tuple((node.lineno, node.end_lineno or node.lineno) for node in moving),
                filename=str(path),
            )
            return updated, ("moved the declared exports to the module end",)

        return cls._semantic_edits(
            tuple(
                item for item in cls._editable_sources(sources) if item[0] in selected
            ),
            rewrite,
        )

    @classmethod
    def _plan_notice_last(
        cls,
        root: Path,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Move each reported docstring's notice paragraph after its other text.

        Returns:
            One edit per module whose notice does not close its docstring.

        """
        selected = {(root / finding.file).resolve() for finding in findings}

        def rewrite(path: Path, source: str) -> t.Infra.TransformResult:
            updated = FlextInfraUtilitiesLintRecipes.notice_last(source, path=path)
            return updated, ("moved the copyright notice to the docstring end",)

        return cls._semantic_edits(
            tuple(
                item for item in cls._editable_sources(sources) if item[0] in selected
            ),
            rewrite,
        )


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverModuleLayout"]
