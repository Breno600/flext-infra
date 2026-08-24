"""Reject dead governance skill paths and conflicting authority sequences."""

from __future__ import annotations

import json
from pathlib import Path

import flext_infra
from flext_infra import u
from flext_tests import tm

ROOT = Path(flext_infra.__file__).resolve().parents[2]
COMMON_DIR = Path(
    tm.ok(
        u.Cli.capture(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=ROOT
        )
    )
)
# When flext-infra is a submodule, the git common-dir resolves to the
# superproject's <superproject>/.git/modules/<name> and --show-toplevel
# returns the submodule checkout. Governance assets (docs/, AGENTS.md,
# .agents/skills) live in the superproject, so resolve its root instead.
_super_modules = [
    p for p in COMMON_DIR.parents if p.name == "modules" and p.parent.name == ".git"
]
_resolve_root = _super_modules[0].parent.parent if _super_modules else ROOT
WORKSPACE_ROOT = Path(
    tm.ok(
        u.Cli.capture(
            ["git", "rev-parse", "--path-format=absolute", "--show-toplevel"],
            cwd=_resolve_root,
        )
    )
)


def test_prompt_skills_resolve_to_existing_paths() -> None:
    prompts = ROOT / ".github" / "prompts"
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


def test_governance_authority_sequence_matches_agents() -> None:
    agents = (WORKSPACE_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    governance = (WORKSPACE_ROOT / "docs" / "GOVERNANCE.md").read_text(encoding="utf-8")
    assert "USER REQUEST > BEADS" in agents
    assert "AIHUB-INVIOLABLE-LAW-PRELUDE" in agents
    assert "quality-gates skill" not in governance
    assert "flext-law" in governance or "AGENTS.md" in governance


def test_docs_validation_required_skills_exist_with_adr() -> None:
    config = json.loads(
        (
            WORKSPACE_ROOT / "docs" / "architecture" / "architecture_config.json"
        ).read_text(encoding="utf-8")
    )
    required = config["docs_validation"]["required_skills"]
    skills_root = WORKSPACE_ROOT / ".agents" / "skills"
    for name in required:
        skill = skills_root / name / "SKILL.md"
        assert skill.is_file(), name
        assert "adr" in skill.read_text(encoding="utf-8").lower(), name


def test_july_handoff_plans_are_marked_historical() -> None:
    plans = (
        WORKSPACE_ROOT
        / "docs"
        / "superpowers"
        / "plans"
        / "2026-07-29-flext-beads-governance-reorganization-handoff.md",
        WORKSPACE_ROOT
        / "docs"
        / "superpowers"
        / "plans"
        / "2026-07-29-flext-governance-beads-execution-continuation.md",
    )
    for plan in plans:
        text = plan.read_text(encoding="utf-8")
        assert "HISTORICAL / SUPERSEDED" in text


def test_markdownlint_does_not_suppress_strict_rules() -> None:
    config = json.loads((ROOT / ".markdownlint.json").read_text(encoding="utf-8"))
    assert config.get("MD012") is not False
    assert config.get("MD050") is not False
    assert config.get("MD064") is not False
    assert config.get("MD075") is not False
    assert config["MD013"]["line_length"] <= 500
