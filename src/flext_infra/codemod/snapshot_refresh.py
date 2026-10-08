"""Explicit regeneration of the owned ast-grep rule-test snapshots.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import override

from flext_cli import cli

from flext_infra import p, r, t, u
from flext_infra.base import FlextInfraServiceBase
from flext_infra.codemod.batch_gates import FlextInfraModGateEngine


class FlextInfraCodemodSnapshotRefresh(FlextInfraServiceBase[t.Cli.ResultValue]):
    """Regenerate governed rule-test snapshots so each change is a reviewed commit.

    ``make mod`` only verifies committed snapshots, so a rule whose output
    changed fails there instead of rewriting its own expectation. This service,
    reached through ``make mod-snapshots``, rebuilds every owned snapshot from
    its rule tests and reports each created, updated or removed file; a dry run
    fails while any projection differs.
    """

    @override
    def execute(self) -> p.Result[t.Cli.ResultValue]:
        """Rebuild or preview the owned snapshot projections.

        Returns:
            The resulting ``p.Result[t.Cli.ResultValue]``.

        """
        planned = u.Infra.codemod_rule_plan(self.repository_root)
        if planned.failure:
            return r[t.Cli.ResultValue].from_failure(planned)
        rules = tuple(dict.fromkeys(rule.resource for rule in planned.value.rules))
        refreshed = FlextInfraModGateEngine.refresh_rule_snapshots(
            self.repository_root,
            rules,
            apply=not self.effective_dry_run,
        )
        if refreshed.failure:
            return r[t.Cli.ResultValue].from_failure(refreshed)
        for change in refreshed.value:
            cli.display_text(f"mod-snapshots: {change}")
        if self.effective_dry_run and refreshed.value:
            return r[t.Cli.ResultValue].fail(
                f"{len(refreshed.value)} ast-grep snapshot projection(s) differ "
                "from their rule tests",
            )
        cli.display_text(
            f"mod-snapshots: {len(refreshed.value)} snapshot projection(s) "
            "changed; review the diff and commit it",
        )
        return r[t.Cli.ResultValue].ok(value=True)


__all__: list[str] = ["FlextInfraCodemodSnapshotRefresh"]
