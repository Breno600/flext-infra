"""Tooling and executable-environment fixture test utilities for flext-infra.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from textwrap import indent

from flext_infra import config, u
from tests import c, m, p, t
from tests.utilities_git import TestsFlextInfraUtilitiesGitMixin


class TestsFlextInfraUtilitiesToolingFixtureMixin:
    """Executable, Make, and toolchain-environment fixture helpers."""

    @staticmethod
    def mypy_deadline_limit() -> m.Infra.MypyResourceLimit:
        """Reserve harness startup and cleanup inside the configured slow budget.

        Returns:
            The resulting ``m.Infra.MypyResourceLimit``.

        """
        policy = config.Infra.tooling.tools.pytest
        available = (
            policy.slow_timeout_seconds
            - c.Infra.MYPY_TIMEOUT_GRACE_SECONDS
            - policy.termination_grace_seconds
        )
        return m.Infra.MypyResourceLimit(
            memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
            timeout_seconds=min(
                config.Infra.tooling.tools.mypy.timeout_seconds,
                available // 2,
            ),
        )

    @staticmethod
    def reap_mypy_descendant(pid_file: Path, timeout: int) -> None:
        """Reap a registered workload in pytest teardown, preserving call failures.

        Raises:
            RuntimeError: If ``snapshot.outcome.raw_return_code not in {0, 1} or
                snapshot.stderr``.

        """
        pid = pid_file.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        snapshot = u.Cli.run_raw(
            ("/bin/ps", "-p", str(int(pid)), "-o", "stat="),
            timeout=timeout,
        ).unwrap()
        if snapshot.outcome.raw_return_code not in {0, 1} or snapshot.stderr:
            raise RuntimeError(snapshot.stderr)
        state = snapshot.stdout.strip()
        if state and not state.startswith("Z"):
            u.Cli.run(("/bin/kill", "-KILL", pid), timeout=timeout).unwrap()

    @staticmethod
    def mypy_workload(root: Path, plugin_body: str = "") -> m.Infra.MypyInvocation:
        """Create a real checker project with an optional workload plugin.

        Returns:
            The resulting ``m.Infra.MypyInvocation``.

        """
        source = root / "checked.py"
        source.write_text("value: int = 1\n", encoding=c.Cli.ENCODING_DEFAULT)
        config_file = root / "mypy.ini"
        # The workload checks through the governed checker settings, so its
        # crash reporting (show_traceback) matches every managed project.
        config_source = "[mypy]\n" + "".join(
            f"{key} = {value}\n"
            for key, value in config.Infra.tooling.tools.mypy.boolean_settings.items()
        )
        if plugin_body:
            plugin = root / "workload.py"
            plugin.write_text(
                "from mypy.plugin import Plugin\n\n"
                "def plugin(version: str) -> type[Plugin]:\n"
                + indent(plugin_body, "    ")
                + "\n    return Plugin\n",
                encoding=c.Cli.ENCODING_DEFAULT,
            )
            config_source += f"plugins = {plugin}\n"
        config_file.write_text(config_source, encoding=c.Cli.ENCODING_DEFAULT)
        return m.Infra.MypyInvocation(targets=(source,), config_file=config_file)

    @staticmethod
    def create_python_environment(root: Path) -> p.Result[bool]:
        """Provision a physical fixture environment with the current interpreter.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        environment = u.Infra.runtime_environment_dir(root)
        environment.parent.mkdir(parents=True, exist_ok=True)
        return u.Cli.run_checked(
            ["uv", "venv", "--python", sys.executable, str(environment)],
            cwd=root,
        )

    @staticmethod
    def provision_checkout(root: Path) -> None:
        """Make a fixture root a checkout whose environment owns the edit tools.

        Protected edits resolve every ``c.Infra.LINT_TOOLS`` executable plus
        python and pytest fail-closed from the checkout's runtime environment
        (``u.Infra.runtime_environment_dir``), which requires a Git checkout.
        The fixture becomes one through the single fixture Git owner and
        receives the real binaries this suite was provisioned with, linked
        inside the pytest-managed tree; a missing tool fails the fixture.

        Raises:
            FileExistsError: If fixture tool conflicts with provisioned executable; or
                if fixture tool path is already occupied.
            FileNotFoundError: If setup did not provision.

        """
        # Provisioning a runtime never rewrites a checkout's declared identity:
        # an existing checkout keeps its origin, only a bare root becomes one.
        if not (root / c.Infra.GIT_DIR).exists():
            TestsFlextInfraUtilitiesGitMixin.initialize_git_repo(root)
        provisioned = Path(sys.executable).parent
        bin_dir = u.Infra.runtime_environment_dir(root) / provisioned.name
        bin_dir.mkdir(parents=True, exist_ok=True)
        tools = {command[0] for _, command in c.Infra.LINT_TOOLS}
        for name in sorted(tools | {c.Infra.PYTHON, c.Infra.PYTEST}):
            source = provisioned / name
            if not source.is_file():
                msg = f"setup did not provision {name}: {source}"
                raise FileNotFoundError(msg)
            destination = bin_dir / name
            if destination.is_symlink():
                if destination.resolve(strict=True) == source.resolve(strict=True):
                    continue
                msg = (
                    f"fixture tool conflicts with provisioned executable: {destination}"
                )
                raise FileExistsError(msg)
            if destination.exists():
                msg = f"fixture tool path is already occupied: {destination}"
                raise FileExistsError(msg)
            destination.symlink_to(source)

    @staticmethod
    def make_read_only(path: Path) -> None:
        """Make one fixture path read-only."""
        path.chmod(0o444)

    @staticmethod
    def isolated_mise_bootstrap_storage(project_root: Path) -> Path:
        """Provision one hermetic Mise bootstrap storage for a fixture run.

        The product contract (``u.Infra.mise_bootstrap_environment``) names
        ``MISE_DATA_DIR`` the storage root variable; a fixture that passes it
        makes the real bootstrap hermetic instead of racing the shared
        operator storage, and only a cold storage exercises the credential
        boundaries a warm install silently skips. The directory sits beside
        — never inside — the fixture checkout the generated Make rejects as
        storage, and inside the pytest-managed tree so teardown reclaims it.

        Returns:
            The resulting ``Path``.

        """
        storage = project_root.parent / "mise-data"
        storage.mkdir(parents=True, exist_ok=True)
        return storage

    @staticmethod
    def copy_tracked_mise_seeds(root: Path, *, source_root: Path | None = None) -> None:
        """Copy declared Mise inputs from this checkout or a native upgrade seed.

        A governed repository carries the declaration, launchers, runtime pin,
        and dependency lock together. Native dependency graphs referenced by
        the lock must travel with it so frozen setup never resolves replacements.
        Conform renders declarations; only ``make upg`` resolves new versions.
        """
        source_root = (
            Path(__file__).resolve().parents[1] if source_root is None else source_root
        )
        for relative in (
            c.Infra.MISE_TOML_FILENAME,
            c.Infra.MISE_LOCK_FILENAME,
            *c.Infra.ARTIFACT_NAMES,
        ):
            source = source_root / relative
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            _ = shutil.copy2(source, destination)
        sidecars = Path(".mise/locks")
        if (source_root / sidecars).is_dir():
            _ = shutil.copytree(
                source_root / sidecars,
                root / sidecars,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("mise*.local"),
            )

    @staticmethod
    def write_executable(path: Path, body: str) -> None:
        """Write one executable fixture with deterministic permissions."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding=c.Cli.ENCODING_DEFAULT)
        path.chmod(0o755)

    @staticmethod
    def run_isolated_make(
        args: t.StrSequence,
        *,
        cwd: Path,
        env: t.StrMapping | None = None,
        capture: bool = True,
    ) -> p.Result[p.Cli.CommandOutput]:
        """Run Make without undeclared state inherited from outer pytest.

        The network bootstrap asks gh for a token when no GITHUB_TOKEN is set.
        gh here reads no configuration (``os.devnull`` is not a directory) and
        reaches no keyring (the session bus is disabled), so the host
        operator's stored credential never enters a test.

        Returns:
            The resulting ``p.Result[p.Cli.CommandOutput]``.

        """
        return u.Cli.run_raw(
            [c.Infra.MAKE, *args],
            cwd=cwd,
            env={
                "GH_CONFIG_DIR": os.devnull,
                "DBUS_SESSION_BUS_ADDRESS": "disabled:",
                **(env or {}),
            },
            capture=capture,
            remove_env_keys=tuple(
                key
                for key in c.Tests.MAKE_ISOLATION_ENV_KEYS
                if env is None or key not in env
            ),
        )

    @staticmethod
    def is_docker_available() -> bool:
        """Return whether Docker is available to integration tests.

        Returns:
            Whether Docker is available to integration tests.

        """
        return shutil.which("docker") is not None

    @staticmethod
    def cli_shim(bin_dir: Path, name: str) -> Path:
        """Provide an executable that records its arguments instead of reaching a service.

        ``gh`` and ``uv publish`` talk to GitHub and to a package index; a
        unit test proves the protocol's command contract against a recorded
        invocation, never against the real remote.

        Returns:
            The resulting ``Path``.

        """
        bin_dir.mkdir(parents=True, exist_ok=True)
        log = bin_dir / f"{name}.log"
        shim = bin_dir / name
        # A ``view`` of a release or pull request answers "absent" (exit 1),
        # the state every first publication starts from.
        shim.write_text(
            "#!/bin/sh\n"
            f'printf "%s\\n" "$*" >> "{log}"\n'
            'case "$2" in view) exit 1 ;; esac\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)
        return log


__all__: list[str] = ["TestsFlextInfraUtilitiesToolingFixtureMixin"]
