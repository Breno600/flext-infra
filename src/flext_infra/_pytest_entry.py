"""Source-live pytest entrypoint with a pre-import absolute clock.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import importlib
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
            TypeError: If the runner returns a non-integer process status.

        """
        # Deliberately deferred past the pre-import clock snapshot: the
        # module contract keeps every FLEXT import inside the budgeted window.
        profile_module = importlib.import_module("flext_infra._pytest_profile")
        runner_module = importlib.import_module("flext_infra.validate.pytest_runner")

        mode = sys.argv[1] if len(sys.argv) > 1 else ""
        if mode == "profile":
            profile = profile_module.FlextInfraPytestProfile(Path(sys.argv[2]))
            status = profile.run_parent(
                started_at_monotonic=cls._STARTED_AT_MONOTONIC,
            )
            if isinstance(status, int):
                return status
            msg = f"pytest profile returned a non-integer process status: {status!r}"
            raise TypeError(msg)

        slow_phase = mode in {"slow", "full-slow", "file-slow"}
        runner = runner_module.FlextInfraPytestRunner.from_environment(
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
            status = runner.execute_coverage().unwrap()
        elif mode in {"full", "full-slow"}:
            status = runner.execute_full().unwrap()
        elif mode in {"", "slow", "file", "file-slow"}:
            status = runner.execute().unwrap()
        else:
            msg = f"unsupported pytest operation: {mode}"
            raise ValueError(msg)
        if isinstance(status, int):
            return status
        msg = f"pytest runner returned a non-integer process status: {status!r}"
        raise TypeError(msg)


if __name__ == "__main__":
    raise SystemExit(FlextInfraPytestEntry.main())
