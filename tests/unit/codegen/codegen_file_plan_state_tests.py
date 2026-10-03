"""Atomic file state comparison preserves exact bytes and file presence.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from flext_infra import c, m, u
from flext_infra.utilities import FlextInfraUtilitiesCodegenFilePlan


class TestsFlextInfraCodegenFilePlanState:
    """Equal binary states converge; content, presence, and mode deltas do not."""

    _GATES: Mapping[str, Mapping[str, int]] = {"lint": {"time-seconds": 30}}

    @staticmethod
    def _observed_state(root: Path, *, content: bytes) -> m.Cli.AtomicFileState:
        """Read one real file through the canonical binary state owner.

        Returns:
            The resulting ``m.Cli.AtomicFileState``.

        Raises:
            AssertionError: If ``state.failure``.

        """
        target = root / "member" / c.PYPROJECT_FILENAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        state = u.Cli.atomic_read_binary_file_state(target, required=True)
        if state.failure:
            raise AssertionError(state.error)
        return state.value

    @pytest.mark.parametrize("content", [b"", b'name = "demo"\n', b"\xff\n"])
    def test_equal_binary_content_is_not_drift(
        self,
        tmp_path: Path,
        content: bytes,
    ) -> None:
        """Test equal binary content is not drift."""
        before = self._observed_state(tmp_path, content=content)

        differs = FlextInfraUtilitiesCodegenFilePlan.atomic_file_state_differs(
            before,
            desired_content=content,
            desired_mode=before.mode,
        )

        assert differs is False

    @pytest.mark.parametrize(
        ("content", "desired_content"),
        [
            (b'name = "demo"\n', b'name = "other"\n'),
            (b'name = "demo"', b'name = "demo"\n'),
            (b'name = "demo"\r\n', b'name = "demo"\n'),
            (b"\xff\n", b"\xfe\n"),
            (b"\xff\n", b"\xef\xbf\xbd\n"),
        ],
    )
    def test_real_content_delta_still_differs(
        self,
        tmp_path: Path,
        content: bytes,
        desired_content: bytes,
    ) -> None:
        """Test real content delta still differs."""
        before = self._observed_state(tmp_path, content=content)

        differs = FlextInfraUtilitiesCodegenFilePlan.atomic_file_state_differs(
            before,
            desired_content=desired_content,
            desired_mode=before.mode,
        )

        assert differs is True

    def test_mode_delta_differs_even_with_equal_content(self, tmp_path: Path) -> None:
        """Test mode delta differs even with equal content."""
        before = self._observed_state(tmp_path, content=b'name = "demo"\n')

        drifted = FlextInfraUtilitiesCodegenFilePlan.atomic_file_state_differs(
            before,
            desired_content=before.content,
            desired_mode=0o755,
        )

        assert drifted is True

    @staticmethod
    def test_absent_file_is_not_an_empty_file(tmp_path: Path) -> None:
        """Test absent file is not an empty file.

        Raises:
            AssertionError: If ``state.failure``.

        """
        state = u.Cli.atomic_read_binary_file_state(
            tmp_path / c.PYPROJECT_FILENAME,
            required=False,
        )
        if state.failure:
            raise AssertionError(state.error)

        assert FlextInfraUtilitiesCodegenFilePlan.atomic_file_state_differs(
            state.value,
            desired_content=b"",
            desired_mode=state.value.mode,
        )
        assert not FlextInfraUtilitiesCodegenFilePlan.atomic_file_state_differs(
            state.value,
            desired_content=None,
            desired_mode=state.value.mode,
        )

    def test_empty_file_requires_deletion(self, tmp_path: Path) -> None:
        """Test empty file requires deletion."""
        before = self._observed_state(tmp_path, content=b"")

        assert FlextInfraUtilitiesCodegenFilePlan.atomic_file_state_differs(
            before,
            desired_content=None,
            desired_mode=None,
        )

    @pytest.mark.parametrize(
        ("content", "desired_content"),
        [
            (b'name = "demo"', b'name = "demo"\n'),
            (b'name = "demo"\r\n', b'name = "demo"\n'),
            (b"\xff\n", b"\xfe\n"),
        ],
    )
    def test_drift_report_exposes_exact_byte_delta(
        self,
        tmp_path: Path,
        content: bytes,
        desired_content: bytes,
    ) -> None:
        """Test drift report exposes exact byte delta."""
        before = self._observed_state(tmp_path, content=content)
        planned = m.Infra.CodegenFilePlan(
            project=tmp_path,
            path=before.path,
            before=before,
            desired_content=desired_content,
            desired_mode=before.mode,
        )

        report = FlextInfraUtilitiesCodegenFilePlan.codegen_file_drift_report((
            planned,
        ))

        assert repr(content) in report
        assert repr(desired_content) in report
        assert "mode-only drift" not in report

    def test_drift_report_names_mode_only_delta(self, tmp_path: Path) -> None:
        """Test drift report names mode only delta."""
        before = self._observed_state(tmp_path, content=b'name = "demo"\n')
        planned = m.Infra.CodegenFilePlan(
            project=tmp_path,
            path=before.path,
            before=before,
            desired_content=before.content,
            desired_mode=0o755,
        )

        report = FlextInfraUtilitiesCodegenFilePlan.codegen_file_drift_report((
            planned,
        ))

        assert "mode-only drift" in report
        assert "desired=0o755" in report

    @staticmethod
    @pytest.mark.parametrize("limit", [0, -1])
    def test_drift_report_rejects_non_positive_limit(limit: int) -> None:
        """Test drift report rejects non positive limit."""
        with pytest.raises(ValueError, match="limit must be positive"):
            FlextInfraUtilitiesCodegenFilePlan.codegen_file_drift_report(
                (),
                limit=limit,
            )
