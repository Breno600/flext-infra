"""Transport ast-grep JSON replacements to the existing guarded publisher.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

import libcst as cst

from flext_infra import c, m, r, t, u
from flext_infra.codemod._batch_dead_scaffold import _DeadScaffold
from flext_infra.codemod._batch_orphan_import import _OrphanImport
from flext_infra.gates.ruff_format import FlextInfraRuffFormatGate
from flext_infra.transformers import FlextInfraSemanticPublication

if TYPE_CHECKING:
    from flext_infra import p


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
            plan = cls._path_plan(root, path, findings)
            if plan.failure:
                return r[bool].from_failure(plan)
            plans.append(plan.value)
        published = FlextInfraSemanticPublication.publish_semantic_file_plans(
            plans,
            repository_root=root,
        )
        if published.failure:
            return r[bool].from_failure(published)
        return cls._finish_publication(root, tuple(sorted(grouped)))

    @classmethod
    def _path_plan(
        cls,
        root: Path,
        path: Path,
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[m.Infra.SemanticFilePlan]:
        """Validate one path's actionable findings into one publication plan.

        Returns:
            The resulting ``p.Result[m.Infra.SemanticFilePlan]``.

        """
        before = findings[0].source_state
        if before is None or before.content is None:
            return r[m.Infra.SemanticFilePlan].fail(
                f"actionable finding lacks authenticated state: {path}",
            )
        replacements: list[t.Triple[int, int, bytes]] = []
        for finding in findings:
            if finding.source_state != before or finding.replacement is None:
                return r[m.Infra.SemanticFilePlan].fail(
                    f"inconsistent actionable finding source: {path}",
                )
            coordinates = cls._finding_replacement(
                before.content,
                finding,
                finding.replacement,
                path,
            )
            if coordinates.failure:
                return r[m.Infra.SemanticFilePlan].from_failure(coordinates)
            replacements.append(coordinates.value)
        updated = cls._apply_replacements(before.content, replacements, path)
        if updated.failure:
            return r[m.Infra.SemanticFilePlan].from_failure(updated)
        bindings: t.MutableMappingKV[Path, m.Cli.AtomicFileState] = {}
        for finding in findings:
            for state in finding.binding_states:
                if bindings.setdefault(state.path, state) != state:
                    return r[m.Infra.SemanticFilePlan].fail(
                        f"binding snapshots disagree: {state.path}",
                    )
        return r[m.Infra.SemanticFilePlan].ok(
            m.Infra.SemanticFilePlan(
                project=u.Infra.project_root(path) or root,
                path=path,
                before=before,
                desired_content=updated.value,
                desired_mode=before.mode,
                changes=tuple(finding.rule_id for finding in findings),
                source_states=tuple(bindings.values()),
            ),
        )

    @staticmethod
    def _finding_replacement(
        content: bytes,
        finding: m.Infra.ModScanFinding,
        replacement: str,
        path: Path,
    ) -> p.Result[t.Triple[int, int, bytes]]:
        """Validate one finding's byte coordinates against the authenticated bytes.

        Returns:
            The resulting ``(start, end, replacement)`` replacement triple.

        """
        raw_offsets = finding.payload.get("replacementOffsets")
        raw_match = finding.range.get("byteOffset")
        if not isinstance(raw_offsets, Mapping) or not isinstance(raw_match, Mapping):
            return r[t.Triple[int, int, bytes]].fail(
                f"ast-grep finding lacks byte coordinates: {path}:{finding.rule_id}",
            )
        offsets = m.Infra.ModReplacementOffsets.model_validate(raw_offsets)
        matched = m.Infra.ModReplacementOffsets.model_validate(raw_match)
        if not (0 <= offsets.start <= offsets.end <= len(content)) or not (
            0 <= matched.start <= matched.end <= len(content)
        ):
            return r[t.Triple[int, int, bytes]].fail(
                f"ast-grep byte coordinates escape source: {path}",
            )
        if content[matched.start : matched.end] != finding.text.encode(
            c.Cli.ENCODING_DEFAULT,
        ):
            return r[t.Triple[int, int, bytes]].fail(
                f"ast-grep match differs from authenticated source: {path}",
            )
        return r[t.Triple[int, int, bytes]].ok((
            offsets.start,
            offsets.end,
            replacement.encode(c.Cli.ENCODING_DEFAULT),
        ))

    @staticmethod
    def _apply_replacements(
        content: bytes,
        replacements: t.SequenceOf[t.Triple[int, int, bytes]],
        path: Path,
    ) -> p.Result[bytes]:
        """Apply one path's replacements back-to-front, rejecting overlaps.

        Returns:
            The resulting updated content.

        """
        updated = content
        boundary = len(updated)
        for start, end, replacement in sorted(replacements, reverse=True):
            if end > boundary:
                return r[bytes].fail(f"ast-grep replacements overlap: {path}")
            updated = updated[:start] + replacement + updated[end:]
            boundary = start
        return r[bytes].ok(updated)

    @classmethod
    def _finish_publication(
        cls,
        root: Path,
        paths: t.SequenceOf[Path],
    ) -> p.Result[bool]:
        """Normalize imports, strip dead scaffolds, and format the changed paths.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        # AST rewrites can also leave imports whose last reference was removed.

        with u.Infra.open_project(root) as rope_project:
            normalized = u.Infra.normalize_imports(
                rope_project,
                file_paths=tuple(sorted(paths)),
            )
        if normalized.failure:
            return r[bool].from_failure(normalized)
        stripped = cls._strip_dead_type_only_scaffolds(tuple(sorted(paths)))
        if stripped.failure:
            return r[bool].from_failure(stripped)
        formatted = FlextInfraRuffFormatGate.format_files(root, tuple(sorted(paths)))
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
