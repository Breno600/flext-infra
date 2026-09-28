"""Fixture staging follows sgconfig declarations, never the owning checkout."""

from __future__ import annotations

from pathlib import Path

import pytest

from flext_infra import c
from flext_infra.codemod.batch_gates import FlextInfraModGateEngine


class TestsFlextInfraModRuleFixtureStaging:
    """Fixture staging follows sgconfig declarations, never the owning checkout."""

    @pytest.mark.parametrize("with_utils", [False, True])
    @pytest.mark.parametrize("regenerate_snapshots", [False, True])
    def test_staging_copies_declared_trees_without_traversing_checkout(
        self, tmp_path: Path, *, with_utils: bool, regenerate_snapshots: bool
    ) -> None:
        owner = tmp_path / "owner"
        owner.mkdir()
        config = "ruleDirs: [rules]\ntestConfigs:\n  - testDir: fixtures\n"
        if with_utils:
            config += "utilDirs: [utils]\n"
        payloads = {
            c.Infra.CODEMOD_CONFIG_FILENAME: config,
            "rules/nested/rule.yml": "id: rule\n",
            "fixtures/rule-test.yml": "id: rule\nvalid: []\n",
            f"fixtures/{c.Infra.CODEMOD_SNAPSHOT_DIRNAME}/rule-snapshot.yml": (
                "id: rule\n"
            ),
        }
        if with_utils:
            payloads["utils/common.yml"] = "id: common\n"
        for relative, content in payloads.items():
            path = owner / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        poison = owner / ".venv"
        poison.mkdir()
        (poison / "recursive").symlink_to(poison, target_is_directory=True)
        (owner / ".agents").symlink_to(tmp_path / "absent", target_is_directory=True)
        (owner / ".git").mkdir()
        (owner / ".git" / "unrelated").write_text("do not copy", encoding="utf-8")
        staged = tmp_path / "staged"

        FlextInfraModGateEngine.stage_rule_fixture_root(
            config_root=owner,
            temp_root=staged,
            regenerate_snapshots=regenerate_snapshots,
        )

        expected = dict(payloads)
        snapshot = f"fixtures/{c.Infra.CODEMOD_SNAPSHOT_DIRNAME}/rule-snapshot.yml"
        if regenerate_snapshots:
            del expected[snapshot]
        assert (owner / snapshot).read_text(encoding="utf-8") == payloads[snapshot]
        assert {
            path.relative_to(staged).as_posix(): path.read_text(encoding="utf-8")
            for path in staged.rglob("*")
            if path.is_file()
        } == expected
        assert not (staged / ".venv").exists()
        assert not (staged / ".agents").is_symlink()
        assert not (staged / ".git").exists()

    @pytest.mark.parametrize("declaration", [".", "../outside", "/outside"])
    def test_staging_rejects_owner_wide_or_escaping_declarations(
        self, tmp_path: Path, declaration: str
    ) -> None:
        owner = tmp_path / "owner"
        owner.mkdir()
        (owner / "fixtures").mkdir()
        (owner / c.Infra.CODEMOD_CONFIG_FILENAME).write_text(
            f"ruleDirs: ['{declaration}']\ntestConfigs: [{{testDir: fixtures}}]\n",
            encoding="utf-8",
        )
        staged = tmp_path / "staged"

        with pytest.raises(ValueError, match="escapes or selects its owner"):
            FlextInfraModGateEngine.stage_rule_fixture_root(
                config_root=owner, temp_root=staged
            )

        assert not staged.exists()

    @pytest.mark.parametrize("linked_directory", [False, True])
    def test_staging_rejects_declared_symlinks_before_copying(
        self, tmp_path: Path, *, linked_directory: bool
    ) -> None:
        owner = tmp_path / "owner"
        owner.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        (owner / "fixtures").mkdir()
        (owner / c.Infra.CODEMOD_CONFIG_FILENAME).write_text(
            "ruleDirs: [rules]\ntestConfigs: [{testDir: fixtures}]\n", encoding="utf-8"
        )
        if linked_directory:
            (owner / "rules").symlink_to(outside, target_is_directory=True)
        else:
            (owner / "rules").mkdir()
            (owner / "rules" / "external.yml").symlink_to(outside / "absent.yml")
        staged = tmp_path / "staged"

        with pytest.raises(ValueError, match=r"symlink|regular file or directory"):
            FlextInfraModGateEngine.stage_rule_fixture_root(
                config_root=owner, temp_root=staged
            )

        assert not staged.exists()
