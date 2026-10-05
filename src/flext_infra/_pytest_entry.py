"""Source-live pytest entrypoint with a pre-import absolute clock.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
import time
from pathlib import Path


class FlextInfraPytestEntry:
    """Facade for the pytest entrypoint with pre-import clock."""

    _STARTED_AT_MONOTONIC: float = time.monotonic()

    @classmethod
    def main(cls) -> int:
        """Parse the Make boundary and return the exact child process status.

        ``full`` runs incremental then complete testmon execution. ``coverage``
        selects coverage alone; the default is the incremental operation. The
        ``slow`` operation runs the incremental phase over the slow marker
        only, as its own bounded process outside the budgeted clock. The
        ``file`` and ``file-slow`` operations run one declared target file
        through the same budgeted and slow phases; they require the Make
        boundary to export the single-file target environment variable.

        Returns:
            The resulting ``int``.

        Raises:
            ValueError: If unsupported pytest operation.

        """
        mode = sys.argv[1] if len(sys.argv) > 1 else ""
        if mode == "profile":
            from flext_infra._pytest_profile import FlextInfraPytestProfile

            return FlextInfraPytestProfile(Path(sys.argv[2])).run_parent(
                started_at_monotonic=cls._STARTED_AT_MONOTONIC,
            )

        from flext_infra.validate.pytest_runner import FlextInfraPytestRunner

        slow_phase = mode in {"slow", "full-slow", "file-slow"}
        runner = FlextInfraPytestRunner.from_environment(
            started_at_monotonic=cls._STARTED_AT_MONOTONIC,
            slow_phase=slow_phase,
        )
        if mode in {"file", "file-slow"} and runner.target_file is None:
            msg = (
                f"pytest operation {mode} requires the Make boundary to export "
                "the single-file target variable"
            )
            raise ValueError(msg)
        if mode == "coverage":
            return runner.execute_coverage().unwrap()
        if mode in {"full", "full-slow"}:
            return runner.execute_full().unwrap()
        if mode in {"", "slow", "file", "file-slow"}:
            return runner.execute().unwrap()
        msg = f"unsupported pytest operation: {mode}"
        raise ValueError(msg)


if __name__ == "__main__":
    raise SystemExit(FlextInfraPytestEntry.main())
