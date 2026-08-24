"""Tests for gate registration of the new durissimas gates.

`loc-cap`, `boundary`, and `canonical-alias` must be in the SSOT-derived
ALLOWED_GATES and resolve through the registry.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import flext_infra.constants  # ruff: ignore[unused-import] - force eager load for monkeypatch targets
from flext_infra.check import FlextInfraGateRegistry
from flext_infra.gates import FlextInfraCanonicalAliasGate
from flext_infra.utilities import FlextInfraUtilities

from tests import c, m, p, r, t, tm, u

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


class TestGateRegistry:
    def test_new_gates_in_allowed(self) -> None:
        tm.that("loc-cap" in c.Infra.ALLOWED_GATES, eq=True)
        tm.that("boundary" in c.Infra.ALLOWED_GATES, eq=True)
        tm.that("canonical-alias" in c.Infra.ALLOWED_GATES, eq=True)

    def test_registry_resolves_loc_cap(self) -> None:
        tm.that(FlextInfraGateRegistry.default().get("loc-cap") is not None, eq=True)

    def test_registry_resolves_boundary(self) -> None:
        tm.that(FlextInfraGateRegistry.default().get("boundary") is not None, eq=True)

    def test_registry_resolves_canonical_alias(self) -> None:
        tm.that(
            FlextInfraGateRegistry.default().get("canonical-alias") is not None, eq=True
        )

    def test_canonical_alias_fix_fails_on_read_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_dir = tmp_path / "demo"
        package_dir = project_dir / "src" / "demo"
        package_dir.mkdir(parents=True)
        source_file = package_dir / "service.py"
        source_file.write_text(
            "from __future__ import annotations\n\n"
            "from flext_core import c\n\n"
            "VALUE = c.MAX_SIZE\n",
            encoding="utf-8",
        )
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "demo"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        monkeypatch.setattr(
            "flext_infra.constants.c.ENFORCEMENT_PROJECT_ALIAS_OWNERS", {"demo": ("c",)}
        )

        def _fail_read(path: Path) -> p.Result[str]:
            return r[str].fail(f"read failed: {path.name}")

        monkeypatch.setattr(u.Cli, "files_read_text", _fail_read)
        gate = FlextInfraCanonicalAliasGate(tmp_path)
        result = gate.fix(
            project_dir,
            m.Infra.GateContext(
                workspace=tmp_path, reports_dir=tmp_path / "reports", apply_fixes=True
            ),
        )

        tm.that(result.result.passed, eq=False)
        tm.that(result.raw_output, has="read failed: service.py")

    def test_canonical_alias_check_detects_root_tests_consumer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_dir = tmp_path / "demo-project"
        package_init = project_dir / "src" / "demo_pkg" / "__init__.py"
        test_file = project_dir / "tests" / "unit" / "test_consumer.py"
        package_init.parent.mkdir(parents=True)
        test_file.parent.mkdir(parents=True)
        package_init.write_text("", encoding="utf-8")
        (project_dir / "tests" / "__init__.py").write_text("", encoding="utf-8")
        test_file.write_text(
            "from flext_core import c\n\nVALUE = c.VALUE\n", encoding="utf-8"
        )
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "demo-project"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        monkeypatch.setattr(
            "flext_infra.constants.c.ENFORCEMENT_PROJECT_ALIAS_OWNERS",
            {"demo_pkg": ("c",)},
        )
        gate = FlextInfraCanonicalAliasGate(tmp_path)
        result = gate.check(
            project_dir,
            m.Infra.GateContext(workspace=tmp_path, reports_dir=tmp_path / "reports"),
        )
        tm.that(result.result.passed, eq=False)
        tm.that(result.raw_output, has="canonical alias 'c'")
        tm.that(result.raw_output, has="from tests import c")

    def test_canonical_alias_fix_rejects_prospective_import_cycle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_dir = tmp_path / "demo-project"
        package_init = project_dir / "src" / "demo_pkg" / "__init__.py"
        tests_init = project_dir / "tests" / "__init__.py"
        unit_init = project_dir / "tests" / "unit" / "__init__.py"
        test_file = project_dir / "tests" / "unit" / "test_consumer.py"
        package_init.parent.mkdir(parents=True)
        unit_init.parent.mkdir(parents=True)
        package_init.write_text("", encoding="utf-8")
        unit_init.write_text("", encoding="utf-8")
        tests_init.write_text(
            "from tests.unit.test_consumer import VALUE\n", encoding="utf-8"
        )
        original = "from flext_core import c\n\nVALUE = c.VALUE\n"
        test_file.write_text(original, encoding="utf-8")
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "demo-project"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        monkeypatch.setattr(
            "flext_infra.constants.c.ENFORCEMENT_PROJECT_ALIAS_OWNERS",
            {"demo_pkg": ("c",)},
        )
        gate = FlextInfraCanonicalAliasGate(tmp_path)
        result = gate.fix(
            project_dir,
            m.Infra.GateContext(
                workspace=tmp_path, reports_dir=tmp_path / "reports", apply_fixes=True
            ),
        )
        tm.that(result.result.passed, eq=False)
        tm.that(result.raw_output, has="import cycle")
        tm.that(test_file.read_text(encoding="utf-8"), eq=original)

    def test_canonical_alias_fix_plans_only_detected_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_dir = tmp_path / "demo-project"
        package_init = project_dir / "src" / "demo_pkg" / "__init__.py"
        tests_init = project_dir / "tests" / "__init__.py"
        test_file = project_dir / "tests" / "unit" / "test_consumer.py"
        clean_file = project_dir / "tests" / "unit" / "test_clean.py"
        package_init.parent.mkdir(parents=True)
        test_file.parent.mkdir(parents=True)
        package_init.write_text("", encoding="utf-8")
        tests_init.write_text("", encoding="utf-8")
        original = "from flext_core import c\n\nVALUE = c.VALUE\n"
        clean_source = "VALUE = 1\n"
        test_file.write_text(original, encoding="utf-8")
        clean_file.write_text(clean_source, encoding="utf-8")
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "demo-project"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        monkeypatch.setattr(
            "flext_infra.constants.c.ENFORCEMENT_PROJECT_ALIAS_OWNERS",
            {"demo_pkg": ("c",)},
        )
        planned_reads: list[Path] = []
        original_read = u.Cli.files_read_text

        def _record_read(path: Path) -> p.Result[str]:
            planned_reads.append(path)
            return original_read(path)

        monkeypatch.setattr(u.Cli, "files_read_text", _record_read)
        gate = FlextInfraCanonicalAliasGate(tmp_path)
        result = gate.fix(
            project_dir,
            m.Infra.GateContext(
                workspace=tmp_path, reports_dir=tmp_path / "reports", apply_fixes=True
            ),
        )
        tm.that(result.result.passed, eq=True)
        tm.that(planned_reads, eq=[test_file])
        tm.that(test_file.read_text(encoding="utf-8"), has="from tests import c")
        tm.that(clean_file.read_text(encoding="utf-8"), eq=clean_source)

    def test_canonical_alias_fix_allows_preexisting_unrelated_cycle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_dir = tmp_path / "demo-project"
        package_dir = project_dir / "src" / "demo_pkg"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "a.py").write_text("from demo_pkg import b\n", encoding="utf-8")
        (package_dir / "b.py").write_text("from demo_pkg import a\n", encoding="utf-8")
        consumer = package_dir / "consumer.py"
        consumer.write_text(
            "from flext_core import c\n\nVALUE = c.VALUE\n", encoding="utf-8"
        )
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "demo-project"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        monkeypatch.setattr(
            "flext_infra.constants.c.ENFORCEMENT_PROJECT_ALIAS_OWNERS",
            {"demo_pkg": ("c",)},
        )
        gate = FlextInfraCanonicalAliasGate(tmp_path)
        result = gate.fix(
            project_dir,
            m.Infra.GateContext(
                workspace=tmp_path, reports_dir=tmp_path / "reports", apply_fixes=True
            ),
        )
        tm.that(result.result.passed, eq=True)
        tm.that(
            consumer.read_text(encoding="utf-8"), has="from demo_pkg.constants import c"
        )

    def test_canonical_alias_fix_rejects_new_cycle_beside_existing_cycle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A baseline cycle must not hide an independent prospective cycle."""
        project_dir = tmp_path / "demo-project"
        package_dir = project_dir / "src" / "demo_pkg"
        tests_dir = project_dir / "tests"
        unit_dir = tests_dir / "unit"
        package_dir.mkdir(parents=True)
        unit_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "a.py").write_text("from demo_pkg import b\n", encoding="utf-8")
        (package_dir / "b.py").write_text("from demo_pkg import a\n", encoding="utf-8")
        consumer = unit_dir / "test_consumer.py"
        original = "from flext_core import c\n\nVALUE = c.VALUE\n"
        consumer.write_text(original, encoding="utf-8")
        (tests_dir / "__init__.py").write_text(
            "from tests.unit.test_consumer import VALUE\n", encoding="utf-8"
        )
        (unit_dir / "__init__.py").write_text("", encoding="utf-8")
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "demo-project"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        monkeypatch.setattr(
            "flext_infra.constants.c.ENFORCEMENT_PROJECT_ALIAS_OWNERS",
            {"demo_pkg": ("c",)},
        )

        result = FlextInfraCanonicalAliasGate(tmp_path).fix(
            project_dir,
            m.Infra.GateContext(
                workspace=tmp_path, reports_dir=tmp_path / "reports", apply_fixes=True
            ),
        )

        tm.that(result.result.passed, eq=False)
        tm.that(result.raw_output, has="import cycle")
        tm.that(consumer.read_text(encoding="utf-8"), eq=original)

    def test_canonical_alias_fix_aborts_on_source_cas_conflict(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        project_dir = tmp_path / "demo-project"
        package_dir = project_dir / "src" / "demo_pkg"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        consumer = package_dir / "consumer.py"
        original = "from flext_core import c\n\nVALUE = c.VALUE\n"
        concurrent = original + "CONCURRENT = True\n"
        consumer.write_text(original, encoding="utf-8")
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "demo-project"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        monkeypatch.setattr(
            "flext_infra.constants.c.ENFORCEMENT_PROJECT_ALIAS_OWNERS",
            {"demo_pkg": ("c",)},
        )
        original_writer: Callable[..., t.Infra.EditResult] = (
            FlextInfraUtilities.Infra.protected_source_writes
        )

        def _concurrent_write(
            updates: t.MappingKV[Path, str],
            *,
            request: m.Infra.ProtectedSourceWritesRequest,
        ) -> t.Infra.EditResult:
            consumer.write_text(concurrent, encoding="utf-8")
            return original_writer(updates, request=request)

        monkeypatch.setattr(u.Infra, "protected_source_writes", _concurrent_write)
        result = FlextInfraCanonicalAliasGate(tmp_path).fix(
            project_dir,
            m.Infra.GateContext(
                workspace=tmp_path, reports_dir=tmp_path / "reports", apply_fixes=True
            ),
        )
        tm.that(result.result.passed, eq=False)
        tm.that(result.raw_output, has="CAS")
        tm.that(consumer.read_text(encoding="utf-8"), eq=concurrent)


def test_every_allowed_gate_resolves_in_the_registry() -> None:
    """Every gate the Make surface accepts must be instantiable.

    mro-38p39: `format` sat in PROJECT_CHECK_GATES_ALLOWED_VALUES and
    FlextInfraRuffFormatGate declared gate_id="format" with can_fix=True, but the
    class was never listed in the registry. So `make check CHECK_GATES=format`
    named a gate that silently resolved to nothing, and the one gate that could
    repair formatting was unreachable from every verb.
    """
    registry = FlextInfraGateRegistry.default()
    unresolved = [
        gate_id
        for gate_id in c.Infra.PROJECT_CHECK_GATES_ALLOWED_VALUES
        if registry.get(gate_id) is None
    ]

    tm.that(unresolved, eq=[])


def test_fixable_gate_vocabulary_matches_the_registry() -> None:
    """The Make fixable-gate vocabulary equals the gates that declare can_fix.

    mro-38p39: `make fix APPLY=Y` routes through `check run --fix`. Without a
    gate selector that run executes EVERY gate, including pyright and mypy,
    which cannot fix anything and cost ~37s -- the verb timed out (exit 124).

    Runtime contract: verbs own tools by intent. `fmt` owns formatting
    (ruff format), `fix` repairs findings (markdown, smells), `check` is
    read-only. `format` therefore appears in NO check vocabulary: not in
    ALLOWED (check never mutates) and not in FIXABLE (fix never formats).
    """
    registry = FlextInfraGateRegistry.default()
    for gate_id in c.Infra.PROJECT_CHECK_GATES_FIXABLE_VALUES:
        gate_cls = registry.get(gate_id)
        tm.that(gate_cls is not None, eq=True)
        tm.that(gate_cls is not None and gate_cls.can_fix, eq=True)
    check_fixable = {
        gate_id
        for gate_id in c.Infra.PROJECT_CHECK_GATES_ALLOWED_VALUES
        if (gate_cls := registry.get(gate_id)) is not None and gate_cls.can_fix
    }
    tm.that(check_fixable <= set(c.Infra.PROJECT_CHECK_GATES_FIXABLE_VALUES), eq=True)
    # `format` belongs to `make fmt` alone: absent from the read-only check
    # vocabulary AND from the fix vocabulary.
    tm.that("format" not in c.Infra.PROJECT_CHECK_GATES_FIXABLE_VALUES, eq=True)
    tm.that("format" not in c.Infra.PROJECT_CHECK_GATES_ALLOWED_VALUES, eq=True)


__all__: t.StrSequence = []
