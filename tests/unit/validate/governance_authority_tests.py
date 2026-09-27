"""Reject dead governance skill paths and conflicting authority sequences."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

import flext_infra
from tests import u


class TestsFlextInfraGovernanceAuthority:
    """Test suite for governance skill-path and authority-sequence integrity."""

    ROOT = Path(flext_infra.__file__).resolve().parents[2]

    def _common_dir(self) -> Path:
        return Path(
            tm.ok(
                u.Cli.capture(
                    ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                    cwd=self.ROOT,
                )
            )
        )

    def _repository_root(self) -> Path:
        # When flext-infra is a submodule, the git common-dir resolves to the
        # superproject's <superproject>/.git/modules/<name> and --show-toplevel
        # returns the submodule checkout. Governance assets (docs/, AGENTS.md,
        # .agents/skills) live in the superproject, so resolve its root instead.
        common_dir = self._common_dir()
        super_modules = [
            p
            for p in common_dir.parents
            if p.name == "modules" and p.parent.name == ".git"
        ]
        resolve_root = super_modules[0].parent.parent if super_modules else self.ROOT
        return Path(
            tm.ok(
                u.Cli.capture(
                    ["git", "rev-parse", "--path-format=absolute", "--show-toplevel"],
                    cwd=resolve_root,
                )
            )
        )

    def test_prompt_skills_resolve_to_existing_paths(self) -> None:
        prompts = self.ROOT / ".github" / "prompts"
        law_link = "../../.agents/skills/flext-law/SKILL.md"
        for prompt in prompts.glob("*.prompt.md"):
            text = prompt.read_text(encoding="utf-8")
            assert "flext-inviolable-rules" not in text
            assert "quality-gates" not in text
            if (
                "flext-aggressive-scale-refactor" in prompt.name
                or "flext-strict-jsonvalue" in prompt.name
            ):
                assert law_link in text
                target = (prompt.parent / law_link).resolve()
                assert target.exists(), f"{prompt.name} dead skill path: {law_link}"

    def test_markdownlint_does_not_suppress_strict_rules(self) -> None:
        config = u.Tests.json_payload(
            (self.ROOT / ".markdownlint.json").read_text(encoding="utf-8")
        )
        assert config.get("MD012") is not False
        assert config.get("MD050") is not False
        assert config.get("MD064") is not False
        assert config.get("MD075") is not False
        line_length = u.Tests.toml_mapping(config["MD013"])["line_length"]
        assert isinstance(line_length, int)
        assert line_length <= 500

    def test_flext_law_requires_automated_structural_rewires(self) -> None:
        # Markdown reflows a clause across lines at whatever column the
        # formatter chooses, so a literal match answers about the wrap and not
        # about the law. Collapse runs of whitespace and assert the sentence
        # itself.
        law = " ".join(
            (self._repository_root() / ".agents/skills/flext-law/SKILL.md")
            .read_text(encoding="utf-8")
            .split()
        )

        for required in (
            "`make mod`",
            "`ast-grep` rewrites",
            "Rope semantic refactors",
            "`pyright-langserver` diagnostics",
            "GitHub and CRG belong to ai-hub",
            "never imports ai-hub or CRG as a library",
            "Repetitive manual call-site editing is prohibited",
        ):
            tm.that(law, has=required)
