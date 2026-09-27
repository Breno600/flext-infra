"""Source-live pytest entrypoint with a pre-import absolute clock."""

from __future__ import annotations

import sys
import time


class FlextInfraPytestEntry:
    """Facade for the pytest entrypoint with pre-import clock."""

    _STARTED_AT_MONOTONIC: float = time.monotonic()

    @classmethod
    def main(cls) -> int:
        """Parse the Make boundary and return the exact child process status.

        ``full`` runs incremental then complete testmon execution. ``coverage``
        selects coverage alone; the default is the incremental operation.
        """
        from flext_infra.validate.pytest_runner import FlextInfraPytestRunner

        runner = FlextInfraPytestRunner.from_environment(
            started_at_monotonic=cls._STARTED_AT_MONOTONIC
        )
        mode = sys.argv[1] if len(sys.argv) > 1 else ""
        if mode == "coverage":
            return runner.execute_coverage().unwrap()
        if mode == "full":
            return runner.execute_full().unwrap()
        if not mode:
            return runner.execute().unwrap()
        msg = f"unsupported pytest operation: {mode}"
        raise ValueError(msg)


if __name__ == "__main__":
    raise SystemExit(FlextInfraPytestEntry.main())
