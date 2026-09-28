"""Public release CLI behavior tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import main
from tests import TestsFlextInfraUtilities as u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraReleaseCli:
    """Behavior contract for the public release command group."""

    class TestsHelp:
        """Public command-discovery behavior."""

        @staticmethod
        def test_release_group_help_returns_zero() -> None:
            """Expose the release command group through the public CLI."""
            tm.that(main(["release", "--help"]), eq=0)

        @staticmethod
        def test_release_run_subcommand_help_returns_zero() -> None:
            """Expose the release run options through the public CLI."""
            tm.that(main(["release", "run", "--help"]), eq=0)

    class TestsValidation:
        """Public input validation behavior."""

        @staticmethod
        def test_unknown_phase_is_rejected(tmp_path: Path) -> None:
            """A phase outside the protocol never reaches execution."""
            workspace = u.Tests.create_release_workspace(tmp_path)

            tm.that(u.Tests.run_release_main(workspace, "--phase", "deploy"), ne=0)
