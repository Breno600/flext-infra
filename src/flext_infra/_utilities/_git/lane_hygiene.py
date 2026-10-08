"""Native facts for the single Git lane evaluator, never a second hygiene gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra import config, m, p, r
from flext_infra._utilities import FlextInfraUtilitiesGitSemanticRefsMixin


class FlextInfraUtilitiesGitLaneHygieneMixin:
    """Collect observations through canonical primitives without policy decisions."""

    @staticmethod
    def git_lane_facts(
        request: m.Infra.GitRepoRequest,
    ) -> p.Result[m.Infra.GitLaneFacts]:
        """Capture stash OIDs and every local/configured-remote reference.

        There is no integration-base election, ancestry test, ownership judgement,
        temporary-directory heuristic, exemption, remediation or writable effect.
        Read errors remain explicit alongside successful observations; only the
        service evaluator decides the verdict from those facts.

        Returns:
            Partial or complete native facts with all causal read errors retained.

        """
        errors: list[str] = []
        refs: list[m.Infra.GitLaneRef] = []
        stash_oids: tuple[str, ...] = ()
        stashes = FlextInfraUtilitiesGitSemanticRefsMixin.git_stash_oids(request)
        if stashes.failure:
            errors.append(f"stash read error: {stashes.error}")
        else:
            stash_oids = tuple(stashes.value.oids)
        remote = config.Infra.codegen.branch_policy.lane_remote
        for namespace in ("refs/heads", f"refs/remotes/{remote}"):
            heads = FlextInfraUtilitiesGitSemanticRefsMixin.git_ref_heads(
                m.Infra.GitRefHeadsRequest(
                    repo_root=request.repo_root,
                    namespace=namespace,
                )
            )
            if heads.failure:
                errors.append(f"ref read error: {namespace}: {heads.error}")
                continue
            refs.extend(
                m.Infra.GitLaneRef(name=f"{namespace}/{name}", oid=oid)
                for name, oid in heads.value.heads.items()
            )
        return r[m.Infra.GitLaneFacts].ok(
            m.Infra.GitLaneFacts(
                repo_root=request.repo_root,
                stash_oids=stash_oids,
                refs=tuple(refs),
                read_errors=tuple(errors),
            )
        )


__all__: list[str] = ["FlextInfraUtilitiesGitLaneHygieneMixin"]
