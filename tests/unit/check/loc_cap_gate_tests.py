"""Tests for the module-cap SUPREME LAW (§3.1) gate.

The gate flags any module whose tokei `code` line count exceeds the owned cap
``c.Infra.LOC_CAP_MAX`` and accepts modules under it, exercised through the
public gate runner. Fixtures derive from that constant so a legitimate cap
change never silently inverts these assertions (UNIVERSAL_CORE P0).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, r
from flext_infra.gates.loc_cap import FlextInfraLocCapGate
from flext_tests import tm
from tests import u

if TYPE_CHECKING:
    from pathlib import Path

    from tests import t

# Why (operator 2026-08-07, cap 200 -> 1000): these fixtures MUST be derived
# from c.Infra.LOC_CAP_MAX, never hardcoded. A literal 250 silently became
# "under cap" when the cap was raised, turning the over-cap test into a lie.
_OVER_CAP_LOC = c.Infra.LOC_CAP_MAX + 50
_UNDER_CAP_LOC = 1
_OVER_CAP = (
    "from __future__ import annotations\n\n"
    + "\n".join(f"x{i} = {i}" for i in range(_OVER_CAP_LOC))
    + "\n"
)
_UNDER_CAP = "from __future__ import annotations\n\nx = 1\n"
_TOKEI_OVER_CAP = (
    '{"Python":{"reports":[{"name":"src/sample.py","stats":{"code":'
    f"{_OVER_CAP_LOC}"
    "}}]}}"
)
_TOKEI_UNDER_CAP = (
    '{"Python":{"reports":[{"name":"src/sample.py","stats":{"code":'
    f"{_UNDER_CAP_LOC}"
    "}}]}}"
)


def _gate_project(tmp_path: Path, *, name: str, module_src: str) -> Path:
    project_path: Path = u.Tests.create_codegen_project(
        tmp_path=tmp_path,
        name=name,
        pkg_name=name.replace("-", "_"),
        files={"sample.py": module_src},
    )
    return project_path


class TestLocCapGate:
    def test_gate_identity(self) -> None:
        tm.that(FlextInfraLocCapGate.gate_id, eq="loc-cap")
        tm.that(FlextInfraLocCapGate.can_fix, eq=False)

    def test_over_cap_module_is_flagged(self, tmp_path: Path) -> None:
        project = _gate_project(tmp_path, name="demo-project", module_src=_OVER_CAP)
        runner = u.Tests.SequenceRunner([
            r.ok(u.Tests.stub_run(stdout=_TOKEI_OVER_CAP))
        ])

        result = u.Tests.run_gate_check(
            FlextInfraLocCapGate, tmp_path, project, runner=runner
        )

        tm.that(not result.result.passed, eq=True)
        tm.that(any(issue.code == "LOC_CAP" for issue in result.issues), eq=True)

    def test_under_cap_module_passes(self, tmp_path: Path) -> None:
        project = _gate_project(tmp_path, name="demo-project", module_src=_UNDER_CAP)
        runner = u.Tests.SequenceRunner([
            r.ok(u.Tests.stub_run(stdout=_TOKEI_UNDER_CAP))
        ])

        result = u.Tests.run_gate_check(
            FlextInfraLocCapGate, tmp_path, project, runner=runner
        )

        tm.that(result.result.passed, eq=True)

    def test_tool_execution_failure_is_not_silenced(self, tmp_path: Path) -> None:
        project = _gate_project(tmp_path, name="demo-project", module_src=_UNDER_CAP)
        runner = u.Tests.SequenceRunner([r.fail("tokei is unavailable")])

        result = u.Tests.run_gate_check(
            FlextInfraLocCapGate, tmp_path, project, runner=runner
        )

        tm.that(result.result.passed, eq=False)
        tm.that(tuple(issue.code for issue in result.issues), has="LOC_CAP_EXEC")


__all__: t.StrSequence = []
