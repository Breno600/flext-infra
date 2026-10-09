"""Exercise serial lifecycle orchestration through real public CLI and Make recipes.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from shlex import quote

import pytest
from flext_tests import tm

from flext_infra import main
from tests import c, m, u


class TestsFlextInfraWorkspaceLifecycle:
    """Public Make boundaries retain order, failure, and unreached scope."""

    @staticmethod
    def _workspace(root: Path, *, fail_at: int = -1) -> Path:
        """Reuse the governed topology fixture with observable public Make recipes.

        Returns:
            The attached member checkout.
        """
        member = u.Tests.WorktreeFixture.governed_workspace_with_member(root)
        log = quote(str(root / "lifecycle.log"))
        verbs = " ".join(dict.fromkeys(c.Infra.LIFECYCLE_VERBS))
        for cwd in (root, member):
            (cwd / "Makefile").write_text(
                f".PHONY: {verbs}\n"
                f"{verbs}:\n"
                f"\t@printf '%s|%s\\n' '$(CURDIR)' '$@' >> {log}; "
                f"step=$$(wc -l < {log}); "
                f'if [ "$$step" -eq {fail_at + 1} ]; then '
                "printf 'lifecycle-fixture-failure\\n' >&2; exit 7; fi\n",
                encoding=c.Cli.ENCODING_DEFAULT,
            )
        return member

    @staticmethod
    def _run(root: Path) -> int:
        """Invoke the public selector-free route.

        Returns:
            The CLI exit code.
        """
        return main([
            c.Infra.CLI_GROUP_WORKSPACE,
            "validate-lifecycle",
            "--repository-root",
            str(root),
        ])

    @staticmethod
    def _report(root: Path) -> m.Infra.LifecycleReport:
        """Read the same typed receipt the real workspace consumer reads.

        Returns:
            The published lifecycle report.
        """
        return m.Infra.LifecycleReport.model_validate_json(
            (root / c.Infra.LIFECYCLE_REPORT_RELATIVE_PATH).read_bytes(),
        )

    def test_runs_root_then_every_member_without_inherited_make_flags(
        self,
        tmp_path: Path,
    ) -> None:
        """Inherited dry-run/parallel flags cannot turn unevaluated recipes green."""
        root = tmp_path / "workspace"
        member = self._workspace(root)
        manifest = tm.ok(u.Infra.load_workspace_manifest(root))[0]
        declaration = manifest.model_copy(
            update={
                "external_consumers": (
                    m.Infra.ExternalConsumerSpec(
                        name="outside-scope",
                        root=tmp_path / "absent-consumer",
                    ),
                ),
            }
        )
        tm.ok(
            u.Cli.yaml_dump(
                u.Infra.workspace_manifest_path(root),
                declaration.model_dump(mode="json", exclude_computed_fields=True),
            ),
        )
        with u.Tests.env_vars_context(env_vars={"MAKEFLAGS": "-n -j8"}):
            tm.that(self._run(root), eq=0)

        report = self._report(root)
        tm.that(report.workspace_root, eq=root)
        tm.that(report.scope, eq=(root, member))
        expected = tuple(
            (cwd, (c.Infra.MAKE, verb))
            for cwd in report.scope
            for verb in c.Infra.LIFECYCLE_VERBS
        )
        tm.that(
            tuple((row.cwd, row.command) for row in report.receipts),
            eq=expected,
        )
        tm.that(all(row.exit_code == 0 for row in report.receipts), eq=True)
        tm.that(all(row.error is None for row in report.receipts), eq=True)
        tm.that(all(row.output_file.is_file() for row in report.receipts), eq=True)
        tm.that(
            (root / "lifecycle.log")
            .read_text(
                encoding=c.Cli.ENCODING_DEFAULT,
            )
            .splitlines(),
            eq=[f"{cwd}|{command[-1]}" for cwd, command in expected],
        )

    @pytest.mark.parametrize("fail_at", range(len(c.Infra.LIFECYCLE_VERBS) * 2))
    def test_first_failure_stops_and_keeps_unreached_receipts_not_green(
        self,
        tmp_path: Path,
        fail_at: int,
    ) -> None:
        """Every lifecycle position can fail without running any later operation."""
        root = tmp_path / "workspace"
        self._workspace(root, fail_at=fail_at)

        tm.that(self._run(root) != 0, eq=True)

        report = self._report(root)
        tm.that(
            len(report.receipts),
            eq=len(report.scope) * len(c.Infra.LIFECYCLE_VERBS),
        )
        tm.that(all(row.exit_code == 0 for row in report.receipts[:fail_at]), eq=True)
        failed = report.receipts[fail_at]
        tm.that(failed.exit_code not in {None, 0}, eq=True)
        tm.that(failed.error is not None, eq=True)
        tm.that(
            failed.output_file.read_text(encoding=c.Cli.ENCODING_DEFAULT),
            has="lifecycle-fixture-failure",
        )
        tm.that(
            all(row.exit_code is None for row in report.receipts[fail_at + 1 :]),
            eq=True,
        )
        tm.that(
            all(not row.output_file.exists() for row in report.receipts[fail_at + 1 :]),
            eq=True,
        )
        tm.that(
            len(
                (root / "lifecycle.log")
                .read_text(encoding=c.Cli.ENCODING_DEFAULT)
                .splitlines(),
            ),
            eq=fail_at + 1,
        )

    def test_standalone_rejects_before_any_lifecycle_effect(
        self,
        tmp_path: Path,
    ) -> None:
        """A public route cannot bypass the workspace-only Make applicability."""
        root = u.Tests.WorktreeFixture.governed_workspace(tmp_path, "standalone")

        tm.that(self._run(root) != 0, eq=True)

        tm.that((root / c.Infra.LIFECYCLE_REPORT_RELATIVE_PATH).exists(), eq=False)
        tm.that((root / "lifecycle.log").exists(), eq=False)

    def test_route_rejects_project_selection_before_any_effect(
        self,
        tmp_path: Path,
    ) -> None:
        """The route accepts only the root boundary, never a partial fleet selector."""
        root = tmp_path / "workspace"
        self._workspace(root)

        tm.that(
            main([
                c.Infra.CLI_GROUP_WORKSPACE,
                "validate-lifecycle",
                "--repository-root",
                str(root),
                "--projects",
                ".",
            ])
            != 0,
            eq=True,
        )

        tm.that((root / c.Infra.LIFECYCLE_REPORT_RELATIVE_PATH).exists(), eq=False)
        tm.that((root / "lifecycle.log").exists(), eq=False)
