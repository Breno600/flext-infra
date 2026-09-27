"""Shared fixtures for the declarative project-layout engine tests."""

from __future__ import annotations

from pathlib import Path

from flext_infra import config
from flext_infra.codegen.layout import FlextInfraCodegenLayout
from tests import u


def build_loose_project(tmp_path: Path, name: str = "flext-demo") -> Path:
    """Create a minimal project carrying one violation of each layout kind."""
    project = tmp_path / name
    package_dir = project / "src" / name.replace("-", "_")
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    # The project's identity is its declared [project].name, so the fixture
    # declares the name it was asked for — never a directory-derived guess.
    (project / "pyproject.toml").write_text(
        f"[project]\nname='{name}'\nversion='0.1.0'\n", encoding="utf-8"
    )
    (project / "README.md").write_text("# demo\n", encoding="utf-8")
    guides = project / "guides"
    guides.mkdir()
    (guides / "intro.md").write_text("intro\n", encoding="utf-8")
    (project / "index.md").write_text("index\n", encoding="utf-8")
    (project / "output.log").write_text("log-line\n", encoding="utf-8")
    (project / "loose.txt").write_text("unknown\n", encoding="utf-8")
    u.Tests.declare_workspace_projects(tmp_path, (name,))
    # A layout plan reads tracked state from the project's own repository;
    # the fixture never borrows an enclosing checkout's index.
    u.Tests.initialize_git_repo(project)
    return project


def layout_engine(
    repository_root: Path, *, apply_changes: bool = False
) -> FlextInfraCodegenLayout:
    """Build the layout service over one fixture repository root.

    Apply mode journals through the generation transaction, whose receipt
    resolves the Git identity of the owning checkout, so the fixture root is
    initialized as a repository exactly like every governed checkout.
    """
    if not (repository_root / ".git").exists():
        provider = u.Tests.provider()
        governed_url = f"{provider.base_url.rstrip('/')}/{repository_root.name}.git"
        u.Tests.initialize_git_repo(repository_root, origin_url=governed_url)
        u.Tests.write_project_beads_config(repository_root, repository_root.name)
        root_pyproject = repository_root / "pyproject.toml"
        if not root_pyproject.is_file():
            root_pyproject.write_text(
                f"[project]\nname='{repository_root.name}'\nversion='0.1.0'\n",
                encoding="utf-8",
            )
        gitmodules = repository_root / ".gitmodules"
        if gitmodules.is_file():
            for project_path in gitmodules.read_text(encoding="utf-8").splitlines():
                if project_path.startswith("\tpath = "):
                    member = repository_root / project_path.removeprefix("\tpath = ")
                    if member.is_dir():
                        member_url = (
                            f"{provider.base_url.rstrip('/')}/{member.name}.git"
                        )
                        u.Tests.initialize_git_repo(member, origin_url=member_url)
                        u.Tests.write_project_beads_config(member, member.name)
    return FlextInfraCodegenLayout(
        repository_root=repository_root, apply_changes=apply_changes
    )


def archive_root() -> str:
    """Archive root from the same typed SSOT the engine consumes."""
    return config.Infra.codegen.layout.archive_root
