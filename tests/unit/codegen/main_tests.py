"""Tests for the centralized codegen CLI group.

Validates CLI argument parsing, command dispatch, and exit codes
using real service instances with temporary workspaces.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import CliRouteService, c, config, main as infra_main
from tests import t, u


class TestsFlextInfraCodegenMain:
    """Test suite for the centralized codegen CLI group."""

    @staticmethod
    def _with_pep621_identity(repo: Path) -> Path:
        """Give the bare fixture repository the PEP 621 identity ``init`` derives from.

        The bootstrap projection reads declarations only: ``config/workspace.yaml``
        when present, otherwise the project name and its provider-matched
        Repository URL. A checkout with neither has no identity to render.
        """
        repository = u.Tests.repository_ref(repo.name)
        (repo / "pyproject.toml").write_text(
            f'[project]\nname = "{repository.distribution}"\nversion = "0.1.0"\n'
            f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\n'
            'authors = [{name = "FLEXT Team", email = "team@flext.dev"}]\n'
            'dependencies = ["flext-core>=0.1.0"]\n\n'
            f'[project.urls]\nRepository = "{repository.url}"\n',
            encoding="utf-8",
        )
        # Identity is not only PEP 621: a governed checkout also declares its own
        # ledger, and conform refuses to render without it.
        u.Tests.write_project_beads_config(repo, repository.distribution)
        # A governed checkout resolves its owner from the declared provider origin;
        # the default local-path origin is not a provider identity.
        u.Tests.initialize_git_repo(repo, origin_url=repository.url)
        return repo

    @staticmethod
    def _seed_public_conform_checkout(root: Path) -> None:
        """Seed a minimal governed package tree plus the real config and Mise inputs.

        The public CLI conform pipeline needs an importable ``src/flext_infra``
        package (for namespace/ruff discovery) and the real ``config/`` +
        tracked Mise seeds (``codegen conform`` validates the tracked,
        checksum-verified launchers rather than minting them). It does not need
        the full real package tree copied byte-for-byte: the minimal seed used by
        ``tests/unit/codegen/test_codegen_conform.py::_seed_infra_package_tree``
        already satisfies the same public conform contract at a fraction of the
        scan cost, so this fixture reuses that pattern instead of copying
        hundreds of real modules per test run.
        """
        project_root = Path(__file__).resolve().parents[3]
        package_init = root / "src" / "flext_infra" / "__init__.py"
        package_init.parent.mkdir(parents=True, exist_ok=True)
        tm.ok(u.Cli.atomic_write_text_file(package_init, ""))
        tests_init = root / "tests" / "__init__.py"
        tests_init.parent.mkdir(parents=True, exist_ok=True)
        tm.ok(u.Cli.atomic_write_text_file(tests_init, ""))
        tm.ok(
            u.Cli.files_copy_directory(
                project_root / "config", root / "config", dirs_exist_ok=True
            )
        )
        u.Tests.copy_tracked_mise_seeds(root)
        tm.ok(
            u.Cli.files_copy(
                project_root / c.Infra.MISE_TOML_FILENAME,
                root / c.Infra.MISE_TOML_FILENAME,
            )
        )

    @staticmethod
    def _mise_transaction_state(root: Path) -> t.Pair[Path, Path]:
        """Return the public workspace journal and root-project staging paths."""
        toolchain = config.Infra.codegen.toolchain
        state_root = (
            root.parent
            / toolchain.state_directory_name
            / root.name
            / toolchain.mise_namespace
        )
        return (
            state_root / "journal.json",
            state_root / "projects" / "root" / "transaction",
        )

    @staticmethod
    def _public_conform_command(root: Path) -> list[str]:
        """Build the real CLI command whose final argument selects check or apply."""
        return [
            sys.executable,
            "-m",
            "flext_infra",
            "codegen",
            "conform",
            "--root",
            str(root),
            "--scope",
            "self",
            "--mode",
        ]

    class TestsHandleLazyInit:
        """Tests for direct init command dispatch."""

        def test_success(self, real_git_repo: Path) -> None:
            """Init returns 0 on empty workspace."""
            result = infra_main([
                "codegen",
                "init",
                "--repository-root",
                str(TestsFlextInfraCodegenMain._with_pep621_identity(real_git_repo)),
            ])
            tm.that(result, eq=0)

        def test_check_mode(self, real_git_repo: Path) -> None:
            """Init check reports managed drift without mutating the repository."""
            repository = TestsFlextInfraCodegenMain._with_pep621_identity(real_git_repo)
            pyproject = repository / c.PYPROJECT_FILENAME
            before = pyproject.read_bytes()
            makefile = repository / c.Infra.MAKEFILE_FILENAME
            result = infra_main([
                "codegen",
                "init",
                "--check",
                "--repository-root",
                str(repository),
            ])
            tm.that(result, ne=0)
            tm.that(makefile.exists(), eq=False)
            tm.that(pyproject.read_bytes(), eq=before)

        def test_enforce_mode(self, real_git_repo: Path) -> None:
            """Init in enforce mode (not check)."""
            result = infra_main([
                "codegen",
                "init",
                "--repository-root",
                str(TestsFlextInfraCodegenMain._with_pep621_identity(real_git_repo)),
            ])
            tm.that(result, eq=0)

    class TestsMainCommandDispatch:
        """Tests for main() command routing."""

        def test_init_command(self, real_git_repo: Path) -> None:
            """main() with init command returns 0."""
            result = infra_main([
                "codegen",
                "init",
                "--repository-root",
                str(TestsFlextInfraCodegenMain._with_pep621_identity(real_git_repo)),
            ])
            tm.that(result, eq=0)

        def test_unknown_command(self) -> None:
            """main() with unknown command returns non-zero exit code."""
            result = infra_main(["codegen", "unknown-command"])
            tm.that(result, ne=0)

        def test_no_command(self) -> None:
            """main() with no command returns non-zero exit code."""
            result = infra_main(["codegen"])
            tm.that(result, ne=0)

        def test_init_rejects_nested_non_worktree_root(
            self, real_git_repo: Path
        ) -> None:
            """Initialization accepts only the exact Git worktree root."""
            custom_root = real_git_repo / "custom"
            custom_root.mkdir()
            result = infra_main([
                "codegen",
                "init",
                "--repository-root",
                str(TestsFlextInfraCodegenMain._with_pep621_identity(custom_root)),
            ])
            tm.that(result, ne=0)

    # Exemplar: every test here spawns a fresh interpreter to prove the real
    # `python -m flext_infra` entry point. That import chain, not the assertion,
    # dominates the runtime, so the class opts into the config-owned slow budget.
    @pytest.mark.slow
    class TestsMainEntryPoint:
        """Tests for the centralized process entrypoint."""

        def test_entry_point_returns_int(self, real_git_repo: Path) -> None:
            """main() returns an integer exit code."""
            result = infra_main([
                "codegen",
                "init",
                "--repository-root",
                str(TestsFlextInfraCodegenMain._with_pep621_identity(real_git_repo)),
            ])
            tm.that(type(result).__name__, eq="int")

        def test_entry_point_via_sys_exit(self) -> None:
            """The root process entrypoint serves the route owner's declared help."""
            route = next(
                item
                for item in CliRouteService.route_table_for(c.Infra.CLI_GROUP_CODEGEN)
                if item.name == "init"
            )
            result = u.Cli.run_raw([
                sys.executable,
                "-m",
                "flext_infra",
                c.Infra.CLI_GROUP_CODEGEN,
                route.name,
                "--help",
            ])
            tm.ok(result)
            tm.that(
                u.Cli.process_succeeded(result.value.outcome),
                eq=True,
                msg=result.value.stderr or result.value.stdout,
            )
            tm.that(" ".join(result.value.stdout.split()), contains=route.help_text)

        def test_managed_conflict_is_planned_and_published_atomically(
            self, infra_git_repo: Path
        ) -> None:
            """Keep live bytes unchanged until the public transaction commits."""
            root = infra_git_repo
            TestsFlextInfraCodegenMain._seed_public_conform_checkout(root)
            distribution = u.Tests.repository_ref(config.Infra.name).distribution
            (root / "pyproject.toml").write_text(
                f'[project]\nname = "{distribution}"\nversion = "0.12.0.dev0"\n'
                f'description = "{distribution} governed fixture"\n'
                f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\n'
                'authors = [{name = "FLEXT Team", email = "team@flext.dev"}]\n'
                'dependencies = ["flext-cli"]\n'
                "\n"
                "[tool.pytest.ini_options]\n"
                "addopts = [\n"
                '  "--timeout=10",\n'
                "]\n",
                encoding="utf-8",
            )
            pyproject = root / "pyproject.toml"
            before = pyproject.read_bytes()
            journal, transaction = TestsFlextInfraCodegenMain._mise_transaction_state(
                root
            )
            command = TestsFlextInfraCodegenMain._public_conform_command(root)
            checked = u.Cli.run_raw([*command, "check"], cwd=root)
            tm.ok(checked)
            tm.that(checked.value.outcome.raw_return_code, eq=1)
            tm.that(pyproject.read_bytes(), eq=before)
            tm.that(journal.exists(), eq=False)
            tm.that(transaction.exists(), eq=False)

            applied = u.Cli.run_raw([*command, "apply"], cwd=root)
            tm.ok(applied)
            tm.that(
                u.Cli.process_succeeded(applied.value.outcome),
                eq=True,
                msg=applied.value.stderr or applied.value.stdout,
            )
            rendered = pyproject.read_text(encoding="utf-8")
            tm.that(rendered, lacks="<<<<<<<")
            ini_options = u.Tests.toml_table_at(
                rendered, "tool", "pytest", "ini_options"
            )
            tm.that(
                ini_options["addopts"],
                has=(
                    f"--timeout={config.Infra.tooling.tools.pytest.case_timeout_seconds}"
                ),
            )
            tm.that(journal.exists(), eq=False)
            tm.that(transaction.exists(), eq=False)

            published = pyproject.read_bytes()
            fixed_point = u.Cli.run_raw([*command, "apply"], cwd=root)
            tm.ok(fixed_point)
            tm.that(
                u.Cli.process_succeeded(fixed_point.value.outcome),
                eq=True,
                msg=fixed_point.value.stderr or fixed_point.value.stdout,
            )
            tm.that(pyproject.read_bytes(), eq=published)
            tm.that(journal.exists(), eq=False)
            tm.that(transaction.exists(), eq=False)

        def test_present_invalid_mise_artifact_never_enters_external_resolution(
            self, infra_git_repo: Path
        ) -> None:
            """Reject a present invalid artifact before credential/network work."""
            root = infra_git_repo
            TestsFlextInfraCodegenMain._seed_public_conform_checkout(root)
            launcher = root / "bin" / "mise"
            launcher_state = tm.ok(
                u.Cli.atomic_read_binary_file_state(launcher, required=True)
            )
            launcher_mode = launcher_state.mode
            tm.that(launcher_mode is None, eq=False)
            if launcher_mode is None:
                msg = "required Mise launcher has no permission mode"
                raise AssertionError(msg)
            if launcher_state.content is None:
                msg = "required Mise launcher has no bytes"
                raise AssertionError(msg)
            corrupted = launcher_state.content + b"\nchecksum_linux_x86_64=invalid\n"
            tm.ok(
                u.Cli.atomic_write_binary_file_guarded(
                    launcher_state, corrupted, permission_mode=launcher_mode
                )
            )
            journal, transaction = TestsFlextInfraCodegenMain._mise_transaction_state(
                root
            )

            applied = u.Cli.run_raw(
                [*TestsFlextInfraCodegenMain._public_conform_command(root), "apply"],
                cwd=root,
                env={"MISE_GITHUB_CREDENTIAL_COMMAND": ""},
            )

            tm.ok(applied)
            tm.that(applied.value.outcome.raw_return_code, eq=1)
            tm.that(
                applied.value.stdout + applied.value.stderr,
                lacks="MISE_GITHUB_CREDENTIAL_COMMAND is required",
            )
            tm.that(launcher.read_bytes(), eq=corrupted)
            tm.that(journal.exists(), eq=False)
            tm.that(transaction.exists(), eq=False)

        def test_unknown_command_surfaces_root_cause_via_subprocess(self) -> None:
            """Unknown codegen subcommands must print the actual CLI failure."""
            # The child renders through the CLI console, which honours COLUMNS and
            # would otherwise wrap the message at the developer's terminal width,
            # splitting the asserted phrase. Pin the width so the assertion tests
            # the message, not the terminal the suite happens to run in.
            result = u.Cli.run_raw(
                [sys.executable, "-m", "flext_infra", "codegen", "unknown-command"],
                env={"COLUMNS": "200"},
            )

            tm.ok(result)
            tm.that(result.value.outcome.raw_return_code, eq=2)
            tm.that(
                result.value.stdout + result.value.stderr,
                contains="No such command 'unknown-command'",
            )
