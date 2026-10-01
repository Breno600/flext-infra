"""Shared edit plumbing for every semantic ``make mod`` cutover planner."""

from __future__ import annotations

import ast
from functools import partial
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesSemanticCutoverEdits:
    """Turn per-module rewrites into edits while keeping every module failure."""

    @staticmethod
    def _editable_sources(
        sources: t.MappingKV[Path, str],
    ) -> t.VariadicTuple[t.Pair[Path, str]]:
        """Return resolved hand-written sources in stable path order."""
        return tuple(
            sorted(
                (path.resolve(), source)
                for path, source in sources.items()
                if not source.startswith(c.Infra.AUTOGEN_HEADERS)
            )
        )

    @staticmethod
    def _finding_statement(finding: m.Infra.ModScanFinding) -> ast.stmt | None:
        """Parse the single statement an ast-grep finding reports."""
        body = ast.parse(finding.text).body
        return body[0] if len(body) == 1 else None

    @staticmethod
    def _semantic_edits(
        items: t.SequenceOf[t.Pair[Path, str]],
        rewrite: Callable[[Path, str], t.Infra.TransformResult],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan one edit per rewritten module and aggregate every module failure.

        A module that cannot be planned yields a failure naming that module;
        the remaining modules are still planned so one run reports them all.
        """
        edits: list[m.Infra.SemanticMigrationEdit] = []
        failures: list[str] = []
        for path, source in items:
            planned = r[t.Infra.TransformResult].create_from_callable(
                partial(rewrite, path, source)
            )
            if planned.failure:
                failures.append(f"{path}: {planned.error}")
                continue
            updated, changes = planned.value
            if updated != source:
                edits.append(
                    m.Infra.SemanticMigrationEdit(
                        file_path=path,
                        original_source=source,
                        updated_source=updated,
                        changes=tuple(changes),
                    )
                )
        result = r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]
        return result.fail("; ".join(failures)) if failures else result.ok(tuple(edits))


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverEdits"]
