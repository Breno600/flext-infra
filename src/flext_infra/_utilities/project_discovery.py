"""Project discovery helpers for flext-infra utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from functools import lru_cache
from operator import attrgetter
from pathlib import Path
from typing import override

from flext_cli import u

from .._config import FlextInfraConfig
from ..constants import c
from ..models import m
from ..typings import t
from . import FlextInfraUtilitiesGit, FlextInfraUtilitiesProjectDiscoveryCandidatesMixin
from .workspace_manifest import FlextInfraUtilitiesWorkspaceManifest


class FlextInfraUtilitiesProjectDiscovery(
    FlextInfraUtilitiesProjectDiscoveryCandidatesMixin
):
    """Static helpers for discovering governed project roots in a workspace."""

    @classmethod
    @lru_cache(maxsize=1)
    def load_refactor_config(cls, repository_root: Path) -> m.Infra.RefactorConfigSpec:
        """Load declared refactor configuration, propagating invalid manifests."""
        manifest_path = FlextInfraUtilitiesWorkspaceManifest.workspace_manifest_path(
            repository_root
        )
        if not manifest_path.is_file():
            return m.Infra.RefactorConfigSpec()
        loaded = u.Cli.config_load(manifest_path, expand_env=False).unwrap()
        manifest = m.Infra.WorkspaceManifestSpec.model_validate(loaded.data)
        return manifest.refactor or m.Infra.RefactorConfigSpec()

    @classmethod
    @lru_cache(maxsize=1)
    def manifest_nonparticipant_paths(cls, repository_root: Path) -> frozenset[str]:
        """Return every manifest-relative path that is not a generation participant.

        One authority for project scope. The transaction derives its participants
        from the workspace manifest, so discovery must derive its candidates from
        exactly the same declaration or the two disagree and a plan is produced
        for a directory the transaction cannot stage into.

        Three manifest fields declare "not ours to generate", and the manifest
        model itself already unions them for validation (`external_paths` in
        `WorkspaceManifestSpec._validate_references`): `exclusions`,
        `content_only` and `external_dependency_paths`. Honouring only
        `exclusions` is what moved this defect from one directory to the next
        instead of ending it.

        Paths are manifest-relative POSIX strings, never leaf names: two
        directories may share a leaf, and excluding by name would silently
        exclude the wrong tree.

        An absent manifest declares no exclusions. An unreadable or invalid
        manifest fails before discovery can expand the declared scope.
        """
        manifest_path = FlextInfraUtilitiesWorkspaceManifest.workspace_manifest_path(
            repository_root
        )
        if not manifest_path.is_file():
            return frozenset()
        loaded = u.Cli.config_load(manifest_path, expand_env=False).unwrap()
        manifest = m.Infra.WorkspaceManifestSpec.model_validate(loaded.data)
        declared = (
            *(exclusion.path for exclusion in manifest.exclusions),
            *manifest.content_only,
            *manifest.external_dependency_paths,
        )
        return frozenset(
            posix
            for path in declared
            if (posix := Path(path).as_posix()) not in {".", ""}
        )

    @classmethod
    def _is_nonparticipant(
        cls, candidate: Path, repository_root: Path, nonparticipants: frozenset[str]
    ) -> bool:
        """Return whether one candidate lies at or under a declared non-participant."""
        # "Is this candidate inside the root?" is a question, not a failure, so
        # it is asked instead of caught. relative_to raised ValueError for the
        # ordinary outside-the-root case, which made an except branch produce a
        # value and hid any real path error behind the same sentinel.
        resolved = candidate.resolve()
        root = repository_root.resolve()
        if not resolved.is_relative_to(root):
            return False
        posix = resolved.relative_to(root).as_posix()
        if posix in {".", ""}:
            return False
        return any(
            posix == declared or posix.startswith(f"{declared}/")
            for declared in nonparticipants
        )

    @classmethod
    @override
    def discover_project_candidates(
        cls, repository_root: Path, *, scan_dirs: frozenset[str] | None = None
    ) -> t.SequenceOf[Path]:
        """Enumerate candidates, dropping every manifest-excluded directory.

        The exclusion is applied at this single shared enumerator rather than in
        each caller. Every discovery consumer -- docs scope, lazy-init
        generation, refactor scans -- goes through here, and filtering per
        caller is what let a declared exclusion be honoured by one stage and
        ignored by the next: discovery skipped an excluded submodule while
        lazy-init still planned files inside it and failed with "lazy-init file
        has no transaction participant".
        """
        candidates = super().discover_project_candidates(
            repository_root, scan_dirs=scan_dirs
        )
        nonparticipants = cls.manifest_nonparticipant_paths(repository_root)
        if not nonparticipants:
            return candidates
        return tuple(
            candidate
            for candidate in candidates
            if not cls._is_nonparticipant(candidate, repository_root, nonparticipants)
        )

    @classmethod
    def discover_project_roots(
        cls, repository_root: Path, *, scan_dirs: frozenset[str] | None = None
    ) -> t.SequenceOf[Path]:
        """Discover all project directories under repository root.

        Algorithm:
          1. Check if repository_root itself looks like a project
          2. Enumerate only projects declared by the root's own ``.gitmodules``.
          3. Return the root and declared projects in deterministic order.

        Args:
            repository_root: Root directory to start search from.
            scan_dirs: Directory names indicating a project exists (e.g., "src", "tests").
                Must be frozenset for use as constant. Defaults to standard project dirs.

        Returns:
            Project roots sorted by their ``.gitmodules`` declaration order.

        """
        declared_paths = FlextInfraUtilitiesGit.git_declared_submodule_paths(
            repository_root
        )
        if declared_paths.failure:
            raise ValueError(declared_paths.error or "invalid .gitmodules")
        configured_projects = tuple(path.as_posix() for path in declared_paths.value)
        candidates = cls.discover_project_candidates(
            repository_root, scan_dirs=scan_dirs
        )
        resolved_repository_root = repository_root.resolve()
        if not configured_projects:
            return candidates
        configured_order = {name: idx for idx, name in enumerate(configured_projects)}
        ordered: list[Path] = []

        def configured_key(candidate: Path) -> t.Pair[int, str]:
            relative = candidate.relative_to(resolved_repository_root).as_posix()
            return configured_order.get(
                relative, len(configured_projects)
            ), candidate.name

        non_root_candidates = sorted(
            (c for c in candidates if c != resolved_repository_root), key=configured_key
        )
        ordered.extend(non_root_candidates)
        return ordered

    @classmethod
    def discover_rope_project_roots(cls, repository_root: Path) -> t.SequenceOf[Path]:
        """Return every direct Python project sharing one Rope workspace root.

        The raw child scan below is a second enumerator, so it must honour the
        same manifest authority as ``discover_project_candidates``. Without that
        filter every direct child holding a ``pyproject.toml`` re-entered the
        scope the manifest had just excluded, and lazy-init planned files for a
        directory the transaction has no participant for -- which aborts staging
        after the phase root already exists on disk.
        """
        resolved_root = repository_root.resolve()
        declared = cls.discover_project_candidates(resolved_root)
        nonparticipants = cls.manifest_nonparticipant_paths(resolved_root)
        direct = tuple(
            child.resolve()
            for child in sorted(resolved_root.iterdir(), key=attrgetter("name"))
            if child.is_dir()
            and not child.name.startswith(".")
            and (child / c.PYPROJECT_FILENAME).is_file()
            and not cls._is_nonparticipant(child, resolved_root, nonparticipants)
        )
        return tuple(sorted({*declared, *direct}, key=Path.as_posix))

    @classmethod
    def ast_grep_scan_targets(cls, repository_root: Path) -> t.StrSequence:
        """Return only governed handwritten Python surfaces as scan targets.

        A workspace root is not itself a Python source surface. Passing ``.`` to
        ast-grep also traverses generated agent hooks and other managed
        projections, so a project-local ``make mod`` could rewrite files owned by
        another generator. The refactor config is the single scope owner for
        source trees; root Python modules cover public entry points such as
        ``conftest.py`` without opening hidden directories.
        """
        resolved_root = repository_root.resolve()
        refactor_config = cls.load_refactor_config(resolved_root)
        scan_dirs = refactor_config.project_scan_dirs
        targets: set[str] = set()
        for project in cls.governed_project_roots(resolved_root):
            # Python files directly in the project root (e.g., conftest.py)
            for target in project.glob(f"*{c.Infra.EXT_PYTHON}"):
                if target.exists():
                    targets.add(target.relative_to(resolved_root).as_posix())
            # Recursively scan configured directories for Python files
            for directory in scan_dirs:
                scan_dir = project / directory
                if scan_dir.exists():
                    for target in scan_dir.rglob(f"*{c.Infra.EXT_PYTHON}"):
                        if target.is_file():
                            targets.add(target.relative_to(resolved_root).as_posix())
        return tuple(sorted(targets))

    @classmethod
    def governed_project_roots(cls, repository_root: Path) -> t.SequenceOf[Path]:
        """Return the workspace root and each declared repository exactly once."""
        resolved_root = repository_root.resolve()
        return tuple(
            dict.fromkeys((
                resolved_root,
                *(
                    project.resolve()
                    for project in cls.discover_project_roots(resolved_root)
                ),
            ))
        )

    @staticmethod
    def external_tool_state_dir(
        repository_root: Path, project_root: Path, tool_name: str
    ) -> Path:
        """Resolve one governed project's canonical state outside the checkout."""
        resolved_workspace = repository_root.resolve()
        resolved_project = project_root.resolve()
        if not resolved_project.is_relative_to(resolved_workspace):
            msg = f"project root is outside workspace: {resolved_project}"
            raise ValueError(msg)
        tool_component = Path(tool_name)
        if (
            tool_component.is_absolute()
            or tool_component.name != tool_name
            or tool_name in {"", ".", ".."}
        ):
            msg = f"tool_name must be one relative directory name: {tool_name!r}"
            raise ValueError(msg)
        state_root: Path = (
            resolved_workspace.parent
            / FlextInfraConfig.fetch_global().Infra.codegen.toolchain.state_directory_name
            / resolved_workspace.name
            / tool_name
        )
        relative_project = resolved_project.relative_to(resolved_workspace)
        return (
            state_root if relative_project == Path() else state_root / relative_project
        )


__all__: list[str] = ["FlextInfraUtilitiesProjectDiscovery"]
