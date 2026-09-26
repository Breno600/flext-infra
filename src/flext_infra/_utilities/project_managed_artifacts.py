"""Load and compose project-owned managed-artifact configuration."""

from __future__ import annotations

import os
import stat
from collections.abc import MutableMapping
from pathlib import Path

from flext_cli import u

from flext_core import r
from flext_infra import c, m, p, t

from .git import FlextInfraUtilitiesGit


class FlextInfraUtilitiesProjectManagedArtifacts:
    """Single owner for ``ManagedArtifacts`` across ``config/*.yaml`` files."""

    @classmethod
    def snapshot_config_sources(
        cls, project_dir: Path
    ) -> p.Result[t.VariadicTuple[m.Cli.AtomicFileState]]:
        """Capture one stable, physical, direct ``config/*.yaml`` file set.

        A project root that is not materialized yet (a scaffold planned
        read-only) owns no config sources, exactly like an absent ``config/``.
        """
        if not project_dir.exists() and not project_dir.is_symlink():
            return r[tuple[m.Cli.AtomicFileState, ...]].ok(())
        project_identity = cls._required_directory_identity(
            project_dir, purpose="project root"
        )
        if project_identity.failure:
            return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(project_identity)
        config_dir = project_dir / c.CONFIG_DIR_NAME
        identity = cls._config_directory_identity(config_dir)
        if identity.failure:
            return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(identity)
        if not identity.value:
            return r[tuple[m.Cli.AtomicFileState, ...]].ok(())
        paths = cls._config_yaml_paths(config_dir, identity.value)
        if paths.failure:
            return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(paths)
        sources: list[m.Cli.AtomicFileState] = []
        for path in paths.value:
            source = u.Cli.atomic_read_binary_file_state(path, required=True)
            if source.failure:
                return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(source)
            sources.append(source.value)
        stable_paths = cls._config_yaml_paths(config_dir, identity.value)
        if stable_paths.failure:
            return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(stable_paths)
        if stable_paths.value != paths.value:
            return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                f"{c.Infra.CONFIG_SNAPSHOT_TOPOLOGY_RACE_MARKER}: {config_dir}"
            )
        stable_project = cls._required_directory_identity(
            project_dir, purpose="project root"
        )
        if stable_project.failure:
            return r[tuple[m.Cli.AtomicFileState, ...]].from_failure(stable_project)
        if stable_project.value != project_identity.value:
            return r[tuple[m.Cli.AtomicFileState, ...]].fail(
                f"{c.Infra.CONFIG_SNAPSHOT_ROOT_RACE_MARKER}: {project_dir}"
            )
        return r[tuple[m.Cli.AtomicFileState, ...]].ok(tuple(sources))

    @classmethod
    def _required_directory_identity(
        cls, path: Path, *, purpose: str
    ) -> p.Result[t.VariadicTuple[int]]:
        try:
            state = path.lstat()
        except OSError as exc:
            return r[t.VariadicTuple[int]].fail_op(f"inspect {purpose}", exc)
        attributes = getattr(state, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if not stat.S_ISDIR(state.st_mode) or attributes & reparse:
            return r[t.VariadicTuple[int]].fail(
                f"{purpose} is not a physical directory: {path}"
            )
        return r[t.VariadicTuple[int]].ok(cls._directory_state_key(state))

    @classmethod
    def _config_directory_identity(
        cls, config_dir: Path
    ) -> p.Result[t.VariadicTuple[int]]:
        try:
            state = config_dir.lstat()
        except FileNotFoundError:
            return r[t.VariadicTuple[int]].ok(())
        except OSError as exc:
            return r[t.VariadicTuple[int]].fail_op(
                "inspect project config directory", exc
            )
        attributes = getattr(state, "st_file_attributes", 0)
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if not stat.S_ISDIR(state.st_mode) or attributes & reparse:
            return r[t.VariadicTuple[int]].fail(
                f"project config path is not a physical directory: {config_dir}"
            )
        return r[t.VariadicTuple[int]].ok(cls._directory_state_key(state))

    @staticmethod
    def empty_snapshot() -> m.Infra.ProjectManagedArtifactsSnapshot:
        """Return the explicit managed-artifact state for a future scaffold."""
        return m.Infra.ProjectManagedArtifactsSnapshot(
            sources=(),
            resolution=m.Infra.ProjectManagedArtifactsResolution(
                artifacts=m.Infra.ProjectManagedArtifactsConfig(), mise_tool_sources={}
            ),
        )

    @classmethod
    def _config_yaml_paths(
        cls, config_dir: Path, expected_identity: t.VariadicTuple[int]
    ) -> p.Result[t.VariadicTuple[Path]]:
        try:
            paths = tuple(
                sorted(path for path in config_dir.iterdir() if path.suffix == ".yaml")
            )
        except OSError as exc:
            return r[t.VariadicTuple[Path]].fail_op(
                "enumerate project config sources", exc
            )
        current = cls._config_directory_identity(config_dir)
        if current.failure:
            return r[t.VariadicTuple[Path]].from_failure(current)
        if current.value != expected_identity:
            return r[t.VariadicTuple[Path]].fail(
                f"project config directory changed during snapshot: {config_dir}"
            )
        return r[t.VariadicTuple[Path]].ok(paths)

    @staticmethod
    def _directory_state_key(state: os.stat_result) -> t.VariadicTuple[int]:
        return (
            state.st_dev,
            state.st_ino,
            state.st_mode,
            state.st_uid,
            state.st_gid,
            state.st_size,
            state.st_mtime_ns,
            state.st_ctime_ns,
        )

    @classmethod
    def load_project_managed_artifacts(
        cls, project_dir: Path
    ) -> p.Result[m.Infra.ProjectManagedArtifactsResolution]:
        """Snapshot every YAML once and parse that exact source set."""
        snapshot = cls.snapshot_project_managed_artifacts(project_dir)
        if snapshot.failure:
            return r[m.Infra.ProjectManagedArtifactsResolution].from_failure(snapshot)
        return r[m.Infra.ProjectManagedArtifactsResolution].ok(
            snapshot.value.resolution
        )

    @classmethod
    def snapshot_project_managed_artifacts(
        cls, project_dir: Path
    ) -> p.Result[m.Infra.ProjectManagedArtifactsSnapshot]:
        """Capture and parse exactly one immutable project configuration view."""
        source_snapshot = cls.snapshot_config_sources(project_dir)
        if source_snapshot.failure:
            return r[m.Infra.ProjectManagedArtifactsSnapshot].from_failure(
                source_snapshot
            )
        resolution = cls.load_project_managed_artifacts_from_snapshot(
            source_snapshot.value
        )
        if resolution.failure:
            return r[m.Infra.ProjectManagedArtifactsSnapshot].from_failure(resolution)
        return r[m.Infra.ProjectManagedArtifactsSnapshot].ok(
            m.Infra.ProjectManagedArtifactsSnapshot(
                sources=source_snapshot.value, resolution=resolution.value
            )
        )

    @classmethod
    def load_committed_project_managed_artifacts(
        cls, project_dir: Path
    ) -> p.Result[m.Infra.ProjectManagedArtifactsResolution]:
        """Load ManagedArtifacts from the project's committed ``HEAD`` catalog.

        Render inputs are ``f(SSOT, templates, PINS)``. A worktree can carry
        concurrent WIP, so codegen renders project overlays only from the
        immutable commit catalog; uncommitted declarations never enter a
        projection.
        """
        snapshot = cls.snapshot_committed_project_managed_artifacts(project_dir)
        if snapshot.failure:
            return r[m.Infra.ProjectManagedArtifactsResolution].from_failure(snapshot)
        return r[m.Infra.ProjectManagedArtifactsResolution].ok(
            snapshot.value.resolution
        )

    @classmethod
    def snapshot_committed_project_managed_artifacts(
        cls, project_dir: Path
    ) -> p.Result[m.Infra.ProjectManagedArtifactsSnapshot]:
        """Capture and parse the committed catalog without physical source states.

        ``sources`` stays empty because Git objects are already immutable: they
        must not enter the transaction's live-file source barrier, and their
        object identity makes a physical re-read meaningless.
        """
        resolved = project_dir.expanduser().resolve()
        blobs = FlextInfraUtilitiesGit.git_committed_directory_blobs(
            resolved, c.CONFIG_DIR_NAME
        )
        if blobs.failure:
            return r[m.Infra.ProjectManagedArtifactsSnapshot].fail(
                f"cannot open committed project config catalog at {resolved}: "
                f"{blobs.error}"
            )
        payloads: t.MutableMappingKV[Path, bytes] = {
            resolved / c.CONFIG_DIR_NAME / name: content
            for name, content in sorted(blobs.value.items())
            if name.endswith(".yaml")
        }
        if not payloads:
            return r[m.Infra.ProjectManagedArtifactsSnapshot].ok(cls.empty_snapshot())
        resolution = cls._load_project_managed_artifacts_from_payloads(payloads)
        if resolution.failure:
            return r[m.Infra.ProjectManagedArtifactsSnapshot].from_failure(resolution)
        return r[m.Infra.ProjectManagedArtifactsSnapshot].ok(
            m.Infra.ProjectManagedArtifactsSnapshot(
                sources=(), resolution=resolution.value
            )
        )

    @classmethod
    def load_project_managed_artifacts_from_snapshot(
        cls, source_snapshot: t.VariadicTuple[m.Cli.AtomicFileState]
    ) -> p.Result[m.Infra.ProjectManagedArtifactsResolution]:
        """Parse one caller-owned immutable project YAML snapshot."""
        payloads: t.MutableMappingKV[Path, bytes] = {}
        for source_state in source_snapshot:
            if source_state.content is None:
                return r[m.Infra.ProjectManagedArtifactsResolution].fail(
                    f"project config snapshot is absent: {source_state.path}"
                )
            payloads[source_state.path] = source_state.content
        return cls._load_project_managed_artifacts_from_payloads(payloads)

    @classmethod
    def _load_project_managed_artifacts_from_payloads(
        cls, payloads: t.MappingKV[Path, bytes]
    ) -> p.Result[m.Infra.ProjectManagedArtifactsResolution]:
        """Parse one immutable path-to-bytes project YAML catalog."""
        if not payloads:
            return r[m.Infra.ProjectManagedArtifactsResolution].ok(
                cls.empty_snapshot().resolution
            )
        ruff_ignores: MutableMapping[str, set[str]] = {}
        mise_tools: MutableMapping[str, m.Infra.ProjectMiseTool] = {}
        mise_sources: MutableMapping[str, Path] = {}
        gitignore_patterns: list[str] = []

        for source, content in sorted(payloads.items()):
            try:
                source_text = content.decode(c.Cli.ENCODING_DEFAULT)
            except UnicodeDecodeError as exc:
                return r[m.Infra.ProjectManagedArtifactsResolution].fail_op(
                    f"decode project config source {source}", exc
                )
            loaded = u.Cli.yaml_parse(source_text)
            if loaded.failure:
                return r[m.Infra.ProjectManagedArtifactsResolution].from_failure(loaded)
            managed = loaded.value.get("ManagedArtifacts")
            if not managed:
                continue
            project_config = m.Infra.ProjectConfigDocument.model_validate({
                "ManagedArtifacts": managed
            })
            artifacts = project_config.ManagedArtifacts
            for pattern, rules in artifacts.Ruff.per_file_ignores.items():
                ruff_ignores.setdefault(pattern, set()).update(rules)
            for pattern in artifacts.Gitignore.patterns:
                if pattern not in gitignore_patterns:
                    gitignore_patterns.append(pattern)
            for selector, tool in artifacts.Mise.tools.items():
                previous = mise_sources.get(selector)
                if previous is not None:
                    return r[m.Infra.ProjectManagedArtifactsResolution].fail(
                        "duplicate project Mise selector "
                        f"{selector!r}: {previous} and {source}"
                    )

                mise_tools[selector] = tool
                mise_sources[selector] = source
        artifacts = m.Infra.ProjectManagedArtifactsConfig(
            Ruff=m.Infra.ProjectRuffConfig(
                per_file_ignores={
                    pattern: tuple(sorted(rules))
                    for pattern, rules in sorted(ruff_ignores.items())
                }
            ),
            Mise=m.Infra.ProjectMiseConfig(tools=dict(sorted(mise_tools.items()))),
            Gitignore=m.Infra.ProjectGitignoreConfig(
                patterns=tuple(gitignore_patterns)
            ),
        )
        return r[m.Infra.ProjectManagedArtifactsResolution].ok(
            m.Infra.ProjectManagedArtifactsResolution(
                artifacts=artifacts,
                mise_tool_sources=dict(sorted(mise_sources.items())),
            )
        )

    @classmethod
    def compose_mise_toml_from_snapshot(
        cls, source_snapshot: t.VariadicTuple[m.Cli.AtomicFileState], rendered: str
    ) -> p.Result[str]:
        """Add local tools from one caller-owned immutable YAML snapshot."""
        resolved = cls.load_project_managed_artifacts_from_snapshot(source_snapshot)
        if resolved.failure:
            return r[str].from_failure(resolved)
        return cls.compose_mise_toml_from_resolution(resolved.value, rendered)

    @classmethod
    def compose_mise_toml_from_resolution(
        cls, resolution: m.Infra.ProjectManagedArtifactsResolution, rendered: str
    ) -> p.Result[str]:
        """Add local tools from one caller-owned immutable parsed catalog."""
        local_tools = resolution.artifacts.Mise.tools
        if not local_tools:
            return r[str].ok(rendered)
        doc = u.Cli.toml_parse_text(rendered)
        if doc is None:
            return r[str].fail("canonical .mise.toml template is invalid")
        tools = u.Cli.toml_ensure_table(doc, "tools")
        for selector, tool in local_tools.items():
            if selector in tools:
                # Resilient composition (operator law 2026-09-18): a project
                # declaring a tool the fleet now provides is promotion residue,
                # never an ambiguous contract. The fleet SSOT wins, the stale
                # local declaration is reported for removal, and generation
                # keeps flowing instead of blocking every consumer.
                source = resolution.mise_tool_sources[selector]
                u.Cli.warning(
                    "project Mise selector "
                    f"{selector!r} ({source}) is now a fleet tool; "
                    "the fleet version wins — remove the local declaration"
                )
                continue
            tools[selector] = tool.version
        return r[str].ok(u.Cli.toml_dumps(doc))


__all__: t.VariadicTuple[str] = ("FlextInfraUtilitiesProjectManagedArtifacts",)
