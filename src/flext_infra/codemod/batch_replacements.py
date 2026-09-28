"""Transport ast-grep JSON replacements to the existing guarded publisher."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, u
from flext_infra.transformers import publish_semantic_file_plans

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraModReplacements:
    """Preserve exact engine rewrites without granting it filesystem effects."""

    @staticmethod
    def require_authored(report: m.Infra.ModScanReport) -> p.Result[bool]:
        """Retain generator findings as blocking evidence, never writable targets."""
        generated = tuple(
            item for item in report.entries if item.source_owner == "generator"
        )
        if generated:
            details = ", ".join(
                f"generator:{item.file}:{item.rule_id}" for item in generated
            )
            return r[bool].fail(
                f"generated findings require canonical generator repair: {details}"
            )
        return r[bool].ok(True)

    @classmethod
    def publish(cls, root: Path, report: m.Infra.ModScanReport) -> p.Result[bool]:
        """Validate byte coordinates and publish complete CAS-owned file plans."""
        allowed = cls.require_authored(report)
        if allowed.failure:
            return allowed
        grouped: dict[Path, list[m.Infra.ModScanFinding]] = {}
        for finding in report.entries:
            if finding.actionable:
                grouped.setdefault(root / finding.file, []).append(finding)
        plans: list[m.Infra.SemanticFilePlan] = []
        for path, findings in sorted(grouped.items()):
            before = findings[0].source_state
            if before is None or before.content is None:
                return r[bool].fail(
                    f"actionable finding lacks authenticated state: {path}"
                )
            replacements: list[t.Triple[int, int, bytes]] = []
            for finding in findings:
                if finding.source_state != before or finding.replacement is None:
                    return r[bool].fail(
                        f"inconsistent actionable finding source: {path}"
                    )
                raw_offsets = finding.payload.get("replacementOffsets")
                raw_match = finding.range.get("byteOffset")
                if not isinstance(raw_offsets, Mapping) or not isinstance(
                    raw_match, Mapping
                ):
                    return r[bool].fail(
                        f"ast-grep finding lacks byte coordinates: {path}:{finding.rule_id}"
                    )
                offsets = m.Infra.ModReplacementOffsets.model_validate(raw_offsets)
                matched = m.Infra.ModReplacementOffsets.model_validate(raw_match)
                if not (
                    0 <= offsets.start <= offsets.end <= len(before.content)
                ) or not (0 <= matched.start <= matched.end <= len(before.content)):
                    return r[bool].fail(
                        f"ast-grep byte coordinates escape source: {path}"
                    )
                if before.content[matched.start : matched.end] != finding.text.encode(
                    c.Cli.ENCODING_DEFAULT
                ):
                    return r[bool].fail(
                        f"ast-grep match differs from authenticated source: {path}"
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
                )
            )
        published = publish_semantic_file_plans(plans, repository_root=root)
        if published.failure:
            return r[bool].from_failure(published)
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraModReplacements"]
