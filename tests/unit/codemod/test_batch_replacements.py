"""Public replacement transport preserves generator authority and exact CAS.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, m, t
from flext_infra.codemod.batch_gates import FlextInfraModGateEngine
from flext_infra.codemod.batch_replacements import FlextInfraModReplacements
from tests import u


class TestsFlextInfraBatchReplacements:
    """Only authenticated authored bytes may receive engine-proposed edits."""

    @staticmethod
    def _report(
        path: Path,
        content: bytes,
        *,
        generated: bool = False,
    ) -> m.Infra.ModScanReport:
        path.write_bytes(content)
        state = tm.ok(u.Cli.atomic_read_binary_file_state(path, required=True))
        start = content.index(b"before")
        offsets: t.JsonDict = {"start": start, "end": start + len(b"before")}
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
        """Test utf8 replacements use engine byte offsets."""
        root = u.Tests.git_repository(tmp_path)
        path = root / "subject.py"
        original = '# ação\nvalue = "before"\n'.encode()
        report = self._report(path, original)
        tm.ok(FlextInfraModReplacements.publish(root, report))
        tm.that(path.read_bytes(), eq=original.replace(b"before", b"after"))

    def test_removed_references_leave_no_type_only_import_scaffold(
        self,
        tmp_path: Path,
    ) -> None:
        """Publishing a rewrite normalizes imports as well as formatting."""
        root = u.Tests.git_repository(tmp_path)
        path = root / "subject.py"
        original = (
            b"from __future__ import annotations\n\n"
            b"from typing import TYPE_CHECKING\n\n"
            b"if TYPE_CHECKING:\n    from pathlib import Path\n\n"
            b'value = "before"\n__all__ = ("value",)\n'
        )
        report = self._report(path, original)
        tm.ok(FlextInfraModReplacements.publish(root, report))
        tm.that(path.read_text(), lacks="TYPE_CHECKING")
        tm.that(path.read_text(), lacks="from pathlib import Path")
        tm.that(path.read_text(), has='value = "after"')
        tm.that(path.read_text(), has='__all__ = ("value",)')

    def test_generator_findings_remain_visible_and_unmodified(
        self,
        tmp_path: Path,
    ) -> None:
        """Test generator findings remain visible and unmodified."""
        root = u.Tests.git_repository(tmp_path)
        path = root / "generated.py"
        original = b'value = "before"\n'
        report = self._report(path, original, generated=True)
        result = FlextInfraModReplacements.publish(root, report)
        tm.fail(result)
        tm.that(result.error, has=f"generator:{path}:fixture-rewrite")
        tm.that(report.findings, eq=1)
        tm.that(path.read_bytes(), eq=original)

    def test_generator_evidence_never_blocks_authored_rewrites(
        self,
        tmp_path: Path,
    ) -> None:
        """Test generator evidence never blocks authored rewrites."""
        root = u.Tests.git_repository(tmp_path)
        original = b'value = "before"\n'
        authored = self._report(root / "authored.py", original).entries[0]
        generated = self._report(
            root / "generated.py",
            original,
            generated=True,
        ).entries[0]
        evidence = generated.model_copy(
            update={
                "replacement": None,
                "actionable": False,
                "classification": c.Infra.ModScanFindingClass.DETECTION_ONLY,
            },
        )
        report = FlextInfraModGateEngine.recounted((authored, evidence))
        tm.ok(FlextInfraModReplacements.publish(root, report))
        tm.that((root / "authored.py").read_bytes(), eq=b'value = "after"\n')
        tm.that((root / "generated.py").read_bytes(), eq=original)
        tm.that(FlextInfraModGateEngine.authored(report).entries, eq=(authored,))

    @pytest.mark.parametrize(
        "changed",
        [b'value = "before"\n\n', b'value = "third-party"\n'],
    )
    def test_changed_source_is_not_overwritten(
        self,
        tmp_path: Path,
        changed: bytes,
    ) -> None:
        """Test changed source is not overwritten."""
        root = u.Tests.git_repository(tmp_path)
        path = root / "subject.py"
        report = self._report(path, b'value = "before"\n')
        path.write_bytes(changed)
        tm.fail(FlextInfraModReplacements.publish(root, report))
        tm.that(path.read_bytes(), eq=changed)

    def test_missing_actionable_snapshot_is_rejected(self, tmp_path: Path) -> None:
        """Test missing actionable snapshot is rejected."""
        root = u.Tests.git_repository(tmp_path)
        path = root / "subject.py"
        report = self._report(path, b'value = "before"\n')
        finding = report.entries[0].model_copy(update={"source_state": None})
        invalid = report.model_copy(update={"entries": (finding,)})
        tm.fail(FlextInfraModReplacements.publish(root, invalid))

    @staticmethod
    def test_emptied_statement_publishes_formatter_clean_file(
        tmp_path: Path,
    ) -> None:
        """An emptied statement fix publishes skeleton-free, format-clean bytes.

        The ban-test-suite-module-all rule rewrites its match to ``""``; the
        byte-splice leaves the source line blank and the mod circuit enforces
        canonical formatting on the first pass after applying.
        """
        root = u.Tests.git_repository(tmp_path)
        path = root / "tests" / "unit" / "test_demo.py"
        path.parent.mkdir(parents=True)
        original = (
            b'"""Demo."""\n\n__all__ = ["X"]\n\n\ndef t() -> None:\n    assert True\n'
        )
        path.write_bytes(original)
        state = tm.ok(u.Cli.atomic_read_binary_file_state(path, required=True))
        statement = b'__all__ = ["X"]'
        start = original.index(statement)
        offsets: t.JsonDict = {"start": start, "end": start + len(statement)}
        finding = m.Infra.ModScanFinding(
            rule_file=str(root / "rule.yaml"),
            rule_id="ban-test-suite-module-all",
            repository=root.name,
            file=path,
            source_owner="authored",
            source_state=state,
            range={"byteOffset": offsets},
            text=statement.decode(),
            replacement="",
            actionable=True,
            classification=c.Infra.ModScanFindingClass.ACTIONABLE,
            payload={"replacementOffsets": offsets, "severity": "error"},
        )
        report = m.Infra.ModScanReport(
            findings=1,
            actionable=1,
            detection_only=0,
            non_actionable_with_fix=0,
            files=frozenset({path}),
            entries=(finding,),
        )
        tm.ok(FlextInfraModReplacements.publish(root, report))
        tm.that(
            path.read_bytes(),
            eq=b'"""Demo."""\n\n\ndef t() -> None:\n    assert True\n',
        )
