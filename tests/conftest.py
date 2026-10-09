"""Test configuration for flext-infra.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import importlib
import sys
import tempfile
from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, infra, p
from tests import c, t, u

# NOTE(flext-p68a.9.4, agent codex): the installed flext-tests pytest11 plugin is
# the only fixture owner; conftest must not re-export or shadow its fixtures.
pytest_plugins = ["tests.unit.fixtures", "tests.unit.fixtures_git"]

_TRACKED_CODEGEN_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent
    / c.Infra.CODEGEN_CONFIG_DIR
    / c.Infra.CODEGEN_CONFIG_FILENAME
)
_SESSION_ISOLATION = pytest.StashKey[ExitStack]()
_TRACKED_CODEGEN_CONFIG_BYTES = pytest.StashKey[bytes]()


@pytest.fixture
def rope_workspace(tmp_path: Path) -> Iterator[p.Infra.RopeWorkspaceDsl]:
    """Provide one real Rope workspace through the public composition root.

    Yields:
        Each ``p.Infra.RopeWorkspaceDsl``.

    """
    with infra.rope_workspace(tmp_path) as workspace:
        yield workspace


def pytest_sessionstart(session: pytest.Session) -> None:
    """Isolate the suite's FLEXT caches and snapshot the tracked codegen config.

    Gates resolve their persistent caches (codemod rule catalogs, Mypy) below
    ``XDG_CACHE_HOME``; a unit test writes only inside session-owned storage,
    so the session scopes that home to one temporary directory per worker and
    restores the environment on exit.

    Root cause (flext-eles2): dependency-floor rewrite tests exercised the
    public ``--rewrite-constraints`` entry point through workspaces that never
    declared their own governed SSOT, so the floor writer fell back to the
    packaged/installed ``flext_infra`` config directory — this very checkout
    in an editable install — and silently flipped floors in the real tracked
    file. The floor writer now resolves its target from the modernizer's own
    ``repository_root`` and every workspace fixture declares its own isolated
    ``config/codegen.yaml``; the session snapshot lets
    ``pytest_sessionfinish`` prove the real file stays untouched by the whole
    suite, current and future.
    """
    spec = config.Infra.codegen.make.codemod_rules_cache
    isolation = ExitStack()
    cache_home = isolation.enter_context(
        tempfile.TemporaryDirectory(prefix="xdg-cache-"),
    )
    isolation.enter_context(
        u.Tests.env_vars_context({
            spec.data_home_environment_variable: cache_home,
        }),
    )
    session.stash[_SESSION_ISOLATION] = isolation
    session.stash[_TRACKED_CODEGEN_CONFIG_BYTES] = (
        _TRACKED_CODEGEN_CONFIG_PATH.read_bytes()
    )


def pytest_sessionfinish(session: pytest.Session) -> None:
    """Restore the cache environment and fail loud on a tracked config write."""
    session.stash[_SESSION_ISOLATION].close()
    if (
        _TRACKED_CODEGEN_CONFIG_PATH.read_bytes()
        != session.stash[_TRACKED_CODEGEN_CONFIG_BYTES]
    ):
        pytest.exit(
            "test suite modified the tracked repository file "
            f"{_TRACKED_CODEGEN_CONFIG_PATH}; dependency-floor and codegen "
            "writers must target an isolated workspace, never the real "
            "checkout (flext-eles2)",
            returncode=pytest.ExitCode.TESTS_FAILED,
        )


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Resolve native-engine and provisioning applicability before fixtures execute.

    Raises:
        ValueError: If requires_engine arguments must be canonical engine names.
    """
    policy = config.Infra.codegen.make.ci
    if u.Infra.env_value(policy.variable).strip() != policy.value:
        return
    excluded_fixtures = frozenset(
        config.Infra.tooling.tools.pytest.ci_excluded_fixtures,
    )
    excluded_engines = frozenset(policy.local_check_gates)
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        engines = tuple(
            engine
            for marker in item.iter_markers("requires_engine")
            for engine in marker.args
        )
        if any(not isinstance(engine, str) for engine in engines):
            msg = "requires_engine arguments must be canonical engine names"
            raise ValueError(msg)
        fixtures = tuple(item.fixturenames) if isinstance(item, pytest.Function) else ()
        target = (
            deselected
            if excluded_engines.intersection(engines)
            or excluded_fixtures.intersection(fixtures)
            else selected
        )
        target.append(item)
    if deselected:
        deselected[0].config.hook.pytest_deselected(items=deselected)
    items[:] = selected


@pytest.fixture
def installed_dependency_path(tmp_path: Path) -> Iterator[Path]:
    """Expose real non-src package files through the selected import environment.

    Yields:
        Each ``Path``.

    """
    location = tmp_path / "installed"
    location.mkdir()
    sys.path.insert(0, str(location))
    importlib.invalidate_caches()
    try:
        yield location
    finally:
        sys.path.remove(str(location))
        importlib.invalidate_caches()


@pytest.fixture
def infra_test_workspace(tmp_path: Path) -> Path:
    """Create a minimal typed project workspace for public service tests.

    Returns:
        The resulting ``Path``.

    """
    workspace = tmp_path / "workspace"
    src_pkg = workspace / "src" / "infra_pkg"
    src_pkg.mkdir(parents=True, exist_ok=True)
    (workspace / "pyproject.toml").write_text(
        "[project]\nname='infra-pkg'\nversion='0.0.0'\n",
        encoding="utf-8",
    )
    (workspace / "Makefile").write_text("help:\n\t@pwd\n", encoding="utf-8")
    (src_pkg / "__init__.py").write_text("", encoding="utf-8")
    return workspace


@pytest.fixture
def infra_subprocess() -> p.Cli.CommandRunner:
    """Provide the public CLI utility facade for subprocess tests.

    Returns:
        The public command runner implemented by ``u.Cli``.

    """
    return u.Cli()


@pytest.fixture
def infra_toml() -> u.Cli:
    """Provide the public CLI utility facade for TOML tests.

    Returns:
        The declaring CLI utility class exposed through ``u.Cli``.

    """
    return u.Cli()


@pytest.fixture
def infra_git() -> u.Infra:
    """Provide the public infrastructure utility facade for Git tests.

    Returns:
        The resulting ``u.Infra``.

    """
    return u.Infra()


@pytest.fixture
def infra_io() -> u.Infra:
    """Provide the public infrastructure utility facade for I/O tests.

    Returns:
        The resulting ``u.Infra``.

    """
    return u.Infra()


@pytest.fixture
def infra_path() -> u.Infra:
    """Provide the public infrastructure utility facade for path tests.

    Returns:
        The resulting ``u.Infra``.

    """
    return u.Infra()


@pytest.fixture
def infra_patterns() -> u.Infra:
    """Provide the public infrastructure utility facade for pattern tests.

    Returns:
        The resulting ``u.Infra``.

    """
    return u.Infra()


@pytest.fixture
def infra_selection() -> u.Infra:
    """Provide the public infrastructure utility facade for selection tests.

    Returns:
        The resulting ``u.Infra``.

    """
    return u.Infra()


@pytest.fixture
def infra_safe_command_output(
    infra_subprocess: p.Cli.CommandRunner,
    infra_test_workspace: Path,
) -> str:
    """Capture successful public command output inside the test workspace.

    Returns:
        The resulting ``str``.

    """
    echo_result = infra_subprocess.capture(
        ["echo", "infra-ok"],
        cwd=infra_test_workspace,
    )
    tm.ok(echo_result)
    pwd_result = infra_subprocess.capture(["pwd"], cwd=infra_test_workspace)
    tm.ok(pwd_result)
    return f"{echo_result.value.strip()}|{pwd_result.value.strip()}"


@pytest.fixture
def infra_git_repo(infra_test_workspace: Path) -> Path:
    """Provide a provider-governed clone whose upstream is a local bare repo.

    Conformance reads this repository twice and both reads must agree. Detection
    only accepts a remote whose host and organization match the provider, while
    integration-branch discovery reads the already materialized tracking ref.
    Declaring the real upstream URL satisfies detection but grades the fixture
    against the live repository; declaring a local path fails detection outright.
    The fixture therefore declares the provider URL and rewrites it to a local
    bare origin through Git's own ``url.<base>.insteadOf`` mechanism. Fixture
    setup materializes the tracking ref once; conformance itself stays offline.

    Returns:
        The resulting ``Path``.

    """
    repo = infra_test_workspace / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    # The governed tree above the clone carries the committed Taplo pin.
    u.Tests.seed_locked_taplo(infra_test_workspace.parent)
    baseline_file = repo / ".infra-baseline"
    baseline_file.write_text("baseline\n", encoding="utf-8")
    u.Tests.write_project_beads_config(repo, config.Infra.name)
    upstream = u.Tests.repository_ref(config.Infra.name).url
    origin = infra_test_workspace / "origin.git"
    origin.mkdir(parents=True, exist_ok=True)
    u.Tests.git_bootstrap(origin, ("init", "--bare"))
    u.Tests.initialize_git_repo(repo, origin_url=upstream)
    u.Tests.git_bootstrap(
        repo,
        ("config", "--local", f"url.{origin}.insteadOf", upstream),
    )
    u.Tests.git_bootstrap(
        repo,
        (
            "push",
            "-q",
            c.Infra.GIT_ORIGIN,
            f"HEAD:refs/heads/{u.Tests.provider_branch()}",
        ),
    )
    u.Tests.git_bootstrap(
        repo,
        (
            "fetch",
            "-q",
            c.Infra.GIT_ORIGIN,
            (
                f"+refs/heads/{u.Tests.provider_branch()}:refs/remotes/origin/"
                f"{u.Tests.provider_branch()}"
            ),
        ),
    )
    return repo


@pytest.fixture
def rope_project(tmp_path: Path) -> Iterator[t.Infra.RopeProject]:
    """Shared minimal rope project for refactor unit tests.

    Yields:
        Each ``t.Infra.RopeProject``.

    """
    project = u.Infra.init_rope_project(tmp_path)
    yield project
    project.close()
