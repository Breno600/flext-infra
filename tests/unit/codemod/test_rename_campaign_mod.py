"""Configured CSV campaigns through the real public mod command."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import FlextInfraConfig, c, infra, m
from tests import u


class TestsRenameCampaignMod:
    """Use separate processes and real config files, never patched owner state."""

    @staticmethod
    def _declare(config_dir: Path) -> None:
        shutil.copytree(FlextInfraConfig.ssot_config_dir(), config_dir)
        (config_dir / "renames.csv").write_text(
            "old,new\ncampaign_token,campaign_renamed_token\n", encoding="utf-8",
        )
        (config_dir / c.Infra.CODEGEN_LOCAL_OVERRIDES_FILENAME).write_text(
            "Infra:\n  refactor_csv_campaigns:\n    campaigns:\n"
            "      - csv: renames.csv\n"
            "        text_globs: ['**/*.md']\n"
            "        python_documentation: true\n",
            encoding="utf-8",
        )

    @pytest.mark.slow
    @pytest.mark.parametrize("apply", [False, True])
    def test_public_mod_consumes_declared_text_campaign(
        self, mod_workspace: Path, tmp_path: Path, *, apply: bool,
    ) -> None:
        config_dir = tmp_path / "campaign_config"
        self._declare(config_dir)
        (mod_workspace / "sample.py").write_text(
            '"""Document campaign_token without changing the runtime payload."""\n'
            "\nfrom __future__ import annotations\n"
            '\nPAYLOAD: str = "campaign_token"\n',
            encoding="utf-8",
        )
        guide = mod_workspace / "guide.md"
        guide.write_text("A campaign_token paragraph.\n", encoding="utf-8")
        result = tm.ok(
            u.Cli.run_raw(
                (
                    sys.executable,
                    "-m",
                    "flext_infra",
                    "refactor",
                    "mod",
                    "--repository-root",
                    str(mod_workspace),
                    *(("--apply",) if apply else ()),
                ),
                env={"FLEXT_INFRA_CONFIG_DIR": str(config_dir)},
            ),
        )
        tm.that(u.Cli.process_succeeded(result.outcome), eq=apply, msg=result.stderr)
        if apply:
            tm.that(result.stdout, has="published file(s)")
        tm.that(
            guide.read_text(),
            eq="A campaign_renamed_token paragraph.\n"
            if apply
            else "A campaign_token paragraph.\n",
        )
        consumer = tm.ok(
            u.Cli.run(
                (sys.executable, "-c", "import sample; print(sample.PAYLOAD)"),
                cwd=mod_workspace,
            ),
        )
        tm.that(consumer.stdout, eq="campaign_token\n")

    def test_packaged_campaigns_preserve_prose_and_converge(
        self, tmp_path: Path,
    ) -> None:
        mod_workspace, _package = u.Tests.create_lazy_init_workspace(tmp_path)
        config_dir = FlextInfraConfig.ssot_config_dir()
        campaigns = (
            FlextInfraConfig.fetch_global().Infra.refactor_csv_campaigns.campaigns
        )
        tm.that(campaigns, empty=False)
        for index, campaign in enumerate(campaigns):
            rows = tm.ok(
                u.Cli.csv_loads((config_dir / campaign.csv).read_text(encoding="utf-8")),
            )
            pairs = tuple((row[0], row[1]) for row in rows[1:])
            mentions = "".join(f"- {old}\n" for old, _new in pairs)
            guide = mod_workspace / f"campaign_{index}.md"
            guide.write_text(
                "# Guide\n\nSurrounding prose remains.\n" + mentions, encoding="utf-8",
            )
            consumer = mod_workspace / f"consumer_{index}.py"
            consumer.write_text(f'"""{mentions}"""\n', encoding="utf-8")
            params = m.Infra.ApplyRenamesInput(
                csv=str(config_dir / campaign.csv),
                roots=(str(mod_workspace),),
                apply=True,
                bindings=campaign.bindings,
                text_globs=campaign.text_globs,
                python_documentation=campaign.python_documentation,
                exclude_globs=campaign.exclude_globs,
            )
            tm.ok(infra.apply_renames(params))
            for old, new in pairs:
                tm.that(guide.read_text(), has=f"- {new}\n")
                tm.that(guide.read_text(), lacks=f"- {old}\n")
            tm.that(guide.read_text(), has="Surrounding prose remains.\n")
            first = guide.read_bytes()
            second = tm.ok(infra.apply_renames(params))
            tm.that(second.files_changed, eq=0)
            tm.that(second.occurrences, eq=0)
            tm.that(guide.read_bytes(), eq=first)
