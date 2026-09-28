"""Public replacement transport preserves generator authority and exact CAS."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, m, u
from flext_infra.codemod.batch_replacements import FlextInfraModReplacements
from tests import u as test_u


class TestsBatchReplacements:
    """Only authenticated authored bytes may receive engine-proposed edits."""

    @staticmethod
    def _report(
        path: Path, content: bytes, *, generated: bool = False
    ) -> m.Infra.ModScanReport:
        path.write_bytes(content)
        state = tm.ok(u.Cli.atomic_read_binary_file_state(path, required=True))
        start = content.index(b"before")
        offsets = {"start": start, "end": start + len(b"before")}
        finding = m.Infra.ModScanFinding(
            rule_file=str(path.parent / "rule.yaml"),
            rule_id="fixture-rewrite",
            repository=path.parent.name,
            file=path,
            source_owner="generator" if generated else "authored",
            source_state=state,
            range={"byteOffset": offsets},
            text="before",
            replacement="after",
            actionable=True,
            classification=c.Infra.ModScanFindingClass.ACTIONABLE,
            payload={"replacementOffsets": offsets, "severity": "error"},
        )
        return m.Infra.ModScanReport(
            findings=1,
            actionable=1,
            detection_only=0,
            non_actionable_with_fix=0,
            files=frozenset({path}),
            entries=(finding,),
        )

    def test_utf8_replacements_use_engine_byte_offsets(self, tmp_path: Path) -> None:
        root = test_u.Tests.git_repository(tmp_path)
        path = root / "subject.py"
        original = '# ação\nvalue = "before"\n'.encode()
        report = self._report(path, original)
        tm.ok(FlextInfraModReplacements.publish(root, report))
        tm.that(path.read_bytes(), eq=original.replace(b"before", b"after"))

    def test_generator_findings_remain_visible_and_unmodified(
        self, tmp_path: Path
    ) -> None:
        root = test_u.Tests.git_repository(tmp_path)
        path = root / "generated.py"
        original = b'value = "before"\n'
        report = self._report(path, original, generated=True)
        result = FlextInfraModReplacements.publish(root, report)
        tm.fail(result)
        tm.that(result.error, has=f"generator:{path}:fixture-rewrite")
        tm.that(report.findings, eq=1)
        tm.that(path.read_bytes(), eq=original)

    @pytest.mark.parametrize(
        "changed", [b'value = "before"\n\n', b'value = "third-party"\n']
    )
    def test_changed_source_is_not_overwritten(
        self, tmp_path: Path, changed: bytes
    ) -> None:
        root = test_u.Tests.git_repository(tmp_path)
        path = root / "subject.py"
        report = self._report(path, b'value = "before"\n')
        path.write_bytes(changed)
        tm.fail(FlextInfraModReplacements.publish(root, report))
        tm.that(path.read_bytes(), eq=changed)

    def test_missing_actionable_snapshot_is_rejected(self, tmp_path: Path) -> None:
        root = test_u.Tests.git_repository(tmp_path)
        path = root / "subject.py"
        report = self._report(path, b'value = "before"\n')
        finding = report.entries[0].model_copy(update={"source_state": None})
        invalid = report.model_copy(update={"entries": (finding,)})
        tm.fail(FlextInfraModReplacements.publish(root, invalid))
