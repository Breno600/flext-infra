"""Process entrypoint for the canonical centralized flext-infra CLI."""

from __future__ import annotations

from flext_cli import cli
from flext_infra import main

if __name__ == "__main__":
    cli.exit(main())
