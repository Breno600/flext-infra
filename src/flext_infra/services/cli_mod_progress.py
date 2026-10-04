"""Mod progress rendered at the CLI transport boundary.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import cli

from flext_infra import m


class FlextInfraCliModProgress:
    """Render mod progress at the CLI transport boundary."""

    @staticmethod
    def emit(message: str) -> None:
        """Show the current canonical mod phase."""
        cli.display_text(message)

    @staticmethod
    def emit_rename(report: m.Infra.ApplyRenamesReport) -> None:
        """Show one completed CSV campaign."""
        cli.display_text(FlextInfraCliModProgress.render_rename(report))

    @staticmethod
    def render_rename(report: m.Infra.ApplyRenamesReport) -> str:
        """Render native published paths and pending edit spans.

        Returns:
            The resulting ``str``.

        """
        return (
            f"{report.label}: {report.files_changed} published file(s), "
            f"{report.occurrences} pending source edit(s), "
            f"{report.files_scanned} scanned file(s)"
        )


__all__: list[str] = ["FlextInfraCliModProgress"]
