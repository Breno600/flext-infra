"""Fail-closed pytest configuration contract."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraToolTablesPhase, config
from tests import t, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraPytestFailClosedConfig:
    """Prove canonical pytest settings replace local bypasses deterministically."""

    @pytest.mark.asyncio
    async def test_declared_async_provider_executes_coroutines(self) -> None:
        """Exercise the installed provider rather than merely registering a marker."""
        await asyncio.sleep(0)
        tm.that(asyncio.current_task() is not None, eq=True)

    def test_phase_replaces_stale_collection_and_warning_policy(
        self, tmp_path: Path
    ) -> None:
        """Replace ignored roots and warning filters without second-apply drift."""
        policy = config.Infra.tooling.tools.pytest
        payload = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python(
            u.Tests.toml_payload(
                '[project]\nname = "flext-sample"\n'
                "[tool.pytest.ini_options]\n"
                'addopts = ["--maxfail=1", "--cov=.", "--markdown-docs"]\n'
                'filterwarnings = ["ignore:legacy warning suppression"]\n'
                'markers = ["custom: stale local marker"]\n'
                'python_classes = ["Spec*"]\n'
                'python_files = ["spec_*.py"]\n'
                'testpaths = ["architecture", "guides", "tests"]\n'
            )
        )
        phase = FlextInfraToolTablesPhase(config.Infra.tooling)
        pyproject = tmp_path / "flext-sample" / "pyproject.toml"

        first_changes = phase.apply_payload(payload, path=pyproject)
        second_changes = phase.apply_payload(payload, path=pyproject)

        tm.that(first_changes, empty=False)
        tm.that(second_changes, empty=True)
        ini = u.Tests.toml_mapping(
            u.Tests.toml_mapping(u.Tests.toml_mapping(payload["tool"])["pytest"])[
                "ini_options"
            ]
        )
        tm.that(
            list(u.Tests.strings(ini["filterwarnings"])),
            eq=sorted(policy.filter_warnings),
        )
        tm.that(list(u.Tests.strings(ini["testpaths"])), eq=sorted(policy.test_paths))
        tm.that(
            ini["asyncio_default_fixture_loop_scope"],
            eq=policy.asyncio_default_fixture_loop_scope,
        )
        tm.that(
            set(u.Tests.strings(ini["addopts"])),
            eq={*policy.standard_addopts, f"--timeout={policy.case_timeout_seconds}"},
        )
        tm.that(
            set(u.Tests.strings(ini["markers"])),
            eq={"custom: stale local marker", *policy.standard_markers},
        )
        tm.that(u.Tests.strings(ini["python_classes"]), has="Spec*")
        tm.that(u.Tests.strings(ini["python_files"]), has="spec_*.py")
