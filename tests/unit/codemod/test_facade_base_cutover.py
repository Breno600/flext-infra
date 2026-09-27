"""Public utility evidence for the facade-base semantic cutover."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import c, infra, m, p, t, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraFacadeBaseCutover:
    """Exercise the facade-base phase only through ``u.Infra``."""

    PARENT_CLASS = "ParentDeclaredModelFacade"

    @pytest.mark.parametrize(
        ("statement", "base", "rebind"),
        [
            ("from parent_pkg import m", "m", "m = ChildModels"),
            (
                "from parent_pkg import m as _parent_m",
                "_parent_m",
                "m: type[ChildModels] = ChildModels",
            ),
        ],
    )
    def test_rebound_letter_base_preserves_public_parent_inheritance(
        self, tmp_path: Path, statement: str, base: str, rebind: str
    ) -> None:
        child, sources = self._workspace(
            tmp_path,
            f"{statement}\n\n\nclass ChildModels({base}):\n    pass\n\n\n{rebind}\n",
        )
        edits = self._edits(tmp_path, sources, child)
        tm.that(tuple(edit.file_path for edit in edits), eq=(child.resolve(),))
        updated = edits[0].updated_source
        self._verify_runtime(tmp_path, {**sources, child: updated})
        replanned = self._edits(tmp_path, {**sources, child: updated}, child)
        tm.that(replanned, empty=True)

    def test_eager_and_deferred_letter_reads_keep_their_runtime_owners(
        self, tmp_path: Path
    ) -> None:
        child, sources = self._workspace(
            tmp_path,
            "from parent_pkg import m\n\n\nclass ChildModels(m):\n"
            "    base = m.BaseModel\n\n"
            "    def later(self) -> object:\n        return m.BaseModel\n\n\n"
            "m = ChildModels\n",
        )
        updated = self._edits(tmp_path, sources, child)[0].updated_source
        self._verify_runtime(
            tmp_path,
            {**sources, child: updated},
            assertions=(
                "assert ChildModels.base is parent_m.BaseModel\n"
                "assert ChildModels().later() is m.BaseModel\n"
            ),
        )

    def test_letter_base_without_rebind_is_untouched(self, tmp_path: Path) -> None:
        child, sources = self._workspace(
            tmp_path, "from parent_pkg import m\n\n\nclass ChildService(m):\n    pass\n"
        )
        tm.that(self._edits(tmp_path, sources, child), empty=True)

    def test_undeclared_letter_owner_fails_the_plan(self, tmp_path: Path) -> None:
        child, sources = self._workspace(
            tmp_path,
            "from parent_pkg import m\n\n\nclass ChildModels(m):\n    pass\n\n\n"
            "m = ChildModels\n",
            parent_exports=(self.PARENT_CLASS,),
        )
        tm.fail(self._plan(tmp_path, sources, child), has="is not declared")

    def test_facade_classes_derive_every_published_letter(
        self, tmp_path: Path, installed_dependency_path: Path
    ) -> None:
        _child, sources = self._workspace(tmp_path, "")
        for path, source in sources.items():
            if "parent_pkg" in path.parts:
                relative = path.relative_to(tmp_path / "parent/src")
                target = installed_dependency_path / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(source, encoding="utf-8")
        tm.that(u.Infra.facade_classes("parent_pkg"), eq={"m": self.PARENT_CLASS})

    def _workspace(
        self,
        tmp_path: Path,
        child_source: str,
        *,
        parent_exports: t.StrSequence | None = None,
    ) -> t.Pair[Path, t.MutableMappingKV[Path, str]]:
        """Declare a parent whose class name no package naming could infer."""
        exports = (self.PARENT_CLASS, "m") if parent_exports is None else parent_exports
        parent = tmp_path / "parent/src/parent_pkg"
        child = tmp_path / "child/src/child_pkg/models.py"
        return child, {
            parent / "__init__.py": (
                f"from .models import {self.PARENT_CLASS}, m\n"
                f"__all__ = [{self.PARENT_CLASS!r}, 'm']\n"
            ),
            parent / "models.py": (
                "from base_pkg import m\n"
                f"class {self.PARENT_CLASS}(m):\n    pass\n"
                f"m = {self.PARENT_CLASS}\n"
                f"__all__ = {list(exports)!r}\n"
            ),
            parent.parent / "base_pkg.py": (
                "class BaseFacade:\n    class BaseModel:\n        pass\n"
                "m = BaseFacade\n"
            ),
            child.parent / "__init__.py": "",
            child: child_source,
        }

    @staticmethod
    def _verify_runtime(
        root: Path, sources: t.MappingKV[Path, str], *, assertions: str = ""
    ) -> None:
        """Import and exercise the emitted public facade in a fresh interpreter."""
        for path, source in sources.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")
        program = (
            "from parent_pkg import m as parent_m\n"
            "from child_pkg.models import ChildModels, m\n"
            "assert issubclass(ChildModels, parent_m)\n"
            "assert m is ChildModels\n"
            "assert m.BaseModel is parent_m.BaseModel\n"
        ) + assertions
        result = u.Cli.run_raw(
            [sys.executable, "-c", program],
            cwd=root,
            env={
                "PYTHONPATH": os.pathsep.join((
                    str(root / "parent/src"),
                    str(root / "child/src"),
                ))
            },
        ).unwrap()
        tm.that(u.Cli.process_succeeded(result.outcome), eq=True)

    @staticmethod
    def _finding(file_path: Path) -> m.Infra.ModScanFinding:
        """Build one detector finding for the facade module."""
        return m.Infra.ModScanFinding(
            rule_file="facade-base-by-class-name.yml",
            rule_id="facade-base-by-class-name",
            repository="child",
            file=file_path,
            range={},
            text="m = ChildModels",
            actionable=False,
            classification=c.Infra.ModScanFindingClass.DETECTION_ONLY,
            payload={},
        )

    @classmethod
    def _plan(
        cls, tmp_path: Path, sources: t.MappingKV[Path, str], child: Path
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan the facade-base phase for the detector finding in ``child``."""
        with infra.rope_workspace(tmp_path) as rope:
            return u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.FACADE_BASE,
                rope_workspace=rope,
                sources=sources,
                findings=(cls._finding(child.relative_to(tmp_path)),),
            )

    @classmethod
    def _edits(
        cls, tmp_path: Path, sources: t.MappingKV[Path, str], child: Path
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        """Return the successful plan's edits."""
        planned = cls._plan(tmp_path, sources, child)
        tm.ok(planned)
        return planned.value
