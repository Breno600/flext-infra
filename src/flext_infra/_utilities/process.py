"""Canonical process-exit classification utilities.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra import c, p, t


class FlextInfraUtilitiesProcess:
    """Normalize external process exits without discarding their status."""

    @staticmethod
    def tool_outcome(
        outcome: p.Cli.ProcessOutcome,
        *,
        findings: int,
        findings_exit_codes: t.VariadicTuple[int],
    ) -> c.Infra.ToolOutcome:
        """Classify one completed tool run as clean, findings or error.

        A tool completes cleanly with a success status and nothing reported,
        and completes with findings when it reports what it found under a
        success status or under a findings status it declares. Any other
        status, a timeout, a signal, or a findings status without a reported
        finding is an error.

        Returns:
            The outcome the run ended with.

        """
        if outcome.timed_out or outcome.forwarded_signal is not None:
            return c.Infra.ToolOutcome.ERROR
        status = outcome.raw_return_code
        if status == c.Cli.EXIT_CODE_SUCCESS:
            return (
                c.Infra.ToolOutcome.FINDINGS if findings else c.Infra.ToolOutcome.CLEAN
            )
        if status in findings_exit_codes and findings:
            return c.Infra.ToolOutcome.FINDINGS
        return c.Infra.ToolOutcome.ERROR

    @staticmethod
    def process_exit_classification(exit_code: int) -> str:
        """Classify a process exit without discarding its original status.

        Returns:
            The resulting ``str``.

        """
        if exit_code == c.Infra.PROCESS_TIMEOUT_EXIT_CODE:
            return "timeout"
        if exit_code < 0:
            return f"signal={-exit_code}"
        if exit_code > c.Infra.PROCESS_SIGNAL_EXIT_OFFSET:
            return f"signal={exit_code - c.Infra.PROCESS_SIGNAL_EXIT_OFFSET}"
        return "failure"


__all__: list[str] = ["FlextInfraUtilitiesProcess"]
