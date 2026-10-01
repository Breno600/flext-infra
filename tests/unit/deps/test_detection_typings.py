"""Dependency limits load from a real TOML file through the public service."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra.deps.detection import FlextInfraDependencyDetectionService


class TestsFlextInfraDepsDetectionTypings:
    """Behaviour of ``load_dependency_limits`` on real files."""

    def test_limits_file_values_are_returned(self, tmp_path: Path) -> None:
        limits = tmp_path / "limits.toml"
        limits.write_text(
            'key = "value"\nnum = 42\nlisted = ["x"]\n'
            '[typing_libraries.module_to_package]\nyaml = "types-pyyaml"\n',
            encoding="utf-8",
        )

        result = FlextInfraDependencyDetectionService().load_dependency_limits(limits)

        tm.that(result.get("key"), eq="value")
        tm.that(result.get("num"), eq=42)
        tm.that(result, has="listed")
        tm.that(result, has="typing_libraries")

    def test_missing_limits_file_fails_loud(self, tmp_path: Path) -> None:
        with pytest.raises(RuntimeError, match="failed to load dependency limits"):
            FlextInfraDependencyDetectionService().load_dependency_limits(
                tmp_path / "absent.toml"
            )

    def test_invalid_limits_file_fails_loud(self, tmp_path: Path) -> None:
        limits = tmp_path / "limits.toml"
        limits.write_text("key = [unterminated\n", encoding="utf-8")

        with pytest.raises(RuntimeError, match="failed to load dependency limits"):
            FlextInfraDependencyDetectionService().load_dependency_limits(limits)
