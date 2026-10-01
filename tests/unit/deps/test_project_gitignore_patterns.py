"""Project-owned ignore patterns: declaration, composition, and rendering."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m, u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import t


class TestsFlextInfraProjectGitignorePatterns:
    """A project declares the ignores the fleet scaffold cannot know."""

    @staticmethod
    def _project(root: Path, documents: t.MappingKV[str, str]) -> Path:
        root.mkdir(parents=True)
        (root / "config").mkdir()
        for name, body in documents.items():
            (root / "config" / name).write_text(body, encoding="utf-8")
        return root

    def test_declared_patterns_render_as_one_project_section(
        self, tmp_path: Path
    ) -> None:
        root = self._project(
            tmp_path / "project",
            {
                "tooling.yaml": (
                    "ManagedArtifacts:\n  Gitignore:\n    patterns:\n"
                    "      - .dmypy/\n      - mcp/generated/*\n"
                    "      - '!mcp/generated/.gitkeep'\n"
                )
            },
        )

        rendered = FlextInfraCodegenConform.render_project_gitignore(
            config.Infra.codegen,
            profile=c.Infra.MakeProfile.STANDALONE,
            project_name=root.name,
            project_dir=root,
        )

        text = tm.ok(rendered)
        section = text.index(c.Infra.GITIGNORE_PROJECT_SECTION_NAME)
        assert text.index(".dmypy/", section) < text.index("mcp/generated/*", section)
        assert "!mcp/generated/.gitkeep" in text[section:]

    def test_patterns_compose_across_documents_without_duplicates(
        self, tmp_path: Path
    ) -> None:
        root = self._project(
            tmp_path / "project",
            {
                "one.yaml": "ManagedArtifacts:\n  Gitignore:\n    patterns: [.dmypy/, logs/]\n",
                "two.yaml": "ManagedArtifacts:\n  Gitignore:\n    patterns: [logs/, .serena/]\n",
            },
        )

        resolved = u.Infra.load_project_managed_artifacts(root)

        patterns = tm.ok(resolved).artifacts.Gitignore.patterns
        assert sorted(patterns) == [".dmypy/", ".serena/", "logs/"]
        assert len(patterns) == 3

    def test_absent_declaration_adds_no_section(self, tmp_path: Path) -> None:
        root = self._project(
            tmp_path / "project", {"tooling.yaml": "ManagedArtifacts: {}\n"}
        )

        rendered = FlextInfraCodegenConform.render_project_gitignore(
            config.Infra.codegen,
            profile=c.Infra.MakeProfile.STANDALONE,
            project_name=root.name,
            project_dir=root,
        )

        assert c.Infra.GITIGNORE_PROJECT_SECTION_NAME not in tm.ok(rendered)

    def test_empty_pattern_is_rejected(self, tmp_path: Path) -> None:
        root = self._project(
            tmp_path / "project",
            {"tooling.yaml": "ManagedArtifacts:\n  Gitignore:\n    patterns: ['']\n"},
        )

        with pytest.raises(m.ValidationError):
            u.Infra.load_project_managed_artifacts(root)
