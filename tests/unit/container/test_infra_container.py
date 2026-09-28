"""Behavioral tests for the DI container and the shared ``u`` namespace.

Every test exercises a real contract through the public facades: container
singleton identity and unknown-service failure, version parsing/bumping,
JSON IO round-trips, pattern matching, output streaming, and workspace
project discovery.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from flext_tests import tm

from flext_core import FlextContainer
from tests import u


class TestsFlextInfraContainerInfraContainer:
    """Exercise container lifecycle and shared namespace behavior."""

    def test_container_is_process_singleton(self) -> None:
        """FlextContainer returns the same process-wide instance."""
        first = FlextContainer()
        tm.that(FlextContainer() is first, eq=True)

    def test_container_has_and_fail_on_unknown_service(self) -> None:
        """Unknown names are reported through ``has`` and a failed resolve."""
        container = FlextContainer()
        tm.that(container.has("definitely-not-registered"), eq=False)
        resolved = container.resolve("definitely-not-registered")
        tm.that(resolved.failure, eq=True)

    def test_versioning_parse_and_bump_round_trip(self) -> None:
        """parse_semver and bump_version agree on a real release chain."""
        parsed = u.Infra.parse_semver("1.2.3")
        tm.that(tm.ok(parsed), eq=(1, 2, 3))
        bumped = u.Infra.bump_version("1.2.3", "patch")
        tm.that(tm.ok(bumped), eq="1.2.4")

    def test_json_io_round_trip(self, tmp_path: Path) -> None:
        """json_write/json_read preserve a typed payload through the file."""
        target = tmp_path / "payload.json"
        tm.ok(u.Cli.json_write(target, {"alpha": 1, "nested": {"beta": "ok"}}))
        loaded = tm.ok(u.Cli.json_read(target))
        tm.that(loaded, eq={"alpha": 1, "nested": {"beta": "ok"}})

    def test_pattern_matching_matches_declared_patterns(self) -> None:
        """u.Cli.matches reports hits and misses on declared patterns."""
        tm.that(u.Cli.matches("deploy failed", "deploy", "rollback"), eq=True)
        tm.that(u.Cli.matches("all good", "deploy", "rollback"), eq=False)

    def test_output_methods_write_to_configured_stream(self) -> None:
        """Output methods write through the shared namespace stream."""
        stream = StringIO()

        with redirect_stdout(stream):
            u.Cli.info("hello")
            u.Cli.warning("careful")

        tm.that(stream.getvalue(), eq="INFO: hello\nWARN: careful\n")

    def test_discover_projects_finds_declared_member(self, tmp_path: Path) -> None:
        """Discovery lists exactly the members declared in ``.gitmodules``."""
        service = u.Infra()
        member = tmp_path / "demo_source"
        member.mkdir()
        (member / "pyproject.toml").write_text(
            "[project]\nname='demo_source'\ndependencies=['flext-core>=0.1.0']\n",
            encoding="utf-8",
        )
        (tmp_path / ".gitmodules").write_text(
            '[submodule "demo_source"]\n'
            "\tpath = demo_source\n"
            "\turl = https://github.com/flext-sh/demo_source.git\n",
            encoding="utf-8",
        )
        projects = tm.ok(service.discover_projects(tmp_path))
        tm.that([project.name for project in projects], eq=["demo_source"])
