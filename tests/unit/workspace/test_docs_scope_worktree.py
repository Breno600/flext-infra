"""Documentation scope behavior inside linked-worktree directory layouts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsScopeWorktree:
    """Contract for docs scope classification inside a linked-worktree lane."""

    def test_project_scope_uses_declared_name_inside_worktree_lane(
        self, tmp_path: Path
    ) -> None:
        """Classify a project from metadata, not the worktree directory basename."""
        lane = tmp_path / ".worktrees" / "lane-example"
        package = lane / "src" / "flext_demo"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (lane / "pyproject.toml").write_text(
            '[project]\nname = "flext-demo"\ndependencies = ["flext-core>=0.1.0"]\n',
            encoding="utf-8",
        )

        result = u.Infra.build_scopes(
            lane, projects=None, output_dir=c.Infra.DEFAULT_DOCS_OUTPUT_DIR
        )

        tm.ok(result)
        tm.that([scope.name for scope in result.value], eq=["flext-demo"])
        tm.that(result.value[0].path, eq=lane.resolve())
