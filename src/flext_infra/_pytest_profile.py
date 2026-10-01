"""Capture each real pytest process through pytest's public session hooks."""

from __future__ import annotations

import cProfile
import os
from pathlib import Path

import pytest


class FlextInfraPytestProfile:
    """Keep controller and worker measurements separate until aggregation."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.profile = cProfile.Profile()
        self.started = False

    @pytest.hookimpl(tryfirst=True)
    def pytest_sessionstart(self) -> None:
        """Include collection, fixture setup, tests, and fixture teardown."""
        self.directory.mkdir(parents=True, exist_ok=True)
        self.profile.enable()
        self.started = True

    @pytest.hookimpl(trylast=True)
    def pytest_unconfigure(self) -> None:
        """Persist after session finish without replacing pytest's exit status."""
        if not self.started:
            return
        self.profile.disable()
        self.profile.dump_stats(str(self.directory / f"{os.getpid()}.pstats"))


__all__: list[str] = ["FlextInfraPytestProfile"]
