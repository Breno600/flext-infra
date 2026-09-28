"""Shared markdown-gate surface: collection, config, and ignore resolution.

``markdown`` (rumdl) and ``markdown-format`` (prettier) drive different tools
over the same governed markdown surface, so the file collection and the
ignore-projection reader live here exactly once.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_infra import c, u

from .base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import m, t


def collect_markdown_files(project_dir: Path) -> list[Path]:
    """Collect the governed markdown surface shared by both markdown gates.

    The walker is git-scope aware, so generated/untracked trees (``.venv``,
    ``target``, ``dist``, ``build``) never enter the surface; provider and
    agent projections (``.agents``, ``.claude``, ``.gemini``, ``.beads``,
    ``.github`` agent directories) are excluded with the check vocabulary.
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


def read_ignore_patterns(project_dir: Path, ignore_filename: str) -> t.StrSequence:
    """Read non-comment patterns from a generated markdown ignore projection."""
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


class FlextInfraMarkdownGateBase(FlextInfraGate):
    """Share file selection and empty-surface handling for Markdown tools."""

    @override
    def _get_check_dirs(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrSequence:
        """Return the governed Markdown paths relative to their repository."""
        _ = ctx
        return [
            str(path.relative_to(project_dir))
            for path in collect_markdown_files(project_dir)
        ]

    @override
    def check(
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> m.Infra.GateExecution:
        """Validate the selected Markdown files or report an empty surface."""
        started = time.monotonic()
        check_dirs = self._get_check_dirs(project_dir, ctx)
        if not check_dirs:
            return self._neutral_skip_result(
                project_dir,
                started,
                message=f"{self.gate_id}: no markdown files to check",
            )
        return self._execute_check_command(project_dir, ctx, check_dirs, started)


__all__: list[str] = [
    "FlextInfraMarkdownGateBase",
    "collect_markdown_files",
    "read_ignore_patterns",
]
