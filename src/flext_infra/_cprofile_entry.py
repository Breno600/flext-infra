"""Render the canonical focused pytest cProfile artifact.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path

from flext_infra import c, config
from flext_infra.validate.cprofile_report import FlextInfraCProfileReport


class FlextInfraCProfileEntry:
    """Thin transport for the canonical cProfile report service."""

    @staticmethod
    def main() -> int:
        """Dispatch focused or explicitly receipted profiles to the report owner.

        Returns:
            The resulting ``int``.

        """
        report_root = Path.cwd().resolve() / ".reports" / "cprofile"
        profile_path = (
            Path(sys.argv[1]) if len(sys.argv) > 1 else report_root / "pytest.pstats"
        )
        output_path = profile_path.with_suffix(".txt")
        policy = config.Infra.tooling.tools.pytest
        FlextInfraCProfileReport(
            repository_root=Path.cwd().resolve(),
            profile=profile_path,
            output=output_path,
            sort=policy.profile_sort,
            limit=policy.profile_limit,
            run_receipt=(
                Path(sys.argv[2])
                if len(sys.argv) >= c.Infra.CPROFILE_RECEIPT_ARGUMENT_COUNT
                else None
            ),
        ).execute().unwrap()
        return 0


if __name__ == "__main__":
    raise SystemExit(FlextInfraCProfileEntry.main())
