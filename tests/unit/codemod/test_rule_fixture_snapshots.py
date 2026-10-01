"""Rule-test snapshots change only through their explicit refresh, never in mod."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, main as infra_main, u
from flext_infra.codemod.batch_gates import FlextInfraModGateEngine
from tests import t


class TestsFlextInfraModRuleFixtureSnapshots:
    """Verification rejects snapshot drift; the refresh records it for review."""

    @staticmethod
    def _owner(
        root: Path,
        *,
        fixtures: str = "codemod",
        fix: str = "bar($A)",
        invalid: t.StrSequence = ("foo(1)",),
    ) -> Path:
        """Declare one governed rule with its test under ``root``; return the rule."""
        for directory in ("src", f"{fixtures}/rules", f"{fixtures}/tests"):
            tm.ok(u.Cli.ensure_dir(root / directory))
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / c.Infra.CODEMOD_CONFIG_FILENAME,
                f"ruleDirs: [{fixtures}/rules]\n"
                f"testConfigs:\n  - testDir: {fixtures}/tests\n",
            ),
        )
        rule = root / fixtures / "rules" / "demo.yml"
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
                root / fixtures / "tests" / "demo-test.yml",
                f"id: demo\nvalid:\n  - baz(1)\ninvalid:\n{cases}",
            ),
        )
        return rule

    @staticmethod
    def _snapshot(root: Path, rule_id: str = "demo") -> Path:
        """Return the committed snapshot path of one rule under ``root``."""
        return (
            root
            / "codemod"
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

        tm.that(infra_main(route), ne=0)
        tm.that(snapshot.exists(), eq=False)
        tm.that(infra_main([*route, "--apply"]), eq=0)
        tm.that(snapshot.exists(), eq=True)
        tm.that(infra_main(route), eq=0)
