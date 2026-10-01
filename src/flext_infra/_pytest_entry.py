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
        selects coverage alone; the default is the incremental operation. The
        ``slow`` operation runs the incremental phase over the slow marker
        only, as its own bounded process outside the budgeted clock.
        """
        mode = sys.argv[1] if len(sys.argv) > 1 else ""
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
            started_at_monotonic=cls._STARTED_AT_MONOTONIC,
        )
        if mode == "coverage":
            return runner.execute_coverage().unwrap()
        if mode == "full":
            return runner.execute_full().unwrap()
        if mode in {"", "slow"}:
            return runner.execute().unwrap()
        msg = f"unsupported pytest operation: {mode}"
        raise ValueError(msg)


if __name__ == "__main__":
    raise SystemExit(FlextInfraPytestEntry.main())
