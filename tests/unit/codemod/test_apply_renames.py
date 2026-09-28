"""Public CSV-driven rename engine contract and its mod-verb wiring."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import FlextInfraConfig, c, m, main as infra_main, p, u

if TYPE_CHECKING:
    from tests import t
from flext_infra.codemod import FlextInfraApplyRenames


class TestsFlextInfraApplyRenames:
    """Exercise the rename engine and its configured campaign wiring."""

    @staticmethod
    def _campaign(tmp_path: Path) -> t.Triple[Path, Path, Path]:
        """One workspace file, its driver CSV, and the scan root."""
        root = tmp_path / "campaign_ws"
        tm.ok(u.Cli.ensure_dir(root))
        target = root / "values.py"
        tm.ok(
            u.Cli.atomic_write_text_file(
                target, 'CAMPAIGN_TOKEN: str = "campaign_token"\n'
            )
        )
        csv = root / "renames.csv"
        tm.ok(
            u.Cli.atomic_write_text_file(
                csv, "old,new\ncampaign_token,campaign_renamed_token\n"
            )
        )
        return root, csv, target

    @staticmethod
    def _run_engine(
        csv: Path, root: Path, *, apply: bool
    ) -> p.Result[m.Infra.ApplyRenamesReport]:
        return FlextInfraApplyRenames.run(
            m.Infra.ApplyRenamesInput(csv=str(csv), roots=(str(root),), apply=apply)
        )

    def test_check_counts_occurrences_and_preserves_every_file(
        self, tmp_path: Path
    ) -> None:
        """Check mode reports pending work and never touches the workspace."""
        root, csv, target = self._campaign(tmp_path)
        original = target.read_bytes()

        report = tm.ok(self._run_engine(csv, root, apply=False))

        # The driver CSV owns its pairs and is excluded from its own scope, so
        # only the workspace file is scanned and exactly one token is pending.
        tm.that(report.files_scanned, eq=1)
        tm.that(report.occurrences, eq=1)
        tm.that(report.applied, eq=False)
        tm.that(target.read_bytes(), eq=original)

    def test_apply_rewrites_targets_and_reaches_idempotent_fixed_point(
        self, tmp_path: Path
    ) -> None:
        """Apply rewrites the workspace file once and never its driver CSV."""
        root, csv, target = self._campaign(tmp_path)
        csv_document = csv.read_text(encoding="utf-8")

        first = tm.ok(self._run_engine(csv, root, apply=True))

        tm.that(first.files_changed, eq=1)
        rewritten = target.read_text(encoding="utf-8")
        tm.that(rewritten, has='CAMPAIGN_TOKEN: str = "campaign_renamed_token"')
        tm.that(rewritten, lacks="campaign_token")
        tm.that(csv.read_text(encoding="utf-8"), eq=csv_document)

        second = tm.ok(self._run_engine(csv, root, apply=True))
        tm.that(second.files_changed, eq=0)

    def test_rejects_malformed_driver_lists(self, tmp_path: Path) -> None:
        """Malformed CSV sources fail loudly and rewrite nothing."""
        root, csv, target = self._campaign(tmp_path)
        original = target.read_bytes()

        tm.ok(u.Cli.atomic_write_text_file(csv, "from,to\ncampaign_token,x\n"))
        tm.fail(self._run_engine(csv, root, apply=False), has="header must be exactly")

        tm.ok(u.Cli.atomic_write_text_file(csv, "old,new\ncampaign_token,\n"))
        tm.fail(
            self._run_engine(csv, root, apply=False), has="non-empty old,new values"
        )

        tm.that(target.read_bytes(), eq=original)

    @staticmethod
    def _declare_campaign_override(config_dir: Path) -> None:
        """Copy the packaged config tree and overlay one config-relative campaign.

        The whole tree travels, not only its top-level YAML: campaign lists the
        packaged config declares live under ``rules/`` and resolve against the
        overriding directory.
        """
        shutil.copytree(
            FlextInfraConfig.ssot_config_dir(), config_dir, dirs_exist_ok=True
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                config_dir / "renames.csv",
                "old,new\ncampaign_token,campaign_renamed_token\n",
            )
        )
        (config_dir / c.Infra.CODEGEN_LOCAL_OVERRIDES_FILENAME).write_text(
            "Infra:\n"
            "  refactor_csv_campaigns:\n"
            "    campaigns:\n"
            "      - csv: renames.csv\n",
            encoding="utf-8",
        )

    @staticmethod
    def _campaign_workspace(tmp_path: Path) -> t.Pair[Path, Path]:
        """Seed the mod workspace with one pending campaign rename."""
        sample = tmp_path / "sample.py"
        tm.ok(
            u.Cli.atomic_write_text_file(
                sample,
                '"""Campaign rename fixture module."""\n'
                "\n"
                "from __future__ import annotations\n"
                "\n"
                "\n"
                'CAMPAIGN_TOKEN: str = "campaign_token"\n',
            )
        )
        return sample, tmp_path / "config_override"

    @pytest.mark.slow
    def test_dry_run_fails_on_pending_configured_campaign(
        self, mod_workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Check mode fails while a configured campaign still has work."""
        sample, config_dir = self._campaign_workspace(mod_workspace)
        tm.ok(u.Cli.ensure_dir(config_dir))
        self._declare_campaign_override(config_dir)
        monkeypatch.setenv("FLEXT_INFRA_CONFIG_DIR", str(config_dir))
        FlextInfraConfig.reset_for_testing()
        try:
            exit_code = infra_main([
                "refactor",
                "mod",
                "--repository-root",
                str(mod_workspace),
            ])
        finally:
            FlextInfraConfig.reset_for_testing()

        tm.that(exit_code != 0, eq=True)
        tm.that(sample.read_text(encoding="utf-8"), has='"campaign_token"')

    @pytest.mark.slow
    def test_apply_converges_configured_campaign_through_the_public_mod_route(
        self, mod_workspace: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The mod verb consumes the config campaigns and reaches a fixed point."""
        sample, config_dir = self._campaign_workspace(mod_workspace)
        tm.ok(u.Cli.ensure_dir(config_dir))
        self._declare_campaign_override(config_dir)
        monkeypatch.setenv("FLEXT_INFRA_CONFIG_DIR", str(config_dir))
        FlextInfraConfig.reset_for_testing()
        try:
            exit_code = infra_main([
                "refactor",
                "mod",
                "--repository-root",
                str(mod_workspace),
                "--apply",
            ])
        finally:
            FlextInfraConfig.reset_for_testing()

        tm.that(exit_code, eq=0)
        rewritten = sample.read_text(encoding="utf-8")
        tm.that(rewritten, has='"campaign_renamed_token"')
        tm.that(rewritten, lacks="campaign_token")

    @staticmethod
    def _shipped_pairs() -> t.SequenceOf[t.Pair[str, str]]:
        """Read every old,new pair the packaged config declares."""
        config_dir = FlextInfraConfig.ssot_config_dir()
        campaigns = (
            FlextInfraConfig.fetch_global().Infra.refactor_csv_campaigns.campaigns
        )
        tm.that(campaigns, empty=False)
        pairs: list[t.Pair[str, str]] = []
        for campaign in campaigns:
            text = tm.ok(u.Cli.files_read_text(config_dir / campaign.csv))
            rows = tm.ok(u.Cli.csv_loads(text))
            pairs.extend((row[0], row[1]) for row in rows[1:])
        return tuple(pairs)

    @staticmethod
    def _run_mod(root: Path, *, apply: bool) -> int:
        """Invoke the public mod route with the packaged configuration."""
        FlextInfraConfig.reset_for_testing()
        try:
            return infra_main([
                "refactor",
                "mod",
                "--repository-root",
                str(root),
                *(("--apply",) if apply else ()),
            ])
        finally:
            FlextInfraConfig.reset_for_testing()

    @pytest.mark.slow
    def test_shipped_campaigns_rewrite_a_consumer_and_reach_a_fixed_point(
        self, mod_workspace: Path
    ) -> None:
        """Packaged campaigns rewrite a repository that carries no list copy."""
        pairs = self._shipped_pairs()
        consumer = mod_workspace / "consumer_names.py"
        mentions = "".join(f"- {old}\n" for old, _new in pairs)
        tm.ok(
            u.Cli.atomic_write_text_file(
                consumer,
                f'"""Consumer module naming every retired symbol.\n\n{mentions}"""\n',
            )
        )
        prose = "Prose paragraphs around a retired name keep every word.\n"
        guide = mod_workspace / "guide.md"
        tm.ok(u.Cli.atomic_write_text_file(guide, f"# Guide\n\n{prose}\n{mentions}"))

        tm.that(self._run_mod(mod_workspace, apply=True), eq=0)
        first = consumer.read_bytes()
        first_guide = guide.read_bytes()
        for rewritten in (first.decode("utf-8"), first_guide.decode("utf-8")):
            for old, new in pairs:
                tm.that(rewritten, has=f"- {new}\n")
                tm.that(rewritten, lacks=f"- {old}\n")
        tm.that(first_guide.decode("utf-8"), has=f"# Guide\n\n{prose}")

        tm.that(self._run_mod(mod_workspace, apply=True), eq=0)
        tm.that(consumer.read_bytes(), eq=first)
        tm.that(guide.read_bytes(), eq=first_guide)
        # mod's check mode also fails on the fixture's deliberate detection-only
        # governance finding, so convergence is proven by the rename engine's
        # own check mode over the same packaged lists.
        config_dir = FlextInfraConfig.ssot_config_dir()
        for (
            campaign
        ) in FlextInfraConfig.fetch_global().Infra.refactor_csv_campaigns.campaigns:
            pending = tm.ok(
                self._run_engine(config_dir / campaign.csv, mod_workspace, apply=False)
            )
            tm.that(pending.occurrences, eq=0)
