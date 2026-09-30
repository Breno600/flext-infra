"""Render parent and child profiles from the canonical pytest operation."""

from __future__ import annotations

import sys
from pathlib import Path

from flext_infra import config, u
from flext_infra.validate.cprofile_report import FlextInfraCProfileReport


class FlextInfraCProfileEntry:
    """Delegate profile rendering to the typed report owner."""

    _REPORT_ARGUMENT_COUNT = 3

    @staticmethod
    def main() -> int:
        """Render the explicit parent profile and latest child profile."""
        if len(sys.argv) != FlextInfraCProfileEntry._REPORT_ARGUMENT_COUNT:
            msg = "profile report requires parent profile and pytest report directory"
            raise ValueError(msg)
        root = Path.cwd().resolve()
        parent = Path(sys.argv[1]).resolve()
        reports = Path(sys.argv[2]).resolve()
        latest = u.Cli.files_read_text(reports / "latest.txt").unwrap().strip()
        child = reports / latest / "pytest.pstats"
        policy = config.Infra.tooling.tools.pytest
        for profile in (parent, child):
            output = profile.with_suffix(".txt")
            FlextInfraCProfileReport(
                repository_root=root,
                profile=profile,
                output=output,
                sort=policy.profile_sort,
                limit=policy.profile_limit,
            ).execute().unwrap()
            sys.stdout.write(f"Profile: {profile}\n")
            sys.stdout.write(u.Cli.files_read_text(output).unwrap())
        return 0


if __name__ == "__main__":
    raise SystemExit(FlextInfraCProfileEntry.main())
