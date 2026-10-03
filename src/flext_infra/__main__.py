"""Process entrypoint for the canonical centralized flext-infra CLI.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations


class FlextInfraMain:
    """Facade for the flext-infra CLI process entrypoint."""

    @staticmethod
    def run() -> None:
        """Load and execute the sole facade-backed CLI."""
        from flext_cli import cli

        from flext_infra.cli import main

        cli.exit(main())


if __name__ == "__main__":
    FlextInfraMain.run()
