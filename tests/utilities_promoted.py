"""Promoted-command test utilities for flext-infra."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests import m, t

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraUtilitiesPromotedMixin:
    """Promoted-command builders shared by the promoted test modules.

    The builder is declared here, not beside one test, because two promoted
    test modules construct the same command and a module-level builder is a
    second owner the namespace contract forbids. ``params`` is typed as the
    model tuple the ``Command`` field actually declares; typing it as the
    protocol made every call a type error while still running.
    """

    @staticmethod
    def promoted_command(
        *,
        path: Path,
        mutates: bool = True,
        params: t.VariadicTuple[m.Infra.PromotedParam] = (),
        verb: str = "probe",
        what: str = "all",
    ) -> m.Infra.PromotedCommand:
        """Build one real promoted command model for contract tests."""
        return m.Infra.PromotedCommand(
            verb=verb,
            what=what,
            domain="probe",
            summary="probe",
            description="probe",
            example=f"make {verb} WHAT={what}",
            path=path,
            mutates=mutates,
            aliases=(),
            params=params,
            rules=(),
        )


__all__: list[str] = ["TestsFlextInfraUtilitiesPromotedMixin"]
