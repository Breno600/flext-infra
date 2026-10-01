"""Source-live pytest entrypoint with a pre-import absolute clock."""

from __future__ import annotations

import cProfile
import sys
import time
from pathlib import Path


class FlextInfraPytestEntry:
    """Facade for the pytest entrypoint with pre-import clock."""

    _PROFILE_ARGUMENT_COUNT = 3
    _STARTED_AT_MONOTONIC: float = time.monotonic()

    @classmethod
    def main(cls) -> int:
        """Parse the Make boundary and return the exact child process status.

        ``full`` runs incremental then complete testmon execution. ``coverage``
        selects coverage alone; the default is the incremental operation.
        """
        mode = sys.argv[1] if len(sys.argv) > 1 else ""
        if mode == "profile":
            if len(sys.argv) != cls._PROFILE_ARGUMENT_COUNT:
                msg = "profile requires the parent cProfile output path"
                raise ValueError(msg)
            destination = Path(sys.argv[2])
            destination.parent.mkdir(parents=True, exist_ok=True)
            profile = cProfile.Profile()
            try:
                return profile.runcall(cls._execute, mode)
            finally:
                profile.dump_stats(str(destination))
        return cls._execute(mode)

    @classmethod
    def _execute(cls, mode: str) -> int:
        """Dispatch one operation under the clock captured before imports."""
        from flext_infra.validate.pytest_runner import FlextInfraPytestRunner

        runner = FlextInfraPytestRunner.from_environment(
            started_at_monotonic=cls._STARTED_AT_MONOTONIC,
            profile_enabled=mode == "profile",
        )
        if mode == "coverage":
            return runner.execute_coverage().unwrap()
        if mode == "full":
            return runner.execute_full().unwrap()
        if mode in {"", "profile"}:
            return runner.execute().unwrap()
        msg = f"unsupported pytest operation: {mode}"
        raise ValueError(msg)


if __name__ == "__main__":
    raise SystemExit(FlextInfraPytestEntry.main())
