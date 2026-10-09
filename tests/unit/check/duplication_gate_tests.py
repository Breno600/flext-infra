"""Fail-closed public behavior for the jscpd duplication gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c
from flext_infra.check.gate_registry import FlextInfraGateRegistry
from flext_infra.gates.duplication import FlextInfraDuplicationGate
from tests import m, u


class TestsFlextInfraDuplicationGate:
    """Exercise observable gate behavior with the real setup-provisioned tool."""

    _DUPLICATED_MODULE = """\
def normalize_records(records: list[str]) -> t.VariadicTuple[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for record in records:
        candidate = record.strip().casefold()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)
    return tuple(sorted(normalized))
"""

    @staticmethod
    def _ctx(root: Path) -> m.Infra.GateContext:
        return m.Infra.GateContext(repository_root=root, reports_dir=root / "reports")

    @staticmethod
    def test_registry_exposes_the_canonical_gate() -> None:
        """Test registry exposes the canonical gate."""
        gate = FlextInfraGateRegistry.default().create("duplication", Path.cwd())
        tm.that(isinstance(gate, FlextInfraDuplicationGate), eq=True)

    def test_empty_workspace_scope_is_a_blocking_failure(self, tmp_path: Path) -> None:
        """Test empty workspace scope is a blocking failure."""
        project = tmp_path / "missing-project"
        project.mkdir()

        execution = FlextInfraDuplicationGate(tmp_path).check(
            project,
            self._ctx(tmp_path),
        )

        tm.that(execution.result.passed, eq=False)
        tm.that(len(execution.issues), eq=1)
        tm.that(execution.issues[0].message, has="the scanned scope is empty")
        tm.that(execution.issues[0].severity, eq=str(c.Infra.GateSeverity.ERROR.value))

    @staticmethod
    def _governed_with_declared_trees(tmp_path: Path, *, declare_trees: bool) -> Path:
        """One governed checkout whose clones live only inside charts/.

        Returns:
            The resulting ``Path``.

        """
        root = tmp_path / "governed-duplication"
        u.Tests.WorktreeFixture.initialize_governed_project(
            root,
            "fixture-duplication",
            workspace="duplication-workspace",
            database="duplication-database",
            issue_prefix="duplication-prefix",
        )
        package = root / "src" / "fixture_duplication"
        package.mkdir(parents=True, exist_ok=True)
        (root / "src" / "fixture_duplication" / "unique.py").write_text(
            "UNIQUE_MODULE_MARKER = 'canonical-scope-only'\n",
            encoding="utf-8",
        )
        (root / "charts").mkdir()
        # The clone must clear BOTH typed gate floors (lines and tokens); a
        # block under the token floor is skipped by the scanner, never a clone.
        chart_block = "apiVersion: apps/v1\nkind: Deployment\nenv:\n" + "".join(
            f"  - name: FIXTURE_SETTING_{index}\n    value: fixture-value-{index}\n"
            for index in range(max(c.Infra.JSCPD_MIN_LINES, c.Infra.JSCPD_MIN_TOKENS))
        )
        (root / "charts" / "values.yaml").write_text(chart_block, encoding="utf-8")
        nested = root / "charts" / "workers" / "prod"
        nested.mkdir(parents=True)
        (nested / "values.yaml").write_text(chart_block, encoding="utf-8")
        if declare_trees:
            manifest = root / "config" / "workspace.yaml"
            manifest.parent.mkdir(parents=True, exist_ok=True)
            provider = u.Tests.provider()
            manifest.write_text(
                "version: 3\n"
                "name: duplication-workspace\n"
                "repository:\n"
                "  name: fixture-duplication\n"
                "  distribution: fixture-duplication\n"
                f"  provider: {provider.name}\n"
                f"  url: {u.Tests.WorktreeFixture.governed_repository_url('fixture-duplication')}\n"
                "  path: .\n"
                "  role: standalone\n"
                "  state: active\n"
                "  kind: internal_flext\n"
                "  checkout: root\n"
                "  codegen: none\n"
                "  package: true\n"
                "  editable: true\n"
                "  read_only: false\n"
                "  duplication_trees: [charts]\n",
                encoding="utf-8",
            )
        return root

    def test_declared_trees_enter_the_scan_and_fail_on_clones(
        self,
        tmp_path: Path,
    ) -> None:
        """A declared project tree joins the scan and its clones are findings."""
        root = self._governed_with_declared_trees(tmp_path, declare_trees=True)

        execution = FlextInfraDuplicationGate(root).check(root, self._ctx(root))

        tm.that(execution.result.passed, eq=False)
        tm.that(
            tuple(issue.file for issue in execution.issues),
            has="charts/values.yaml",
        )

    def test_undeclared_trees_stay_outside_the_scan(self, tmp_path: Path) -> None:
        """Without a declaration the canonical Python discovery owns the scope."""
        root = self._governed_with_declared_trees(tmp_path, declare_trees=False)

        execution = FlextInfraDuplicationGate(root).check(root, self._ctx(root))

        tm.that(execution.result.passed, eq=True)
        tm.that(execution.issues, eq=())

    @staticmethod
    def _sibling_prefix_workspace(tmp_path: Path) -> Path:
        """One workspace whose member directories prefix each other.

        ``fixture-dup`` and ``fixture-dup-extra`` share a string prefix but are
        distinct projects; a clone between them must never be attributed to the
        shorter one.

        Returns:
            The resulting ``Path``.

        """
        root = tmp_path / "sibling-workspace"
        root.mkdir()
        module = "".join(
            f"def helper_{index}(value: int) -> int:\n    return value + {index}\n\n"
            for index in range(12)
        )
        for name in ("fixture-dup", "fixture-dup-extra"):
            member = root / name
            member.mkdir()
            u.Tests.WorktreeFixture.initialize_governed_project(
                member,
                name,
                workspace="sibling-workspace",
                database="sibling_workspace",
                issue_prefix="sibling",
            )
            package = member / "src" / name.replace("-", "_")
            package.mkdir(parents=True, exist_ok=True)
            (package / "duplicated.py").write_text(module, encoding="utf-8")
        u.Tests.write_workspace_manifest(
            root,
            "sibling-workspace",
            role=c.Infra.MakeProfile.WORKSPACE,
        )
        u.Tests.declare_workspace_projects(root, ("fixture-dup", "fixture-dup-extra"))
        return root

    def test_project_scan_never_reaches_a_prefix_named_sibling(
        self,
        tmp_path: Path,
    ) -> None:
        """A project evaluates only itself, locally exactly as in CI.

        Both members carry the same module, yet the gate for ``fixture-dup``
        scans only its own tree: the sibling whose name it prefixes is a
        library, never scanned, so no cross-project clone is reported.
        """
        root = self._sibling_prefix_workspace(tmp_path)
        own = root / "fixture-dup"

        execution = FlextInfraDuplicationGate(root).check(own, self._ctx(root))

        tm.that(execution.result.passed, eq=True)
        tm.that(execution.issues, eq=())
