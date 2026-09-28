"""Public tests for docs-related write helpers."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import m, t, u


class TestsFlextInfraDocsSharedWrite:
    """Public tests for docs-related write helpers."""

    _MIN_MARKDOWN_NEWLINES = 3

    def test_json_write_round_trips_dict_payload(self, tmp_path: Path) -> None:
        json_file = tmp_path / "nested/data.json"

        result = u.Cli.json_write(json_file, {"key": "value", "number": 42})
        read_result = u.Cli.json_read(json_file)

        tm.ok(result)
        tm.ok(read_result)
        expected: t.JsonMapping = {"key": "value", "number": 42}
        tm.that(read_result.unwrap(), eq=expected)

    def test_json_write_accepts_pydantic_model(self, tmp_path: Path) -> None:
        json_file = tmp_path / "report.json"
        report = m.Infra.DocsPhaseReport(
            phase="audit", scope="root", items=[], checks=[], strict=False, passed=True
        )

        result = u.Cli.json_write(json_file, report)

        tm.ok(result)
        tm.that(json_file.exists(), eq=True)

    def test_write_markdown_writes_exact_content(self, tmp_path: Path) -> None:
        md_file = tmp_path / "exact.md"
        lines = ["Line 1", "Line 2", "Line 3"]

        result = u.Infra.write_markdown(md_file, lines)

        tm.ok(result)
        tm.that(md_file.read_text(), eq="Line 1\nLine 2\nLine 3\n")

    def test_write_markdown_preserves_empty_lines(self, tmp_path: Path) -> None:
        md_file = tmp_path / "empty-lines.md"

        result = u.Infra.write_markdown(md_file, ["# Title", "", "", "Content"])

        tm.ok(result)
        tm.that(md_file.read_text().count("\n") >= self._MIN_MARKDOWN_NEWLINES, eq=True)

    def test_write_markdown_fails_for_non_directory_parent(self) -> None:
        result = u.Infra.write_markdown(Path("/dev/null/test.md"), ["test"])

        tm.fail(result)
        tm.that((result.error or ""), has="markdown write error")
