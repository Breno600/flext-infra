"""CLI entrypoint for the canonical flext-infra command surface.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys

from flext_infra.constants import c
from flext_infra.services.cli_dispatch import FlextInfraCliDispatchService
from flext_infra.typings import t


class FlextInfraCli(FlextInfraCliDispatchService):
    """Single CLI entry surface for every flext-infra command group."""

    @staticmethod
    def docs_main(args: t.StrSequence | None = None) -> int:
        """Run the docs group directly (``flext-docs`` == ``flext-infra docs``).

        Returns:
            The resulting ``int``.

        """
        cli_args = list(args) if args is not None else sys.argv[1:]
        return FlextInfraCli().main([c.Infra.CLI_GROUP_DOCS, *cli_args])


def main(args: t.StrSequence | None = None) -> int:
    """Run the canonical flext-infra CLI.

    Returns:
        The resulting ``int``.

    """
    cli_args = list(args) if args is not None else sys.argv[1:]
    return FlextInfraCli().main(cli_args)


__all__: list[str] = ["FlextInfraCli", "main"]
