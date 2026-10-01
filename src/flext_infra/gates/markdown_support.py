"""Shared markdown-gate surface: collection, config, and ignore resolution.

``markdown`` (rumdl) and ``markdown-format`` (prettier) drive different tools
over the same governed markdown surface, so the file collection and the
ignore-projection reader live here exactly once.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_infra import c, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import m, t


class FlextInfraMarkdownGateBase(FlextInfraGate):
    """Share file selection and empty-surface handling for Markdown tools."""

    @staticmethod
    def collect_markdown_files(project_dir: Path) -> list[Path]:
        """Collect the governed markdown surface shared by both markdown gates.

        The walker is git-scope aware, so generated/untracked trees (``.venv``,
        ``target``, ``dist``, ``build``) never enter the surface; provider and
        agent projections (``.agents``, ``.claude``, ``.gemini``, ``.beads``,
        ``.github`` agent directories) are excluded with the check vocabulary.

        Returns:
            The resulting ``list[Path]``.

        """
        markdown_files: list[Path] = []
        for path in u.Infra.iter_matching_files(project_dir, includes=["*.md"]):
            relative_parts = path.relative_to(project_dir).parts
            if any(part in c.Infra.CHECK_EXCLUDED_DIRS for part in relative_parts):
                continue
            if (
                len(relative_parts) > 1
                and relative_parts[0] == ".github"
                and relative_parts[1] in c.Infra.GITHUB_AGENT_PROJECTION_DIRS
            ):
                continue
            markdown_files.append(path)
        return markdown_files

    @staticmethod
    def read_ignore_patterns(project_dir: Path, ignore_filename: str) -> t.StrSequence:
        """Read non-comment patterns from a generated markdown ignore projection.

        Returns:
            The resulting ``t.StrSequence``.

        """
        ignore_path = project_dir / ignore_filename
        if not ignore_path.is_file():
            return ()
        patterns: list[str] = []
        for line in ignore_path.read_text(c.Cli.ENCODING_DEFAULT).splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            patterns.append(stripped)
        return tuple(patterns)

    @override
    def selected_for(self, project_dir: Path) -> bool:
        """Only a project with governed Markdown selects a Markdown gate.

        Returns:
            The resulting ``bool``.

        """
        return bool(self.collect_markdown_files(project_dir))

    @override
    def _get_check_dirs(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.StrSequence:
        """Return the governed Markdown paths relative to their repository.

        Returns:
            The governed Markdown paths relative to their repository.

        """
        _ = ctx
        return [
            str(path.relative_to(project_dir))
            for path in self.collect_markdown_files(project_dir)
        ]


__all__: list[str] = ["FlextInfraMarkdownGateBase"]
