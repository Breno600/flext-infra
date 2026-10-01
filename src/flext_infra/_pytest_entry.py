"""Source-live pytest entrypoint with a pre-import absolute clock."""

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
        selects coverage alone; the default is the incremental operation. A
        trailing ``slow`` runs the operation over the slow marker only, as its
        own bounded process outside the budgeted clock (``slow`` alone is the
        incremental slow phase, ``full slow`` the complete one).
        """
        arguments = sys.argv[1:]
        slow_phase = arguments[-1:] == ["slow"]
        operation = arguments[:-1] if slow_phase else arguments
        mode = operation[0] if operation else ""
        if mode in {"profile", "profile-collection"}:
            from ._pytest_profile import FlextInfraPytestProfile

            adapter = FlextInfraPytestProfile(Path(sys.argv[2]))
            if mode == "profile-collection":
                return adapter.run_collection(Path(sys.argv[3]), tuple(sys.argv[4:]))
            return adapter.run_parent(
                started_at_monotonic=cls._STARTED_AT_MONOTONIC,
                collection_command_prefix=(
                    sys.executable,
                    "-m",
                    "flext_infra._pytest_entry",
                    "profile-collection",
                ),
            )

        from flext_infra.validate.pytest_runner import FlextInfraPytestRunner

        runner = FlextInfraPytestRunner.from_environment(
<<<<<<< HEAD
            started_at_monotonic=cls._STARTED_AT_MONOTONIC
=======
            started_at_monotonic=cls._STARTED_AT_MONOTONIC,
            slow_phase=slow_phase,
>>>>>>> origin/0.12.0-dev
        )
        if mode == "coverage" and not slow_phase:
            return runner.execute_coverage().unwrap()
        if mode == "full" and len(operation) == 1:
            return runner.execute_full().unwrap()
        if not operation:
            return runner.execute().unwrap()
        msg = f"unsupported pytest operation: {mode}"
        raise ValueError(msg)


if __name__ == "__main__":
    raise SystemExit(FlextInfraPytestEntry.main())
