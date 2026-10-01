"""Release staging carries the project's prepared dist inputs.

A project build hook may force-include inputs its own lifecycle generates
under ``dist/``. The stage is a Git archive and never contains ignored build
outputs, so the builder mirrors the prepared files verbatim; the hook keeps
ownership of the names and of failing when one is missing.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.release import FlextInfraReleaseProjectMixin

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraReleaseStageInputs:
    """Behavior contract for mirroring prepared release inputs into a stage."""

    def test_prepared_dist_inputs_are_mirrored_verbatim(self, tmp_path: Path) -> None:
        """Every regular file in the project dist lands in the staged dist."""
        project = tmp_path / "project"
        stage = tmp_path / "stage"
        prepared = project / "dist"
        prepared.mkdir(parents=True)
        (prepared / "pylock.example.toml").write_text("lock = 1\n", encoding="utf-8")
        (prepared / "source-receipt.json").write_text(
            '{"head": "a"}\n',
            encoding="utf-8",
        )
        stage.mkdir()

        mirrored = FlextInfraReleaseProjectMixin.mirror_release_inputs(project, stage)

        tm.ok(mirrored)
        staged = stage / "dist"
        tm.that(
            sorted(path.name for path in staged.iterdir()),
            eq=["pylock.example.toml", "source-receipt.json"],
        )
        tm.that(
            (staged / "pylock.example.toml").read_text(encoding="utf-8"),
            eq="lock = 1\n",
        )

    def test_project_without_dist_stages_unchanged(self, tmp_path: Path) -> None:
        """No dist directory is invented for a project that prepares none."""
        project = tmp_path / "project"
        stage = tmp_path / "stage"
        project.mkdir()
        stage.mkdir()

        mirrored = FlextInfraReleaseProjectMixin.mirror_release_inputs(project, stage)

        tm.ok(mirrored)
        tm.that((stage / "dist").exists(), eq=False)

    def test_non_regular_dist_entry_fails_loud(self, tmp_path: Path) -> None:
        """A directory inside dist is refused instead of silently dropped."""
        project = tmp_path / "project"
        stage = tmp_path / "stage"
        nested = project / "dist" / "nested"
        nested.mkdir(parents=True)
        stage.mkdir()

        mirrored = FlextInfraReleaseProjectMixin.mirror_release_inputs(project, stage)

        tm.that(
            tm.fail(mirrored),
            eq="project dist must contain only regular files: " + str(nested),
        )
