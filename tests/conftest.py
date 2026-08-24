"""Test configuration for flext-infra."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

import flext_infra as infra_pkg
from flext_infra import config
from flext_tests import tm
from tests import c, t, u

# NOTE(mro-p68a.9.4, agent codex): the installed flext-tests pytest11 plugin is
# the only fixture owner; conftest must not re-export or shadow its fixtures.
pytest_plugins = ["tests.unit.fixtures", "tests.unit.fixtures_git"]


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register the slow-timeout ini option consumed by the test suite.

    Why (root cause, rc0 plugin gap): the pyproject ``[tool.pytest.ini_options]``
    declares ``flext_slow_timeout_seconds`` (consumed by ``flext_tests``) and
    ``tests/unit/deps/test_modernizer_pytest`` reads it back through
    ``config.getini``. The installed ``flext-tests 0.12.0rc0`` entry-point does
    not register the option, so pytest aborts collection with
    ``Unknown config option`` before any test runs. This conftest owns its ini
    surface and declares the option here; a real plugin re-registering the same
    name is a no-op merge.
    """
    parser.addini(
        "flext_slow_timeout_seconds",
        help="Seconds after which a test is flagged slow (flext-tests option)",
    )


@pytest.fixture
def infra_public_root() -> Iterator[ModuleType]:
    """Reload the root public package after clearing lazy-export caches.

    Why (root cause, reload isolation): ``importlib.reload(flext_infra)``
    re-executes the package ``__init__``, which re-imports ``pathlib`` and
    binds a NEW ``Path`` class. Any ``Path`` instance created before the
    reload keeps the OLD class, whose private slots (``_str``/``_drv``) no
    longer match, so every later ``path.exists()`` on a pre-reload instance
    raises ``AttributeError`` — corrupting every test that runs after this
    fixture. The purge also drops the lazy-export registry the ``tests``
    package shares, so ``tests.u`` resolved to the infra facade without
    ``Tests``. Both module snapshots are restored after the fixture so the
    process-global interpreter state is left exactly as found.
    """
    stdlib_snapshots = {
        name: module
        for name, module in sys.modules.items()
        if name == "pathlib" or name.startswith("pathlib.")
    }
    wrapper_snapshots = {
        name: sys.modules.pop(name, None)
        for name in c.Tests.INFRA_PUBLIC_WRAPPER_MODULES
    }
    try:
        for export_name in c.Tests.INFRA_PUBLIC_ROOT_EXPORTS:
            _ = infra_pkg.__dict__.pop(export_name, None)
        yield importlib.reload(infra_pkg)
    finally:
        for name, module in stdlib_snapshots.items():
            sys.modules[name] = module
        for name, module in wrapper_snapshots.items():
            if module is not None:
                sys.modules[name] = module


def _is_collectable_test_module(collection_path: Path) -> bool:
    tests_root = Path(__file__).parent
    try:
        collection_path.relative_to(tests_root)
    except ValueError:
        return True

    file_name = collection_path.name
    if collection_path.suffix != ".py" or file_name == "conftest.py":
        return True

    return file_name.startswith("test_") or file_name.endswith("_tests.py")


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    """Collect only executable test modules from the canonical test tree."""
    del config
    if _is_collectable_test_module(collection_path):
        return None
    return True


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Deselect non-test facade modules that pytest plugins may discover."""
    kept_items: list[pytest.Item] = []
    deselected_items: list[pytest.Item] = []

    for item in items:
        if _is_collectable_test_module(Path(item.path)):
            # mro-wkii.4.15: settings identity is fixed at process startup.
            kept_items.append(item)
            continue
        deselected_items.append(item)

    if deselected_items:
        config.hook.pytest_deselected(items=deselected_items)
        items[:] = kept_items


@pytest.fixture
def infra_test_workspace(tmp_path: Path) -> Path:
    """Create a minimal typed project workspace for public service tests."""
    workspace = tmp_path / "workspace"
    src_pkg = workspace / "src" / "infra_pkg"
    src_pkg.mkdir(parents=True, exist_ok=True)
    (workspace / "pyproject.toml").write_text(
        "[project]\nname='infra-pkg'\nversion='0.0.0'\n", encoding="utf-8"
    )
    (workspace / "Makefile").write_text("help:\n\t@pwd\n", encoding="utf-8")
    (src_pkg / "__init__.py").write_text("", encoding="utf-8")
    return workspace


@pytest.fixture
def infra_subprocess() -> u.Cli:
    """Provide the public CLI utility facade for subprocess tests."""
    return u.Cli()


@pytest.fixture
def infra_toml() -> u.Cli:
    """Provide the public CLI utility facade for TOML tests."""
    return u.Cli()


@pytest.fixture
def infra_git() -> u.Infra:
    """Provide the public infrastructure utility facade for Git tests."""
    return u.Infra()


@pytest.fixture
def infra_io() -> u.Infra:
    """Provide the public infrastructure utility facade for I/O tests."""
    return u.Infra()


@pytest.fixture
def infra_path() -> u.Infra:
    """Provide the public infrastructure utility facade for path tests."""
    return u.Infra()


@pytest.fixture
def infra_patterns() -> u.Infra:
    """Provide the public infrastructure utility facade for pattern tests."""
    return u.Infra()


@pytest.fixture
def infra_selection() -> u.Infra:
    """Provide the public infrastructure utility facade for selection tests."""
    return u.Infra()


@pytest.fixture
def infra_reporting() -> u.Infra:
    """Provide the public infrastructure utility facade for reporting tests."""
    return u.Infra()


@pytest.fixture
def infra_safe_command_output(
    infra_subprocess: u.Cli, infra_test_workspace: Path
) -> str:
    """Capture successful public command output inside the test workspace."""
    echo_result = infra_subprocess.capture(
        ["echo", "infra-ok"], cwd=infra_test_workspace
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
    baseline ancestry resolves the provider branch by fetching that same remote.
    Declaring the real upstream URL satisfies detection but grades the fixture
    against the live repository; declaring a local path fails detection outright.
    The fixture therefore declares the provider URL and rewrites it to a local
    bare origin through Git's own ``url.<base>.insteadOf`` mechanism, so the two
    reads observe one self-consistent topology without any network access.
    """
    repo = infra_test_workspace / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    baseline_file = repo / ".infra-baseline"
    baseline_file.write_text("baseline\n", encoding="utf-8")
    provider = config.Infra.codegen.providers[0]
    upstream = u.Tests.repository_ref(config.Infra.name).url
    origin = infra_test_workspace / "origin.git"
    origin.mkdir(parents=True, exist_ok=True)
    u.Tests.git_bootstrap(origin, ("init", "--bare"))
    u.Tests.initialize_git_repo(repo, origin_url=upstream)
    u.Tests.git_bootstrap(
        repo, ("config", "--local", f"url.{origin}.insteadOf", upstream)
    )
    u.Tests.git_bootstrap(
        repo, ("push", "-q", c.Infra.GIT_ORIGIN, f"HEAD:refs/heads/{provider.branch}")
    )
    u.Tests.git_bootstrap(
        repo,
        (
            "fetch",
            "-q",
            c.Infra.GIT_ORIGIN,
            f"+refs/heads/{provider.branch}:refs/remotes/origin/{provider.branch}",
        ),
    )
    return repo


@pytest.fixture
def rope_project(tmp_path: Path) -> Iterator[t.Infra.RopeProject]:
    """Shared minimal rope project for refactor unit tests."""
    project = u.Infra.init_rope_project(tmp_path)
    yield project
    project.close()
