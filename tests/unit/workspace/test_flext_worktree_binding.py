"""``FLEXT=<worktree>`` rebinds an external consumer onto one flext checkout.

An external project declares flext packages by pinned git URL, so it validates
PUBLISHED code and never the checkout being worked on. Reviewing a cross-project
change then required publishing first, which is backwards.

The binding is a SESSION override, not a declaration: the consumer's
``pyproject.toml`` keeps its pins untouched, so nothing local is ever committed
and dropping the flag restores the pinned resolution. Which distributions get
rebound is derived from the worktree's own manifest, never a hardcoded list.
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_core import p as core_p
from flext_infra.workspace.flext_binding import FlextInfraFlextBindingService
from tests import t, u


class TestsFlextInfraWorktreeBinding:
    """The service resolves which distributions a worktree can supply."""

    @staticmethod
    def _consumer(tmp_path: Path) -> Path:
        """Return an external consumer declaring flext packages by pinned git URL."""
        provider = u.Tests.provider()
        consumer = tmp_path / "consumer"
        consumer.mkdir()
        (consumer / "pyproject.toml").write_text(
            "[project]\n"
            'name = "consumer"\n'
            'version = "0.1.0"\n'
            'requires-python = ">=3.13"\n'
            "dependencies = [\n"
            f'  "flext-core @ git+{provider.base_url.rstrip("/")}/flext-core.git@'
            f'{u.Tests.provider_branch()}",\n'
            f'  "flext-cli @ git+{provider.base_url.rstrip("/")}/flext-cli.git@'
            f'{u.Tests.provider_branch()}",\n'
            '  "httpx>=0.27",\n'
            "]\n",
            encoding="utf-8",
        )
        return consumer

    @staticmethod
    def _flext_workspace(tmp_path: Path) -> Path:
        """Return a self-contained flext workspace supplying flext-core and flext-cli.

        Built here rather than pointed at a real checkout so the test states its
        own premise: the rebind set is the intersection of what the consumer
        declares with what the worktree PROVIDES, and only a fixture that owns
        both sides can prove the intersection rather than inherit it from one
        machine's disk.
        """
        flext_root = tmp_path / "flext"
        u.Tests.WorktreeFixture.initialize_governed_project(
            flext_root,
            "flext",
            workspace="flext",
            database="flext",
            issue_prefix="flext",
        )
        for name in ("flext-core", "flext-cli"):
            u.Tests.WorktreeFixture.initialize_governed_project(
                flext_root / name,
                name,
                workspace=name,
                database=name,
                issue_prefix=name,
                beads_owner=False,
            )
            u.Tests.WorktreeFixture.link_member_beads(
                flext_root / name,
                flext_root,
                workspace_name="flext",
                database="flext",
                issue_prefix="flext",
            )
        u.Tests.WorktreeFixture.write_gitmodules(
            flext_root, ("flext-core", "flext-cli")
        )
        return flext_root

    def test_binding_targets_only_the_flext_packages_the_consumer_declares(
        self, tmp_path: Path
    ) -> None:
        """Only declared flext deps present in the worktree are rebound."""
        consumer = self._consumer(tmp_path)

        planned: core_p.Result[t.VariadicTuple[str]] = (
            FlextInfraFlextBindingService.plan_targets(
                consumer_root=consumer, flext_root=self._flext_workspace(tmp_path)
            )
        )

        names = tm.ok(planned)
        tm.that(sorted(names), eq=["flext-cli", "flext-core"])

    def test_binding_rejects_a_path_that_is_not_a_flext_workspace(
        self, tmp_path: Path
    ) -> None:
        """A non-workspace path fails closed instead of silently binding nothing."""
        consumer = self._consumer(tmp_path)
        not_flext = tmp_path / "elsewhere"
        not_flext.mkdir()

        planned = FlextInfraFlextBindingService.plan_targets(
            consumer_root=consumer, flext_root=not_flext
        )

        tm.that(planned.failure, eq=True)
        tm.that(planned.error or "", has="workspace")

    def test_a_consumer_without_flext_dependencies_binds_nothing(
        self, tmp_path: Path
    ) -> None:
        """No flext dependency means no rebind, not an error."""
        consumer = tmp_path / "plain"
        consumer.mkdir()
        (consumer / "pyproject.toml").write_text(
            '[project]\nname = "plain"\nversion = "0.1.0"\n'
            'requires-python = ">=3.13"\ndependencies = ["httpx>=0.27"]\n',
            encoding="utf-8",
        )

        planned = FlextInfraFlextBindingService.plan_targets(
            consumer_root=consumer, flext_root=self._flext_workspace(tmp_path)
        )

        tm.that(tm.ok(planned), eq=())
