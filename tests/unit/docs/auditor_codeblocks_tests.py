"""Regression tests for docs codeblock and exported-docstring auditing.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraAuditorCodeblocks:
    """Regression tests for docs codeblock and exported-docstring auditing."""

    @staticmethod
    def test_docs_python_codeblock_issues_ignore_snippet_only_rules(
        tmp_path: Path,
    ) -> None:
        """Test docs python codeblock issues ignore snippet only rules."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "snippet.md").write_text(
            "```python\n"
            "def ready() -> bool:\n"
            '    """Report readiness.\n\n'
            "    Returns:\n"
            "        Whether the service is ready.\n"
            '    """\n'
            "    return True\n"
            "```\n",
            encoding="utf-8",
        )
        scope = m.Infra.DocScope(
            name="test",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )

        issues = u.Infra.docs_python_codeblock_issues(scope)

        tm.that(issues, eq=[])

    @staticmethod
    def test_docs_python_codeblock_issues_report_unbound_name(
        tmp_path: Path,
    ) -> None:
        """Executable snippets cannot rely on an unseen surrounding import."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "snippet.md").write_text(
            "```python\nresult = unavailable_name()\n```\n",
            encoding="utf-8",
        )
        scope = m.Infra.DocScope(
            name="test",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )
        issues = u.Infra.docs_python_codeblock_issues(scope)
        tm.that(len(issues), eq=1)
        tm.that(issues[0].file, eq="docs/snippet.md")
        tm.that(issues[0].issue_type, eq="python_codeblock")

    @staticmethod
    def test_docs_python_codeblock_issues_report_invalid_python(
        tmp_path: Path,
    ) -> None:
        """Test docs python codeblock issues report invalid python."""
        docs_dir = tmp_path / "docs"
        docs_dir.mkdir(parents=True, exist_ok=True)
        (docs_dir / "broken.md").write_text(
            "```python\n**Happy coding!** 🚀\n```\n",
            encoding="utf-8",
        )
        scope = m.Infra.DocScope(
            name="test",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )

        issues = u.Infra.docs_python_codeblock_issues(scope)

        tm.that(len(issues), eq=1)
        tm.that(issues[0].issue_type, eq="python_codeblock")
        tm.that(issues[0].file, eq="docs/broken.md")

        with pytest.raises(RuntimeError, match="Ruff could not fix"):
            u.Infra.docs_fix_python_codeblocks(scope, apply=True)

    @staticmethod
    def test_scanner_excerpt_requires_non_executable_text_fence(
        tmp_path: Path,
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
            name="test",
            path=tmp_path,
            report_dir=tmp_path / "reports",
        )

        python_issues = u.Infra.docs_python_codeblock_issues(scope)

        tm.that(len(python_issues), eq=1)
        tm.that(python_issues[0].issue_type, eq="python_codeblock")

        evidence.write_text(f"```text\n{excerpt}```\n", encoding="utf-8")

        tm.that(evidence.read_text(encoding="utf-8"), has=excerpt)
        tm.that(u.Infra.docs_python_codeblock_issues(scope), eq=[])

    @staticmethod
    def test_docstring_issues_accept_assignment_docstrings(
        tmp_path: Path,
    ) -> None:
        """Test docstring issues accept assignment docstrings."""
        package_root = tmp_path / "src" / "demo_pkg"
        package_root.mkdir(parents=True, exist_ok=True)
        (package_root / "__init__.py").write_text(
            '"""Demo package."""\n',
            encoding="utf-8",
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
