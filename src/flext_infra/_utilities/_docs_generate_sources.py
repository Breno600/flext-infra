"""Authenticated source discovery and CAS verification for docs generation.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_cli import u as cli_u

from flext_infra import c, m, p, r, t
from flext_infra._utilities import (
    FlextInfraUtilitiesCodegenFilePlan,
    FlextInfraUtilitiesDocsScope,
)


class FlextInfraUtilitiesDocsGenerateSourcesMixin:
    """Freeze every physical source consumed by one documentation render."""

    @staticmethod
    def _source_directory_exists(path: Path) -> p.Result[bool]:
        """Return source-directory presence after physical path authentication.

        Returns:
            Source-directory presence after physical path authentication.

        """
        planned = cli_u.Cli.atomic_plan_directory_chain(path)
        if planned.failure:
            return r[bool].from_failure(planned)
        return r[bool].ok(not planned.value.directories)

    @staticmethod
    def _source_tree_files(
        root: Path,
        *,
        recursive: bool,
        suffixes: frozenset[str],
        excluded_names: frozenset[str] = frozenset(),
    ) -> p.Result[t.VariadicTuple[Path]]:
        """List regular source files through one authenticated tree inventory.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        from flext_cli import u as cli_u
        """
        planned = cli_u.Cli.atomic_plan_directory_chain(root)
        if planned.failure:
            return r[t.VariadicTuple[Path]].from_failure(planned)
        if planned.value.directories:
            return r[t.VariadicTuple[Path]].ok(())
        inventory = cli_u.Cli.atomic_inventory_physical_tree(root)
        if inventory.failure:
            return r[t.VariadicTuple[Path]].from_failure(inventory)
        return r[t.VariadicTuple[Path]].ok(
            tuple(
                entry.path
                for entry in inventory.value.entries
                if entry.kind == "file"
                and entry.path.suffix in suffixes
                and entry.path.name not in excluded_names
                and (recursive or entry.path.parent == root)
            ),
        )

    @staticmethod
    def docs_source_paths(
        repository_root: Path,
        extra_roots: t.SequenceOf[Path] = (),
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Discover every physical source consumed by one docs render.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        from flext_cli import u as cli_u
        """
        roots = FlextInfraUtilitiesDocsScope.docs_repository_roots(
            repository_root,
            extra_roots,
        )
        if roots.failure:
            return r[t.VariadicTuple[Path]].from_failure(roots)
        paths: set[Path] = set()
        for root in roots.value:
            collected = (
                FlextInfraUtilitiesDocsGenerateSourcesMixin._collected_root_paths(
                    root,
                )
            )
            if collected.failure:
                return r[t.VariadicTuple[Path]].from_failure(collected)
            paths.update(collected.value)
        templates_root = Path(__file__).absolute().parent.parent / "templates"
        paths.update({
            templates_root / c.Infra.TEMPLATE_MKDOCS_PROJECT,
            templates_root / c.Infra.TEMPLATE_MKDOCS_ROOT,
        })
        return r[t.VariadicTuple[Path]].ok(tuple(sorted(paths)))

    @classmethod
    def _collected_root_paths(cls, root: Path) -> p.Result[t.VariadicTuple[Path]]:
        """Collect one repository root's documented physical source paths.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[Path]]``.

        """
        # The docs configuration lives one directory down, and a repository
        # that has never generated documentation has no `docs/` yet. Reading
        # a leaf under a directory that does not exist is not "absent", it
        # is a failure, so its presence is established first.
        docs_root_present = cls._source_directory_exists(root / c.Infra.DIR_DOCS)
        if docs_root_present.failure:
            return r[t.VariadicTuple[Path]].from_failure(docs_root_present)
        paths: set[Path] = set()
        fixed_paths = (
            root / c.Infra.GITMODULES,
            root / c.PYPROJECT_FILENAME,
            *(
                (root / c.Infra.DIR_DOCS / c.Infra.DOCS_CONFIG_FILENAME,)
                if docs_root_present.value
                else ()
            ),
        )
        collectors = (
            cls._collected_fixed_paths(paths, fixed_paths),
            cls._collected_tree_paths(
                paths,
                root / "config",
                recursive=False,
                suffixes=frozenset({".yaml", ".yml"}),
            ),
            cls._collected_tree_paths(
                paths,
                root / c.Infra.DEFAULT_SRC_DIR,
                recursive=True,
                suffixes=frozenset({".py"}),
            ),
            cls._collected_tree_paths(
                paths,
                root / c.Infra.DIR_DOCS / "guides",
                recursive=False,
                suffixes=frozenset({".md"}),
                excluded_names=frozenset({"README.md"}),
            ),
        )
        for collected in collectors:
            if collected.failure:
                return r[t.VariadicTuple[Path]].from_failure(collected)
        return r[t.VariadicTuple[Path]].ok(tuple(sorted(paths)))

    @staticmethod
    def _collected_fixed_paths(
        paths: set[Path],
        fixed_paths: t.SequenceOf[Path],
    ) -> p.Result[bool]:
        """Add each existing fixed path to the collected set.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for fixed_path in fixed_paths:
            state = cli_u.Cli.atomic_read_binary_file_state(
                fixed_path,
                required=False,
            )
            if state.failure:
                return r[bool].from_failure(state)
            if state.value.content is not None:
                paths.add(fixed_path)
        return r[bool].ok(value=True)

    @classmethod
    def _collected_tree_paths(
        cls,
        paths: set[Path],
        tree_root: Path,
        *,
        recursive: bool,
        suffixes: frozenset[str],
        excluded_names: frozenset[str] = frozenset(),
    ) -> p.Result[bool]:
        """Add one inventoried source tree's files to the collected set.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        tree_paths = cls._source_tree_files(
            tree_root,
            recursive=recursive,
            suffixes=suffixes,
            excluded_names=excluded_names,
        )
        if tree_paths.failure:
            return r[bool].from_failure(tree_paths)
        paths.update(tree_paths.value)
        return r[bool].ok(value=True)

    @staticmethod
    def docs_verify_sources(
        repository_root: Path,
        source_states: t.SequenceOf[m.Cli.AtomicFileState],
        *,
        extra_roots: t.SequenceOf[Path] = (),
    ) -> p.Result[bool]:
        """Require exact source topology and physical states to remain unchanged.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        discovered = FlextInfraUtilitiesDocsGenerateSourcesMixin.docs_source_paths(
            repository_root,
            extra_roots,
        )
        if discovered.failure:
            return r[bool].from_failure(discovered)
        expected_paths = tuple(state.path for state in source_states)
        if discovered.value != expected_paths:
            added = sorted(set(discovered.value).difference(expected_paths))
            removed = sorted(set(expected_paths).difference(discovered.value))
            return r[bool].fail(
                f"{c.Infra.DOCS_SOURCE_TOPOLOGY_RACE_MARKER}: "
                f"added={[path.as_posix() for path in added]}, "
                f"removed={[path.as_posix() for path in removed]}",
            )
        current = FlextInfraUtilitiesCodegenFilePlan.required_file_states(
            discovered.value,
        )
        if current.failure:
            return r[bool].from_failure(current)
        for expected, observed in zip(source_states, current.value, strict=True):
            if observed != expected:
                model_fields = type(expected).model_fields
                differing = tuple(
                    field
                    for field in model_fields
                    if getattr(expected, field) != getattr(observed, field)
                )
                return r[bool].fail(
                    f"{c.Infra.DOCS_SOURCE_STATE_RACE_MARKER}: {expected.path}; "
                    f"differing={list(differing)}",
                )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraUtilitiesDocsGenerateSourcesMixin"]
