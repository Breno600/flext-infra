"""Project discovery helpers for flext-infra utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from functools import lru_cache
from operator import attrgetter
from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_cli import u

from flext_infra import c, config, m
from flext_infra._utilities import (
    FlextInfraUtilitiesGit,
    FlextInfraUtilitiesWorkspaceManifest,
)
from flext_infra._utilities._project_discovery_candidates import (
    FlextInfraUtilitiesProjectDiscoveryCandidatesMixin,
)

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraUtilitiesProjectDiscovery(
    FlextInfraUtilitiesProjectDiscoveryCandidatesMixin,
):
    """Static helpers for discovering governed project roots in a workspace."""

    @classmethod
    @lru_cache(maxsize=1)
    def load_refactor_config(cls, repository_root: Path) -> m.Infra.RefactorConfigSpec:
        """Load declared refactor configuration, propagating invalid manifests.

        Returns:
            The resulting ``m.Infra.RefactorConfigSpec``.

        """
        manifest_path = FlextInfraUtilitiesWorkspaceManifest.workspace_manifest_path(
            repository_root,
        )
        packaged = m.Infra.RefactorConfigSpec(
            project_scan_dirs=config.Infra.source_scan.roots,
        )
        if not manifest_path.is_file():
            return packaged
        loaded = u.Cli.config_load(manifest_path, expand_env=False).unwrap()
        manifest = m.Infra.WorkspaceManifestSpec.model_validate(loaded.data)
        if manifest.refactor is None:
            return packaged
        return manifest.refactor

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

        Returns:
            Every manifest-relative path that is not a generation participant.

        """
        manifest_path = FlextInfraUtilitiesWorkspaceManifest.workspace_manifest_path(
            repository_root,
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
        cls,
        candidate: Path,
        repository_root: Path,
        nonparticipants: frozenset[str],
    ) -> bool:
        """Return whether one candidate lies at or under a declared non-participant.

        Returns:
            Whether one candidate lies at or under a declared non-participant.

        """
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
        cls,
        repository_root: Path,
        *,
        scan_dirs: frozenset[str] | None = None,
    ) -> t.SequenceOf[Path]:
        """Enumerate candidates, dropping every manifest-excluded directory.

        The exclusion is applied at this single shared enumerator rather than in
        each caller. Every discovery consumer -- docs scope, lazy-init
        generation, refactor scans -- goes through here, and filtering per
        caller is what let a declared exclusion be honoured by one stage and
        ignored by the next: discovery skipped an excluded submodule while
        lazy-init still planned files inside it and failed with "lazy-init file
        has no transaction participant".

        Returns:
            The resulting ``t.SequenceOf[Path]``.

        """
        candidates = super().discover_project_candidates(
            repository_root,
            scan_dirs=scan_dirs,
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
        cls,
        repository_root: Path,
        *,
        scan_dirs: frozenset[str] | None = None,
    ) -> t.SequenceOf[Path]:
        """Discover all project directories under repository root.

        Algorithm:
          1. Check if repository_root itself looks like a project
          2. Enumerate only projects declared by the root's own ``.gitmodules``.
          3. Return the root and declared projects in deterministic order.

        Args:
            repository_root: Root directory to start search from.
            scan_dirs: Directory names indicating a project (e.g., "src", "tests").
                Must be a frozenset constant. Defaults to standard project dirs.

        Returns:
            Project roots sorted by their ``.gitmodules`` declaration order.

        Raises:
            ValueError: If ``declared.failure``.

        """
        declared = FlextInfraUtilitiesGit.git_submodule_declarations(repository_root)
        if declared.failure:
            raise ValueError(declared.error or "invalid .gitmodules")
        configured_projects = tuple(item.path.as_posix() for item in declared.value)
        candidates = cls.discover_project_candidates(
            repository_root,
            scan_dirs=scan_dirs,
        )
        resolved_repository_root = repository_root.resolve()
        if not configured_projects:
            return candidates
        configured_order = {name: idx for idx, name in enumerate(configured_projects)}
        ordered: list[Path] = []

        def configured_key(candidate: Path) -> t.Pair[int, str]:
            relative = candidate.relative_to(resolved_repository_root).as_posix()
            return configured_order.get(
                relative,
                len(configured_projects),
            ), candidate.name

        non_root_candidates = sorted(
            (c for c in candidates if c != resolved_repository_root),
            key=configured_key,
        )
        ordered.extend(non_root_candidates)
        return ordered

    @classmethod
    def discover_rope_project_roots(cls, repository_root: Path) -> t.SequenceOf[Path]:
        """Return every Python project this repository's Rope workspace owns.

        A declared submodule is another repository: it is consumed as an
        installed library and never indexed from here (every repository
        evaluates only itself). The raw child scan
        below is a second enumerator, so it must honour the same manifest
        authority as ``discover_project_candidates``. Without that filter every
        direct child holding a ``pyproject.toml`` re-entered the scope the
        manifest had just excluded, and lazy-init planned files for a directory
        the transaction has no participant for -- which aborts staging after the
        phase root already exists on disk.

        Returns:
            Every Python project this repository's Rope workspace owns.

        Raises:
            ValueError: If ``declared_paths.failure``.

        """
        resolved_root = repository_root.resolve()
        declared_paths = FlextInfraUtilitiesGit.git_submodule_declarations(
            resolved_root,
        )
        if declared_paths.failure:
            raise ValueError(declared_paths.error or "invalid .gitmodules")
        submodules = frozenset(
            (resolved_root / item.path).resolve() for item in declared_paths.value
        )
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
        return tuple(
            sorted(
                {root for root in (*declared, *direct) if root not in submodules},
                key=Path.as_posix,
            ),
        )

    @classmethod
    def ast_grep_scan_targets(cls, repository_root: Path) -> t.StrSequence:
        """Return only governed handwritten Python surfaces as scan targets.

        A workspace root is not itself a Python source surface. Passing ``.`` to
        ast-grep also traverses generated agent hooks and other managed
        projections, so a project-local ``make mod`` could rewrite files owned by
        another generator. The refactor config is the single scope owner for
        source trees; root Python modules cover public entry points such as
        ``conftest.py`` without opening hidden directories.

        Returns:
            Only governed handwritten Python surfaces as scan targets.

        """
        resolved_root = repository_root.resolve()
        refactor_config = cls.load_refactor_config(resolved_root)
        scan_dirs = refactor_config.project_scan_dirs
        targets: set[str] = set()
        for project in cls.governed_project_roots(resolved_root):
            for suffix in c.Infra.PYTHON_SOURCE_SUFFIXES:
                # Python files directly in the project root (e.g., conftest.py)
                for target in project.glob(f"*{suffix}"):
                    if target.exists():
                        targets.add(target.relative_to(resolved_root).as_posix())
                # Recursively scan configured directories for Python sources:
                # modules and the stubs the catalog rules also govern.
                for directory in scan_dirs:
                    cls._collect_scan_dir_targets(
                        project / directory,
                        f"*{suffix}",
                        resolved_root,
                        targets,
                    )
        nonparticipants = cls.manifest_nonparticipant_paths(resolved_root)
        return tuple(
            target
            for target in sorted(targets)
            if not cls._is_nonparticipant(
                resolved_root / target, resolved_root, nonparticipants
            )
        )

    @staticmethod
    def _collect_scan_dir_targets(
        scan_dir: Path,
        pattern: str,
        resolved_root: Path,
        targets: set[str],
    ) -> None:
        """Add every Python file under one configured scan directory.

        Trees the codegen artifact SSOT ignores for source scans (generated
        sources included) are outside the inventory the semantic phases
        index, so they never become scan or rewrite targets either.
        """
        if not scan_dir.exists():
            return
        ignored = frozenset(config.Infra.codegen.source_scan_ignored)
        for target in scan_dir.rglob(pattern):
            if target.is_file() and not ignored.intersection(
                target.relative_to(scan_dir).parts,
            ):
                targets.add(target.relative_to(resolved_root).as_posix())

    @classmethod
    def governed_project_roots(cls, repository_root: Path) -> t.SequenceOf[Path]:
        """Return the repositories a verb run at ``repository_root`` governs.

        Every repository evaluates and rewrites only itself: a workspace root
        consumes its declared members as installed libraries and never scans,
        checks, or rewrites them; each member runs its own verbs in its own
        repository.

        Returns:
            The repositories a verb run at ``repository_root`` governs.

        """
        return (repository_root.resolve(),)

    @staticmethod
    def nearest_project_root(repository_root: Path, path: Path) -> Path | None:
        """Find the nearest manifest owner inside one governed repository.

        Returns:
            The resulting ``Path | None``.

        """
        boundary = repository_root.resolve()
        candidate = path.resolve()
        if not candidate.is_relative_to(boundary):
            return None
        for parent in (candidate, *candidate.parents):
            if (parent / c.PYPROJECT_FILENAME).is_file():
                return parent
            if parent == boundary:
                return None
        return None

    @staticmethod
    def runtime_environment_dir(
        project_root: Path,
        *,
        runtime_root: Path | None = None,
    ) -> Path:
        """Resolve the checkout's Python environment.

        A declared ``runtime_root`` (the generated Makefile's ``RUNTIME_ROOT``)
        owns the environment. Undeclared, the owner derives it: a subproject
        checked out inside a workspace uses the workspace environment; a
        standalone checkout owns its local environment. A linked Git worktree
        uses the environment its primary worktree uses, wherever Git places
        the lane, exactly as the generated Makefile and ``.envrc`` resolve it.

        Returns:
            The resulting ``Path``.

        """
        if runtime_root is None:
            runtime = FlextInfraUtilitiesGit.git_repository_root(
                m.Infra.GitRepoRequest(repo_root=project_root),
            ).unwrap()
            runtime_root = runtime.repository_root
        owner = runtime_root.resolve()
        if (owner / c.Infra.GIT_DIR).is_file():
            identity = FlextInfraUtilitiesGit.git_identity(
                m.Infra.GitRepoRequest(repo_root=owner),
            ).unwrap()
            if identity.is_worktree:
                return FlextInfraUtilitiesProjectDiscovery.runtime_environment_dir(
                    identity.primary_root,
                )
        return owner / c.Infra.ENVIRONMENT_DIRECTORY

    @classmethod
    def runtime_python(
        cls,
        project_root: Path,
        *,
        runtime_root: Path | None = None,
    ) -> Path:
        """Resolve the fixed Python entrypoint inside the managed environment.

        ``runtime_root`` mirrors ``runtime_environment_dir``: a declared runtime
        root (the generated Makefile's ``RUNTIME_ROOT``) owns the environment.

        Returns:
            The resulting ``Path``.

        """
        return (
            cls.runtime_environment_dir(project_root, runtime_root=runtime_root)
            / ("Scripts" if sys.platform == "win32" else "bin")
            / ("python.exe" if sys.platform == "win32" else c.Infra.PYTHON)
        )


__all__: list[str] = ["FlextInfraUtilitiesProjectDiscovery"]
