"""Public Git utilities facet for ``u.Infra`` (composed into utilities MRO).

Private GitPython parts live under ``_utilities/_git/``. Consumers use
``from flext_infra import u`` only — never import this module or ``_git``.
"""

from __future__ import annotations

from flext_infra._utilities._git.scope import FlextInfraUtilitiesGitScopeMixin


class FlextInfraUtilitiesGit(FlextInfraUtilitiesGitScopeMixin):
    """Canonical Git owner for flext-infra: scope + worktree + checkpoint/patch."""


__all__: list[str] = ["FlextInfraUtilitiesGit"]
