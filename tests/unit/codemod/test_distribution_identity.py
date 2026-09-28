"""Rule planning distinguishes repeated search paths from duplicate installs."""

from __future__ import annotations

from pathlib import Path

import pytest

from flext_infra import u


class TestsFlextInfraDistributionIdentity:
    """Exercise real installed metadata through the public rule planner."""

    @staticmethod
    def project(root: Path) -> None:
        (root / "pyproject.toml").write_text(
            '[project]\nname = "metadata-consumer"\ndependencies = []\n',
            encoding="utf-8",
        )

    @staticmethod
    def distribution(root: Path) -> None:
        metadata = root / "rule_identity_fixture-1.0.dist-info"
        metadata.mkdir(parents=True)
        (metadata / "METADATA").write_text(
            "Metadata-Version: 2.1\nName: rule-identity-fixture\nVersion: 1.0\n",
            encoding="utf-8",
        )

    def test_repeated_directory_is_one_installation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self.project(tmp_path)
        site = tmp_path / "site"
        self.distribution(site)
        monkeypatch.syspath_prepend(str(site))
        monkeypatch.syspath_prepend(str(site))
        planned = u.Infra.codemod_rule_plan(tmp_path)
        assert planned.success, planned.error

    def test_distinct_duplicate_installations_are_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self.project(tmp_path)
        for name in ("first", "second"):
            site = tmp_path / name
            self.distribution(site)
            monkeypatch.syspath_prepend(str(site))
        with pytest.raises(ValueError, match="duplicate installed distribution"):
            u.Infra.codemod_rule_plan(tmp_path)
