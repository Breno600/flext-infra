"""Rendered GitHub workflows satisfy the YAML inline-comment spacing contract."""

from __future__ import annotations

import itertools
from typing import TYPE_CHECKING

import pytest
import yaml
from flext_tests import tm

from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraWorkflowCommentSpacing:
    """Every generated workflow keeps two spaces before an inline comment.

    yamllint's ``comments`` rule (``min-spaces-from-content: 2``) runs in every
    consumer gate. A template with ``contents: write # reason`` projected a
    lint failure into each repository that renders it.
    """

    _WORKFLOW_PREFIX = ".github/workflows/"
    _MIN_SPACES = 2

    @staticmethod
    def _inline_comment_offenders(text: str) -> list[str]:
        """Return inline comments closer than two spaces to their content.

        Mirrors yamllint: a comment is the text between two scanner tokens,
        and it is inline when it starts on the line where the previous token
        ends. Block-scalar bodies are token content, so shell ``#`` never
        counts.
        """
        offenders: list[str] = []
        lines = text.splitlines()
        tokens = list(yaml.scan(text, Loader=yaml.SafeLoader))
        for previous, following in itertools.pairwise(tokens):
            gap = text[previous.end_mark.index : following.start_mark.index]
            first_line = gap.split("\n", 1)[0]
            if "#" not in first_line:
                continue
            spaces = first_line[: first_line.index("#")]
            line = lines[previous.end_mark.line]
            if not line[: previous.end_mark.column].strip():
                continue
            if len(spaces) < TestsFlextInfraWorkflowCommentSpacing._MIN_SPACES:
                offenders.append(f"{previous.end_mark.line + 1}: {line}")
        return offenders

    @pytest.mark.slow
    def test_rendered_workflows_keep_two_spaces_before_inline_comments(
        self, tmp_path: Path
    ) -> None:
        """Render the governed workflow surface and lint its inline comments."""
        root = tmp_path / "project"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "fixture-project",
            workspace="fixture-workspace",
            database="project_database",
            issue_prefix="project-prefix",
        )

        plan = u.Tests.governed_project_plan(root)
        workflows = {
            item.path.relative_to(root).as_posix(): tm.not_none(
                item.desired_content
            ).decode("utf-8")
            for item in plan.files
            if item.path.relative_to(root).as_posix().startswith(self._WORKFLOW_PREFIX)
            and item.desired_content is not None
        }

        tm.that(workflows, has=f"{self._WORKFLOW_PREFIX}ci.yml")
        tm.that(workflows, lacks=f"{self._WORKFLOW_PREFIX}release.yml")
        tm.that(
            {
                path: self._inline_comment_offenders(text)
                for path, text in workflows.items()
            },
            eq={key: [] for key in workflows},
        )
