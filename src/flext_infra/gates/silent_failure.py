"""Silent failure quality gate.

Enforces silent-failure detection across every Python project the workspace
discovers. Projects without Python sources provide an empty scan input; no
project-name allowlist exists.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, m
from flext_infra.detectors.silent_failure_detector import (
    FlextInfraSilentFailureDetector,
)

from .scanner_gate import FlextInfraScannerGateMixin

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraSilentFailureGate(FlextInfraScannerGateMixin):
    """Block silent failure sentinels in any Python project under the workspace."""

    gate_id: ClassVar[str] = "silent-failure"
    gate_name: ClassVar[str] = "Silent Failure"
    can_fix: ClassVar[bool] = False

    scan_error_message: ClassVar[str] = "silent-failure scan failed"

    @override
    def _detect_file_issues(
        self, file_path: Path, project_dir: Path, rope_project: t.Infra.RopeProject
    ) -> t.SequenceOf[m.Infra.Issue]:
        """Detect silent failure violations in a single file."""
        # Why: ADR-0018 declares the stdlib hook-client island the sole,
        # performance-motivated exception to the no-hidden-errors rules; the
        # boundary and namespace gates already honor the same declaration.
        posix = str(file_path).replace("\\", "/")
        if any(
            fragment in posix
            for fragment in c.Infra.NAMESPACE_STDLIB_ISLAND_PATH_FRAGMENTS
        ):
            return ()
        return FlextInfraSilentFailureDetector.detect_file(
            m.Infra.DetectorContext(
                file_path=file_path, project_root=project_dir, rope_project=rope_project
            )
        )


__all__: list[str] = ["FlextInfraSilentFailureGate"]
