"""Tests for refactor namespace-alias rewriting."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra.detectors.import_alias_detector import FlextInfraImportAliasDetector
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraRefactorInfraRefactorNamespaceAliases:
    """Behavior contract for test_infra_refactor_namespace_aliases."""

    def test_import_alias_detector_skips_private_and_class_imports(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraImportAliasDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "sample.py",
                "from __future__ import annotations\n"
                "from flext_core import FlextModelsBase\n"
                "from flext_core import FlextModels\n"
                "from flext_core import m\n",
                rope_project,
            )
        )
        tm.that(violations, eq=[])

    def test_import_alias_detector_skips_nested_private_and_as_renames(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraImportAliasDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "sample.py",
                "from __future__ import annotations\n"
                "from flext_infra import FlextInfraModelsNamespaceEnforcer\n"
                "from flext_core import m as mm\n",
                rope_project,
            )
        )
        tm.that(violations, eq=[])

    def test_import_alias_detector_skips_facade_and_subclass_files(
        self, tmp_path: Path, rope_project: t.Infra.RopeProject
    ) -> None:
        violations = FlextInfraImportAliasDetector.detect_file(
            u.Tests.detector_context(
                tmp_path / "models.py",
                "from __future__ import annotations\n"
                "from flext_core import u\n"
                "from flext_core import FlextModels\n\n"
                "class FlextFooModels(FlextModels):\n"
                "    pass\n",
                rope_project,
            )
        )
        tm.that(violations, eq=[])

    @pytest.mark.parametrize(
        ("project_parts", "source"),
        [
            (
                ("flext-core",),
                (
                    "from __future__ import annotations\n\nfrom collections.abc import Mapping, Sequence\n"
                    "from flext_core import FlextModelsBase\n"
                    "from flext_core import FlextModels\n"
                    "from flext_core import m\n"
                ),
            ),
            (
                ("flext-core",),
                "from __future__ import annotations\nfrom flext_core import u\n",
            ),
            (
                (),
                (
                    "from __future__ import annotations\n"
                    "from flext_core import c, m, r, p, t, u, p\n"
                    "from flext_infra import FlextInfraModelsNamespaceEnforcer\n"
                    "from flext_core import m as mm\n"
                    "from flext_core import (m)\n"
                ),
            ),
        ],
        ids=["runtime_alias_imports", "contextual_alias_subset", "nested_and_renamed"],
    )
    def test_namespace_rewriter_preserves_top_level_package_imports(
        self, tmp_path: Path, project_parts: t.VariadicTuple[str], source: str
    ) -> None:
        """The submodule cleaner never touches ``from <package> import X``.

        Only submodule imports (``from flext_core.<sub> import X``) are
        removed, so every case here — plain runtime aliases, a contextual
        alias subset, and nested private/``as``-renamed/duplicated names —
        leaves the module byte-identical. A foreign package (``flext_infra``)
        is preserved for the same reason: it is not ``project_package``.
        """
        package_root = u.Tests.src_package(
            tmp_path.joinpath(*project_parts),
            "flext_core",
            pyproject="[project]\nname = 'flext-core'\n",
        )
        sample_file = package_root / "sample.py"
        sample_file.write_text(source, encoding="utf-8")

        u.Infra.rewrite_import_violations(
            py_files=[sample_file], project_package="flext_core"
        )

        tm.that(sample_file.read_text(encoding="utf-8"), eq=source)

    def test_namespace_rewriter_skips_facade_and_subclass_files(
        self, tmp_path: Path
    ) -> None:
        package_root = u.Tests.src_package(
            tmp_path, "flext_core", pyproject="[project]\nname = 'flext-core'\n"
        )
        sample_file = package_root / "models.py"
        source = (
            "from __future__ import annotations\n"
            "from flext_core import u\n"
            "from flext_core import FlextModels\n\n"
            "class FlextFooModels(FlextModels):\n"
            "    pass\n"
        )
        sample_file.write_text(source, encoding="utf-8")

        u.Infra.rewrite_import_violations(
            py_files=[sample_file], project_package="flext_core"
        )

        rewritten = sample_file.read_text(encoding="utf-8")
        # Top-level package imports are preserved (not submodule), so file is unchanged.
        tm.that(rewritten, has="from flext_core import u")
        tm.that(rewritten, has="FlextModels")
        tm.that(rewritten, eq=source)
