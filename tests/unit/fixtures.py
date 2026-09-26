"""Pytest fixtures for FLEXT infra tests.

Provides reusable fixtures for creating real project structures using tmp_path.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import fcntl
import tempfile
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, infra
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
    """Give the workspace its own governed SSOT so ``--rewrite-constraints``.

    stays inside the fixture (flext-eles2): the floor writer resolves its
    target from the modernizer's own ``repository_root``, never the real
    flext-infra checkout, so every isolated workspace needs a minimal
    ``config/codegen.yaml`` of its own.
    """
    config_dir = workspace / c.Infra.CODEGEN_CONFIG_DIR
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / c.Infra.CODEGEN_CONFIG_FILENAME).write_text(
        (
            "Infra:\n"
            "  codegen:\n"
            "    scaffold:\n"
            "      project:\n"
            "        dependency_profiles: []\n"
        ),
        encoding="utf-8",
    )


@pytest.fixture
def deptry_report_payload() -> t.JsonPayload:
    parsed = u.Cli.json_parse(_read_fixture("deps", "deptry_report.json"))
    parsed = tm.not_none(parsed)
    tm.ok(parsed)
    return parsed.value


@pytest.fixture
def tool_config_document() -> m.Infra.ToolConfigDocument:
    return u.Tests.tool_config_document()


_DETECTOR_FIXTURE = "real_detector_project"
_DETECTOR_PROJECT_NAME = "detector-fixture"
_DETECTOR_UPGRADE_RECEIPT = "upgrade-receipt.json"


def _detector_template_parent(modules: t.StrSequence) -> Path:
    """Return the run-scoped home of one resolved detector consumer.

    The pytest invocation's temporary root is shared by every worker of one
    run and removed with it, so each run resolves its own environment once.
    """
    return Path(tempfile.gettempdir()) / "detector-templates" / "-".join(modules)


def _provision_detector_template(modules: t.StrSequence) -> None:
    """Resolve one detector consumer through ``make upg`` and commit its locks.

    ``make upg`` is the sole writer of a new consumer's locks; it resolves over
    the network, so it runs once per run and dependency set, before any test
    item starts. The command output is kept as the receipt every consumer of
    the template asserts.
    """
    parent = _detector_template_parent(modules)
    distributions = {"requests": "requests", "pytz": "pytz", "six": "six"}
    # A governed FLEXT consumer declares exactly one runtime upstream profile;
    # conform derives its project spec from it (context_render.py).
    upstream = u.Tests.flext_source("flext-core")
    dependencies = ", ".join(
        f'"{name}"' for name in (upstream, *(distributions[name] for name in modules))
    )
    infrastructure = tm.ok(
        u.Infra.configured_repository_ref(
            codegen=config.Infra.codegen, repository_root=_PROJECT_ROOT
        )
    )
    integration = tm.ok(
        u.Infra.flext_integration_line(
            codegen=config.Infra.codegen, repository_root=_PROJECT_ROOT
        )
    )
    root = u.Tests.mk_project(
        parent,
        _DETECTOR_PROJECT_NAME,
        with_src=True,
        pyproject=(
            '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
            '[project]\nname = "detector-fixture"\nversion = "0.1.0"\n'
            'authors = [{name = "FLEXT Team", email = "team@flext.dev"}]\n'
            f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\n'
            f"dependencies = [{dependencies}]\n"
            '[project.optional-dependencies]\nfeature = ["requests"]\n'
            # A governed checkout declares every internal requirement with its
            # own direct Git source; the scaffold dev SSOT includes flext-tests.
            '[dependency-groups]\ndev = ["deptry", "mypy", "pip", '
            f'"{infrastructure.distribution} @ git+{infrastructure.url}@{integration.branch}", '
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
        root.name, role=c.Infra.MakeProfile.STANDALONE
    ).model_copy(update={"editable": True})
    u.Tests.initialize_git_repo(root, origin_url=repository.url)
    workspace = u.Tests.workspace_spec(
        repository, project=u.Tests.project_spec(root.name)
    )
    conform_request = u.Tests.conform_request(
        root, what=c.Infra.CodegenConformSurface.MAKEFILE
    )
    plan = tm.ok(
        FlextInfraCodegenConform(
            repository_root=root, initial_workspace=workspace, request=conform_request
        ).plan(conform_request)
    )
    makefile = next(
        item for item in plan.files if item.path.name == c.Infra.MAKEFILE_FILENAME
    )
    tm.ok(
        u.Cli.atomic_write_text_file(
            root / c.Infra.MAKEFILE_FILENAME, u.Tests.codegen_file_text(makefile)
        )
    )
    tm.ok(
        infra.sync_environment_files(
            m.Infra.WorkspaceEnvironmentSyncRequest(repository_root=root, apply=True)
        )
    )
    # A newly scaffolded consumer has no committed locks yet. The public upgrade
    # lifecycle is their sole writer; frozen setup starts only after that first
    # resolved environment has been reviewed and committed by the consumer.
    upgrade = tm.ok(u.Tests.run_isolated_make(["upg"], cwd=root, capture=False))
    if u.Cli.process_succeeded(upgrade.outcome):
        u.Tests.git_bootstrap(root, ("add", "-A"))
        u.Tests.git_bootstrap(root, ("commit", "-q", "-m", "upg: resolved locks"))
    _write_receipt(parent / _DETECTOR_UPGRADE_RECEIPT, upgrade)


_MAKE_TEMPLATES_FIXTURE = "resolved_make_templates"
_MAKE_UPGRADE_RECEIPT = c.Tests.MAKE_TEMPLATE_UPG_RECEIPT
_MAKE_CI_SETUP_RECEIPT = c.Tests.MAKE_TEMPLATE_CI_RECEIPT
_INFRA_CHECKOUT_FIXTURE = "provisioned_infra_checkout"
_INFRA_SETUP_RECEIPT = "setup-receipt.json"
# Every scenario that provisions the candidate's own environment before `gen`.
_INFRA_CHECKOUT_SCENARIOS = (
    "builtin",
    "custom",
    "producer-failure",
    "activation-failure",
)


def _run_scoped(kind: str, key: str) -> Path:
    """Return the run-scoped home of one provisioned consumer."""
    return Path(tempfile.gettempdir()) / kind / key


def _write_receipt(path: Path, output: p.Cli.CommandOutput) -> None:
    u.Tests.record_dependency_command_output(output)
    tm.ok(
        u.Cli.atomic_write_text_file(
            path,
            m.Cli.CommandOutput.model_validate(
                output, from_attributes=True
            ).model_dump_json(),
        )
    )


def _provision_make_template(profile: c.Infra.MakeProfile) -> None:
    """Resolve one generated consumer through ``make upg`` once per run.

    The upgrade runs under a foreign uv environment with a declared post-upg
    hook, and a checkout of the resolved result installs every locked tool
    into cold CI storage; both receipts are what the consumers assert.
    """
    parent = _run_scoped("make-templates", profile.value)
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
        )
    )
    _write_receipt(parent / _MAKE_UPGRADE_RECEIPT, upgrade)
    if not u.Cli.process_succeeded(upgrade.outcome):
        return
    checkout = u.Tests.resolved_make_checkout(
        root, parent / c.Tests.MAKE_TEMPLATE_CI_CHECKOUT, profile
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
                    parent / c.Tests.COLD_MISE_STORAGE
                ),
            },
        )
    )
    _write_receipt(parent / _MAKE_CI_SETUP_RECEIPT, setup)


def _provision_infra_checkout(scenario: str) -> None:
    """Set up one candidate checkout from its committed locks before its item."""
    parent = _run_scoped("infra-checkouts", scenario)
    root = u.Tests.infra_source_checkout(parent)
    setup = tm.ok(
        u.Tests.run_isolated_make(["--no-print-directory", "setup"], cwd=root)
    )
    _write_receipt(parent / _INFRA_SETUP_RECEIPT, setup)


def pytest_collection_finish(session: pytest.Session) -> None:
    """Provision every selected run-scoped consumer before any item runs.

    Network resolution and environment installation are provisioning, not the
    behaviour under test, so they never run inside an item's time budget.
    Workers of one run share the provisioned consumers; the first worker
    provisions one while the others wait on its lock and reuse its receipt.
    """
    functions = tuple(
        item for item in session.items if isinstance(item, pytest.Function)
    )
    detector = dict.fromkeys(
        tuple(
            t.Infra.STR_SEQ_ADAPTER.validate_python(
                item.callspec.params[_DETECTOR_FIXTURE]
            )
        )
        for item in functions
        if _DETECTOR_FIXTURE in item.fixturenames
    )
    profiles = (
        tuple(c.Infra.MakeProfile)
        if any(_MAKE_TEMPLATES_FIXTURE in item.fixturenames for item in functions)
        else ()
    )
    scenarios = dict.fromkeys(
        str(item.callspec.params[_INFRA_CHECKOUT_FIXTURE])
        for item in functions
        if _INFRA_CHECKOUT_FIXTURE in item.fixturenames
    )
    jobs = (
        *(
            (_detector_template_parent(modules), _DETECTOR_UPGRADE_RECEIPT, modules)
            for modules in detector
        ),
        *(
            (
                _run_scoped("make-templates", profile.value),
                _MAKE_UPGRADE_RECEIPT,
                profile,
            )
            for profile in profiles
        ),
        *(
            (_run_scoped("infra-checkouts", scenario), _INFRA_SETUP_RECEIPT, scenario)
            for scenario in scenarios
        ),
    )
    for parent, receipt, key in jobs:
        parent.mkdir(parents=True, exist_ok=True)
        with (parent.with_suffix(".lock")).open("a", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            if (parent / receipt).is_file():
                continue
            match key:
                case c.Infra.MakeProfile():
                    _provision_make_template(key)
                case str():
                    _provision_infra_checkout(key)
                case _:
                    _provision_detector_template(key)


@pytest.fixture
def resolved_make_templates() -> t.MappingKV[c.Infra.MakeProfile, Path]:
    """Return every profile's committed ``make upg`` template for this run.

    Consumers clone a template rather than resolving inside their budget; the
    template directory also holds the upgrade and cold CI setup receipts.
    """
    templates: dict[c.Infra.MakeProfile, Path] = {}
    for profile in c.Infra.MakeProfile:
        parent = _run_scoped("make-templates", profile.value)
        upgrade = u.Tests.command_receipt(parent / _MAKE_UPGRADE_RECEIPT)
        tm.that(
            u.Cli.process_succeeded(upgrade.outcome),
            eq=True,
            msg=upgrade.stdout + upgrade.stderr,
        )
        templates[profile] = parent / profile.value / "fixture-project"
    return templates


@pytest.fixture(params=_INFRA_CHECKOUT_SCENARIOS)
def provisioned_infra_checkout(request: pytest.FixtureRequest) -> t.Pair[str, Path]:
    """Return one scenario's candidate checkout, set up from committed locks."""
    scenario = str(request.param)
    parent = _run_scoped("infra-checkouts", scenario)
    setup = u.Tests.command_receipt(parent / _INFRA_SETUP_RECEIPT)
    tm.that(
        u.Cli.process_succeeded(setup.outcome), eq=True, msg=setup.stdout + setup.stderr
    )
    root = parent / config.Infra.name
    tm.that((root / ".venv" / "pyvenv.cfg").is_file(), eq=True)
    return scenario, root


@pytest.fixture(params=[("requests",)])
def real_detector_project(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """Check out the run's resolved detector consumer and set it up from its locks.

    The consumer clones the committed template exactly as a developer clones a
    reviewed repository, then ``make setup`` provisions its own environment
    from the committed locks without resolving anything new.
    """
    modules = t.Infra.STR_SEQ_ADAPTER.validate_python(request.param)
    parent = _detector_template_parent(modules)
    upgrade = m.Cli.CommandOutput.model_validate_json(
        (parent / _DETECTOR_UPGRADE_RECEIPT).read_text(encoding="utf-8")
    )
    tm.that(u.Cli.process_succeeded(upgrade.outcome), eq=True, msg=upgrade.stderr)
    root = tmp_path / _DETECTOR_PROJECT_NAME
    u.Tests.git_bootstrap(
        tmp_path, ("clone", "-q", str(parent / _DETECTOR_PROJECT_NAME), str(root))
    )
    u.Tests.initialize_git_repo(
        root,
        origin_url=u.Tests.repository_ref(
            root.name, role=c.Infra.MakeProfile.STANDALONE
        ).url,
    )
    setup = tm.ok(u.Tests.run_isolated_make(["setup"], cwd=root, capture=False))
    u.Tests.record_dependency_command_output(setup)
    tm.that(u.Cli.process_succeeded(setup.outcome), eq=True, msg=setup.stderr)
    tm.that((root / c.Infra.VENV_BIN_REL / c.Infra.DEPTRY).is_file(), eq=True)
    (root / "limits.toml").write_text(
        "[typing_libraries]\nexclude = []\n", encoding="utf-8"
    )
    return root


@pytest.fixture
def real_toml_project(tmp_path: Path) -> Path:
    """Create a real project with valid pyproject.toml."""
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
    """Create a real project with valid Makefile."""
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
    """Create a real Python package with src layout."""
    project_root = tmp_path / "python_package"
    project_root.mkdir()
    src_dir = project_root / "src" / "test_pkg"
    src_dir.mkdir(parents=True)
    (src_dir / "__init__.py").write_text('"""Test package."""\n__version__ = "0.1.0"\n')
    (src_dir / "identity.py").write_text(
        '"""Substantive unique source consumed by real scanner fixtures."""\n\n'
        "from __future__ import annotations\n\n"
        "def normalize_identity(parts: tuple[str, ...]) -> str:\n"
        '    """Normalize one ordered identity without duplicated code."""\n'
        "    normalized = tuple(part.strip() for part in parts if part.strip())\n"
        "    if not normalized:\n"
        '        raise ValueError("identity requires at least one non-empty part")\n'
        '    return "::".join(normalized).casefold()\n',
        encoding="utf-8",
    )
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "test-pkg"\nversion = "0.1.0"\n'
    )
    return project_root


@pytest.fixture
def cached_runner_project(tmp_path: Path) -> Path:
    """Create a real one-test consumer for the public cached pytest runner."""
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
        "def answer() -> int:\n    return 42\n", encoding="utf-8"
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
    """Create a real consumer whose suite violates the slow-timeout policy."""
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
    """Create the shared real workspace for the public refactor-mod CLI."""
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
        )
    )
    # A declared distribution owns a package: resolving the package name from
    # `[project].name` alone is impossible for a `flext-` distribution, so a
    # fixture without `src/<pkg>/` is not the project it claims to be.
    package_dir = (
        workspace / c.Infra.DEFAULT_SRC_DIR / (project.project.name.replace("-", "_"))
    )
    tm.ok(u.Cli.ensure_dir(package_dir))
    tm.ok(u.Cli.atomic_write_text_file(package_dir / c.Infra.INIT_PY, ""))
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
                '    """Stand-in infra namespace owning every name the fixture uses."""\n'
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
        )
    )
    package_dir = workspace / "src" / project.project.name.replace("-", "_")
    tm.ok(u.Cli.ensure_dir(package_dir))
    tm.ok(
        u.Cli.atomic_write_text_file(
            package_dir / c.Infra.INIT_PY,
            '"""Public refactor-mod fixture package."""\n\nfrom __future__ import annotations\n',
        )
    )
    u.Tests.initialize_git_repo(workspace)
    return workspace


@pytest.fixture
def real_workspace(tmp_path: Path) -> Path:
    """Create a real multi-project workspace."""
    repository_root = tmp_path / "workspace"
    repository_root.mkdir()
    (repository_root / "Makefile").write_text(
        ".PHONY: help\nhelp:\n\t@echo 'Workspace'\n"
    )
    (repository_root / "pyproject.toml").write_text(
        '[project]\nname = "workspace"\nversion = "0.1.0"\n'
    )
    for i in range(1, 4):
        project_dir = repository_root / f"project_{i}"
        project_dir.mkdir()
        (project_dir / "pyproject.toml").write_text(
            f'[project]\nname = "project-{i}"\nversion = "0.1.0"\n'
        )
        src_dir = project_dir / "src" / f"project_{i}"
        src_dir.mkdir(parents=True)
        (src_dir / "__init__.py").write_text(f'"""Project {i}."""\n')
    return repository_root


@pytest.fixture
def modernizer_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / c.PYPROJECT_FILENAME).write_text(
        _modernizer_workspace_pyproject(), encoding="utf-8"
    )
    u.Tests.write_beads_project(
        workspace, workspace="workspace", database="workspace", issue_prefix="workspace"
    )
    _write_modernizer_codegen_config(workspace)
    return workspace


@pytest.fixture
def modernizer_workspace_with_projects(modernizer_workspace: Path) -> Path:
    (modernizer_workspace / c.PYPROJECT_FILENAME).write_text(
        _modernizer_workspace_pyproject("selected", "ignored"), encoding="utf-8"
    )
    selected = u.Tests.mk_project(
        modernizer_workspace, "selected", pyproject=_modernizer_pyproject("selected")
    )
    ignored = u.Tests.mk_project(
        modernizer_workspace, "ignored", pyproject=_modernizer_pyproject("ignored")
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
    """Create a real project with documentation."""
    project_root = tmp_path / "docs_project"
    project_root.mkdir()
    docs_dir = project_root / "docs"
    docs_dir.mkdir()
    (docs_dir / "README.md").write_text("# Documentation\n")
    (docs_dir / "index.md").write_text("# Index\n")
    (project_root / "README.md").write_text("# Project\n")
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "docs-project"\nversion = "0.1.0"\n'
    )
    return project_root


@pytest.fixture
def rope_workspace(tmp_path: Path) -> t.Pair[t.Infra.RopeProject, Path]:
    """Create a real rope workspace with semantic-analysis fixtures."""
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
    rope_workspace: t.Pair[t.Infra.RopeProject, Path],
) -> t.Infra.RopeResource:
    """Return the Rope resource for the semantic models fixture module."""
    rope_project, repository_root = rope_workspace
    resource = u.Infra.get_resource_from_path(
        rope_project, repository_root / "src" / "rope_demo" / "models.py"
    )
    validated: t.Infra.RopeResource = tm.not_none(resource)
    return validated


@pytest.fixture
def services_resource(
    rope_workspace: t.Pair[t.Infra.RopeProject, Path],
) -> t.Infra.RopeResource:
    """Return the Rope resource for the semantic services fixture module."""
    rope_project, repository_root = rope_workspace
    resource = u.Infra.get_resource_from_path(
        rope_project, repository_root / "src" / "rope_demo" / "services.py"
    )
    validated: t.Infra.RopeResource = tm.not_none(resource)
    return validated
