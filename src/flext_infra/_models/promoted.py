"""Promoted-command domain models for flext-infra.

``PromotedParam``/``PromotedCommand``/``PromotedAliasTarget`` mirror the frozen
promoted-command contract; ``PromotedWorkspaceSpec`` is the typed
projection of repository facts the framework consumes. Construction is
keyword-only; leaf code annotates with the ``p.Infra.Promoted*`` protocols
(a model is never a type).

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_cli import m

from flext_infra import t
from flext_infra._models import FlextInfraModelsBase


class FlextInfraModelsPromoted(FlextInfraModelsBase):
    """Promoted-command models mixed into ``m.Infra``."""

    """flext-command registry models (promoted script headers)."""

    class PromotedParam(m.BaseModel):
        """One promoted command parameter declared in the script header."""

        model_config = m.ConfigDict(extra="forbid", frozen=True)

        name: str
        help: str
        required: bool = False
        default: str = ""
        choices: t.VariadicTuple[str] = ()

    class PromotedCommand(m.BaseModel):
        """One promoted command discovered from a flext-command header."""

        model_config = m.ConfigDict(extra="forbid", frozen=True)

        verb: str
        what: str
        domain: str
        summary: str
        description: str
        example: str
        path: Path
        mutates: bool
        aliases: t.VariadicTuple[str]
        params: t.VariadicTuple[FlextInfraModelsPromoted.PromotedParam]
        rules: t.VariadicTuple[str]

    class PromotedAliasTarget(m.BaseModel):
        """Resolved command alias target."""

        model_config = m.ConfigDict(extra="forbid", frozen=True)

        verb: str
        what: str

    class PromotedWorkspaceSpec(m.BaseModel):
        """Repository facts the promoted framework consumes, resolved once."""

        model_config = m.ConfigDict(extra="forbid", frozen=True)

        root: Path
        scripts: Path
        local_python: Path
        submodule_script_roots: t.VariadicTuple[Path] = ()
        consumer_scripts_root: Path | None = None


__all__: list[str] = ["FlextInfraModelsPromoted"]
