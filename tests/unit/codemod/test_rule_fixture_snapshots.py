"""Rule-test snapshots change only through their explicit refresh, never in mod.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, main
from flext_infra.codemod.batch_gates import FlextInfraModGateEngine
from tests import t, u


class TestsFlextInfraModRuleFixtureSnapshots:
    """Verification rejects snapshot drift; the refresh records it for review."""

    @staticmethod
    def _catalog(root: Path) -> Path:
        """Return the project's own rule catalog directory under ``root``.

        Returns:
            The directory holding the local ``sgconfig.yml`` the plan reads.

        """
        return root / c.Infra.CODEMOD_CONFIG_RELPATH.parent

    @classmethod
    def _owner(
        cls,
        root: Path,
        *,
        fix: str = "bar($A)",
        invalid: t.StrSequence = ("foo(1)",),
    ) -> Path:
        """Declare one governed rule with its test in the local catalog.

        The catalog sits where the rule plan reads a project's own rules, and
        Git must track it: Git decides which provider a repository governs.

        Returns:
            The resulting ``Path``.

        """
        catalog = cls._catalog(root)
        for directory in (root / "src", catalog / "rules", catalog / "tests"):
            tm.ok(u.Cli.ensure_dir(directory))
        u.Tests.copy_tracked_mise_seeds(root)
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / c.Infra.CODEMOD_CONFIG_RELPATH,
                "ruleDirs: [rules]\ntestConfigs:\n  - testDir: tests\n",
            ),
        )
        rule = catalog / "rules" / "demo.yml"
        tm.ok(
            u.Cli.atomic_write_text_file(
                rule,
                "id: demo\nlanguage: python\nseverity: error\n"
                f"rule:\n  pattern: foo($A)\nfix: {fix}\n",
            ),
        )
        cases = "".join(f"  - {case}\n" for case in invalid)
        tm.ok(
            u.Cli.atomic_write_text_file(
                catalog / "tests" / "demo-test.yml",
                f"id: demo\nvalid:\n  - baz(1)\ninvalid:\n{cases}",
            ),
        )
        # The rule engine runs ast-grep through the owner's pinned Mise lock,
        # which every governed repository carries; without it a host-global
        # binary (or none, on CI runners) answered instead.
        u.Tests.copy_tracked_mise_seeds(root)
        # A bare root becomes a checkout through its initial commit; an
        # existing checkout commits the catalog it now declares.
        if (root / c.Infra.GIT_DIR).exists():
            u.Tests.commit_git_changes(root, "Declare the demo rule catalog")
        else:
            u.Tests.initialize_git_repo(root)
        u.Tests.git_bootstrap(root, ("add", str(c.Infra.CODEMOD_CONFIG_RELPATH)))
        u.Tests.git_bootstrap(root, ("add", c.Infra.CODEMOD_CONFIG_FILENAME))
        return rule

    @classmethod
    def _snapshot(cls, root: Path, rule_id: str = "demo") -> Path:
        """Return the committed snapshot path of one rule under ``root``.

        Returns:
            The committed snapshot path of one rule under ``root``.

        """
        return (
            cls._catalog(root)
            / "tests"
            / c.Infra.CODEMOD_SNAPSHOT_DIRNAME
            / f"{rule_id}{c.Infra.CODEMOD_SNAPSHOT_SUFFIX}"
        )

    def test_refresh_records_what_verification_then_accepts(
        self,
        tmp_path: Path,
    ) -> None:
        """A dry refresh writes nothing; the applied refresh makes mod verify."""
        rule = self._owner(tmp_path)

        preview = tm.ok(
            FlextInfraModGateEngine.refresh_rule_snapshots(
                tmp_path,
                (rule,),
                apply=False,
            ),
        )
        tm.that(preview, eq=(f"created {self._snapshot(tmp_path)}",))
        tm.that(self._snapshot(tmp_path).exists(), eq=False)
        tm.fail(FlextInfraModGateEngine.validate_rule_fixtures(tmp_path, (rule,)))

        applied = tm.ok(
            FlextInfraModGateEngine.refresh_rule_snapshots(
                tmp_path,
                (rule,),
                apply=True,
            ),
        )

        tm.that(applied, eq=preview)
        tm.that(self._snapshot(tmp_path).exists(), eq=True)
        tm.ok(FlextInfraModGateEngine.validate_rule_fixtures(tmp_path, (rule,)))
        tm.that(
            tm.ok(
                FlextInfraModGateEngine.refresh_rule_snapshots(
                    tmp_path,
                    (rule,),
                    apply=True,
                ),
            ),
            empty=True,
        )

    def test_changed_rule_output_fails_verification_without_rewriting(
        self,
        tmp_path: Path,
    ) -> None:
        """Mod never accepts a new fix output as its own expectation."""
        rule = self._owner(tmp_path)
        tm.ok(
            FlextInfraModGateEngine.refresh_rule_snapshots(
                tmp_path,
                (rule,),
                apply=True,
            ),
        )
        committed = self._snapshot(tmp_path).read_bytes()
        _ = self._owner(tmp_path, fix="qux($A)")

        failure = FlextInfraModGateEngine.validate_rule_fixtures(tmp_path, (rule,))

        tm.fail(failure, has=c.Infra.CODEMOD_SNAPSHOT_REFRESH_HINT)
        tm.that(self._snapshot(tmp_path).read_bytes(), eq=committed)
        changes = tm.ok(
            FlextInfraModGateEngine.refresh_rule_snapshots(
                tmp_path,
                (rule,),
                apply=True,
            ),
        )
        tm.that(changes, eq=(f"updated {self._snapshot(tmp_path)}",))
        tm.that(self._snapshot(tmp_path).read_text(encoding="utf-8"), has="qux(1)")
        tm.ok(FlextInfraModGateEngine.validate_rule_fixtures(tmp_path, (rule,)))

    @pytest.mark.parametrize("residue", ["removed-rule", "deleted-case"])
    def test_snapshot_residue_fails_verification_until_refreshed(
        self,
        tmp_path: Path,
        residue: str,
    ) -> None:
        """A snapshot no rule test produces is reported, then removed by refresh."""
        rule = self._owner(tmp_path, invalid=("foo(1)", "foo(2)"))
        tm.ok(
            FlextInfraModGateEngine.refresh_rule_snapshots(
                tmp_path,
                (rule,),
                apply=True,
            ),
        )
        if residue == "removed-rule":
            stale = self._snapshot(tmp_path, "retired")
            tm.ok(
                u.Cli.atomic_write_text_file(
                    stale,
                    self
                    ._snapshot(tmp_path)
                    .read_text(encoding="utf-8")
                    .replace("id: demo", "id: retired"),
                ),
            )
            expected = f"removed {stale}"
        else:
            _ = self._owner(tmp_path, invalid=("foo(1)",))
            expected = f"updated {self._snapshot(tmp_path)}"

        failure = FlextInfraModGateEngine.validate_rule_fixtures(tmp_path, (rule,))

        tm.fail(failure, has=c.Infra.CODEMOD_SNAPSHOT_REFRESH_HINT)
        changes = tm.ok(
            FlextInfraModGateEngine.refresh_rule_snapshots(
                tmp_path,
                (rule,),
                apply=True,
            ),
        )
        tm.that(changes, eq=(expected,))
        tm.ok(FlextInfraModGateEngine.validate_rule_fixtures(tmp_path, (rule,)))

    @pytest.mark.slow
    def test_public_refresh_route_dry_run_fails_until_applied(
        self,
        mod_workspace: Path,
    ) -> None:
        """The public route previews pending snapshots as red and applies them."""
        _ = self._owner(mod_workspace)
        snapshot = self._snapshot(mod_workspace)
        route = ["refactor", "mod-snapshots", "--repository-root", str(mod_workspace)]

        tm.that(main(route), ne=0)
        tm.that(snapshot.exists(), eq=False)
        tm.that(main([*route, "--apply"]), eq=0)
        tm.that(snapshot.exists(), eq=True)
        tm.that(main(route), eq=0)
