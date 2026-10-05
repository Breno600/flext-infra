"""Pytest fixtures for FLEXT infra tests.

Provides reusable fixtures for creating real project structures using tmp_path.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, infra, u as infra_u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import c, m, p, t, u

_FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _read_fixture(*parts: str) -> str:
    return _FIXTURES_DIR.joinpath(*parts).read_text(encoding="utf-8")


def _modernizer_pyproject(name: str) -> str:
    return f'[project]\nname = "{name}"\nversion = "0.1.0"\n'


def _modernizer_workspace_pyproject(*members: str) -> str:
    base = _modernizer_pyproject("workspace")
    if not members:
        return base
    members_text = ", ".join(f'"{member}"' for member in members)
    return f"{base}\n[tool.uv.workspace]\nmembers = [{members_text}]\n"


def _write_modernizer_codegen_config(workspace: Path) -> None:
    """Copy the valid governed SSOT into the isolated modernizer owner.

    Constraint rewriting validates the complete typed codegen contract and
    must never write the installed infrastructure checkout (flext-eles2).
    """
    config_dir = workspace / c.Infra.CODEGEN_CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / c.Infra.CODEGEN_CONFIG_FILENAME).write_bytes(
        (
            _PROJECT_ROOT / c.Infra.CODEGEN_CONFIG_DIR / c.Infra.CODEGEN_CONFIG_FILENAME
        ).read_bytes(),
    )


@pytest.fixture
def deptry_report_payload() -> t.JsonPayload:
    """Provide ``deptry_report_payload``.

    Returns:
        The resulting ``t.JsonPayload``.

    """
    parsed = u.Cli.json_parse(_read_fixture("deps", "deptry_report.json"))
    parsed = tm.not_none(parsed)
    tm.ok(parsed)
    return parsed.value


@pytest.fixture
def tool_config_document() -> m.Infra.ToolConfigDocument:
    """Provide ``tool_config_document``.

    Returns:
        The resulting ``m.Infra.ToolConfigDocument``.

    """
    return u.Tests.tool_config_document()


_DETECTOR_PROJECT_NAME = "detector-fixture"
_DETECTOR_UPGRADE_RECEIPT = "upgrade-receipt.json"


def _detector_template_parent(run_root: Path, modules: t.StrSequence) -> Path:
    """Return the run-scoped home of one resolved detector consumer.

    The pytest invocation's temporary root is shared by every worker of one
    run and removed with it, so each run resolves its own environment once.

    Returns:
        The run-scoped home of one resolved detector consumer.

    """
    return run_root / "detector-templates" / "-".join(modules)


def _provision_detector_template(run_root: Path, modules: t.StrSequence) -> None:
    """Resolve one detector consumer through ``make upg`` and commit its locks.

    ``make upg`` is the sole writer of a new consumer's locks; it resolves over
    the network, so it runs once per run and dependency set, before any test
    item starts. The command output is kept as the receipt every consumer of
    the template asserts.
    """
    parent = _detector_template_parent(run_root, modules)
    distributions = {"requests": "requests", "pytz": "pytz", "six": "six"}
    # A governed FLEXT consumer declares exactly one runtime upstream profile;
    # conform derives its project spec from it (context_render.py).
    upstream = u.Tests.flext_source("flext-core")
    dependencies = ", ".join(
        f'"{name}"' for name in (upstream, *(distributions[name] for name in modules))
    )
    infrastructure = tm.ok(
        u.Infra.configured_repository_ref(
            codegen=config.Infra.codegen,
            repository_root=_PROJECT_ROOT,
        ),
    )
    integration = tm.ok(
        u.Infra.flext_integration_line(
            codegen=config.Infra.codegen,
            repository_root=_PROJECT_ROOT,
        ),
    )
    python_required = config.Infra.codegen.toolchain.python_required_version
    infrastructure_source = (
        f"{infrastructure.distribution} @ git+{infrastructure.url}@{integration.branch}"
    )
    root = u.Tests.mk_project(
        parent,
        _DETECTOR_PROJECT_NAME,
        with_src=True,
        pyproject=(
            '[build-system]\nrequires = ["hatchling"]\n'
            'build-backend = "hatchling.build"\n'
            '[project]\nname = "detector-fixture"\nversion = "0.1.0"\n'
            'authors = [{name = "FLEXT Team", email = "team@flext.dev"}]\n'
            f'requires-python = "{python_required}"\n'
            f"dependencies = [{dependencies}]\n"
            '[project.optional-dependencies]\nfeature = ["requests"]\n'
            # A governed checkout declares every internal requirement with its
            # own direct Git source; the scaffold dev SSOT includes flext-tests.
            '[dependency-groups]\ndev = ["deptry", "mypy", "pip", '
            f'"{infrastructure_source}", '
            f'"{u.Tests.flext_source("flext-tests")}"]\n'
            "[tool.hatch.metadata]\nallow-direct-references = true\n"
            "[tool.mypy]\n"
            '[tool.deptry]\npep621_dev_dependency_groups = ["dev"]\n'
        ),
    )
    (root / "src" / "detector_fixture" / "__init__.py").write_text(
        "\n".join(f"import {name}" for name in ("flext_core", *modules)) + "\n",
        encoding="utf-8",
    )
    u.Tests.copy_tracked_mise_seeds(root)
    repository = u.Tests.repository_ref(
        root.name,
        role=c.Infra.MakeProfile.STANDALONE,
    ).model_copy(update={"editable": True})
    u.Tests.initialize_git_repo(root, origin_url=repository.url)
    workspace = u.Tests.workspace_spec(
        repository,
        project=u.Tests.project_spec(root.name),
    )
    conform_request = u.Tests.conform_request(
        root,
        what=c.Infra.CodegenConformSurface.MAKEFILE,
    )
    plan = tm.ok(
        FlextInfraCodegenConform(
            repository_root=root,
            initial_workspace=workspace,
            request=conform_request,
        ).plan(conform_request),
    )
    makefile = next(
        item for item in plan.files if item.path.name == c.Infra.MAKEFILE_FILENAME
    )
    tm.ok(
        u.Cli.atomic_write_text_file(
            root / c.Infra.MAKEFILE_FILENAME,
            u.Tests.codegen_file_text(makefile),
        ),
    )
    tm.ok(
        infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(repository_root=root, apply=True),
        ),
    )
    # A newly scaffolded consumer has no committed locks yet. The public upgrade
    # lifecycle is their sole writer; frozen setup starts only after that first
    # resolved environment has been reviewed and committed by the consumer.
    upgrade = tm.ok(u.Tests.run_isolated_make(["upg"], cwd=root, capture=False))
    if u.Cli.process_succeeded(upgrade.outcome):
        u.Tests.git_bootstrap(root, ("add", "-A"))
        u.Tests.git_bootstrap(root, ("commit", "-q", "-m", "upg: resolved locks"))
    _write_receipt(parent / _DETECTOR_UPGRADE_RECEIPT, upgrade)


_MAKE_UPGRADE_RECEIPT = c.Tests.MAKE_TEMPLATE_UPG_RECEIPT
_MAKE_CI_SETUP_RECEIPT = c.Tests.MAKE_TEMPLATE_CI_RECEIPT
_INFRA_SETUP_RECEIPT = "setup-receipt.json"
_GIT_MIRRORS_RECEIPT = "mirrors-receipt.txt"
# Every scenario that provisions the candidate's own environment before `gen`.
_INFRA_CHECKOUT_SCENARIOS = (
    "builtin",
    "custom",
    "producer-failure",
    "activation-failure",
)


def _run_root(factory: pytest.TempPathFactory) -> Path:
    """Use pytest's invocation directory, shared across xdist workers.

    Returns:
        The resulting ``Path``.

    """
    base = factory.getbasetemp()
    return base.parent if os.environ.get("PYTEST_XDIST_WORKER") else base


def _run_scoped(run_root: Path, kind: str, key: str) -> Path:
    """Return the run-scoped home of one provisioned consumer.

    Returns:
        The run-scoped home of one provisioned consumer.

    """
    return run_root / kind / key


def _write_receipt(path: Path, output: p.Cli.CommandOutput) -> None:
    u.Tests.record_dependency_command_output(output)
    tm.ok(
        u.Cli.atomic_write_text_file(
            path,
            m.Cli.CommandOutput.model_validate(
                output,
                from_attributes=True,
            ).model_dump_json(),
        ),
    )


def _provision_make_template(run_root: Path, profile: c.Infra.MakeProfile) -> None:
    """Resolve one generated consumer through ``make upg`` once per run.

    The upgrade runs under a foreign uv environment with a declared post-upg
    hook, and a checkout of the resolved result installs every locked tool
    into cold CI storage; both receipts are what the consumers assert.
    """
    parent = _run_scoped(run_root, "make-templates", profile.value)
    root, _ = u.Tests.render_make_environment(parent, profile, bootstrap=True)
    hostile_venv = parent / c.Tests.MAKE_TEMPLATE_HOSTILE_VENV
    (hostile_venv / "bin").mkdir(parents=True)
    (hostile_venv / "sentinel").write_text("untouched\n", encoding="utf-8")
    custom = root / c.Infra.CUSTOM_MAKE_FILENAME
    custom.write_text(
        custom.read_text(encoding="utf-8")
        + ".PHONY: post-upg\npost-upg:\n\t@printf '%s\\n' 'upg-hook-ran'\n",
        encoding="utf-8",
    )
    upgrade = tm.ok(
        u.Tests.run_isolated_make(
            ["--no-print-directory", "upg"],
            cwd=root,
            env=u.Tests.hostile_uv_environment(hostile_venv),
        ),
    )
    _write_receipt(parent / _MAKE_UPGRADE_RECEIPT, upgrade)
    if not u.Cli.process_succeeded(upgrade.outcome):
        return
    checkout = u.Tests.resolved_make_checkout(
        root,
        parent / c.Tests.MAKE_TEMPLATE_CI_CHECKOUT,
        profile,
    )
    make = config.Infra.codegen.make
    (checkout / c.Infra.CUSTOM_MAKE_FILENAME).write_text(
        ".PHONY: post-setup\npost-setup:\n"
        '\t@test -x "$(MAKE_COMMAND)"\n'
        '\t@test "$(MAKE_COMMAND)" = "$(SELF_MAKE_EXECUTABLE)"\n'
        f'\t@test "$({make.ci.variable})" = "{make.ci.value}"\n'
        "\t@printf '%s\\n' 'ci-runtime-provisioned'\n",
        encoding="utf-8",
    )
    setup = tm.ok(
        u.Tests.run_isolated_make(
            ["--no-print-directory", "setup"],
            cwd=checkout,
            env={
                **u.Tests.hostile_uv_environment(hostile_venv),
                make.ci.variable: make.ci.value,
                u.Infra.mise_bootstrap_environment().storage_root_variable: str(
                    parent / c.Tests.COLD_MISE_STORAGE,
                ),
            },
        ),
    )
    _write_receipt(parent / _MAKE_CI_SETUP_RECEIPT, setup)


def _provision_infra_checkout(run_root: Path, scenario: str) -> None:
    """Set up one candidate checkout from its committed locks before its item."""
    parent = _run_scoped(run_root, "infra-checkouts", scenario)
    root = u.Tests.infra_source_checkout(parent)
    setup = tm.ok(
        u.Tests.run_isolated_make(["--no-print-directory", "setup"], cwd=root),
    )
    _write_receipt(parent / _INFRA_SETUP_RECEIPT, setup)


def _ensure_provisioned(
    run_root: Path,
    parent: Path,
    receipt: str,
    key: c.Infra.MakeProfile | str | t.StrSequence,
) -> None:
    """Provision only a consumed fixture under the canonical filesystem lease.

    Testmon inventory and selection collect tests without network or writes.
    Provisioning belongs to the item that actually consumes the checkout, so
    its cost and failure remain visible to the test deadline and report.
    """
    parent.mkdir(parents=True, exist_ok=True)
    with u.Infra.codegen_transaction_lease(parent / receipt):
        if (parent / receipt).is_file():
            return
        match key:
            case c.Infra.MakeProfile():
                _provision_make_template(run_root, key)
            case str():
                _provision_infra_checkout(run_root, key)
            case _:
                _provision_detector_template(run_root, key)


@pytest.fixture
def hermetic_git_environment(tmp_path_factory: pytest.TempPathFactory) -> t.StrMapping:
    """Serve the fixture provider's Git sources from this run's local mirrors.

    The mirrors are built once per locked-source set under the canonical
    filesystem lease from objects this checkout already holds; the directory is
    keyed by that set, so a relock never reuses mirrors of superseded commits.
    The returned environment routes the provider to them and makes any network
    transport fail.

    Returns:
        The resulting ``t.StrMapping``.

    """
    sources = "\n".join(
        "@".join(source) for source in u.Tests.locked_git_sources(_PROJECT_ROOT)
    )
    parent = _run_scoped(
        _run_root(tmp_path_factory),
        "git-mirrors",
        hashlib.sha256(sources.encode()).hexdigest()[:16],
    )
    parent.mkdir(parents=True, exist_ok=True)
    receipt = parent / _GIT_MIRRORS_RECEIPT
    mirrors = parent / "mirrors"
    with u.Infra.codegen_transaction_lease(receipt):
        if not receipt.is_file():
            mirrored = u.Tests.build_git_mirrors(_PROJECT_ROOT, mirrors)
            tm.ok(u.Cli.atomic_write_text_file(receipt, "\n".join(mirrored) + "\n"))
    return u.Tests.hermetic_git_environment(mirrors)


@pytest.fixture
def resolved_make_templates(
    tmp_path_factory: pytest.TempPathFactory,
) -> t.MappingKV[c.Infra.MakeProfile, Path]:
    """Return every profile's committed ``make upg`` template for this run.

    Consumers clone a template rather than resolving inside their budget; the
    template directory also holds the upgrade and cold CI setup receipts.

    Returns:
        Every profile's committed ``make upg`` template for this run.

    """
    templates: dict[c.Infra.MakeProfile, Path] = {}
    for profile in c.Infra.MakeProfile:
        run_root = _run_root(tmp_path_factory)
        parent = _run_scoped(run_root, "make-templates", profile.value)
        _ensure_provisioned(run_root, parent, _MAKE_UPGRADE_RECEIPT, profile)
        upgrade = u.Tests.command_receipt(parent / _MAKE_UPGRADE_RECEIPT)
        tm.that(
            u.Cli.process_succeeded(upgrade.outcome),
            eq=True,
            msg=upgrade.stdout + upgrade.stderr,
        )
        templates[profile] = parent / profile.value / "fixture-project"
    return templates


@pytest.fixture(params=_INFRA_CHECKOUT_SCENARIOS)
def provisioned_infra_checkout(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> t.Pair[str, Path]:
    """Return one scenario's candidate checkout, set up from committed locks.

    Returns:
        One scenario's candidate checkout, set up from committed locks.

    """
    scenario = str(request.param)
    run_root = _run_root(tmp_path_factory)
    parent = _run_scoped(run_root, "infra-checkouts", scenario)
    _ensure_provisioned(run_root, parent, _INFRA_SETUP_RECEIPT, scenario)
    setup = u.Tests.command_receipt(parent / _INFRA_SETUP_RECEIPT)
    tm.that(
        u.Cli.process_succeeded(setup.outcome),
        eq=True,
        msg=setup.stdout + setup.stderr,
    )
    root = parent / config.Infra.name
    tm.that((u.Infra.runtime_environment_dir(root) / "pyvenv.cfg").is_file(), eq=True)
    return scenario, root


@pytest.fixture(params=[("requests",)])
def real_detector_project(
    tmp_path: Path,
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    """Check out the run's resolved detector consumer and set it up from its locks.

    The consumer clones the committed template exactly as a developer clones a
    reviewed repository, then ``make setup`` provisions its own environment
    from the committed locks without resolving anything new.

    Returns:
        The resulting ``Path``.

    """
    modules = t.Infra.STR_SEQ_ADAPTER.validate_python(request.param)
    run_root = _run_root(tmp_path_factory)
    parent = _detector_template_parent(run_root, modules)
    _ensure_provisioned(run_root, parent, _DETECTOR_UPGRADE_RECEIPT, modules)
    upgrade = m.Cli.CommandOutput.model_validate_json(
        (parent / _DETECTOR_UPGRADE_RECEIPT).read_text(encoding="utf-8"),
    )
    tm.that(u.Cli.process_succeeded(upgrade.outcome), eq=True, msg=upgrade.stderr)
    root = tmp_path / _DETECTOR_PROJECT_NAME
    u.Tests.git_bootstrap(
        tmp_path,
        ("clone", "-q", str(parent / _DETECTOR_PROJECT_NAME), str(root)),
    )
    u.Tests.initialize_git_repo(
        root,
        origin_url=u.Tests.repository_ref(
            root.name,
            role=c.Infra.MakeProfile.STANDALONE,
        ).url,
    )
    setup = tm.ok(u.Tests.run_isolated_make(["setup"], cwd=root, capture=False))
    u.Tests.record_dependency_command_output(setup)
    tm.that(u.Cli.process_succeeded(setup.outcome), eq=True, msg=setup.stderr)
    runtime = infra_u.Infra.runtime_environment_dir(root)
    executable = c.Infra.DEPTRY + (".exe" if os.name == "nt" else "")
    tool_path = runtime / ("Scripts" if os.name == "nt" else "bin") / executable
    tm.that(tool_path.is_file(), eq=True)
    (root / "limits.toml").write_text(
        "[typing_libraries]\nexclude = []\n",
        encoding="utf-8",
    )
    return root


@pytest.fixture
def real_toml_project(tmp_path: Path) -> Path:
    """Create a real project with valid pyproject.toml.

    Returns:
        The resulting ``Path``.

    """
    project_root = tmp_path / "test_project"
    project_root.mkdir()
    pyproject_content = """\
[build-system]
requires = ["poetry-core>=1.0.0"]
build-backend = "poetry.core.masonry.api"

[project]
name = "test-project"
version = "0.1.0"
description = "Test project"
authors = [{name = "Test", email = "test@example.com"}]
"""
    (project_root / "pyproject.toml").write_text(pyproject_content)
    return project_root


@pytest.fixture
def real_makefile_project(tmp_path: Path) -> Path:
    """Create a real project with valid Makefile.

    Returns:
        The resulting ``Path``.

    """
    project_root = tmp_path / "makefile_project"
    project_root.mkdir()
    makefile_content = """\
.PHONY: help setup check test

help:
\t@echo "Available targets"

setup:
\t@echo "Setting up"

check:
\t@echo "Checking"

test:
\t@echo "Testing"
"""
    (project_root / "Makefile").write_text(makefile_content)
    return project_root


@pytest.fixture
def real_python_package(tmp_path: Path) -> Path:
    """Create a real Python package with src layout.

    Returns:
        The resulting ``Path``.

    """
    project_root = tmp_path / "python_package"
    project_root.mkdir()
    src_dir = project_root / "src" / "test_pkg"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text('"""Test package."""\n__version__ = "0.1.0"\n')
    (src_dir / "identity.py").write_text(
        '"""Substantive unique source consumed by real scanner fixtures."""\n\n'
        "def normalize_identity(parts: tuple[str, ...]) -> str:\n"
        '    """Normalize one ordered identity without duplicated code."""\n'
        "    normalized = tuple(part.strip() for part in parts if part.strip())\n"
        "    if not normalized:\n"
        '        raise ValueError("identity requires at least one non-empty part")\n'
        '    return "::".join(normalized).casefold()\n',
        encoding="utf-8",
    )
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "test-pkg"\nversion = "0.1.0"\n',
    )
    return project_root


@pytest.fixture
def cached_runner_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a real one-test consumer for the public cached pytest runner.

    Returns:
        The resulting ``Path``.

    """
    external_cache = tmp_path / "external-cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(external_cache))
    monkeypatch.setenv("LOCALAPPDATA", str(external_cache))
    project_root = tmp_path / "cached_runner_project"
    policy = config.Infra.codegen.make.testmon_cache
    package_root = project_root / c.Infra.DEFAULT_SRC_DIR / "runner_sample"
    tests_root = project_root / policy.target_directory
    package_root.mkdir(parents=True)
    tests_root.mkdir(parents=True)
    # A faithful consumer project carries the fleet-standard coverage
    # boundary: the Cython provider mapping of dependency_injector is not
    # parseable source and is omitted by every fleet coverage config.
    (project_root / "pyproject.toml").write_text(
        '[tool.coverage.run]\nomit = ["*/dependency_injector/providers.pyx"]\n'
        "[tool.pytest.ini_options]\n"
        f'pythonpath = ["{c.Infra.DEFAULT_SRC_DIR}"]\n',
        encoding="utf-8",
    )
    (package_root / "__init__.py").write_text(
        "def answer() -> int:\n    return 42\n",
        encoding="utf-8",
    )
    (tests_root / "test_runtime.py").write_text(
        "from flext_tests import tm\n"
        "from runner_sample import answer\n\n"
        "def test_runtime() -> None:\n"
        "    tm.that(answer(), eq=42)\n",
        encoding="utf-8",
    )
    return project_root


@pytest.fixture
def policy_violation_project(tmp_path: Path) -> Path:
    """Create a real consumer whose suite violates the slow-timeout policy.

    Returns:
        The resulting ``Path``.

    """
    project_root = tmp_path / "policy_violation_project"
    policy = config.Infra.codegen.make.testmon_cache
    tests_root = project_root / policy.target_directory
    tests_root.mkdir(parents=True)
    # The ini value is an arbitrary non-production budget owned by this probe.
    (project_root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nflext_slow_timeout_seconds = "30"\n',
        encoding="utf-8",
    )
    (tests_root / "test_policy.py").write_text(
        "import pytest\n"
        "\n"
        "\n"
        "@pytest.mark.timeout(1)\n"
        "def test_breaks_policy() -> None:\n"
        "    pass\n",
        encoding="utf-8",
    )
    return project_root


@pytest.fixture
def mod_workspace(tmp_path: Path) -> Path:
    """Create the shared real workspace for the public refactor-mod CLI.

    Returns:
        The resulting ``Path``.

    """
    project_document = u.read_project_document_cached(_PROJECT_ROOT)
    project = u.build_project_metadata(_PROJECT_ROOT, project_document)
    workspace = tmp_path / "mod_workspace"
    tm.ok(u.Cli.ensure_dir(workspace))
    tm.ok(
        u.Cli.atomic_write_text_file(
            workspace / c.PYPROJECT_FILENAME,
            (
                "[project]\n"
                f'name = "{workspace.name.replace("_", "-")}"\n'
                f'version = "{project.project.version}"\n'
                f"{c.Infra.DEPENDENCIES} = []\n"
            ),
        ),
    )
    # A declared distribution owns a package: resolving the package name from
    # `[project].name` alone is impossible for a `flext-` distribution, so a
    # fixture without `src/<pkg>/` is not the project it claims to be. The
    # package follows the fixture's own declared name: naming it after the
    # real project would shadow the installed flext_infra for Rope, and every
    # packaged campaign binding (flext_infra.c / .t) would lose its owner.
    package_dir = workspace / c.Infra.DEFAULT_SRC_DIR / workspace.name
    tm.ok(u.Cli.ensure_dir(package_dir))
    tm.ok(
        u.Cli.atomic_write_text_file(
            package_dir / c.Infra.INIT_PY,
            '"""Public refactor-mod fixture package."""\n\n'
            "from __future__ import annotations\n",
        ),
    )
    tm.ok(
        u.Cli.atomic_write_text_file(
            workspace / "sample.py",
            # The fixture owns every name it uses and carries exactly one
            # defect: the governance rule the tests exercise. Undefined names
            # or an unresolvable import would make the diagnostic gates red for
            # a reason unrelated to the rule, and mod's own contract is that
            # the tree is clean before and after.
            (
                '"""Public refactor-mod fixture module with one governance defect."""\n'
                "\n"
                "from __future__ import annotations\n"
                "\n"
                "from flext_core import t\n"
                "\n"
                "class _FixtureInfra:\n"
                '    """Stand-in infra namespace owning every name'
                ' the fixture uses."""\n'
                "\n"
                "    @staticmethod\n"
                "    def serialization_lock_execute(\n"
                "        paths: tuple[str, ...], timeout: float\n"
                "    ) -> None:\n"
                '        """Accept the governed call shape without any effect."""\n'
                "\n"
                "\n"
                "class _FixtureFacade:\n"
                '    """Stand-in utilities facade exposing the infra namespace."""\n'
                "\n"
                "    Infra = _FixtureInfra\n"
                "\n"
                "\n"
                "u = _FixtureFacade()\n"
                "paths: tuple[str, ...] = ()\n"
                "timeout: float = 1.0\n"
                "\n"
                "u.Infra.serialization_lock_execute(paths, timeout)\n"
            ),
        ),
    )
    u.Tests.initialize_git_repo(workspace)
    return workspace


@pytest.fixture
def real_workspace(tmp_path: Path) -> Path:
    """Create a real multi-project workspace.

    Returns:
        The resulting ``Path``.

    """
    repository_root = tmp_path / "workspace"
    repository_root.mkdir()
    (repository_root / "Makefile").write_text(
        ".PHONY: help\nhelp:\n\t@echo 'Workspace'\n",
    )
    (repository_root / "pyproject.toml").write_text(
        '[project]\nname = "workspace"\nversion = "0.1.0"\n',
    )
    for i in range(1, 4):
        project_dir = repository_root / f"project_{i}"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(
            f'[project]\nname = "project-{i}"\nversion = "0.1.0"\n',
        )
        src_dir = project_dir / "src" / f"project_{i}"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text(f'"""Project {i}."""\n')
    return repository_root


@pytest.fixture
def modernizer_workspace(tmp_path: Path) -> Path:
    """Provide ``modernizer_workspace``.

    Returns:
        The resulting ``Path``.

    """
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    # The governed tree above the workspace carries the committed Taplo pin.
    u.Tests.seed_locked_taplo(tmp_path)
    (workspace / c.PYPROJECT_FILENAME).write_text(
        _modernizer_workspace_pyproject(),
        encoding="utf-8",
    )
    u.Tests.write_beads_project(
        workspace,
        workspace="workspace",
        database="workspace",
        issue_prefix="workspace",
    )
    _write_modernizer_codegen_config(workspace)
    return workspace


@pytest.fixture
def modernizer_workspace_with_projects(modernizer_workspace: Path) -> Path:
    """Provide ``modernizer_workspace_with_projects``.

    Returns:
        The resulting ``Path``.

    """
    (modernizer_workspace / c.PYPROJECT_FILENAME).write_text(
        _modernizer_workspace_pyproject("selected", "ignored"),
        encoding="utf-8",
    )
    selected = u.Tests.mk_project(
        modernizer_workspace,
        "selected",
        pyproject=_modernizer_pyproject("selected"),
    )
    ignored = u.Tests.mk_project(
        modernizer_workspace,
        "ignored",
        pyproject=_modernizer_pyproject("ignored"),
    )
    for project in (selected, ignored):
        u.Tests.write_beads_project(
            project,
            workspace="workspace",
            database=project.name,
            issue_prefix=project.name,
        )
    (modernizer_workspace / ".gitmodules").write_text(
        '[submodule "selected"]\n\tpath = selected\n'
        "\turl = https://github.com/flext-sh/selected.git\n"
        '[submodule "ignored"]\n\tpath = ignored\n'
        "\turl = https://github.com/flext-sh/ignored.git\n",
        encoding="utf-8",
    )
    # FLEXT: public modernizer commands fail loud outside a real Git workspace.
    u.Tests.initialize_git_repo(modernizer_workspace)
    return modernizer_workspace


@pytest.fixture
def real_docs_project(tmp_path: Path) -> Path:
    """Create a real project with documentation.

    Returns:
        The resulting ``Path``.

    """
    project_root = tmp_path / "docs_project"
    project_root.mkdir()
    docs_dir = project_root / "docs"
    docs_dir.mkdir()
    (docs_dir / "README.md").write_text("# Documentation\n")
    (docs_dir / "index.md").write_text("# Index\n")
    (project_root / "README.md").write_text("# Project\n")
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "docs-project"\nversion = "0.1.0"\n',
    )
    return project_root


@pytest.fixture
def semantic_rope_workspace(tmp_path: Path) -> t.Pair[t.Infra.RopeProject, Path]:
    """Create a real rope workspace with semantic-analysis fixtures.

    Returns:
        The resulting ``t.Pair[t.Infra.RopeProject, Path]``.

    """
    repository_root = tmp_path / "rope_workspace"
    package_root = repository_root / "src" / "rope_demo"
    package_root.mkdir(parents=True, exist_ok=True)
    (package_root / "__init__.py").write_text("", encoding="utf-8")
    (package_root / "models.py").write_text(
        "from pathlib import Path\n\n"
        "class Animal:\n"
        "    pass\n\n"
        "class Dog(Animal):\n"
        "    home = Path('kennel')\n\n"
        "    @staticmethod\n"
        "    def fetch() -> str:\n"
        "        return 'ball'\n\n"
        "    @classmethod\n"
        "    def breed(cls) -> str:\n"
        "        return cls.__name__\n\n"
        "    def _wag(self) -> str:\n"
        "        return 'wag'\n",
        encoding="utf-8",
    )
    (package_root / "services.py").write_text(
        "from rope_demo.models import Dog\n\n"
        "class Kennel:\n"
        "    def adopt(self) -> Dog:\n"
        "        return Dog()\n",
        encoding="utf-8",
    )

    rope_project = u.Infra.init_rope_project(repository_root)
    return rope_project, repository_root


@pytest.fixture
def models_resource(
    semantic_rope_workspace: t.Pair[t.Infra.RopeProject, Path],
) -> t.Infra.RopeResource:
    """Return the Rope resource for the semantic models fixture module.

    Returns:
        The Rope resource for the semantic models fixture module.

    """
    rope_project, repository_root = semantic_rope_workspace
    resource = u.Infra.resolve_resource_from_path(
        rope_project,
        repository_root / "src" / "rope_demo" / "models.py",
    )
    validated: t.Infra.RopeResource = tm.not_none(resource)
    return validated


@pytest.fixture
def services_resource(
    semantic_rope_workspace: t.Pair[t.Infra.RopeProject, Path],
) -> t.Infra.RopeResource:
    """Return the Rope resource for the semantic services fixture module.

    Returns:
        The Rope resource for the semantic services fixture module.

    """
    rope_project, repository_root = semantic_rope_workspace
    resource = u.Infra.resolve_resource_from_path(
        rope_project,
        repository_root / "src" / "rope_demo" / "services.py",
    )
    validated: t.Infra.RopeResource = tm.not_none(resource)
    return validated
