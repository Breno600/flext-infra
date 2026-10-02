"""Behavior tests for FlextInfraPytestDiagExtractor.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from defusedxml import ElementTree as DefusedET
from flext_tests import tm

from flext_infra import FlextInfraPytestDiagExtractor, c, t
from tests import m

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraPytestDiag:
    """Tests for ``FlextInfraPytestDiag``."""

    @staticmethod
    def _extractor(
        junit: Path,
        log: Path,
        *,
        failed: Path | None = None,
        errors: Path | None = None,
        warnings: Path | None = None,
        slowest: Path | None = None,
        skips: Path | None = None,
        events: str = '{"$report_type":"SessionStart"}\n'
        '{"$report_type":"SessionFinish","exitstatus":0}\n',
        identities: str = "",
    ) -> FlextInfraPytestDiagExtractor:
        report_log = log.with_suffix(".jsonl")
        report_log.write_text(events, encoding="utf-8")
        report_log.with_suffix(c.Infra.PYTEST_WARNING_EVENTS_SUFFIX).write_text(
            identities,
            encoding="utf-8",
        )
        return FlextInfraPytestDiagExtractor(
            junit=junit,
            log=log,
            report_log=report_log,
            failed=failed,
            errors=errors,
            warnings=warnings,
            slowest=slowest,
            skips=skips,
        )

    @staticmethod
    def _identity(category: str, message: str, *, module: str = "consumer") -> str:
        return (
            m.Infra.PytestWarningEvent(
                category=category,
                category_module=module,
                category_qualname=category,
                filename="test_case.py",
                lineno=10,
                message=message,
            ).model_dump_json()
            + "\n"
        )

    def test_extract_valid_junit_xml(self, tmp_path: Path) -> None:
        """Test extract valid junit xml."""
        junit = tmp_path / "junit.xml"
        junit.write_text(
            '<?xml version="1.0"?><testsuites><testsuite name="t" tests="1"'
            ' failures="0" errors="0" skipped="0"></testsuite></testsuites>',
        )
        log = tmp_path / "log.txt"
        log.write_text("")

        report: m.Infra.PytestDiagnostics = tm.ok(
            self._extractor(junit, log).extract(
                junit,
                log,
                report_log=log.with_suffix(".jsonl"),
            ),
        )

        tm.that(report, is_=m.Infra.PytestDiagnostics)
        tm.that(report.failed_count, eq=0)
        tm.that(report.error_count, eq=0)

    def test_extract_missing_xml_preserves_file_error(self, tmp_path: Path) -> None:
        """Test extract missing xml preserves file error."""
        log = tmp_path / "log.txt"
        log.write_text("FAILED test_case.py::test_foo")
        missing_xml = tmp_path / "missing.xml"

        with pytest.raises(FileNotFoundError):
            self._extractor(missing_xml, log).extract(
                missing_xml,
                log,
                report_log=log.with_suffix(".jsonl"),
            )

    def test_extract_invalid_xml_preserves_parser_error(self, tmp_path: Path) -> None:
        """Test extract invalid xml preserves parser error."""
        log = tmp_path / "log.txt"
        log.write_text("")

        bad_xml = tmp_path / "bad.xml"
        bad_xml.write_text("invalid xml content")

        with pytest.raises(DefusedET.ParseError):
            self._extractor(bad_xml, log).extract(
                bad_xml,
                log,
                report_log=log.with_suffix(".jsonl"),
            )

    def test_extract_failed_and_error_tests_from_xml(self, tmp_path: Path) -> None:
        """Test extract failed and error tests from xml."""
        log = tmp_path / "log.txt"
        log.write_text("")
        fail_xml = tmp_path / "fail.xml"
        fail_xml.write_text(
            '<?xml version="1.0"?><testsuites><testsuite name="t" tests="1"'
            ' failures="1" errors="0" skipped="0"><testcase name="test_fail"'
            ' classname="TC" time="0.1"><failure message="fail">Traceback</failure>'
            "</testcase></testsuite></testsuites>",
        )

        fail_report: m.Infra.PytestDiagnostics = tm.ok(
            self._extractor(fail_xml, log).extract(
                fail_xml,
                log,
                report_log=log.with_suffix(".jsonl"),
            ),
        )
        tm.that(fail_report.failed_count, eq=1)
        tm.that(fail_report.error_count, eq=0)
        tm.that(fail_report.error_traces, length_gt=0)

        err_xml = tmp_path / "err.xml"
        err_xml.write_text(
            '<?xml version="1.0"?><testsuites><testsuite name="t" tests="1"'
            ' failures="0" errors="1" skipped="0"><testcase name="test_err"'
            ' classname="TC" time="0.1"><error message="err">Trace</error>'
            "</testcase></testsuite></testsuites>",
        )

        err_report: m.Infra.PytestDiagnostics = tm.ok(
            self._extractor(err_xml, log).extract(
                err_xml,
                log,
                report_log=log.with_suffix(".jsonl"),
            ),
        )
        tm.that(err_report.error_count, eq=1)

    def test_extract_skipped_and_slow_tests_from_xml(self, tmp_path: Path) -> None:
        """Test extract skipped and slow tests from xml."""
        log = tmp_path / "log.txt"
        log.write_text("")
        skip_xml = tmp_path / "skip.xml"
        skip_xml.write_text(
            '<?xml version="1.0"?><testsuites><testsuite name="t" tests="1"'
            ' failures="0" errors="0" skipped="1"><testcase name="test_skip"'
            ' classname="TC" time="0.1"><skipped message="skip"/>'
            "</testcase></testsuite></testsuites>",
        )

        skip_report: m.Infra.PytestDiagnostics = tm.ok(
            self._extractor(skip_xml, log).extract(
                skip_xml,
                log,
                report_log=log.with_suffix(".jsonl"),
            ),
        )
        tm.that(skip_report.skipped_count, eq=1)

        slow_xml = tmp_path / "slow.xml"
        slow_xml.write_text(
            '<?xml version="1.0"?><testsuites><testsuite name="t" tests="2">'
            '<testcase name="fast" time="0.1"/><testcase name="slow" time="5.5"/>'
            "</testsuite></testsuites>",
        )

        slow_report: m.Infra.PytestDiagnostics = tm.ok(
            self._extractor(slow_xml, log).extract(
                slow_xml,
                log,
                report_log=log.with_suffix(".jsonl"),
            ),
        )
        tm.that(slow_report.slow_entries, length_gt=0)

    def test_extract_missing_log_preserves_file_error(self, tmp_path: Path) -> None:
        """Test extract missing log preserves file error."""
        junit = tmp_path / "junit.xml"
        junit.write_text(
            '<?xml version="1.0"?><testsuites>'
            '<testsuite name="t" tests="0"/></testsuites>',
        )

        with pytest.raises(FileNotFoundError):
            self._extractor(junit, tmp_path / "missing.txt").extract(
                junit,
                tmp_path / "missing.txt",
                report_log=tmp_path / "missing.jsonl",
            )

    def test_extract_unreadable_log_surfaces_failure(self, tmp_path: Path) -> None:
        """Test extract unreadable log surfaces failure."""
        junit = tmp_path / "junit.xml"
        junit.write_text(
            '<?xml version="1.0"?><testsuites>'
            '<testsuite name="t" tests="0"/></testsuites>',
        )
        log_is_dir = tmp_path / "log_is_dir"
        log_is_dir.mkdir()

        with pytest.raises(IsADirectoryError):
            self._extractor(junit, log_is_dir).extract(
                junit,
                log_is_dir,
                report_log=log_is_dir.with_suffix(".jsonl"),
            )

    def test_extract_warnings_from_report_log(self, tmp_path: Path) -> None:
        """Test extract warnings from report log."""
        junit = tmp_path / "junit.xml"
        junit.write_text(
            '<?xml version="1.0"?><testsuites>'
            '<testsuite name="t" tests="0"/></testsuites>',
        )
        log = tmp_path / "log.txt"
        log.write_text(
            "=== FAILURES ===\n"
            "test_case.py::test_foo\n"
            "AssertionError: expected True\n"
            "=== short test summary info ===\n"
            "=== warnings summary ===\n"
            "DeprecationWarning: test warning\n"
            "-- Docs: https://docs.pytest.org/\n",
        )

        report: m.Infra.PytestDiagnostics = tm.ok(
            self._extractor(
                junit,
                log,
                events='{"$report_type":"WarningMessage",'
                '"category":"DeprecationWarning","filename":"test_case.py",'
                '"lineno":10,"message":"test warning","when":"runtest"}\n',
                identities=self._identity("DeprecationWarning", "test warning"),
            ).extract(junit, log, report_log=log.with_suffix(".jsonl")),
        )

        tm.that(report.error_count, eq=0)
        tm.that(report.warning_lines, length_gt=0)
        tm.that(report.warning_count, eq=1)

    def test_count_each_custom_warning_without_a_terminal_summary(
        self,
        tmp_path: Path,
    ) -> None:
        """Test count each custom warning without a terminal summary."""
        junit = tmp_path / "junit.xml"
        junit.write_text(
            '<?xml version="1.0"?><testsuites>'
            '<testsuite name="t" tests="0"/></testsuites>',
        )
        log = tmp_path / "log.txt"
        log.write_text("2 passed")
        event = (
            '{"$report_type":"WarningMessage","category":"DomainNotice",'
            '"filename":"test_case.py","lineno":10,"message":"first\\nsecond"}\n'
        )

        report: m.Infra.PytestDiagnostics = tm.ok(
            self._extractor(
                junit,
                log,
                events=event * 2,
                identities=self._identity("DomainNotice", "first\nsecond") * 2,
            ).extract(junit, log, report_log=log.with_suffix(".jsonl")),
        )

        tm.that(report.warning_count, eq=2)
        tm.that(report.warning_lines[0], contains="first\nsecond")

    def test_extract_invalid_duration_preserves_value_error(
        self,
        tmp_path: Path,
    ) -> None:
        """Test extract invalid duration preserves value error."""
        junit = tmp_path / "junit.xml"
        junit.write_text(
            '<?xml version="1.0"?><testsuites><testsuite name="t" tests="1">'
            '<testcase name="invalid" time="not-a-number"/>'
            "</testsuite></testsuites>",
        )
        log = tmp_path / "log.txt"
        log.write_text("")

        with pytest.raises(ValueError, match="not-a-number"):
            self._extractor(junit, log).extract(
                junit,
                log,
                report_log=log.with_suffix(".jsonl"),
            )

    def test_execute_writes_selected_output_files(self, tmp_path: Path) -> None:
        """Test execute writes selected output files."""
        junit = tmp_path / "junit.xml"
        junit.write_text(
            '<?xml version="1.0"?><testsuites><testsuite name="t" tests="2">'
            '<testcase name="test_fail" classname="TC" time="2.5">'
            '<failure message="fail">Traceback</failure></testcase>'
            '<testcase name="test_skip" classname="TC" time="0.1">'
            '<skipped message="skip"/></testcase></testsuite></testsuites>',
        )
        log = tmp_path / "log.txt"
        log.write_text(
            "=== warnings summary ===\n"
            "DeprecationWarning: test warning\n"
            "-- Docs: https://docs.pytest.org/\n",
        )
        extractor = self._extractor(
            junit,
            log,
            failed=tmp_path / "failed.txt",
            errors=tmp_path / "errors.txt",
            warnings=tmp_path / "warnings.txt",
            slowest=tmp_path / "slow.txt",
            skips=tmp_path / "skips.txt",
            events='{"$report_type":"WarningMessage",'
            '"category":"DeprecationWarning","filename":"test_case.py",'
            '"lineno":10,"message":"test warning"}\n',
            identities=self._identity("DeprecationWarning", "test warning"),
        )

        tm.ok(extractor.execute())

        tm.that((tmp_path / "failed.txt").read_text(), contains="TC::test_fail")
        tm.that((tmp_path / "errors.txt").read_text(), contains="Traceback")
        tm.that((tmp_path / "warnings.txt").read_text(), contains="DeprecationWarning")
        tm.that((tmp_path / "slow.txt").read_text(), contains="TC::test_fail")
        tm.that((tmp_path / "skips.txt").read_text(), contains="TC::test_skip")

    def test_mro_violation_warning_is_counted_like_every_warning(
        self,
        tmp_path: Path,
    ) -> None:
        """An MRO enforcement warning is one counted occurrence with its identity."""
        junit = tmp_path / "junit.xml"
        junit.write_text('<testsuites><testsuite name="t"/></testsuites>')
        log = tmp_path / "pytest.log"
        log.write_text("1 warning")
        category = c.FlextSmellViolation.__name__
        extractor = self._extractor(
            junit,
            log,
            events='{"$report_type":"WarningMessage",'
            f'"category":"{category}","filename":"test_case.py",'
            '"lineno":10,"message":"enforcement evidence"}\n',
            identities=self._identity(
                category,
                "enforcement evidence",
                module=c.FlextSmellViolation.__module__,
            ),
        )
        report = tm.ok(extractor.extract(junit, log, report_log=extractor.report_log))
        tm.that(report.warning_count, eq=1)
        tm.that(report.warning_lines[0], contains="enforcement evidence")
        tm.that(report.warning_lines[0], contains=c.FlextSmellViolation.__module__)

    @pytest.mark.parametrize(
        "events",
        [
            "",
            "not JSON\n",
            '{"$report_type":"WarningMessage","category":"DomainNotice"}\n',
            (
                '{"$report_type":"WarningMessage","category":"DomainNotice",'
                '"filename":"consumer.py","lineno":"invalid","message":"evidence"}\n'
            ),
        ],
        ids=["empty", "malformed", "incomplete", "invalid-line"],
    )
    def test_invalid_report_log_preserves_the_first_error(
        self,
        tmp_path: Path,
        events: str,
    ) -> None:
        """Missing warning evidence cannot become a zero-warning result."""
        junit = tmp_path / "junit.xml"
        junit.write_text('<testsuites><testsuite name="t"/></testsuites>')
        log = tmp_path / "pytest.log"
        log.write_text("consumer output")
        extractor = self._extractor(junit, log, events=events)
        with pytest.raises(ValueError, match=r"contains no events|validation error"):
            extractor.extract(junit, log, report_log=extractor.report_log)

    def test_missing_report_log_preserves_file_error(self, tmp_path: Path) -> None:
        """Test missing report log preserves file error."""
        junit = tmp_path / "junit.xml"
        junit.write_text('<testsuites><testsuite name="t"/></testsuites>')
        log = tmp_path / "pytest.log"
        log.write_text("consumer output")
        extractor = self._extractor(junit, log)
        with pytest.raises(FileNotFoundError):
            extractor.extract(junit, log, report_log=tmp_path / "missing.jsonl")

    def test_warning_without_identity_is_not_counted_as_green(
        self,
        tmp_path: Path,
    ) -> None:
        """Test warning without identity is not counted as green."""
        junit = tmp_path / "junit.xml"
        junit.write_text('<testsuites><testsuite name="t"/></testsuites>')
        log = tmp_path / "pytest.log"
        log.write_text("consumer output")
        extractor = self._extractor(
            junit,
            log,
            events='{"$report_type":"WarningMessage","category":"DomainNotice",'
            '"filename":"test_case.py","lineno":10,"message":"evidence"}\n',
        )
        with pytest.raises(ValueError, match="zip"):
            extractor.extract(junit, log, report_log=extractor.report_log)

    @staticmethod
    @pytest.mark.parametrize(
        ("phases", "expected"),
        [
            (("setup", "teardown"), "incomplete pytest lifecycle"),
            (("setup", "call"), "incomplete pytest lifecycle"),
            (("setup", "setup", "call", "teardown"), "duplicate pytest phase"),
        ],
        ids=["missing-call", "missing-teardown", "duplicate-setup"],
    )
    def test_report_log_rejects_incomplete_or_repeated_lifecycles(
        tmp_path: Path,
        phases: t.StrTuple,
        expected: str,
    ) -> None:
        """Every reported node needs exactly one setup, call and teardown."""
        report_log = tmp_path / "suite.events.jsonl"
        report_log.write_text(
            "".join(
                m.Infra.PytestReportEvent.model_validate({
                    "$report_type": "TestReport",
                    "nodeid": "tests/test_lifecycle.py::test_case",
                    "when": phase,
                    "outcome": "passed",
                }).model_dump_json(by_alias=True, exclude_none=True)
                + "\n"
                for phase in phases
            ),
            encoding="utf-8",
        )
        report_log.with_suffix(c.Infra.PYTEST_WARNING_EVENTS_SUFFIX).write_text(
            "",
            encoding="utf-8",
        )

        with pytest.raises(ValueError, match=expected):
            FlextInfraPytestDiagExtractor.extract_report_log(report_log)
