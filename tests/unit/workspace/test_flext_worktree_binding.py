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

from flext_core import p as core_p
from flext_infra import u
from flext_infra.workspace.flext_binding import FlextInfraFlextBindingService
from flext_tests import tm


def _consumer(tmp_path: Path) -> Path:
    """Return an external consumer declaring flext packages by pinned git URL."""
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / "pyproject.toml").write_text(
        "[project]\n"
        'name = "consumer"\n'
        'version = "0.1.0"\n'
        'requires-python = ">=3.13"\n'
        "dependencies = [\n"
        '  "flext-core @ git+https://github.com/flext-sh/flext-core.git@0.12.0-dev",\n'
        '  "flext-cli @ git+https://github.com/flext-sh/flext-cli.git@0.12.0-dev",\n'
        '  "httpx>=0.27",\n'
        "]\n",
        encoding="utf-8",
    )
    return consumer


def _flext_workspace(tmp_path: Path) -> Path:
    """Return a self-contained flext workspace supplying flext-core and flext-cli.

    Built here rather than pointed at a real checkout so the test states its own
    premise: the rebind set is the intersection of what the consumer declares
    with what the worktree PROVIDES, and only a fixture that owns both sides can
    prove the intersection rather than inherit it from one machine's disk.
    """
    flext_root = tmp_path / "flext"
    (flext_root / "config").mkdir(parents=True)
    members = "\n".join(
        f'  - {{name: "{name}", distribution: "{name}", provider: "flext-sh", '
        f'url: "https://github.com/flext-sh/{name}.git", path: "{name}", '
        'role: "workspace-member", state: "active", checkout: submodule, '
        "codegen: conform, package: true, editable: true, read_only: false}"
        for name in ("flext-core", "flext-cli")
    )
    (flext_root / "config" / "workspace.yaml").write_text(
        "version: 3\n"
        "name: flext\n"
        "repository:\n"
        '  name: flext\n  distribution: flext\n  provider: "flext-sh"\n'
        '  url: "https://github.com/flext-sh/flext.git"\n  path: "."\n'
        '  role: "workspace-root"\n  state: "active"\n  checkout: root\n'
        "  codegen: conform\n  package: false\n  editable: false\n"
        "  read_only: false\n"
        # Every key the workspace schema requires of `project`; a partial block
        # fails validation, and validation is what proves the fixture is a real
        # workspace rather than a shape that merely looks like one.
        "project:\n"
        '  package_name: "flext"\n'
        '  class_stem: "Flext"\n'
        '  namespace: "Flext"\n'
        '  constant_name: "flext"\n'
        '  namespace_attribute: "flext"\n'
        '  alias: "flext"\n'
        '  environment_prefix: "FLEXT_"\n'
        '  description: "Test workspace fixture"\n'
        '  version: "0.12.0"\n'
        '  license: "MIT"\n'
        '  author_name: "FLEXT Team"\n'
        '  author_email: "team@flext.sh"\n'
        '  upstream: "flext_core"\n'
        '  homepage: "https://github.com/flext-sh/flext"\n'
        '  documentation: "https://docs.flext.sh"\n'
        '  workspace_root_rel: "."\n'
        "  year: 2026\n"
        f"members:\n{members}\n",
        encoding="utf-8",
    )
    # A governed member must be a real Git checkout: the detector rejects a
    # member that is neither in .gitmodules nor a live repository, which is
    # exactly the guard that keeps a half-provisioned tree from validating.
    for name in ("flext-core", "flext-cli"):
        member = flext_root / name
        member.mkdir()
        tm.ok(u.Cli.run_checked(["git", "init", "-q"], cwd=member))
    return flext_root


class TestsFlextWorktreeBinding:
    """The service resolves which distributions a worktree can supply."""

    def test_binding_targets_only_the_flext_packages_the_consumer_declares(
        self, tmp_path: Path
    ) -> None:
        """Only declared flext deps present in the worktree are rebound."""
        consumer = _consumer(tmp_path)

        planned: core_p.Result[tuple[str, ...]] = (
            FlextInfraFlextBindingService.plan_targets(
                consumer_root=consumer, flext_root=_flext_workspace(tmp_path)
            )
        )

        names = tm.ok(planned)
        tm.that(sorted(names), eq=["flext-cli", "flext-core"])

    def test_binding_rejects_a_path_that_is_not_a_flext_workspace(
        self, tmp_path: Path
    ) -> None:
        """A non-workspace path fails closed instead of silently binding nothing."""
        consumer = _consumer(tmp_path)
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
            consumer_root=consumer, flext_root=_flext_workspace(tmp_path)
        )

        tm.that(tm.ok(planned), eq=())


__all__: tuple[str, ...] = ()
