"""Shared markdown-gate surface: collection, config, and the rumdl invocation.

``markdown`` (``rumdl check``) and ``markdown-format`` (``rumdl fmt``) drive
the same tool over the same governed markdown surface with the same generated
configuration, so the file collection, the ignore-projection reader, and the
rumdl invocation contract live here exactly once.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_infra import c, config, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import m, t


class FlextInfraMarkdownGateBase(FlextInfraGate):
    """Share file selection, configuration, and the rumdl invocation."""

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

    @staticmethod
    @override
    def _findings_exit_codes() -> t.VariadicTuple[int]:
        """Exit statuses with which rumdl reports its findings.

        Returns:
            The findings statuses declared for rumdl in the tooling config.

        """
        return config.Infra.tooling.tools.markdown.findings_exit_codes

    @staticmethod
    def _resolve_config_args(project_dir: Path) -> t.StrSequence:
        """Resolve only the repository-local markdown settings owner.

        Returns:
            The resulting ``t.StrSequence``.

        """
        config_path = project_dir / c.Infra.MARKDOWNLINT_CONFIG_FILENAME
        if not config_path.is_file():
            return ["--no-config"]
        return ["--config", str(config_path.resolve())]

    def _resolve_exclude_args(self, project_dir: Path) -> t.StrSequence:
        """Build ``--exclude`` from .markdownlintignore patterns.

        ``rumdl`` only applies ignore patterns when scanning directories,
        not when files are passed explicitly on the command line. The gates
        collect files explicitly, so the generated ignore projection is read
        once and its patterns are forwarded via ``--exclude`` to replicate
        standard tool behavior.

        Returns:
            The resulting ``t.StrSequence``.

        """
        patterns = self.read_ignore_patterns(
            project_dir,
            c.Infra.MARKDOWNLINT_IGNORE_FILENAME,
        )
        if not patterns:
            return ()
        return ["--exclude", ",".join(patterns)]

    def _rumdl_command(
        self,
        project_dir: Path,
        subcommand: str,
        targets: t.StrSequence,
        *mode_args: str,
    ) -> t.StrSequence:
        """Keep every markdown gate on the same rumdl invocation contract.

        Returns:
            The rumdl ``subcommand`` invocation over ``targets``.

        """
        return self._python_console_script_command(
            c.Infra.RUMDL,
            subcommand,
            *mode_args,
            "--no-cache",
            "--color",
            "never",
            "--output-format",
            "text",
            "--deny-config-warnings",
            *self._resolve_config_args(project_dir),
            *self._resolve_exclude_args(project_dir),
            *targets,
        )

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
