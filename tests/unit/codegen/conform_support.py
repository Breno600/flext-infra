"""Public functional contract for new and existing project conformance.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from difflib import unified_diff
from pathlib import Path

from flext_tests import tm

from flext_infra import config
from flext_infra.codegen import FlextInfraCodegenConform
from tests import c, m, t, u


class TestsFlextInfraConformSupport:
    """Shared project fixtures for conformance and Make runtime contracts."""

    @staticmethod
    def conform_target(
        root: Path,
        repository: m.Infra.RepositoryRef,
        *,
        make_profile: c.Infra.MakeProfile,
    ) -> m.Infra.RepositoryConformTarget:
        """Build the current public target without retired branch-policy fields."""
        return m.Infra.RepositoryConformTarget(
            repository=repository,
            root=root,
            make_profile=make_profile,
            beads=u.Tests.beads_project(repository.name),
            canonical_project_name=repository.distribution,
            ci_enabled=True,
        )

    @staticmethod
    def standalone_workspace(root: Path) -> m.Infra.WorkspaceSpec:
        """Load the smallest repository-local topology for conform tests."""
        return u.Tests.standalone_workspace(root)

    @staticmethod
    def apply_conform_surface(
        root: Path,
        workspace: m.Infra.WorkspaceSpec,
        surface: c.Infra.CodegenConformSurface,
    ) -> None:
        """Materialize one exact public conform surface for a focused test."""
        tm.ok(
            FlextInfraCodegenConform.execute_request(
                u.Tests.conform_request(
                    root,
                    what=surface,
                    scope=c.Infra.CodegenConformScope.SELF,
                    mode=c.Infra.CodegenConformMode.APPLY,
                ),
                initial_workspace=workspace,
            )
        )

    @staticmethod
    def project_tree(root: Path) -> t.VariadicTuple[t.Pair[str, bytes]]:
        """Return the versionable project tree independently of Git test fixtures."""
        return tuple(
            sorted(
                (path.relative_to(root).as_posix(), path.read_bytes())
                for path in root.rglob("*")
                if path.is_file()
                and ".git" not in path.relative_to(root).parts
                and ".infra-baseline" not in path.relative_to(root).parts
            )
        )

    @staticmethod
    def project_tree_diff(
        expected: t.VariadicTuple[t.Pair[str, bytes]],
        actual: t.VariadicTuple[t.Pair[str, bytes]],
    ) -> str:
        """Render only differing generated files when a fixed-point contract fails."""
        expected_files = dict(expected)
        actual_files = dict(actual)
        return "\n".join(
            line
            for path in sorted(expected_files.keys() | actual_files.keys())
            if expected_files.get(path) != actual_files.get(path)
            for line in unified_diff(
                expected_files.get(path, b"").decode(errors="replace").splitlines(),
                actual_files.get(path, b"").decode(errors="replace").splitlines(),
                fromfile=f"created/{path}",
                tofile=f"conformed/{path}",
                lineterm="",
            )
        )

    @staticmethod
    def seed_infra_package_tree(root: Path) -> None:
        """Seed the minimal flext-infra tree (pyproject, src package, tests package).

        The conform templates materialize tests/fixtures/ci/docker/*, and the
        existing-tree tooling render discovers python roots from directories that
        exist on disk (env_dirs). Seeding tests/ makes the first render match the
        post-apply fixed point.
        """
        dist = u.Tests.repository_ref(config.Infra.name).distribution
        tm.ok(
            u.Cli.atomic_write_text_file(
                root / "pyproject.toml",
                f'[project]\nname = "{dist}"\nversion = "0.12.0.dev0"\n'
                'description = "Existing repository fixture"\n'
                f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\n'
                'authors = [{name = "FLEXT Team", email = "team@flext.dev"}]\n'
                'dependencies = ["flext-cli"]\n',
            )
        )
        package_init = root / "src" / "flext_infra" / "__init__.py"
        package_init.parent.mkdir(parents=True, exist_ok=True)
        tm.ok(u.Cli.atomic_write_text_file(package_init, ""))
        tests_init = root / "tests" / "__init__.py"
        tests_init.parent.mkdir(parents=True, exist_ok=True)
        tm.ok(u.Cli.atomic_write_text_file(tests_init, ""))

    @staticmethod
    def self_check_conform_service(
        root: Path,
    ) -> t.Pair[FlextInfraCodegenConform, m.Infra.CodegenConformRequest]:
        """Materialize the standalone root fixture and its CHECK-mode conform service."""
        repository = u.Tests.repository_ref("flext-infra").model_copy(
            update={"path": Path()}
        )
        workspace = u.Tests.workspace_spec(
            repository, project=u.Tests.project_spec(repository.name)
        )
        (root / "pyproject.toml").write_text(
            f"[project]\nname = '{repository.distribution}'\nversion = '0.1.0'\n",
            encoding="utf-8",
        )
        package = root / "src" / repository.distribution.replace("-", "_")
        package.mkdir(parents=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
        request = u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        service = FlextInfraCodegenConform(
            repository_root=root, request=request, initial_workspace=workspace
        )
        return service, request
