"""Deterministic projection lock emitted beside the lazy-init projections.

``.agents/projections.lock.json`` (v1) is derived entirely from the composed
lazy-init file plans: one entry per projected ``.agents``/``.codex`` file with
its sha256 digest and byte length, ordered by path. Being just another plan
entry, the conform fixed-point gate owns its convergence, and workspace
consumers gain the machine-checkable contract their post-generation
projection synchronization verifies. The path deliberately avoids the
ai-hub-owned ``.agents/projection.json`` (the projection INPUT manifest);
this file is the projected OUTPUT state, owned by the generator alone.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import hashlib
from collections.abc import MutableMapping
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t, u

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenLazyInitProjectionManifest:
    """Derive the per-project projection manifest from composed file plans."""

    @staticmethod
    def projection_manifest_plans(
        *,
        files: t.VariadicTuple[m.Infra.CodegenFilePlan],
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]:
        """Append one manifest plan per project that owns projected files.

        Entries derive only from the other plans' desired states, so the
        manifest bytes are a pure function of the phase plan: stable order,
        stable digests, no self-reference.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]``.

        """
        projected: MutableMapping[Path, list[t.JsonDict]] = {}
        for plan in files:
            if plan.desired_content is None:
                continue
            relative = plan.path.relative_to(plan.project)
            if relative.parts[0] not in c.Infra.PROJECTED_ROOTS:
                continue
            if relative.name == c.Infra.MANIFEST_FILENAME:
                continue
            projected.setdefault(plan.project, []).append({
                "path": relative.as_posix(),
                "sha256": hashlib.sha256(plan.desired_content).hexdigest(),
                "bytes": len(plan.desired_content),
            })
        plans: t.MutableSequenceOf[m.Infra.CodegenFilePlan] = []
        for project in sorted(projected):
            payload: t.JsonDict = {
                "apiVersion": c.Infra.MANIFEST_API_VERSION,
                "entries": [
                    {
                        "path": entry["path"],
                        "sha256": entry["sha256"],
                        "bytes": entry["bytes"],
                    }
                    for entry in sorted(projected[project], key=itemgetter("path"))
                ],
            }
            serialized = u.Cli.json_dumps(payload, indent=2)
            if serialized.failure:
                return r[t.VariadicTuple[m.Infra.CodegenFilePlan]].from_failure(
                    serialized,
                )
            content = f"{serialized.value}\n".encode(c.Cli.ENCODING_DEFAULT)
            manifest_path = project / ".agents" / c.Infra.MANIFEST_FILENAME
            state = u.Cli.atomic_read_binary_file_state(manifest_path, required=False)
            if state.failure:
                return r[t.VariadicTuple[m.Infra.CodegenFilePlan]].from_failure(state)
            plans.append(
                m.Infra.CodegenFilePlan(
                    project=project,
                    path=manifest_path,
                    before=state.value,
                    desired_content=content,
                    desired_mode=0o644,
                ),
            )
        return r[t.VariadicTuple[m.Infra.CodegenFilePlan]].ok(tuple(plans))


__all__: tuple[str, ...] = ("FlextInfraCodegenLazyInitProjectionManifest",)
