"""Observable public collection-policy contract of the cached-pytest runtime.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import pstats
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraPytestDiagExtractor, c, m
from tests.unit.validate.pytest_runner_support import profile_parent, runner_for


class TestsFlextInfraPytestCollectionPolicy:
    """Keep collection findings loud, accounted, and identity-preserving."""

    @staticmethod
    @pytest.mark.slow
    def test_collection_policy_error_fails_loud_and_names_the_offender(
        policy_violation_project: Path,
    ) -> None:
        """A collection-time policy error rejects the run and names the offender."""
        runner = runner_for(policy_violation_project)

        with pytest.raises(RuntimeError) as raised:
            runner.execute()

        tm.that(str(raised.value), has=["FLEXT slow timeout policy", "test_policy.py"])

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("profile_collection", [False, True])
    @pytest.mark.parametrize("finding", ["warning", "module-skip", "module-error"])
    def test_collection_findings_block_before_suite_execution(
        cached_runner_project: Path,
        finding: str,
        *,
        profile_collection: bool,
    ) -> None:
        """Collect-only warnings, skips and import failures retain native evidence."""
        runner = runner_for(
            cached_runner_project,
            profile_collection=profile_collection,
        )
        if finding == "warning":
            (cached_runner_project / "conftest.py").write_text(
                "import warnings\n\n"
                "def pytest_collection_finish(session):\n"
                "    if session.config.getoption('collectonly'):\n"
                "        warnings.warn('collect-only finding', RuntimeWarning)\n",
                encoding="utf-8",
            )
        else:
            source = (
                "import pytest\npytest.skip('required module', allow_module_level=True)\n"
                if finding == "module-skip"
                else "raise RuntimeError('first collection failure')\n"
            )
            (cached_runner_project / runner.target / "test_collect.py").write_text(
                source,
                encoding="utf-8",
            )

        expected = (
            "first collection failure"
            if finding == "module-error"
            else "collection contains blocking findings"
        )

        def execute_blocking_collection() -> None:
            if profile_collection:
                profile_parent(
                    runner,
                    cached_runner_project / ".reports" / "profiles" / "pytest.pstats",
                )
            else:
                runner.execute()

        with pytest.raises(RuntimeError, match=expected):
            execute_blocking_collection()

        (events,) = (cached_runner_project / runner.reports).glob(
            "*/testmon-selection.events.jsonl",
        )
        diagnostic = tm.ok(FlextInfraPytestDiagExtractor.extract_report_log(events))
        tm.that(diagnostic.warning_count, eq=int(finding == "warning"))
        tm.that(diagnostic.collection_skipped_count, eq=int(finding == "module-skip"))
        tm.that(diagnostic.collection_failed_count, eq=int(finding == "module-error"))
        tm.that((events.parent / "suite-outcome.json").exists(), eq=False)
        outcome = m.Cli.ProcessOutcome.model_validate_json(
            (events.parent / "selection-outcome.json").read_text(),
        )
        tm.that(outcome.raw_return_code != 0, eq=finding == "module-error")
        if finding == "module-error":
            assert outcome.raw_return_code == pytest.ExitCode.INTERRUPTED
        profile = events.parent / "testmon-selection.pstats"
        assert profile.is_file() == profile_collection
        if profile_collection:
            assert pstats.Stats(str(profile)).get_stats_profile().func_profiles
            parent = cached_runner_project / ".reports" / "profiles" / "pytest.pstats"
            assert pstats.Stats(str(parent)).get_stats_profile().func_profiles
            # A blocked collection is a profiled run too: the parent binds the
            # receipt this invocation wrote before the collection failed.
            assert parent.with_suffix(".pstats.json").is_file()

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("homonym", [False, True])
    def test_serial_collection_warning_blocks_and_preserves_identity(
        cached_runner_project: Path,
        *,
        homonym: bool,
    ) -> None:
        """Serial collection blocks on every warning, MRO violations included."""
        runner = runner_for(cached_runner_project)
        category = c.FlextSmellViolation.__name__ if homonym else "ConsumerNotice"
        declaration = (
            f"class {category}(UserWarning):\n    pass\n"
            if homonym
            else f"from flext_core import c\n\nclass {category}(c.FlextSmellViolation):\n    pass\n"
        )
        (
            cached_runner_project
            / c.Infra.DEFAULT_SRC_DIR
            / "runner_sample"
            / "notices.py"
        ).write_text(declaration, encoding="utf-8")
        (cached_runner_project / "conftest.py").write_text(
            f"import warnings\nfrom runner_sample.notices import {category}\n\n"
            "def pytest_collection_finish(session):\n"
            "    if session.config.getoption('collectonly'):\n"
            "        warnings.simplefilter('always')\n"
            f"        warnings.warn('serial policy evidence', {category})\n",
            encoding="utf-8",
        )
        with pytest.raises(RuntimeError, match="collection contains blocking findings"):
            runner.execute()

        (receipt,) = (cached_runner_project / runner.reports).glob(
            "*/testmon-selection.events.diagnostics.json",
        )
        diagnostics = m.Infra.PytestDiagnostics.model_validate_json(receipt.read_text())
        tm.that(diagnostics.warning_count, eq=1)
        tm.that(diagnostics.warning_lines[0], contains="serial policy evidence")
        events = receipt.with_name("testmon-selection.events.jsonl")
        identity = m.Infra.PytestWarningEvent.model_validate_json(
            events
            .with_suffix(c.Infra.PYTEST_WARNING_EVENTS_SUFFIX)
            .read_text()
            .strip(),
        )
        tm.that(identity.category, eq=category)
        tm.that(identity.category_module, eq="runner_sample.notices")

    @staticmethod
    @pytest.mark.slow
    def test_warm_inventory_captures_warnings_from_stable_modules(
        cached_runner_project: Path,
    ) -> None:
        """A file omitted by testmon remains covered by complete collection policy."""
        runner = runner_for(cached_runner_project)
        target = cached_runner_project / runner.target
        (target / "test_stable.py").write_text(
            "from pathlib import Path\nimport warnings\n\n"
            "if Path(__file__).with_name('emit-warning').exists():\n"
            "    warnings.warn('stable inventory finding', RuntimeWarning)\n\n"
            "def test_stable():\n    assert 17 == 17\n",
            encoding="utf-8",
        )
        tm.that(tm.ok(runner.execute()), eq=0)
        reports_root = cached_runner_project / runner.reports
        existing = set(reports_root.glob("*/run-context.json"))
        (target / "emit-warning").touch()

        inventory_runner = runner_for(cached_runner_project)
        with pytest.raises(RuntimeError, match="collection contains blocking findings"):
            inventory_runner.execute()

        (context,) = set(reports_root.glob("*/run-context.json")) - existing
        selection = m.Infra.PytestCollectionManifest.model_validate_json(
            (context.parent / "testmon-selection.json").read_text(),
        )
        tm.that(selection.node_ids, eq=())
        diagnostics = m.Infra.PytestDiagnostics.model_validate_json(
            (context.parent / "testmon-inventory.events.diagnostics.json").read_text(),
        )
        tm.that(diagnostics.warning_count, eq=1)
        tm.that(diagnostics.warning_lines[0], contains="stable inventory finding")
        tm.that((context.parent / "suite-outcome.json").exists(), eq=False)

    @staticmethod
    @pytest.mark.slow
    def test_coverage_pass_fails_loud_on_collection_policy_error(
        policy_violation_project: Path,
    ) -> None:
        """The coverage inventory rejects the same collection policy violation."""
        runner = runner_for(policy_violation_project)

        with pytest.raises(RuntimeError) as raised:
            runner.execute_coverage()

        tm.that(str(raised.value), has=["FLEXT slow timeout policy", "test_policy.py"])
