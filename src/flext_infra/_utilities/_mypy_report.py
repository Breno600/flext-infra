"""Machine-channel Mypy report runner: one JSON diagnostic per line, on file.

The checker's human channel drifts across releases: verbose progress may share
the standard-output stream with the ``--output json`` diagnostics, and the gate
parser must never classify human text as a malformed diagnostic. This runner
owns that boundary by construction: it classifies every standard-output line
exactly once — JSON objects go to the report file, every other line is
forwarded verbatim to the standard error stream — so the structured report is
exact for every checker release and no real diagnostic is suppressed.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraMypyReportRunner:
    """Route the checker's machine report to a file and its prose to stderr."""

    @staticmethod
    def _is_machine_line(line: str) -> bool:
        """Return whether one checker output line is a JSON diagnostic object.

        Returns:
            The resulting ``bool``.

        """
        if not line.startswith("{"):
            return False
        try:
            parsed = json.loads(line)
        except json.JSONDecodeError:
            return False
        return isinstance(parsed, dict)

    @classmethod
    def _write_report(
        cls,
        stdout: str,
        stderr: str,
        report_path: Path,
    ) -> None:
        """Classify the checker output into the report file and the error stream.

        Raises:
            OSError: If the report destination cannot be written.

        """
        with report_path.open("w", encoding=c.Cli.ENCODING_DEFAULT) as report:
            for line in stdout.splitlines():
                if cls._is_machine_line(line):
                    _ = report.write(f"{line}\n")
                elif line.strip():
                    sys.stderr.write(f"{line}\n")
        sys.stderr.write(stderr)

    @classmethod
    def run(
        cls,
        invocation: m.Infra.MypyInvocation,
    ) -> int:
        """Run the checker and route its output through the machine boundary.

        Returns:
            The checker's native exit code.

        Raises:
            ValueError: If the invocation carries no report destination.

        """
        from flext_cli import u

        from flext_infra._utilities import FlextInfraUtilitiesResourceLimits

        if invocation.report_file is None:
            msg = "report runner requires a report destination"
            raise ValueError(msg)
        destination = invocation.report_file
        if not destination.is_absolute():
            msg = f"report destination must be absolute: {destination}"
            raise ValueError(msg)
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = (
            sys.executable,
            "-m",
            c.Infra.MYPY,
            *FlextInfraUtilitiesResourceLimits.mypy_arguments(invocation),
        )
        outcome: p.Cli.CommandOutput = u.Cli.run_raw(command).unwrap()
        cls._write_report(
            outcome.stdout,
            outcome.stderr,
            destination,
        )
        return outcome.outcome.raw_return_code


if __name__ == "__main__":
    raise SystemExit(
        FlextInfraMypyReportRunner.run(
            m.Infra.MypyInvocation.model_validate_json(sys.argv[1]),
        ),
    )


__all__: list[str] = ["FlextInfraMypyReportRunner"]
