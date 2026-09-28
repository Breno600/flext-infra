"""Consolidation phase tests for deps modernizer."""

from __future__ import annotations

from flext_tests import tm

from flext_infra import FlextInfraConsolidateGroupsPhase, c
from tests import t, u


class TestsFlextInfraDepsModernizerConsolidate:
    """Legacy optional and Poetry groups converge into one canonical dev group."""

    @staticmethod
    def _consolidated(
        source: str, canonical_dev: t.StrSequence = ()
    ) -> t.Pair[t.JsonMapping, t.StrSequence]:
        """Consolidate one payload twice; return the payload and first changes."""
        payload = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python(
            u.Tests.toml_payload(source)
        )
        phase = FlextInfraConsolidateGroupsPhase()
        changes = phase.apply_payload(payload, canonical_dev)
        tm.that(phase.apply_payload(payload, canonical_dev), empty=True)
        return payload, changes

    def test_missing_tables_create_dev_group_and_deptry_policy(self) -> None:
        """An empty payload gains the dev group and the deptry dev-group policy."""
        payload, changes = self._consolidated("")
        tm.that(changes, has="tool.deptry.pep621_dev_dependency_groups set to ['dev']")
        deptry = u.Tests.toml_mapping(u.Tests.toml_mapping(payload["tool"])["deptry"])
        tm.that(
            list(u.Tests.strings(deptry["pep621_dev_dependency_groups"])),
            eq=[str(c.Infra.DEV)],
        )

    def test_legacy_optional_groups_merge_into_dev(self) -> None:
        """Every legacy optional group merges into dev and is removed."""
        legacy = c.Infra.LEGACY_DEV_DEPENDENCY_GROUPS
        payload, changes = self._consolidated(
            "[project.optional-dependencies]\n"
            + "".join(f'{group} = ["requirement-{group}"]\n' for group in legacy),
            canonical_dev=("pytest",),
        )
        optional = u.Tests.toml_mapping(
            u.Tests.toml_mapping(payload["project"])["optional-dependencies"]
        )
        tm.that(set(optional), eq={str(c.Infra.DEV)})
        tm.that(
            set(u.Tests.strings(optional[str(c.Infra.DEV)])),
            eq={"pytest", *(f"requirement-{group}" for group in legacy)},
        )
        for group in legacy:
            tm.that(changes, has=f"project.optional-dependencies.{group} removed")

    def test_legacy_poetry_groups_merge_into_dev_dependencies(self) -> None:
        """Legacy Poetry group dependencies move under the dev group."""
        legacy_group = c.Infra.LEGACY_DEV_DEPENDENCY_GROUPS[0]
        payload, changes = self._consolidated(
            f"[tool.poetry.group.{legacy_group}.dependencies]\n"
            'legacy-requirement = "^1.0"\n'
        )
        groups = u.Tests.toml_mapping(
            u.Tests.toml_mapping(u.Tests.toml_mapping(payload["tool"])["poetry"])[
                "group"
            ]
        )
        tm.that(groups, lacks=str(legacy_group))
        tm.that(
            u.Tests.toml_mapping(
                u.Tests.toml_mapping(groups[str(c.Infra.DEV)])["dependencies"]
            ),
            eq={"legacy-requirement": "^1.0"},
        )
        tm.that(changes, has=f"tool.poetry.group.{legacy_group} removed")
