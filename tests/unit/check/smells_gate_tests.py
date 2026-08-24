"""Tests for the qlty code-smells gate (report-only posture, warnings always).

The gate parses a qlty SARIF payload into per-project issues, emits one
``FlextSmellViolation`` warning per finding on every run, and passes while
``SMELLS_GATE_MODE`` is WARN. A failed/absent scanner surfaces as a visible
issue instead of a silent pass. All assertions run against a literal SARIF
fixture returned by an owned temporary ``qlty`` executable, exercising only
the public gate boundary.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from flext_core import e as core_e
from flext_infra import c, m, u
from flext_infra.check.workspace_check_gates import FlextInfraGateRegistry
from flext_infra.gates.smells import FlextInfraSmellsGate
from flext_tests import tm
from tests import t

if TYPE_CHECKING:
    from pathlib import Path

_SMELL_CODES: t.StrSequence = tuple(sorted(c.Infra.SMELLS_RULE_TAGS))


def _sarif_fixture(project: str, codes: t.StrSequence = _SMELL_CODES) -> str:
    """One finding per smell type inside ``project`` + one foreign-project row."""
    results: list[t.JsonValue] = [
        {
            "ruleId": f"{c.Infra.SMELLS_RULE_PREFIX}{code}",
            "message": {"text": f"{code} finding"},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": f"{project}/src/sample.py"},
                        "region": {"startLine": index + 1, "startColumn": 2},
                    }
                }
            ],
        }
        for index, code in enumerate(codes)
    ]
    results.append({
        "ruleId": f"{c.Infra.SMELLS_RULE_PREFIX}similar-code",
        "message": {"text": "foreign finding"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": "other-project/src/y.py"},
                    "region": {"startLine": 3},
                }
            }
        ],
    })
    payload = u.Cli.json_dumps({"runs": [{"results": results}]}).unwrap()
    tm.that(payload, is_=str)
    validated_payload: str = t.Infra.STR_ADAPTER.validate_python(payload)
    return validated_payload


def _scanner_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdout: str,
    stderr: str = "",
    exit_code: int = 0,
) -> FlextInfraSmellsGate:
    """Return a gate backed by an executable scanner at the external boundary."""
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    scanner = binary_dir / c.Infra.QLTY_BINARY
    scanner.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n\n"
        f"sys.stdout.write({stdout!r})\n"
        f"sys.stderr.write({stderr!r})\n"
        f"raise SystemExit({exit_code})\n",
        encoding="utf-8",
    )
    scanner.chmod(0o755)
    monkeypatch.setenv("PATH", str(binary_dir), prepend=":")
    return FlextInfraSmellsGate(tmp_path)


def _ctx(tmp_path: Path, *, apply_fixes: bool = False) -> m.Infra.GateContext:
    return m.Infra.GateContext(
        workspace=tmp_path, reports_dir=tmp_path / "reports", apply_fixes=apply_fixes
    )


class TestSmellsGate:
    def test_gate_identity(self) -> None:
        tm.that(FlextInfraSmellsGate.gate_id, eq="smells")
        tm.that(FlextInfraSmellsGate.can_fix, eq=True)

    def test_fix_applies_only_core_auto_strategies(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The public fix boundary applies the automatic boolean strategy only."""
        project_dir = tmp_path / "demo-project"
        source_file = project_dir / "src" / "sample.py"
        source_file.parent.mkdir(parents=True)
        source_file.write_text(
            "def f(p):\n    return p.a or p.b or p.c or p.d or p.e\n", encoding="utf-8"
        )
        gate = _scanner_gate(
            tmp_path,
            monkeypatch,
            stdout=_sarif_fixture(
                project_dir.name, ("boolean-logic", "function-parameters")
            ),
        )

        with pytest.warns(core_e.SmellViolation):
            execution = gate.fix(project_dir, _ctx(tmp_path, apply_fixes=True))

        tm.that(execution.result.passed, eq=True)
        tm.that(len(execution.result.errors), eq=1)
        tm.that(
            source_file.read_text(encoding="utf-8"),
            has="any((p.a, p.b, p.c, p.d, p.e))",
        )

    def test_registered_and_allowed(self) -> None:
        tm.that("smells" in c.Infra.ALLOWED_GATES, eq=True)
        tm.that(FlextInfraGateRegistry.default().get("smells") is not None, eq=True)

    def test_check_filters_sarif_to_project(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gate = _scanner_gate(
            tmp_path, monkeypatch, stdout=_sarif_fixture("demo-project")
        )
        project_dir = tmp_path / "demo-project"
        project_dir.mkdir()

        with pytest.warns(core_e.SmellViolation):
            execution = gate.check(project_dir, _ctx(tmp_path))

        issues = execution.issues
        tm.that(len(issues), eq=len(_SMELL_CODES))
        tm.that(sorted(issue.code for issue in issues), eq=list(_SMELL_CODES))
        tm.that(all(issue.file == "src/sample.py" for issue in issues), eq=True)
        tm.that(issues[0].line >= 1, eq=True)
        tm.that(
            all("foreign finding" not in issue.message for issue in issues), eq=True
        )

    def test_warn_mode_passes_with_issues_and_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gate = _scanner_gate(
            tmp_path, monkeypatch, stdout=_sarif_fixture("demo-project")
        )
        project_dir = tmp_path / "demo-project"
        project_dir.mkdir()

        with pytest.warns(core_e.SmellViolation):
            execution = gate.check(project_dir, _ctx(tmp_path))

        tm.that(execution.result.passed, eq=True)
        tm.that(len(execution.issues), eq=len(_SMELL_CODES))
        tm.that(len(execution.result.errors), eq=len(_SMELL_CODES))
        tm.that(
            all(
                issue.severity == c.Infra.GateSeverity.WARNING.value
                for issue in execution.issues
            ),
            eq=True,
        )

    def test_failed_scanner_is_visible(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_dir = tmp_path / ".qlty"
        config_dir.mkdir()
        (config_dir / "qlty.toml").write_text("[config]\n", encoding="utf-8")
        gate = _scanner_gate(
            tmp_path, monkeypatch, stdout="", stderr="qlty exploded", exit_code=1
        )
        project_dir = tmp_path / "demo-project"
        project_dir.mkdir()

        with pytest.warns(core_e.SmellViolation):
            execution = gate.check(project_dir, _ctx(tmp_path))

        tm.that(execution.result.passed, eq=True)
        tm.that(len(execution.issues), eq=1)
        tm.that("qlty exploded" in execution.issues[0].message, eq=True)

    def test_unconfigured_scanner_is_cleanly_skipped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        gate = _scanner_gate(
            tmp_path,
            monkeypatch,
            stdout="",
            stderr="No qlty config file found. Try running `qlty init`",
            exit_code=1,
        )
        project_dir = tmp_path / "demo-project"
        project_dir.mkdir()

        execution = gate.check(project_dir, _ctx(tmp_path))

        tm.that(execution.result.passed, eq=True)
        tm.that(execution.issues, eq=())
        tm.that(execution.result.errors, eq=[])

    def test_resolve_binary_fallback_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When qlty is absent from PATH but present at ~/.qlty/bin/qlty, it is found."""
        fallback_home = tmp_path / "home"
        fallback_dir = fallback_home / ".qlty" / "bin"
        fallback_dir.mkdir(parents=True)
        fallback = fallback_dir / c.Infra.QLTY_BINARY
        fallback.write_text(
            "#!/usr/bin/env python3\nimport sys\nsys.stdout.write('{}')\n",
            encoding="utf-8",
        )
        fallback.chmod(0o755)
        monkeypatch.setenv("HOME", str(fallback_home))
        monkeypatch.setenv("PATH", str(tmp_path / "empty-bin"))
        (tmp_path / "empty-bin").mkdir()

        gate = FlextInfraSmellsGate(tmp_path)
        execution = gate.execute(_ctx(tmp_path))

        tm.that(execution.result.passed, eq=True)

    def test_smell_tags_have_core_rule_text(self) -> None:
        """Every qlty smell tag mapped by the gate has a FLEXT problem/fix text."""
        missing = [
            enforcement_tag
            for enforcement_tag in c.Infra.SMELLS_RULE_TAGS.values()
            if enforcement_tag not in c.ENFORCEMENT_RULES_TEXT
        ]
        tm.that(missing, eq=[])


__all__: t.StrSequence = []
