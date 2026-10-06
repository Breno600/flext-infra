"""Observable public profiling contract for the cached-pytest runtime.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pstats
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import (
    FlextInfraCProfileReport,
    FlextInfraPytestRunner,
    c,
    config,
    m,
    t,
    u,
)
from tests.unit.validate.pytest_runner_support import (
    profile_collection,
    profile_parent,
    runner_for,
)


class TestsFlextInfraPytestProfile:
    """Exercise the real profiling child transport and its receipt binding."""

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize(
        ("arguments", "expected_exit"),
        [
            (("--version",), pytest.ExitCode.OK),
            (("--flext-invalid-profile-option",), pytest.ExitCode.USAGE_ERROR),
        ],
    )
    def test_profile_child_preserves_exit_status_and_arguments(
        tmp_path: Path,
        arguments: t.StrTuple,
        expected_exit: int,
    ) -> None:
        """The real pytest module exits natively and leaves its raw profile."""
        profile = tmp_path / "collection.pstats"
        result = profile_collection(profile, arguments)
        assert result.outcome.raw_return_code == expected_exit
        assert not result.outcome.timed_out
        assert result.outcome.forwarded_signal is None
        if expected_exit == pytest.ExitCode.USAGE_ERROR:
            assert arguments[0] in result.stderr
        assert pstats.Stats(str(profile)).get_stats_profile().func_profiles

    @staticmethod
    @pytest.mark.slow
    def test_profile_failure_exposes_the_write_error(tmp_path: Path) -> None:
        """A real profile I/O failure remains visible rather than becoming success."""
        output = tmp_path / "collection.pstats"
        output.mkdir()
        result = profile_collection(output, ("--version",))
        assert result.outcome.raw_return_code != 0
        assert not result.outcome.timed_out
        assert result.outcome.forwarded_signal is None
        assert "IsADirectoryError" in result.stderr

    @staticmethod
    @pytest.mark.parametrize("complete", [False, True])
    def test_collection_profile_preserves_pytest_arguments(
        cached_runner_project: Path,
        *,
        complete: bool,
    ) -> None:
        """Only the interpreter prefix changes; suite execution is not profiled."""
        plain = runner_for(cached_runner_project)
        profiled = runner_for(cached_runner_project, profile_collection=True)
        report = cached_runner_project / plain.reports
        manifest = report / "collection.json"
        plain_command = plain.build_selection_command(
            report_log=report / "collection.jsonl",
            manifest_path=manifest,
            complete=complete,
        )
        profiled_command = profiled.build_selection_command(
            report_log=report / "collection.jsonl",
            manifest_path=manifest,
            complete=complete,
        )
        assert profiled_command == (
            *profiled.collection_command_prefix,
            str(manifest.with_suffix(".pstats")),
            *plain_command[3:],
        )
        assert c.Infra.PYTEST_PROFILE_LAUNCHER not in profiled.build_command(report)

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("profile_collection", [False, True])
    def test_complete_suite_persists_cache_and_zero_diagnostic_evidence(
        cached_runner_project: Path,
        *,
        profile_collection: bool,
    ) -> None:
        """One public execution collects every test and publishes real evidence.

        The profiled run loads ``flext_infra`` as a plugin package, as consumer
        projects do: a child that imported it before pytest makes pytest warn
        that it cannot rewrite it, and the collection gate rejects warnings.
        """
        cache = config.Infra.codegen.make.testmon_cache
        if profile_collection:
            pyproject = cached_runner_project / c.PYPROJECT_FILENAME
            pyproject.write_text(
                pyproject.read_text(encoding="utf-8") + 'addopts = "-p flext_infra"\n',
                encoding="utf-8",
            )
        runner = runner_for(
            cached_runner_project,
            profile_collection=profile_collection,
        )
        testmon_db = runner.testmon_db

        parent_profile = (
            cached_runner_project / ".reports" / "profiles" / "pytest.pstats"
        )
        exit_code = (
            profile_parent(runner, parent_profile)
            if profile_collection
            else tm.ok(runner.execute())
        )

        tm.that(exit_code, eq=0)
        tm.that(testmon_db.is_file(), eq=True)
        tm.that(testmon_db.is_relative_to(cached_runner_project), eq=False)
        tm.that((cached_runner_project / cache.database_filename).exists(), eq=False)
        reports_root = cached_runner_project / cache.reports_directory
        latest_name = tm.ok(u.Cli.files_read_text(reports_root / "latest.txt")).strip()
        profile = reports_root / latest_name / "testmon-selection.pstats"
        assert profile.is_file() == profile_collection
        if profile_collection:
            stats = pstats.Stats(str(profile))
            assert any(
                "_pytest" in function.file_name
                for function in stats.get_stats_profile().func_profiles.values()
            )
            parent_stats = pstats.Stats(str(parent_profile)).get_stats_profile()
            # The class body runs on import, unlike its methods: this proves the
            # public runner was first imported while the parent profiler was active.
            assert FlextInfraPytestRunner.__name__ in parent_stats.func_profiles
            policy = config.Infra.tooling.tools.pytest
            report = FlextInfraCProfileReport(
                repository_root=cached_runner_project,
                profile=parent_profile,
                output=parent_profile.with_suffix(".txt"),
                run_receipt=parent_profile.with_suffix(".pstats.json"),
                sort=policy.profile_sort,
                limit=policy.profile_limit,
            )
            # An unrelated latest pointer must never pair this parent with another run.
            latest = reports_root / "latest.txt"
            latest.write_text("unrelated-run\n", encoding="utf-8")
            tm.ok(report.execute())
            latest.write_text(latest_name + "\n", encoding="utf-8")
            text = report.output.read_text(encoding="utf-8")
            assert str(parent_profile) in text
            assert str(profile) in text
            receipt_path = profile.with_suffix(".pstats.json")
            original = receipt_path.read_text(encoding="utf-8")
            receipt = m.Infra.PytestRunContext.model_validate_json(original)
            receipt_path.write_text(
                receipt.model_copy(
                    update={"deadline_monotonic": receipt.deadline_monotonic + 1},
                ).model_dump_json(),
                encoding="utf-8",
            )
            assert report.execute().failure
            receipt_path.write_text("{", encoding="utf-8")
            assert report.execute().failure
            receipt_path.unlink()
            assert report.execute().failure
            receipt_path.write_text(original, encoding="utf-8")
            parent_profile.write_bytes(parent_profile.read_bytes() + b"stale")
            assert report.execute().failure
        assert not (reports_root / latest_name / "testmon-inventory.pstats").exists()
        summary = tm.ok(
            u.Cli.files_read_text(reports_root / latest_name / "summary.txt"),
        )
        tm.that(
            summary,
            has=[
                "executed=1",
                "failed=0",
                "errors=0",
                "warnings=0",
                "skipped=0",
                "exit=0",
            ],
        )
        tm.that((reports_root / latest_name / "junit.xml").is_file(), eq=True)
        # The testmon verb owns no coverage plugin (testmon 2.x refuses branch
        # coverage through the cov plugin), so its command carries --no-cov and
        # the coverage artifact belongs to the coverage verb alone.
        selection = tm.ok(
            u.Cli.files_read_text(reports_root / latest_name / "testmon-selection.txt"),
        )
        command = tm.ok(
            u.Cli.files_read_text(reports_root / latest_name / "command.txt"),
        )
        # A complete selection runs the whole target; the collection plugin
        # enforces exactly the selected node ids in the recorded order.
        tm.that(selection.splitlines(), has="tests/test_runtime.py::test_runtime")
        tm.that(command, has=c.Infra.PYTEST_SELECTED_COLLECTION_OPTION)
        tm.that(command, has="--no-cov")
        tm.that(command, has="--testmon --testmon-noselect")
        tm.that((reports_root / latest_name / "coverage.xml").is_file(), eq=False)
        # A cold run has no database to inspect before pytest; its only cache
        # receipt is the post-run seed decision.
        tm.that((reports_root / latest_name / "cache-before.json").exists(), eq=False)
        seeded = m.Infra.TestmonCacheState.model_validate_json(
            tm.ok(
                u.Cli.files_read_text(reports_root / latest_name / "cache-after.json"),
            ),
        )
        tm.that(seeded.seed_needed, eq=True)
        tm.that(seeded.saveable, eq=True)
