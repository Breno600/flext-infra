"""Authenticated source discovery and CAS verification for docs generation."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_cli import u as cli_u

from flext_core import r
from flext_infra import c, m, t

from .codegen_file_plan import FlextInfraUtilitiesCodegenFilePlan
from .docs_scope import FlextInfraUtilitiesDocsScope

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesDocsGenerateSourcesMixin:
    """Freeze every physical source consumed by one documentation render."""

    @staticmethod
    def _source_directory_exists(path: Path) -> p.Result[bool]:
        """Return source-directory presence after physical path authentication."""
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
        """List regular source files through one authenticated tree inventory."""
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
            )
        )

    @staticmethod
    def docs_source_paths(
        repository_root: Path, extra_roots: t.SequenceOf[Path] = ()
    ) -> p.Result[t.VariadicTuple[Path]]:
        """Discover every physical source consumed by one docs render."""
        roots = FlextInfraUtilitiesDocsScope.docs_repository_roots(
            repository_root, extra_roots
        )
        if roots.failure:
            return r[t.VariadicTuple[Path]].from_failure(roots)
        paths: set[Path] = set()
        for root in roots.value:
            # The docs configuration lives one directory down, and a repository
            # that has never generated documentation has no `docs/` yet. Reading
            # a leaf under a directory that does not exist is not "absent", it
            # is a failure, so its presence is established first.
            docs_root_present = (
                FlextInfraUtilitiesDocsGenerateSourcesMixin._source_directory_exists(
                    root / c.Infra.DIR_DOCS
                )
            )
            if docs_root_present.failure:
                return r[t.VariadicTuple[Path]].from_failure(docs_root_present)
            fixed_paths = (
                root / c.Infra.GITMODULES,
                root / c.PYPROJECT_FILENAME,
                *(
                    (root / c.Infra.DIR_DOCS / c.Infra.DOCS_CONFIG_FILENAME,)
                    if docs_root_present.value
                    else ()
                ),
            )
            for fixed_path in fixed_paths:
                state = cli_u.Cli.atomic_read_binary_file_state(
                    fixed_path, required=False
                )
                if state.failure:
                    return r[t.VariadicTuple[Path]].from_failure(state)
                if state.value.content is not None:
                    paths.add(fixed_path)
            config_paths = (
                FlextInfraUtilitiesDocsGenerateSourcesMixin._source_tree_files(
                    root / "config",
                    recursive=False,
                    suffixes=frozenset({".yaml", ".yml"}),
                )
            )
            if config_paths.failure:
                return r[t.VariadicTuple[Path]].from_failure(config_paths)
            paths.update(config_paths.value)
            source_paths = (
                FlextInfraUtilitiesDocsGenerateSourcesMixin._source_tree_files(
                    root / c.Infra.DEFAULT_SRC_DIR,
                    recursive=True,
                    suffixes=frozenset({".py"}),
                )
            )
            if source_paths.failure:
                return r[t.VariadicTuple[Path]].from_failure(source_paths)
            paths.update(source_paths.value)
            guide_paths = (
                FlextInfraUtilitiesDocsGenerateSourcesMixin._source_tree_files(
                    root / c.Infra.DIR_DOCS / "guides",
                    recursive=False,
                    suffixes=frozenset({".md"}),
                    excluded_names=frozenset({"README.md"}),
                )
            )
            if guide_paths.failure:
                return r[t.VariadicTuple[Path]].from_failure(guide_paths)
            paths.update(guide_paths.value)
        templates_root = Path(__file__).absolute().parent.parent / "templates"
        paths.update({
            templates_root / c.Infra.TEMPLATE_MKDOCS_PROJECT,
            templates_root / c.Infra.TEMPLATE_MKDOCS_ROOT,
        })
        return r[t.VariadicTuple[Path]].ok(tuple(sorted(paths)))

    @staticmethod
    def docs_verify_sources(
        repository_root: Path,
        source_states: t.SequenceOf[m.Cli.AtomicFileState],
        *,
        extra_roots: t.SequenceOf[Path] = (),
    ) -> p.Result[bool]:
        """Require exact source topology and physical states to remain unchanged."""
        discovered = FlextInfraUtilitiesDocsGenerateSourcesMixin.docs_source_paths(
            repository_root, extra_roots
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
                f"removed={[path.as_posix() for path in removed]}"
            )
        current = FlextInfraUtilitiesCodegenFilePlan.required_file_states(
            discovered.value
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
                    f"differing={list(differing)}"
                )
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraUtilitiesDocsGenerateSourcesMixin"]
