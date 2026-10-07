"""Transport ast-grep JSON replacements to the existing guarded publisher.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra.constants
from flext_infra.gates.ruff_format import FlextInfraRuffFormatGate
from flext_infra.models
from flext_infra.transformers import FlextInfraSemanticPublication
from flext_infra.utilities

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraModReplacements:
    """Preserve exact engine rewrites without granting it filesystem effects."""

    @staticmethod
    def generator_owned(
        entries: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> t.StrTuple:
        """Name the findings whose file the canonical generator owns.

        One entry per file and rule; the per-finding detail stays in the mod
        findings report.

        Returns:
            Sorted ``generator:<file>:<rule>`` identities.

        """
        return tuple(
            sorted({
                f"generator:{item.file}:{item.rule_id}"
                for item in entries
                if item.source_owner == "generator"
            }),
        )

    @classmethod
    def require_authored(
        cls,
        entries: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[bool]:
        """Refuse to write generated files: their findings are generator repairs.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        generated = cls.generator_owned(entries)
        if generated:
            return r[bool].fail(
                "generated findings require canonical generator repair: "
                + ", ".join(generated),
            )
        return r[bool].ok(value=True)

    @classmethod
    def publish(cls, root: Path, report: m.Infra.ModScanReport) -> p.Result[bool]:
        """Validate byte coordinates and publish complete CAS-owned file plans.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        allowed = cls.require_authored(
            tuple(finding for finding in report.entries if finding.actionable),
        )
        if allowed.failure:
            return allowed
        grouped: MutableMapping[Path, list[m.Infra.ModScanFinding]] = {}
        for finding in report.entries:
            if finding.actionable:
                grouped.setdefault(root / finding.file, []).append(finding)
        plans: list[m.Infra.SemanticFilePlan] = []
        for path, findings in sorted(grouped.items()):
            before = findings[0].source_state
            if before is None or before.content is None:
                return r[bool].fail(
                    f"actionable finding lacks authenticated state: {path}",
                )
            replacements: list[t.Triple[int, int, bytes]] = []
            for finding in findings:
                if finding.source_state != before or finding.replacement is None:
                    return r[bool].fail(
                        f"inconsistent actionable finding source: {path}",
                    )
                raw_offsets = finding.payload.get("replacementOffsets")
                raw_match = finding.range.get("byteOffset")
                if not isinstance(raw_offsets, Mapping) or not isinstance(
                    raw_match,
                    Mapping,
                ):
                    return r[bool].fail(
                        f"ast-grep finding lacks byte coordinates: "
                        f"{path}:{finding.rule_id}",
                    )
                offsets = m.Infra.ModReplacementOffsets.model_validate(raw_offsets)
                matched = m.Infra.ModReplacementOffsets.model_validate(raw_match)
                if not (
                    0 <= offsets.start <= offsets.end <= len(before.content)
                ) or not (0 <= matched.start <= matched.end <= len(before.content)):
                    return r[bool].fail(
                        f"ast-grep byte coordinates escape source: {path}",
                    )
                if before.content[matched.start : matched.end] != finding.text.encode(
                    c.Cli.ENCODING_DEFAULT,
                ):
                    return r[bool].fail(
                        f"ast-grep match differs from authenticated source: {path}",
                    )
                replacements.append((
                    offsets.start,
                    offsets.end,
                    finding.replacement.encode(c.Cli.ENCODING_DEFAULT),
                ))
            updated = before.content
            boundary = len(updated)
            for start, end, replacement in sorted(replacements, reverse=True):
                if end > boundary:
                    return r[bool].fail(f"ast-grep replacements overlap: {path}")
                updated = updated[:start] + replacement + updated[end:]
                boundary = start
            plans.append(
                m.Infra.SemanticFilePlan(
                    project=u.Infra.project_root(path) or root,
                    path=path,
                    before=before,
                    desired_content=updated,
                    desired_mode=before.mode,
                    changes=tuple(finding.rule_id for finding in findings),
                ),
            )
        published = FlextInfraSemanticPublication.publish_semantic_file_plans(
            plans,
            repository_root=root,
        )
        if published.failure:
            return r[bool].from_failure(published)
        # AST rewrites can also leave imports whose last reference was removed.
        with u.Infra.open_project(root) as rope_project:
            normalized = u.Infra.normalize_imports(
                rope_project,
                file_paths=tuple(sorted(grouped)),
            )
        if normalized.failure:
            return r[bool].from_failure(normalized)
        stripped = FlextInfraModReplacements._strip_dead_type_only_scaffolds(
            tuple(sorted(grouped)),
        )
        if stripped.failure:
            return r[bool].from_failure(stripped)
        formatted = FlextInfraRuffFormatGate.format_files(root, tuple(sorted(grouped)))
        if formatted.failure:
            return r[bool].from_failure(formatted)
        return r[bool].ok(value=True)

    @staticmethod
    def _strip_dead_type_only_scaffolds(paths: t.SequenceOf[Path]) -> p.Result[bool]:
        """Remove ``if TYPE_CHECKING:`` scaffolds whose body an earlier pass emptied.

        Import normalization drops the last real reference inside a type-only
        block and a statement fix leaves ``pass`` behind; the scaffold then
        carries no information. The block is removed and the ``TYPE_CHECKING``
        subjects are left untouched; the following format gate stays the owner
        of any syntax verdict.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        import libcst as cst

        class _DeadScaffold(cst.CSTTransformer):
            """Remove ``if TYPE_CHECKING:`` blocks whose body is only ``pass``."""

            @override
            def leave_If(
                self,
                original_node: cst.If,
                updated_node: cst.If,
            ) -> cst.If | cst.RemovalSentinel:
                test = updated_node.test
                body = updated_node.body
                if isinstance(test, cst.Name) and test.value == "TYPE_CHECKING":
                    statements = (
                        body.body
                        if isinstance(
                            body,
                            cst.SimpleStatementSuite | cst.IndentedBlock,
                        )
                        else ()
                    )
                    if len(statements) == 1 and isinstance(
                        statements[0],
                        cst.SimpleStatementLine,
                    ):
                        inner = statements[0].body
                        if len(inner) == 1 and isinstance(inner[0], cst.Pass):
                            return cst.RemoveFromParent()
                return updated_node

        class _OrphanImport(cst.CSTTransformer):
            """Drop the ``TYPE_CHECKING`` name once its block is gone."""

            @override
            def leave_ImportFrom(
                self,
                original_node: cst.ImportFrom,
                updated_node: cst.ImportFrom,
            ) -> cst.ImportFrom | cst.RemovalSentinel:
                module = updated_node.module
                if not (isinstance(module, cst.Name) and module.value == "typing"):
                    return updated_node
                names = updated_node.names
                if isinstance(names, cst.ImportStar):
                    return updated_node
                kept = tuple(
                    alias
                    for alias in names
                    if not (
                        isinstance(alias.name, cst.Name)
                        and alias.name.value == "TYPE_CHECKING"
                    )
                )
                if len(kept) == len(names):
                    return updated_node
                if not kept:
                    return cst.RemoveFromParent()
                return updated_node.with_changes(names=kept)

        changed = False
        for path in paths:
            if not path.is_file():
                continue
            before = path.read_text(c.Cli.ENCODING_DEFAULT)
            try:
                module = cst.parse_module(before)
            except cst.ParserSyntaxError:
                continue
            stripped = module.visit(_DeadScaffold())
            if stripped.code.count("TYPE_CHECKING") == 1:
                stripped = stripped.visit(_OrphanImport())
            if stripped.code == before:
                continue
            path.write_text(stripped.code, c.Cli.ENCODING_DEFAULT)
            changed = True
        return r[bool].ok(value=changed)


__all__: list[str] = ["FlextInfraModReplacements"]
