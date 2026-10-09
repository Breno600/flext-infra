"""Immutable source-bundle and physical-path contracts for docs planning.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import c, m
from flext_infra.docs.generator import FlextInfraDocGenerator
from tests import u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsGeneratorBundle:
    """Immutable source-bundle and physical-path contracts for docs planning."""

    @staticmethod
    def _generator(workspace: Path) -> FlextInfraDocGenerator:
        """Return the public generator for the governed fixture project.

        Returns:
            The public generator for the governed fixture project.

        """
        return FlextInfraDocGenerator(
            repository_root=workspace,
            selected_projects=["flext-a"],
        )

    @staticmethod
    def _materialize_required_parents(
        generator: FlextInfraDocGenerator,
        bundle: m.Infra.DocsGenerationBundle,
    ) -> None:
        """Materialize fixture parents after the read-only planner has named them."""
        required = generator.required_directories(bundle)
        tm.ok(required)
        for directory in required.value:
            directory.mkdir(parents=True, exist_ok=True)

    def test_plan_files_rejects_source_change_after_directory_preflight(
        self,
        tmp_path: Path,
    ) -> None:
        """Reject changed bytes from the exact bundle instead of rerendering them."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        guide = workspace / "flext-a/docs/guides/operator.md"
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text("# Original\n", encoding="utf-8")
        generator = self._generator(workspace)
        prepared = generator.prepare_bundle()
        tm.ok(prepared)
        self._materialize_required_parents(generator, prepared.value)

        guide.write_text("# Changed\n", encoding="utf-8")
        planned = generator.plan_files(prepared.value)

        tm.fail(planned)
        tm.that(planned.error or "", has=c.Infra.DOCS_SOURCE_STATE_RACE_MARKER)

    def test_plan_files_rejects_source_topology_addition_after_bundle(
        self,
        tmp_path: Path,
    ) -> None:
        """Reject a newly consumed source that was absent from the frozen inventory."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        generator = self._generator(workspace)
        prepared = generator.prepare_bundle()
        tm.ok(prepared)
        self._materialize_required_parents(generator, prepared.value)

        added = workspace / "flext-a/src/flext_a/added.py"
        added.write_text('"""Added after render."""\n', encoding="utf-8")
        planned = generator.plan_files(prepared.value)

        tm.fail(planned)
        tm.that(planned.error or "", has=c.Infra.DOCS_SOURCE_TOPOLOGY_RACE_MARKER)

    def test_docs_target_leaf_symlink_to_in_project_file_is_rejected(
        self,
        tmp_path: Path,
    ) -> None:
        """Never turn a managed lexical target into an unmanaged in-project referent."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        project = workspace / "flext-a"
        unmanaged = project / "NOTES.md"
        unmanaged.write_text("keep\n", encoding="utf-8")
        target = project / "README.md"
        target.unlink()
        target.symlink_to(unmanaged.name)
        generator = self._generator(workspace)
        prepared = generator.prepare_bundle()
        tm.ok(prepared)
        self._materialize_required_parents(generator, prepared.value)

        planned = generator.plan_files(prepared.value)

        tm.fail(planned)
        tm.that(planned.error or "", has="atomic")
        tm.that(unmanaged.read_text(encoding="utf-8"), eq="keep\n")

    def test_docs_generated_parent_symlink_is_rejected_before_prune(
        self,
        tmp_path: Path,
    ) -> None:
        """Reject an aliased generated tree before deriving any delete artifact."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        project = workspace / "flext-a"
        curated = project / "curated"
        curated.mkdir()
        keep = curated / "keep.md"
        keep.write_text("keep\n", encoding="utf-8")
        generated = project / "docs/api-reference/generated"
        generated.parent.mkdir(parents=True, exist_ok=True)
        generated.symlink_to(curated, target_is_directory=True)

        prepared = self._generator(workspace).prepare_bundle()

        tm.fail(prepared)
        tm.that(prepared.error or "", has="atomic")
        tm.that(keep.read_text(encoding="utf-8"), eq="keep\n")

    @staticmethod
    def test_selected_project_symlink_cannot_escape_workspace(
        tmp_path: Path,
    ) -> None:
        """Reject a selected local path whose physical project is outside the root."""
        workspace = u.Tests.create_docs_workspace(tmp_path)
        outside = tmp_path / "outside"
        package = outside / "src/outside"
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        (outside / "pyproject.toml").write_text(
            '[project]\nname = "outside"\nversion = "0.1.0"\n',
            encoding="utf-8",
        )
        (workspace / "escaped").symlink_to(outside, target_is_directory=True)

        prepared = FlextInfraDocGenerator(
            repository_root=workspace,
            selected_projects=["escaped"],
        ).prepare_bundle()

        tm.fail(prepared)
        tm.that(prepared.error or "", has="atomic")

    def test_bundle_captures_actual_guide_and_template_sources(
        self,
        tmp_path: Path,
    ) -> None:
        """Bind every guide and both templates that materially feed the render."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        guide = workspace / "flext-a/docs/guides/operator.md"
        guide.parent.mkdir(parents=True, exist_ok=True)
        guide.write_text("# Operator\n", encoding="utf-8")

        prepared = self._generator(workspace).prepare_bundle()

        tm.ok(prepared)
        source_paths = {state.path for state in prepared.value.source_states}
        source_names = {path.name for path in source_paths}
        tm.that(guide in source_paths, eq=True)
        tm.that(c.Infra.TEMPLATE_MKDOCS_PROJECT in source_names, eq=True)
        tm.that(c.Infra.TEMPLATE_MKDOCS_ROOT in source_names, eq=True)

    def test_cached_pyproject_cannot_diverge_from_bundle_source_bytes(
        self,
        tmp_path: Path,
    ) -> None:
        """Render a later valid pyproject version rather than a path-keyed old value."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        generator = self._generator(workspace)
        first = generator.prepare_bundle()
        tm.ok(first)
        pyproject = workspace / "flext-a/pyproject.toml"
        pyproject.write_text(
            '[project]\nname = "flext-a"\nversion = "0.2.0"\n'
            'description = "Fresh metadata"\n',
            encoding="utf-8",
        )

        second = generator.prepare_bundle()

        tm.ok(second)
        readme = next(
            artifact
            for scoped in second.value.scopes
            if scoped.scope.name == "flext-a"
            for artifact in scoped.artifacts
            if artifact.relative_path.as_posix() == "README.md"
        )
        tm.that(readme.desired_content or b"", has=b"Fresh metadata")
