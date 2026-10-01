"""Contract test for the compose_per_file_ignores calling shapes.

The method is consumed through two boundaries — instance dispatch from
apply_payload and a constructed-instance call from the conform context
render — and #1075 left the parameter list without a binding slot, breaking
every caller (and with them the whole gen pipeline). This pins the public
signature both ways.
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import config
from flext_infra.deps.phases.ensure_ruff import FlextInfraEnsureRuffConfigPhase


class TestsFlextInfraRuffComposeSignature:
    """Both call shapes bind project_dir positionally and compose a mapping."""

    def test_instance_dispatch_composes_the_exemption_map(self, tmp_path: Path) -> None:
        """apply_payload's self-dispatch shape works with one positional."""
        phase = FlextInfraEnsureRuffConfigPhase(config.Infra.tooling)
        composed = phase.compose_per_file_ignores(tmp_path)
        tm.that(composed, eq=dict(composed))

    def test_constructed_call_composes_the_exemption_map(self, tmp_path: Path) -> None:
        """The conform context render's shape works with one positional."""
        composed = FlextInfraEnsureRuffConfigPhase(
            config.Infra.tooling,
        ).compose_per_file_ignores(tmp_path, managed_artifacts=None)
        tm.that(isinstance(composed, dict), eq=True)
