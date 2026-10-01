"""Loader for declarative Rope shape rules (ADR-014, one YAML file per rule)."""

from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_infra import c, m, p, r, t
from flext_infra.base import FlextInfraServiceBase

if TYPE_CHECKING:
    from collections.abc import Iterator


class FlextInfraRopeRuleLoaderService(FlextInfraServiceBase[t.Cli.ResultValue]):
    """Load and validate ``codemod/rope_rules/**.yml`` into typed models."""

    @override
    def execute(self) -> p.Result[t.Cli.ResultValue]:
        """Load every declared Rope rule shipped with the engine package."""
        loaded = self.load_rules()
        if loaded.failure:
            return r[t.Cli.ResultValue].from_failure(loaded)
        return r.ok(True)

    @classmethod
    def load_rules(cls) -> p.Result[t.SequenceOf[m.Infra.RopeRule]]:
        """Parse each rule file once at the boundary; fail loud on any defect."""
        from flext_infra import u

        rule_files = sorted(cls._rule_files())
        if not rule_files:
            return r.fail("no declarative rope rules found in the engine package")
        rules: list[m.Infra.RopeRule] = []
        for rule_file in rule_files:
            parsed = u.Cli.yaml_safe_load(rule_file)
            if parsed.failure:
                return r.fail(f"rule file {rule_file.name}: {parsed.error}")
            rules.append(m.Infra.RopeRule.model_validate(parsed.value))
        return r.ok(tuple(rules))

    @classmethod
    def _rule_files(cls) -> Iterator[Path]:
        """Yield every ``*.yml`` rule file shipped under ``codemod/rope_rules``."""
        spec = find_spec("flext_infra")
        roots = (
            tuple(Path(path) for path in (spec.submodule_search_locations or ()))
            if spec is not None
            else ()
        )
        for package_root in roots:
            rules_dir = package_root / c.Infra.CODEMOD_RESOURCE_DIRNAME / "rope_rules"
            if rules_dir.is_dir():
                yield from rules_dir.rglob("*.yml")


__all__: list[str] = ["FlextInfraRopeRuleLoaderService"]
