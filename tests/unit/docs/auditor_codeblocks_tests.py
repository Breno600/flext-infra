"""Regression tests for docs codeblock and exported-docstring auditing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraAuditorCodeblocks:
    """Regression tests for docs codeblock and exported-docstring auditing."""

    def test_docs_python_codeblock_issues_ignore_snippet_only_rules(
        self, tmp_path: Path
    ) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "snippet.md").write_text(
            "```python\ndef ready() -> bool:\n    return True\n\n\nassert ready()\n```\n",
            encoding="utf-8",
        )
        scope = m.Infra.DocScope(
            name="test", path=tmp_path, report_dir=tmp_path / "reports"
        )

        issues = u.Infra.docs_python_codeblock_issues(scope)

        tm.that(issues, eq=[])

    def test_docs_python_codeblock_issues_report_invalid_python(
        self, tmp_path: Path
    ) -> None:
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "broken.md").write_text(
            "```python\n**Happy coding!** 🚀\n```\n", encoding="utf-8"
        )
        scope = m.Infra.DocScope(
            name="test", path=tmp_path, report_dir=tmp_path / "reports"
        )

        issues = u.Infra.docs_python_codeblock_issues(scope)

        tm.that(len(issues), eq=1)
        tm.that(issues[0].issue_type, eq="python_codeblock")
        tm.that(issues[0].file, eq="docs/broken.md")

    def test_scanner_excerpt_requires_non_executable_text_fence(
        self, tmp_path: Path
    ) -> None:
        """Keep numbered scanner evidence intact without presenting it as Python."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        excerpt = (
            "      157                  continue\n"
            ">>>   158              rewritten = rewrite(lines)\n"
        )
        evidence = docs_dir / "scanner-triage.md"
        evidence.write_text(f"```python\n{excerpt}```\n", encoding="utf-8")
        scope = m.Infra.DocScope(
            name="test", path=tmp_path, report_dir=tmp_path / "reports"
        )

        python_issues = u.Infra.docs_python_codeblock_issues(scope)

        tm.that(len(python_issues), eq=1)
        tm.that(python_issues[0].issue_type, eq="python_codeblock")

        evidence.write_text(f"```text\n{excerpt}```\n", encoding="utf-8")

        tm.that(evidence.read_text(encoding="utf-8"), has=excerpt)
        tm.that(u.Infra.docs_python_codeblock_issues(scope), eq=[])

    def test_docstring_issues_accept_assignment_docstrings(
        self, tmp_path: Path
    ) -> None:
        package_root = tmp_path / "src" / "demo_pkg"
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text(
            '"""Demo package."""\n', encoding="utf-8"
        )
        (package_root / "lazy.py").write_text(
            '"""Lazy helpers for docs tests."""\n\n'
            "from __future__ import annotations\n\n"
            "class DemoLazy:\n"
            '    """Simple lazy holder for docs tests."""\n\n'
            "lazy = DemoLazy()\n"
            '"""Shared lazy singleton."""\n',
            encoding="utf-8",
        )

        issues = u.Infra.docstring_issues(
            tmp_path,
            {
                "package_name": "demo_pkg",
                "modules": ["demo_pkg.lazy"],
                "target_map": {"lazy": "demo_pkg.lazy"},
            },
        )

        tm.that(issues, eq=[])
