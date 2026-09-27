"""Pytest fixtures for FLEXT infra tests.

Provides reusable fixtures for creating real project structures using tmp_path.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, infra
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import c, m, t, u

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


@pytest.fixture(params=[("requests",)])
def real_detector_project(tmp_path: Path, request: pytest.FixtureRequest) -> Path:
    """Provision a real isolated detector consumer through generated Make upgrade."""
    modules = t.Infra.STR_SEQ_ADAPTER.validate_python(request.param)
    distributions = {
        "requests": "requests",
        "dateutil": "python-dateutil",
        "yaml": "pyyaml",
    }
    dependencies = ", ".join(f'"{distributions[name]}"' for name in modules)
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
        tmp_path,
        "detector-fixture",
        with_src=True,
        pyproject=(
            '[build-system]\nrequires = ["hatchling"]\nbuild-backend = "hatchling.build"\n'
            '[project]\nname = "detector-fixture"\nversion = "0.1.0"\n'
            f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\n'
            f"dependencies = [{dependencies}]\n"
            '[project.optional-dependencies]\nfeature = ["requests"]\n'
            '[dependency-groups]\ndev = ["deptry", "mypy", "pip", '
            f'"{infrastructure.distribution} @ git+{infrastructure.url}@{integration.branch}"]\n'
            "[tool.mypy]\n"
            '[tool.deptry]\npep621_dev_dependency_groups = ["dev"]\n'
        ),
    )
    (root / "src" / "detector_fixture" / "__init__.py").write_text(
        "\n".join(f"import {name}" for name in modules) + "\n", encoding="utf-8"
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
    # A newly scaffolded consumer has no committed locks yet; the full upgrade
    # lifecycle is the consumer's own first landing, not this suite's unit.
    # The detector's dependency boundary is the deptry executable itself, so
    # the fixture provisions a physical environment with a real recording
    # deptry: the offline run still proves the command contract and every
    # invocation is receipted next to the boundary.
    environment = tm.ok(u.Tests.create_python_environment(root))
    _ = environment
    u.Tests.copy_tracked_mise_seeds(root)
    u.Tests.write_executable(
        root / c.Infra.VENV_BIN_REL / c.Infra.DEPTRY,
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$0.invocations.log"\n'
        'printf \'{"issues": []}\\n\'\n'
        "exit 0\n",
    )
    u.Tests.write_executable(
        root / c.Infra.VENV_BIN_REL / "uv",
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$0.invocations.log"\n'
        'printf \'{"issues": []}\\n\'\n'
        "exit 0\n",
    )
    (root / "uv.lock").write_text(
        'version = 1\nrequires-python = ">=3.13"\n\n[options]\nexclude-newer = ""\n',
        encoding=c.Cli.ENCODING_DEFAULT,
    )
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
            workspace / c.Infra.PYPROJECT_FILENAME,
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
    (workspace / c.Infra.PYPROJECT_FILENAME).write_text(
        _modernizer_workspace_pyproject(), encoding="utf-8"
    )
    u.Tests.write_beads_project(
        workspace, workspace="workspace", database="workspace", issue_prefix="workspace"
    )
    _write_modernizer_codegen_config(workspace)
    return workspace


@pytest.fixture
def modernizer_workspace_with_projects(modernizer_workspace: Path) -> Path:
    (modernizer_workspace / c.Infra.PYPROJECT_FILENAME).write_text(
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
