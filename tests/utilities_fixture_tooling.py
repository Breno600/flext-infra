"""Tooling and executable-environment fixture test utilities for flext-infra."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from flext_infra import u
from tests import c, p, t


class TestsFlextInfraUtilitiesToolingFixtureMixin:
    """Executable, Make, and toolchain-environment fixture helpers."""

    @staticmethod
    def create_python_environment(root: Path) -> p.Result[bool]:
        """Provision a physical fixture environment with the current interpreter."""
        return u.Cli.run_checked(
            ["uv", "venv", "--python", sys.executable, str(root / ".venv")], cwd=root
        )

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
            c.Infra.MISE_VERSION_PIN_FILENAME,
            "bin/mise",
            "bin/mise.cmd",
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
        """Run Make without undeclared state inherited from outer pytest."""
        return u.Cli.run_raw(
            [c.Infra.MAKE, *args],
            cwd=cwd,
            env=env,
            capture=capture,
            remove_env_keys=tuple(
                key
                for key in c.Tests.MAKE_ISOLATION_ENV_KEYS
                if env is None or key not in env
            ),
        )

    @staticmethod
    def is_docker_available() -> bool:
        """Return whether Docker is available to integration tests."""
        return shutil.which("docker") is not None

    @staticmethod
    def cli_shim(bin_dir: Path, name: str) -> Path:
        """Provide an executable that records its arguments instead of reaching a service.

        ``gh`` and ``uv publish`` talk to GitHub and to a package index; a
        unit test proves the protocol's command contract against a recorded
        invocation, never against the real remote.
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
