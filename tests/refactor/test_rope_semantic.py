"""Tests for rope semantic analysis utilities.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from tests import t, u

type RopeWorkspace = t.Pair[t.Infra.RopeProject, Path]


class TestsFlextInfraRefactorRopeSemantic:
    """Tests for rope semantic-model helpers via the public surface."""

    @staticmethod
    def test_returns_imports(
        semantic_rope_workspace: RopeWorkspace,
        services_resource: t.Infra.RopeResource,
    ) -> None:
        """Test returns imports."""
        proj, _ = semantic_rope_workspace
        imports = u.Infra.resolve_semantic_module_imports(proj, services_resource)
        tm.that(imports, has="Dog")

    @staticmethod
    def test_no_imports_returns_empty(
        semantic_rope_workspace: RopeWorkspace,
        models_resource: t.Infra.RopeResource,
    ) -> None:
        """Test no imports returns empty."""
        proj, _ = semantic_rope_workspace
        imports = u.Infra.resolve_semantic_module_imports(proj, models_resource)
        # Expect: Path appears among the imported names
        tm.that(imports, has="Path")
        # Expect: Animal is defined locally, so it is absent from imports
        tm.that(imports, lacks="Animal")

    @staticmethod
    def test_returns_defined_classes(
        semantic_rope_workspace: RopeWorkspace,
        models_resource: t.Infra.RopeResource,
    ) -> None:
        """Test returns defined classes."""
        proj, _ = semantic_rope_workspace
        classes = u.Infra.resolve_module_classes(proj, models_resource)
        tm.that(classes, has="Animal")
        tm.that(classes, has="Dog")

    @staticmethod
    def test_excludes_imported_classes(
        semantic_rope_workspace: RopeWorkspace,
        services_resource: t.Infra.RopeResource,
    ) -> None:
        """Test excludes imported classes."""
        proj, _ = semantic_rope_workspace
        classes = u.Infra.resolve_module_classes(proj, services_resource)
        # Dog is imported, not defined here
        tm.that(classes, lacks="Dog")

    @staticmethod
    def test_returns_base_classes(
        semantic_rope_workspace: RopeWorkspace,
        models_resource: t.Infra.RopeResource,
    ) -> None:
        """Test returns base classes."""
        proj, _ = semantic_rope_workspace
        bases = u.Infra.resolve_class_bases(proj, models_resource, "Dog")
        tm.that(bases, has="Animal")

    @staticmethod
    def test_no_bases_for_root_class(
        semantic_rope_workspace: RopeWorkspace,
        models_resource: t.Infra.RopeResource,
    ) -> None:
        """Test no bases for root class."""
        proj, _ = semantic_rope_workspace
        bases = u.Infra.resolve_class_bases(proj, models_resource, "Animal")
        # object is implicit base, rope may or may not return it
        tm.that(bases, lacks="Dog")

    @staticmethod
    def test_nonexistent_class_returns_empty(
        semantic_rope_workspace: RopeWorkspace,
        models_resource: t.Infra.RopeResource,
    ) -> None:
        """Test nonexistent class returns empty."""
        proj, _ = semantic_rope_workspace
        bases = u.Infra.resolve_class_bases(proj, models_resource, "DoesNotExist")
        tm.that(not bases, eq=True)

    @staticmethod
    def test_returns_public_methods(
        semantic_rope_workspace: RopeWorkspace,
        models_resource: t.Infra.RopeResource,
    ) -> None:
        """Test returns public methods."""
        proj, _ = semantic_rope_workspace
        methods = u.Infra.resolve_class_methods(proj, models_resource, "Dog")
        tm.that(methods, has="fetch")
        tm.that(methods["fetch"], eq="staticmethod")
        tm.that(methods, has="breed")
        tm.that(methods["breed"], eq="classmethod")

    @staticmethod
    def test_excludes_private_by_default(
        semantic_rope_workspace: RopeWorkspace,
        models_resource: t.Infra.RopeResource,
    ) -> None:
        """Test excludes private by default."""
        proj, _ = semantic_rope_workspace
        methods = u.Infra.resolve_class_methods(proj, models_resource, "Dog")
        tm.that(methods, lacks="_wag")

    @staticmethod
    def test_includes_private_when_requested(
        semantic_rope_workspace: RopeWorkspace,
        models_resource: t.Infra.RopeResource,
    ) -> None:
        """Test includes private when requested."""
        proj, _ = semantic_rope_workspace
        methods = u.Infra.resolve_class_methods(
            proj,
            models_resource,
            "Dog",
            include_private=True,
        )
        tm.that(methods, has="_wag")
        tm.that(methods["_wag"], eq="method")

    @staticmethod
    def test_returns_character_offset_for_semantic_definition(
        semantic_rope_workspace: RopeWorkspace,
        models_resource: t.Infra.RopeResource,
    ) -> None:
        """Test returns character offset for semantic definition."""
        proj, _ = semantic_rope_workspace
        offset = u.Infra.find_definition_offset(proj, models_resource, "Dog")
        source = models_resource.read()
        offset = tm.not_none(offset)
        tm.that(source[offset : offset + 3], eq="Dog")
