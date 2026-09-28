"""Tests for the catalog-driven declarative enforcement engine."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import m
from flext_infra.refactor.declarative_enforcement import (
    FlextInfraRefactorDeclarativeEnforcement,
)
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class TestsFlextInfraRefactorDeclarativeEnforcement:
    """Root-cause coverage for declarative detection strategies."""

    @staticmethod
    def _ctx(
        rope_project: t.Infra.RopeProject, file_path: Path
    ) -> m.Infra.DetectorContext:
        return m.Infra.DetectorContext(
            file_path=file_path,
            rope_project=rope_project,
            project_name="demo",
            project_root=file_path.parent,
        )

    @classmethod
    def _detect(
        cls,
        tmp_path: Path,
        *,
        rule: m.EnforcementRuleSpec,
        file_name: str,
        source_text: str,
    ) -> t.Pair[Path, t.SequenceOf[p.AttributeProbe]]:
        """Write one fixture module and detect ``rule`` violations inside it."""
        source = tmp_path / file_name
        source.write_text(source_text, encoding="utf-8")
        with u.Infra.open_project(tmp_path) as rope_project:
            probes = FlextInfraRefactorDeclarativeEnforcement.detect(
                rule, cls._ctx(rope_project, source)
            )
        return source, probes

    def test_stub_file_detection(self, tmp_path: Path) -> None:
        """ENFORCE-090 probe is emitted for ``.pyi`` files."""
        stub, probes = self._detect(
            tmp_path,
            rule=u.Tests.enforcement_rule("ENFORCE-090"),
            file_name="demo.pyi",
            source_text="x: int\n",
        )
        tm.that(len(probes), eq=1)
        tm.that(getattr(probes[0], "file_path", ""), eq=str(stub))
        tm.that(getattr(probes[0], "rule_id", ""), eq="090")

    def test_supported_rules_are_selected_by_source_metadata(
        self, tmp_path: Path
    ) -> None:
        """Declarative support is source-driven, not tied to catalog IDs."""
        rule = m.EnforcementRuleSpec(
            id="ENFORCE-999",
            description="Synthetic stub-file rule",
            severity=m.EnforcementRuleSeverity.HIGH,
            source=m.EnforcementInfraDetectorSource(
                violation_field="stub_file_violations"
            ),
        )
        tm.that(FlextInfraRefactorDeclarativeEnforcement.supports(rule), eq=True)
        stub, probes = self._detect(
            tmp_path, rule=rule, file_name="demo.pyi", source_text="x: int\n"
        )
        tm.that(len(probes), eq=1)
        tm.that(getattr(probes[0], "file_path", ""), eq=str(stub))

    def test_magic_literal_in_function_body(self, tmp_path: Path) -> None:
        """ENFORCE-097 detects a bare integer inside a function body."""
        _source, probes = self._detect(
            tmp_path,
            rule=u.Tests.enforcement_rule("ENFORCE-097"),
            file_name="demo.py",
            source_text=(
                "from __future__ import annotations\n\ndef f() -> int:\n    return 42\n"
            ),
        )
        tm.that(len(probes), eq=1)
        tm.that(getattr(probes[0], "line", 0), eq=4)
        tm.that(getattr(probes[0], "rule_id", ""), eq="097")

    @pytest.mark.parametrize(
        ("source_text", "exemption"),
        [
            (
                (
                    "from __future__ import annotations\n"
                    "\ndef f(x: int = 42) -> int:\n    return x\n"
                ),
                "default argument values",
            ),
            (
                "from __future__ import annotations\n\nLITERAL: str = 'ok'\n",
                "type annotations",
            ),
            (
                "from __future__ import annotations\n\nMAGIC = 42\n",
                "module-level assignments",
            ),
        ],
    )
    def test_magic_literal_exemptions(
        self, tmp_path: Path, source_text: str, exemption: str
    ) -> None:
        """Default args, annotations, and module constants stay exempt."""
        _source, probes = self._detect(
            tmp_path,
            rule=u.Tests.enforcement_rule("ENFORCE-097"),
            file_name="demo.py",
            source_text=source_text,
        )
        tm.that(len(probes), eq=0, msg=f"{exemption} must not be reported")

    def test_classvar_constant_detection(self, tmp_path: Path) -> None:
        """ENFORCE-079 delegates to the class-placement detector."""
        _source, probes = self._detect(
            tmp_path,
            rule=u.Tests.enforcement_rule("ENFORCE-079"),
            file_name="consumer.py",
            source_text=(
                "from typing import ClassVar\n"
                "class PlainClass:\n"
                "    GROUPS: ClassVar[frozenset[str]] = frozenset({'a'})\n"
            ),
        )
        tm.that(len(probes), eq=1)
        tm.that(getattr(probes[0], "object_name", ""), eq="GROUPS")
        tm.that(getattr(probes[0], "rule_id", ""), eq="079")

    def test_missing_rope_resource_fails_loud(self, tmp_path: Path) -> None:
        """Missing source resources are detector failures, not clean scans."""
        missing = tmp_path / "missing.py"
        with (
            u.Infra.open_project(tmp_path) as rope_project,
            pytest.raises(RuntimeError, match="unable to resolve rope resource"),
        ):
            FlextInfraRefactorDeclarativeEnforcement.detect(
                u.Tests.enforcement_rule("ENFORCE-097"),
                self._ctx(rope_project, missing),
            )

    def test_foreign_canonical_alias_detection(self, tmp_path: Path) -> None:
        """ENFORCE-080 detects a canonical alias imported from flext_core."""
        source = tmp_path / "src" / "flext_infra" / "consumer.py"
        source.parent.mkdir(parents=True)
        # Why (flext-ygc2k): package discovery requires src/<pkg>/__init__.py;
        # without it the policy owner resolves empty and detection is vacuous.
        (source.parent / "__init__.py").write_text("", encoding="utf-8")
        source.write_text(
            "from __future__ import annotations\nfrom flext_core import c\n",
            encoding="utf-8",
        )
        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "flext_infra"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        with u.Infra.open_project(tmp_path) as rope_project:
            ctx = self._ctx(rope_project, source)
            ctx.project_name = "flext_infra"
            probes = FlextInfraRefactorDeclarativeEnforcement.detect(
                u.Tests.enforcement_rule("ENFORCE-080"), ctx
            )
        tm.that(len(probes), eq=1)
        tm.that(getattr(probes[0], "object_name", ""), eq="c")
        tm.that(getattr(probes[0], "rule_id", ""), eq="080")

    def test_unsupported_source_fails_loud(self, tmp_path: Path) -> None:
        """Unsupported source kinds fail explicitly instead of yielding no probes."""
        rule = m.EnforcementRuleSpec(
            id="ENFORCE-999",
            description="Unsupported declarative source",
            severity=m.EnforcementRuleSeverity.HIGH,
            source=m.EnforcementRuntimeWarningSource(category="UserWarning"),
        )
        source = tmp_path / "consumer.py"
        source.write_text("", encoding="utf-8")
        tm.that(FlextInfraRefactorDeclarativeEnforcement.supports(rule), eq=False)
        with (
            u.Infra.open_project(tmp_path) as rope_project,
            pytest.raises(ValueError, match="unsupported declarative"),
        ):
            FlextInfraRefactorDeclarativeEnforcement.detect(
                rule, self._ctx(rope_project, source)
            )


class TestsFlextInfraRefactorDeclarativeEnforcementInCensus:
    """Declarative rules surface in the census report."""

    @staticmethod
    def _build_workspace(tmp_path: Path, project_name: str) -> Path:
        workspace = tmp_path / "workspace"
        src = workspace / "src" / project_name
        src.mkdir(parents=True)
        (src / "__init__.py").write_text(
            "from __future__ import annotations\n", encoding="utf-8"
        )
        (workspace / "pyproject.toml").write_text(
            f'[project]\nname = "{project_name}"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        return workspace

    def test_census_reports_enforce_079_classvar_constant(self, tmp_path: Path) -> None:
        """ENFORCE-079 appears in the census when classvar_constant is selected."""
        workspace = self._build_workspace(tmp_path, "demo_pkg")
        source = workspace / "src" / "demo_pkg" / "domain.py"
        source.write_text(
            "from __future__ import annotations\n"
            "from typing import ClassVar\n\n"
            "class DemoService:\n"
            "    GROUPS: ClassVar[frozenset[str]] = frozenset({'a'})\n",
            encoding="utf-8",
        )

        report = u.Tests.census_report(workspace, rules=("ENFORCE-079",))
        violations = u.Tests.census_violations(report)

        tm.that(len(violations), eq=1)
        tm.that(violations[0].kind, eq="classvar_constant")
        tm.that(violations[0].object_name, eq="GROUPS")
        tm.that(violations[0].fix_action, eq="classvar_relocation")
        tm.that(violations[0].fixable, eq=True)

    def test_census_reports_enforce_090_stub_file(self, tmp_path: Path) -> None:
        """ENFORCE-090 appears in the census for prohibited ``.pyi`` files."""
        workspace = self._build_workspace(tmp_path, "demo_pkg")
        stub = workspace / "src" / "demo_pkg" / "service.pyi"
        stub.write_text("x: int\n", encoding="utf-8")

        report = u.Tests.census_report(workspace, rules=("ENFORCE-090",))
        violations = u.Tests.census_violations(report)

        tm.that(len(violations), eq=1)
        tm.that(violations[0].kind, eq="stub_file")
        tm.that(violations[0].fix_action, eq="remove_stub_file")
        tm.that(violations[0].fixable, eq=True)

    def test_census_apply_enforce_090_removes_stub_file(self, tmp_path: Path) -> None:
        """ENFORCE-090 apply removes the reported ``.pyi`` file."""
        workspace = self._build_workspace(tmp_path, "demo_pkg")
        stub = workspace / "src" / "demo_pkg" / "service.pyi"
        stub.write_text("x: int\n", encoding="utf-8")

        u.Tests.census_report(
            workspace, rules=("ENFORCE-090",), apply_changes=True, dry_run=True
        )
        tm.that(stub.exists(), eq=True)

        u.Tests.census_report(workspace, rules=("ENFORCE-090",), apply_changes=True)
        tm.that(stub.exists(), eq=False)

    def test_census_reports_enforce_097_magic_literal(self, tmp_path: Path) -> None:
        """ENFORCE-097 appears in the census for magic literals."""
        workspace = self._build_workspace(tmp_path, "demo_pkg")
        source = workspace / "src" / "demo_pkg" / "service.py"
        source.write_text(
            "from __future__ import annotations\n\n"
            "def compute() -> int:\n"
            "    return 42\n",
            encoding="utf-8",
        )

        report = u.Tests.census_report(workspace, rules=("ENFORCE-097",))
        violations = u.Tests.census_violations(report)

        tm.that(len(violations), eq=1)
        tm.that(violations[0].kind, eq="magic_literal")
        tm.that(violations[0].fix_action, eq="extract_magic_literal")
        tm.that(violations[0].fixable, eq=False)

    def test_census_reports_enforce_080_foreign_canonical_alias(
        self, tmp_path: Path
    ) -> None:
        """ENFORCE-080 appears in the census for foreign canonical aliases."""
        workspace = self._build_workspace(tmp_path, "flext_infra")
        source = workspace / "src" / "flext_infra" / "service.py"
        source.write_text(
            "from __future__ import annotations\nfrom flext_core import c\n",
            encoding="utf-8",
        )

        report = u.Tests.census_report(workspace, rules=("ENFORCE-080",))
        violations = u.Tests.census_violations(report)

        tm.that(len(violations), eq=1)
        tm.that(violations[0].kind, eq="foreign_canonical_alias")
        tm.that(violations[0].object_name, eq="c")
        tm.that(violations[0].fix_action, eq="rewrite_foreign_canonical_alias")
        tm.that(violations[0].fixable, eq=True)
