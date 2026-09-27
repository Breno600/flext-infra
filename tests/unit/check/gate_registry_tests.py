"""Gate vocabulary contract: one SSOT, every gate reachable.

``c.Infra.SARIF_TOOL_INFO`` owns the gate ids; the registry classes and the
`make check` vocabulary are derived from it and must never diverge.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import config
from flext_infra.check import FlextInfraGateRegistry
from flext_infra.gates import FlextInfraCanonicalAliasGate
from tests import c, m

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraGateRegistry:
    @staticmethod
    def _apply_alias_fix(tmp_path: Path, project_dir: Path) -> m.Infra.GateExecution:
        """Write the canonical root manifest and apply the alias gate fix."""
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "flext-infra"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        return FlextInfraCanonicalAliasGate(tmp_path).fix(
            project_dir,
            m.Infra.GateContext(
                repository_root=tmp_path,
                reports_dir=tmp_path / "reports",
                apply_fixes=True,
            ),
        )

    def test_every_allowed_gate_resolves_in_registry(self) -> None:
        registry = FlextInfraGateRegistry.default()
        for gate_id in c.Infra.ALLOWED_GATES:
            gate_cls = registry.get(gate_id)
            tm.that(gate_cls is not None, eq=True)
            tm.that(gate_cls is not None and gate_cls.gate_id == gate_id, eq=True)

    def test_check_vocabulary_is_allowed_minus_mutating(self) -> None:
        allowed = frozenset(c.Infra.CANONICAL_GATE_IDS)
        tm.that(allowed, eq=c.Infra.ALLOWED_GATES - c.Infra.MUTATING_GATES)
        tm.that(allowed & c.Infra.MUTATING_GATES, eq=frozenset())

    def test_default_and_fixable_are_subsets_of_check_vocabulary(self) -> None:
        allowed = frozenset(c.Infra.CANONICAL_GATE_IDS)
        tm.that(frozenset(c.Infra.CANONICAL_DEFAULT_GATE_IDS) <= allowed, eq=True)
        tm.that(frozenset(c.Infra.CANONICAL_FIXABLE_GATE_IDS) <= allowed, eq=True)

    def test_canonical_alias_check_detects_root_tests_consumer(
        self, tmp_path: Path
    ) -> None:
        project_dir = tmp_path / "flext-infra"
        package_init = project_dir / "src" / "flext_infra" / "__init__.py"
        test_file = project_dir / "tests" / "unit" / "test_consumer.py"
        package_init.parent.mkdir(parents=True)
        test_file.parent.mkdir(parents=True)
        package_init.write_text("", encoding="utf-8")
        (project_dir / "tests" / "__init__.py").write_text("", encoding="utf-8")
        test_file.write_text(
            "from flext_core import c\n\nVALUE = c.VALUE\n", encoding="utf-8"
        )
        (project_dir / "pyproject.toml").write_text(
            '[project]\nname = "flext-infra"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        gate = FlextInfraCanonicalAliasGate(tmp_path)
        result = gate.check(
            project_dir,
            m.Infra.GateContext(
                repository_root=tmp_path, reports_dir=tmp_path / "reports"
            ),
        )
        tm.that(result.result.passed, eq=False)
        tm.that(result.raw_output, has="canonical alias 'c'")
        tm.that(result.raw_output, has="from tests import c")

    def test_canonical_alias_fix_rejects_prospective_import_cycle(
        self, tmp_path: Path
    ) -> None:
        project_dir = tmp_path / "flext-infra"
        package_init = project_dir / "src" / "flext_infra" / "__init__.py"
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
        result = TestsFlextInfraGateRegistry._apply_alias_fix(tmp_path, project_dir)
        tm.that(result.result.passed, eq=False)
        tm.that(result.raw_output, has="import cycle")
        tm.that(test_file.read_text(encoding="utf-8"), eq=original)

    def test_canonical_alias_fix_is_deterministic_and_preserves_clean_files(
        self, tmp_path: Path
    ) -> None:
        project_dir = tmp_path / "flext-infra"
        package_init = project_dir / "src" / "flext_infra" / "__init__.py"
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
            '[project]\nname = "flext-infra"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        gate = FlextInfraCanonicalAliasGate(tmp_path)
        context = m.Infra.GateContext(
            repository_root=tmp_path, reports_dir=tmp_path / "reports", apply_fixes=True
        )
        first_result = gate.fix(project_dir, context)
        first_consumer = test_file.read_bytes()
        first_clean = clean_file.read_bytes()
        second_result = gate.fix(project_dir, context)

        tm.that(first_result.result.passed, eq=True)
        tm.that(second_result.result.passed, eq=True)
        tm.that(test_file.read_text(encoding="utf-8"), has="from tests import c")
        tm.that(clean_file.read_text(encoding="utf-8"), eq=clean_source)
        tm.that(test_file.read_bytes(), eq=first_consumer)
        tm.that(clean_file.read_bytes(), eq=first_clean)

    def test_canonical_alias_fix_allows_preexisting_unrelated_cycle(
        self, tmp_path: Path
    ) -> None:
        project_dir = tmp_path / "flext-infra"
        package_dir = project_dir / "src" / "flext_infra"
        package_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "a.py").write_text(
            "from flext_infra import b\n", encoding="utf-8"
        )
        (package_dir / "b.py").write_text(
            "from flext_infra import a\n", encoding="utf-8"
        )
        consumer = package_dir / "consumer.py"
        consumer.write_text(
            "from flext_core import c\n\nVALUE = c.VALUE\n", encoding="utf-8"
        )
        result = TestsFlextInfraGateRegistry._apply_alias_fix(tmp_path, project_dir)
        tm.that(result.result.passed, eq=True)
        tm.that(
            consumer.read_text(encoding="utf-8"),
            has="from flext_infra.constants import c",
        )

    def test_canonical_alias_fix_rejects_new_cycle_beside_existing_cycle(
        self, tmp_path: Path
    ) -> None:
        """A baseline cycle must not hide an independent prospective cycle."""
        project_dir = tmp_path / "flext-infra"
        package_dir = project_dir / "src" / "flext_infra"
        tests_dir = project_dir / "tests"
        unit_dir = tests_dir / "unit"
        package_dir.mkdir(parents=True)
        unit_dir.mkdir(parents=True)
        (package_dir / "__init__.py").write_text("", encoding="utf-8")
        (package_dir / "a.py").write_text(
            "from flext_infra import b\n", encoding="utf-8"
        )
        (package_dir / "b.py").write_text(
            "from flext_infra import a\n", encoding="utf-8"
        )
        consumer = unit_dir / "test_consumer.py"
        original = "from flext_core import c\n\nVALUE = c.VALUE\n"
        consumer.write_text(original, encoding="utf-8")
        (tests_dir / "__init__.py").write_text(
            "from tests.unit.test_consumer import VALUE\n", encoding="utf-8"
        )
        (unit_dir / "__init__.py").write_text("", encoding="utf-8")
        result = TestsFlextInfraGateRegistry._apply_alias_fix(tmp_path, project_dir)

        tm.that(result.result.passed, eq=False)
        tm.that(result.raw_output, has="import cycle")
        tm.that(consumer.read_text(encoding="utf-8"), eq=original)

    def test_every_allowed_gate_resolves_in_the_registry(self) -> None:
        """Every gate the Make surface accepts must be instantiable.

        flext-38p39: `format` once sat in the canonical check-gate vocabulary
        and FlextInfraRuffFormatGate declared gate_id="format" with
        can_fix=True, but the class was never listed in the registry. The
        generated check command could therefore name a gate that silently
        resolved to nothing.
        """
        registry = FlextInfraGateRegistry.default()
        unresolved = [
            gate_id
            for gate_id in c.Infra.CANONICAL_GATE_IDS
            if registry.get(gate_id) is None
        ]

        tm.that(unresolved, eq=[])

    def test_fixable_gate_vocabulary_matches_the_registry(self) -> None:
        """The Make fixable-gate vocabulary equals the gates that declare can_fix.

        flext-38p39: `make fix` routes through `check run --fix`. Without a
        gate selector that run executes EVERY gate, including pyright and
        mypy, which cannot fix anything and cost ~37s -- the verb timed out
        (exit 124).

        Runtime contract: verbs own tools by intent. `fmt` owns formatting
        (ruff format plus the fmt_gates writers such as markdown-format),
        `fix` repairs findings (markdown, markdown-code, smells), `check` is
        read-only. `format` therefore appears in NO check vocabulary: not in
        ALLOWED (check never mutates) and not in FIXABLE (fix never formats).
        """
        registry = FlextInfraGateRegistry.default()
        mutating = {
            gate_id
            for gate_id in c.Infra.CANONICAL_GATE_IDS
            if (gate_cls := registry.get(gate_id)) is not None and gate_cls.can_fix
        }
        # `make fix` owns every mutating check-gate EXCEPT the fmt-owned
        # formatters (single-pass verb law: one operation per tool per verb).
        fmt_owned = set(config.Infra.codegen.make.fmt_gates)
        tm.that(set(c.Infra.CANONICAL_FIXABLE_GATE_IDS), eq=mutating - fmt_owned)
        tm.that(fmt_owned <= mutating, eq=True)
        # `format` belongs to `make fmt` alone: absent from the read-only
        # check vocabulary AND from the fix vocabulary.
        tm.that(c.Infra.FORMAT not in c.Infra.CANONICAL_FIXABLE_GATE_IDS, eq=True)
        tm.that(c.Infra.FORMAT not in c.Infra.CANONICAL_GATE_IDS, eq=True)
