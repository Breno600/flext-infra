"""Refactor helper utilities for infrastructure code analysis.

Centralizes rope-based helpers previously defined as module-level
functions in ``flext_infra.refactor.analysis``.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path

from flext_cli import r, u

from flext_infra import c, m, p, t


class FlextInfraUtilitiesRefactor:
    """Rope-based refactor helpers for code analysis.

    Usage via namespace::

        from flext_infra import u

        methods = u.Infra.extract_public_methods_from_dir(package_dir)
    """

    @staticmethod
    def string_list(value: t.JsonValue | None) -> t.StrSequence:
        """Normalize policy fields that should contain string collections."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        validated: p.Result[t.StrSequence] = u.validate_value(
            t.Infra.STR_SEQ_ADAPTER, value
        )
        if validated.failure:
            msg = f"expected list value: {validated.error}"
            raise TypeError(msg) from validated.exception
        return list(validated.value)

    @staticmethod
    def normalize_module_path(path_value: str | Path) -> str:
        """Normalize module path."""
        path = Path(str(path_value).replace("\\", "/"))
        parts = path.parts
        if c.Infra.DEFAULT_SRC_DIR in parts:
            src_index = parts.index(c.Infra.DEFAULT_SRC_DIR)
            suffix = parts[src_index + 1 :]
            if suffix:
                return Path(*suffix).as_posix()
        return path.as_posix().lstrip("./")

    @staticmethod
    def write_impact_map(
        results: t.SequenceOf[m.Infra.Result], output_path: Path
    ) -> p.Result[bool]:
        """Write refactor impact map JSON to disk."""
        payload = {
            "files": [
                {
                    "path": str(item.file_path),
                    "success": item.success,
                    "modified": item.modified,
                    "error": item.error,
                    "changes": list(item.changes),
                }
                for item in results
            ]
        }
        normalized_payload: t.JsonValue = t.Cli.JSON_VALUE_ADAPTER.validate_python(
            payload
        )
        write_result = u.Cli.json_write(output_path, normalized_payload)
        if write_result.failure:
            return r[bool].from_failure(write_result)
        return r[bool].ok(True)

    @staticmethod
    def publish_mod_scan_evidence(
        root: Path,
        report: m.Infra.ModScanReport,
        *,
        command: c.Infra.ModScanCommand,
        scope: t.StrSequence,
    ) -> p.Result[m.Infra.ModScanEvidenceReceipt]:
        """Atomically replace the complete structured evidence for one mod scan."""
        classified = (
            report.actionable + report.detection_only + report.non_actionable_with_fix
        )
        if classified != report.findings or report.findings != len(report.entries):
            return r[m.Infra.ModScanEvidenceReceipt].fail(
                "mod scan classification invariant failed: "
                f"findings={report.findings} entries={len(report.entries)} "
                f"classified={classified}"
            )
        repository_totals: MutableMapping[str, int] = {}
        rule_totals: MutableMapping[str, int] = {}
        class_totals: MutableMapping[c.Infra.ModScanFindingClass, int] = dict.fromkeys(
            c.Infra.ModScanFindingClass, 0
        )
        for finding in report.entries:
            repository_totals[finding.repository] = (
                repository_totals.get(finding.repository, 0) + 1
            )
            rule_totals[finding.rule_id] = rule_totals.get(finding.rule_id, 0) + 1
            class_totals[finding.classification] += 1
        expected_class_totals = {
            c.Infra.ModScanFindingClass.ACTIONABLE: report.actionable,
            c.Infra.ModScanFindingClass.DETECTION_ONLY: report.detection_only,
            c.Infra.ModScanFindingClass.NON_ACTIONABLE_WITH_FIX: (
                report.non_actionable_with_fix
            ),
        }
        if class_totals != expected_class_totals:
            return r[m.Infra.ModScanEvidenceReceipt].fail(
                "mod scan entry classification differs from report totals: "
                f"entries={class_totals} report={expected_class_totals}"
            )
        evidence = m.Infra.ModScanEvidence(
            schema_version=c.Infra.MOD_SCAN_REPORT_SCHEMA_VERSION,
            command=command,
            root=root.resolve(),
            scope=tuple(scope),
            findings=report.findings,
            actionable=report.actionable,
            detection_only=report.detection_only,
            non_actionable_with_fix=report.non_actionable_with_fix,
            totals_by_class=class_totals,
            totals_by_repository=dict(sorted(repository_totals.items())),
            totals_by_rule=dict(sorted(rule_totals.items())),
            entries=report.entries,
        )
        content = (evidence.model_dump_json(indent=2) + "\n").encode(
            c.Cli.ENCODING_DEFAULT
        )
        report_path = root.resolve() / c.Infra.MOD_SCAN_REPORT_RELATIVE_PATH
        prepared = u.Cli.ensure_dir(report_path.parent)
        if prepared.failure:
            return r[m.Infra.ModScanEvidenceReceipt].from_failure(prepared)
        before = u.Cli.atomic_read_binary_file_state(report_path, required=False)
        if before.failure:
            return r[m.Infra.ModScanEvidenceReceipt].from_failure(before)
        written = u.Cli.atomic_write_binary_file_guarded(
            before.value, content, permission_mode=c.Infra.MOD_SCAN_REPORT_MODE
        )
        if written.failure:
            return r[m.Infra.ModScanEvidenceReceipt].from_failure(written)
        published = u.Cli.atomic_read_binary_file_state(report_path, required=True)
        if published.failure:
            return r[m.Infra.ModScanEvidenceReceipt].from_failure(published)
        if (
            published.value.content != content
            or published.value.mode != c.Infra.MOD_SCAN_REPORT_MODE
        ):
            return r[m.Infra.ModScanEvidenceReceipt].fail(
                f"published mod evidence differs from planned bytes: {report_path}"
            )
        return r[m.Infra.ModScanEvidenceReceipt].ok(
            m.Infra.ModScanEvidenceReceipt(
                path=report_path, sha256=u.Cli.sha256_bytes(content), evidence=evidence
            )
        )


__all__: list[str] = ["FlextInfraUtilitiesRefactor"]
