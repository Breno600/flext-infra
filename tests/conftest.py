"""Test configuration for flext-infra."""

from __future__ import annotations

import importlib
import os
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, m, t, u

# NOTE(flext-p68a.9.4, agent codex): the installed flext-tests pytest11 plugin is
# the only fixture owner; conftest must not re-export or shadow its fixtures.
pytest_plugins = ["tests.unit.fixtures", "tests.unit.fixtures_git"]

_TRACKED_CODEGEN_CONFIG_PATH = (
    Path(__file__).resolve().parent.parent
    / c.Infra.CODEGEN_CONFIG_DIR
    / c.Infra.CODEGEN_CONFIG_FILENAME
)


@pytest.fixture(scope="session", autouse=True)
def _guard_tracked_codegen_config_untouched() -> Iterator[None]:
    """Fail loud if the suite writes to the real, tracked ``config/codegen.yaml``.

    Root cause (flext-eles2): dependency-floor rewrite tests exercised the
    public ``--rewrite-constraints`` entry point through workspaces that never
    declared their own governed SSOT, so the floor writer fell back to the
    packaged/installed ``flext_infra`` config directory — this very checkout
    in an editable install — and silently flipped floors in the real tracked
    file. The floor writer now resolves its target from the modernizer's own
    ``repository_root`` and every workspace fixture declares its own isolated
    ``config/codegen.yaml``; this session-wide guard proves the real file
    stays untouched by the whole suite, current and future.
    """
    before = _TRACKED_CODEGEN_CONFIG_PATH.read_bytes()
    yield
    after = _TRACKED_CODEGEN_CONFIG_PATH.read_bytes()
    if after != before:
        pytest.fail(
            "test suite modified the tracked repository file "
            f"{_TRACKED_CODEGEN_CONFIG_PATH}; dependency-floor and codegen "
            "writers must target an isolated workspace, never the real "
            "checkout (flext-eles2)"
        )


@pytest.fixture(scope="session", autouse=True)
def _isolate_host_gas_city_identity() -> Iterator[None]:
    """Keep the operator's Gas City identity out of every fixture process.

    The generated ``.envrc`` selects its Gas City Beads branch from the
    caller's identity variable. A host shell connected to a city exports it,
    so every fixture repository (declaring no city) would inherit the host
    city and fail reading its absent ``.beads/metadata.json``. Tests that
    exercise the city branch pass the variable explicitly.
    """
    name = m.Infra.BeadsWorkspaceEnvironmentSpec().identity_var
    original = os.environ.pop(name, None)
    yield
    u.Tests.restore_env(name, original)


@pytest.fixture
def installed_dependency_path(tmp_path: Path) -> Iterator[Path]:
    """Expose real non-src package files through the selected import environment."""
    location = tmp_path / "installed"
    location.mkdir()
    sys.path.insert(0, str(location))
    importlib.invalidate_caches()
    try:
        yield location
    finally:
        sys.path.remove(str(location))
        importlib.invalidate_caches()


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
            # flext-wkii.4.15: settings identity is fixed at process startup.
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
    integration-branch discovery reads the already materialized tracking ref.
    Declaring the real upstream URL satisfies detection but grades the fixture
    against the live repository; declaring a local path fails detection outright.
    The fixture therefore declares the provider URL and rewrites it to a local
    bare origin through Git's own ``url.<base>.insteadOf`` mechanism. Fixture
    setup materializes the tracking ref once; conformance itself stays offline.
    """
    repo = infra_test_workspace / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    baseline_file = repo / ".infra-baseline"
    baseline_file.write_text("baseline\n", encoding="utf-8")
    u.Tests.write_project_beads_config(repo, config.Infra.name)
    upstream = u.Tests.repository_ref(config.Infra.name).url
    origin = infra_test_workspace / "origin.git"
    origin.mkdir(parents=True, exist_ok=True)
    u.Tests.git_bootstrap(origin, ("init", "--bare"))
    u.Tests.initialize_git_repo(repo, origin_url=upstream)
    u.Tests.git_bootstrap(
        repo, ("config", "--local", f"url.{origin}.insteadOf", upstream)
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
    """Shared minimal rope project for refactor unit tests."""
    project = u.Infra.init_rope_project(tmp_path)
    yield project
    project.close()
