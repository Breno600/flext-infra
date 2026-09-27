"""Tests for rope-migrated transformers: symbol_propagator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra.transformers.symbol_propagator import (
    FlextInfraRefactorSymbolPropagator,
)
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t


class TestsFlextInfraInfraRefactorRopeMigrations:
    """Verify symbol_propagator stays rope-oriented."""

    def _apply_transformer(
        self,
        tmp_path: Path,
        file_name: str,
        source: str,
        transform: t.Infra.RopeTransformFn,
    ) -> t.Infra.TransformResult:
        file_path = tmp_path / "src" / file_name
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(source, encoding="utf-8")
        updated, changes = u.Infra.apply_transformer_to_source(
            source, file_path, transform
        )
        return updated, list(changes)

    def test_module_rename(self, tmp_path: Path) -> None:
        """Transformer renames import module path."""
        source = "from old_module import SomeClass\n"
        transformer = FlextInfraRefactorSymbolPropagator(
            target_modules={"new_module"},
            module_renames={"old_module": "new_module"},
            import_symbol_renames={},
        )
        result, changes = self._apply_transformer(
            tmp_path, "demo.py", source, transformer.transform
        )
        tm.that(result, has="new_module")
        tm.that(result, lacks="old_module")
        tm.that(len(changes), eq=1)

    def test_symbol_rename_in_import(self, tmp_path: Path) -> None:
        """Transformer renames symbols within target module imports."""
        source = "from mylib import OldName\nOldName()\n"
        transformer = FlextInfraRefactorSymbolPropagator(
            target_modules={"mylib"},
            module_renames={},
            import_symbol_renames={"OldName": "NewName"},
        )
        result, _ = self._apply_transformer(
            tmp_path, "demo.py", source, transformer.transform
        )
        tm.that(result, has="NewName")
        tm.that(result, lacks="OldName")

    def test_symbol_rename_propagates_to_usage(self, tmp_path: Path) -> None:
        """Transformer propagates symbol rename from import to usage sites."""
        source = "from mylib import Alpha\nx = Alpha()\n"
        transformer = FlextInfraRefactorSymbolPropagator(
            target_modules={"mylib"},
            module_renames={},
            import_symbol_renames={"Alpha": "Beta"},
        )
        result, _ = self._apply_transformer(
            tmp_path, "demo.py", source, transformer.transform
        )
        tm.that(result, has="Beta")
        tm.that(result, lacks="Alpha")

    def test_no_change_when_no_match(self, tmp_path: Path) -> None:
        """Transformer returns unchanged source when no renames apply."""
        source = "from other import SomeClass\n"
        transformer = FlextInfraRefactorSymbolPropagator(
            target_modules={"mylib"},
            module_renames={},
            import_symbol_renames={"OldName": "NewName"},
        )
        result, changes = self._apply_transformer(
            tmp_path, "demo.py", source, transformer.transform
        )
        tm.that(result, eq=source)
        tm.that(changes, eq=[])

    def test_on_change_callback_invoked(self, tmp_path: Path) -> None:
        """on_change callback is invoked for each change made."""
        source = "from mylib import OldName\n"
        recorded: t.MutableSequenceOf[str] = []
        transformer = FlextInfraRefactorSymbolPropagator(
            target_modules={"mylib"},
            module_renames={},
            import_symbol_renames={"OldName": "NewName"},
            on_change=recorded.append,
        )
        self._apply_transformer(tmp_path, "demo.py", source, transformer.transform)
        tm.that(len(recorded), eq=1)
        tm.that(recorded[0], has="OldName")

    def test_apply_to_source_matches_rope_transform(self, tmp_path: Path) -> None:
        """Text and rope entrypoints keep the same symbol propagation behavior."""
        source = "from mylib import OldName\nOldName()\n"
        transformer = FlextInfraRefactorSymbolPropagator(
            target_modules={"mylib"},
            module_renames={},
            import_symbol_renames={"OldName": "NewName"},
        )
        rope_result, rope_changes = self._apply_transformer(
            tmp_path, "demo.py", source, transformer.transform
        )
        text_result, text_changes = transformer.apply_to_source(source)
        tm.that(text_result, eq=rope_result)
        tm.that(text_changes, eq=rope_changes)

    def test_apply_transformer_to_source_restores_disk_state(
        self, tmp_path: Path
    ) -> None:
        """Temporary rope sync must not leak source updates to the real file."""
        file_path = tmp_path / "src" / "demo.py"
        file_path.parent.mkdir(parents=True, exist_ok=True)
        original_source = "from mylib import OldName\nOldName()\n"
        staged_source = "from mylib import OldName\nvalue = OldName()\nOldName()\n"
        file_path.write_text(original_source, encoding="utf-8")
        transformer = FlextInfraRefactorSymbolPropagator(
            target_modules={"mylib"},
            module_renames={},
            import_symbol_renames={"OldName": "NewName"},
        )

        updated, changes = u.Infra.apply_transformer_to_source(
            staged_source, file_path, transformer.transform
        )

        tm.that(updated, has="NewName")
        tm.that(changes, empty=False)
        tm.that(file_path.read_text(encoding="utf-8"), eq=original_source)
