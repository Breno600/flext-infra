"""Tests for layout gitignore, tracked-file moves, and the canonical render.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, infra
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.codegen.layout import FlextInfraCodegenLayout
from flext_infra.codegen.project_new import FlextInfraCodegenProjectNew
from tests import u
from tests.unit.codegen.layout_fixture import (
    archive_root,
    build_loose_project,
    layout_engine,
)


class TestsFlextInfraCodegenLayoutGitignore:
    """Test suite for layout gitignore, tracked-file moves, and canonical render."""

    @staticmethod
    def test_apply_adds_gitignore_entries_exactly_once(tmp_path: Path) -> None:
        """Gitignore additions from the SSOT are appended once across applies."""
        project = build_loose_project(tmp_path, name="flext-cli")
        (project / "settings.json").write_text("{}\n", encoding="utf-8")
        engine = layout_engine(tmp_path, apply_changes=True)

        first = engine.execute()
        tm.ok(first)
        second = engine.execute()
        tm.ok(second)

        gitignore = (project / c.Infra.GITIGNORE).read_text(encoding="utf-8")
        # Why: count exact ENTRIES, never substrings. The SSOT also carries
        # negations such as !.vscode/settings.json, so a substring count reports
        # two occurrences for a file that was appended exactly once.
        entries = gitignore.splitlines()
        tm.that(entries.count("settings.json"), eq=1)
        tm.that(entries.count(f"{archive_root()}/"), eq=1)
        tm.that(
            (project / archive_root() / project.name / "settings.json").is_file(),
            eq=True,
        )

    @staticmethod
    def test_apply_uses_git_mv_for_tracked_files(tmp_path: Path) -> None:
        """Tracked sources move through git so history follows the rename."""
        project = build_loose_project(tmp_path)
        engine = layout_engine(tmp_path, apply_changes=True)

        result = engine.execute()

        tm.ok(result)
        tracked = u.Cli.capture([c.Infra.GIT, "ls-files"], cwd=project)
        tm.ok(tracked)
        tracked_names = set(tracked.value.split())
        tm.that("docs/guides/intro.md" in tracked_names, eq=True)
        tm.that("guides/intro.md" in tracked_names, eq=False)
        tm.that(
            f"{archive_root()}/{project.name}/output.log" in tracked_names,
            eq=False,
        )

    @staticmethod
    def test_managed_gitignore_render_includes_layout_additions() -> None:
        """The canonical gitignore render owns the layout SSOT additions."""
        rendered = FlextInfraCodegenConform.render_project_gitignore(
            config.Infra.codegen,
            profile=c.Infra.MakeProfile.STANDALONE,
            project_name="flext-cli",
        )

        tm.ok(rendered)
        tm.that(rendered.value, has="settings.json")
        tm.that(rendered.value, has=f"{archive_root()}/")

    @staticmethod
    def test_rendered_gitignore_keeps_backup_named_python_sources(
        tmp_path: Path,
    ) -> None:
        """A backup module is source code even when its name contains backup."""
        rendered = FlextInfraCodegenConform.render_project_gitignore(
            config.Infra.codegen,
            profile=c.Infra.MakeProfile.STANDALONE,
            project_name="flext-cli",
        )
        tm.ok(rendered)
        (tmp_path / ".gitignore").write_text(rendered.value, encoding="utf-8")
        tm.ok(u.Cli.capture([c.Infra.GIT, "init"], cwd=tmp_path))
        source = tmp_path / "src" / "dc_backup" / "workspace_backup_request.py"
        source.parent.mkdir(parents=True)
        source.write_text("pass\n", encoding="utf-8")
        tracked = u.Cli.capture(
            [c.Infra.GIT, "check-ignore", str(source.relative_to(tmp_path))],
            cwd=tmp_path,
        )
        tm.that(tracked.failure, eq=True)

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize("directory_suffix", ["", "-lane"])
    def test_rendered_gitignore_satisfies_layout_additions(
        tmp_path: Path,
        directory_suffix: str,
    ) -> None:
        """The public gitignore renderer satisfies the layout consumer.

        The planner used to render ``base/gitignore.j2`` from its own section list
        without the layout override, so ``make gen`` never satisfied the layout gate
        and a governed member ended up hand-editing the projection. One owner now
        derives the sections for every renderer: after conform, the layout engine
        finds no missing gitignore pattern for a project declared in the SSOT.

        The override is keyed by the declared ``[project].name``, never by the
        checkout directory: a linked worktree named after its lane renders the same
        additions (conform used ``repository_root.name`` and dropped them there).
        """
        owner, override = next(
            (name, item)
            for name, item in sorted(
                config.Infra.codegen.layout.project_overrides.items(),
            )
            if item.gitignore_additions
        )
        # The new project is created inside a governed workspace: its Taplo pin
        # resolves through the nearest committed mise.lock above it.
        u.Tests.copy_tracked_mise_seeds(tmp_path)
        root = tmp_path / f"{owner}{directory_suffix}"
        repository = u.Tests.repository_ref(owner)
        project = u.Tests.project_spec(owner)
        tm.ok(
            infra.codegen_new(
                FlextInfraCodegenProjectNew(
                    flext_source=u.Tests.flext_source(),
                    name=owner,
                    kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
                    output_root=root,
                    provider=repository.provider,
                    repository_url=repository.url,
                    repository_branch=u.Tests.provider_branch(),
                    flext_repository_url=u.Tests.repository_ref(config.Infra.name).url,
                    flext_repository_ref=u.Tests.provider_branch(),
                    license=project.license,
                    author_name=project.author_name,
                    author_email=project.author_email,
                    upstream=project.upstream,
                    year=project.year,
                    apply_changes=True,
                ),
            ),
        )
        tm.that(
            (root / c.CONFIG_DIR_NAME / c.Infra.WORKSPACE_MANIFEST_FILENAME).is_file(),
            eq=True,
        )
        entries = (root / c.Infra.GITIGNORE).read_text(encoding="utf-8").splitlines()
        missing = tuple(
            pattern
            for pattern in override.gitignore_additions
            if entries.count(pattern) != 1
        )
        tm.that(missing, eq=())
        report = FlextInfraCodegenLayout(repository_root=root).check_project(root)
        tm.that(
            tuple(
                finding for finding in report.findings if finding.rule == "gitignore"
            ),
            eq=(),
        )

    @staticmethod
    def test_layout_preserves_tracked_ignored_files_and_ignores_local_artifacts(
        tmp_path: Path,
    ) -> None:
        """Local ignored files are not layout inputs; tracked files stay."""
        project = build_loose_project(tmp_path)
        local = project / "local-artifact"
        tracked = project / "tracked-artifact"
        local.write_text("local\n", encoding="utf-8")
        tracked.write_text("tracked\n", encoding="utf-8")
        ignore = project / c.Infra.GITIGNORE
        content = ignore.read_text(encoding="utf-8") if ignore.exists() else ""
        ignore.write_text(
            f"{content}\n{local.name}\n{tracked.name}\n",
            encoding="utf-8",
        )
        tm.ok(
            u.Cli.capture(
                [c.Infra.GIT, "add", "--force", "--", tracked.name],
                cwd=project,
            ),
        )

        report = layout_engine(tmp_path, apply_changes=False).plan_project(project)

        paths = {finding.path for finding in report.findings}
        tm.that(local.name in paths, eq=False)
        tm.that(tracked.name in paths, eq=True)
