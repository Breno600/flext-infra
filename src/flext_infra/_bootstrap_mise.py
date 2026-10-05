# Copyright 2026 FLEXT
"""Bootstrap Mise reconcile and converge in an isolated pinned-Mise environment.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import shutil
import tempfile
import tomllib
from pathlib import Path

from flext_infra import c, t, u
from flext_infra._bootstrap_transaction import FlextInfraBootstrapTransactionMixin

STORAGE_DIRECTORIES = ("cache", "state", "installs", "shims", "uv-cache", "bootstrap")
"""Persistent Mise storage layout (mirrors the bootstrap recipe contract)."""


class FlextInfraBootstrapMiseMixin(FlextInfraBootstrapTransactionMixin):
    """Rebuild or hold a mise.lock the pinned Mise release satisfies."""

    @staticmethod
    def _mise_storage_root() -> Path:
        """Resolve the persistent Mise storage the bootstrap recipe declared.

        Returns:
            The resulting ``Path``.

        Raises:
            ValueError: If MISE_DATA_DIR, XDG_DATA_HOME, or HOME must identify Mise
                storage.
        """
        override = u.Cli.env_read("MISE_DATA_DIR", dict(os.environ)).unwrap()
        if override:
            return Path(override)
        data_home = u.Cli.env_read("XDG_DATA_HOME", dict(os.environ)).unwrap()
        if data_home:
            return Path(data_home) / "mise"
        home = u.Cli.env_read("HOME", dict(os.environ)).unwrap()
        if home:
            return Path(home) / ".local/share/mise"
        msg = "MISE_DATA_DIR, XDG_DATA_HOME, or HOME must identify Mise storage"
        raise ValueError(msg)

    @classmethod
    def _pinned_runtime(cls, storage: Path, release: str) -> Path:
        """Locate the installed Mise runtime the pin names (layout from config).

        Returns:
            The resulting ``Path``.

        Raises:
            ValueError: If missing pinned Mise runtime.
        """
        base = storage / "bootstrap"
        suffix = ".exe" if os.name == "nt" else ""
        exact = base / f"mise-{release.lstrip('v')}{suffix}"
        if exact.is_file() and os.access(exact, os.X_OK):
            return exact
        candidates = sorted(base.glob(f"mise-{release.lstrip('v')}*"))
        for candidate in candidates:
            if candidate.is_file() and os.access(candidate, os.X_OK):
                return candidate
        msg = f"missing pinned Mise runtime {exact}; run make setup"
        raise ValueError(msg)

    @staticmethod
    def _manifest_settings(manifest: Path) -> tuple[str, str]:
        """Read the cooldown and lockfile platforms the manifest projects.

        Returns:
            The resulting ``tuple[str, str]``.

        Raises:
            ValueError: If Mise manifest has no settings table; or if Mise manifest
                lacks cooldown or lockfile platforms.
        """
        payload = tomllib.loads(manifest.read_text(encoding="utf-8"))
        settings = payload.get("settings")
        if not isinstance(settings, dict):
            msg = f"Mise manifest has no settings table: {manifest}"
            raise ValueError(msg)
        cooldown = settings.get("minimum_release_age")
        platforms = settings.get("lockfile_platforms")
        if not isinstance(cooldown, str) or not isinstance(platforms, list):
            msg = f"Mise manifest lacks cooldown or lockfile platforms: {manifest}"
            raise ValueError(msg)
        return cooldown, ",".join(str(platform) for platform in platforms)

    @staticmethod
    def _mise_environment(
        storage: Path,
        stage: Path,
        scratch: Path,
        cooldown: str,
        platforms: str,
    ) -> t.StrDict:
        """Build the isolated Mise environment the bootstrap recipe runs in.

        Returns:
            The resulting ``t.StrDict``.
        """
        for name in (
            "home",
            "appdata",
            "config",
            "tmp",
            "xdg-config",
            "xdg-data",
            "xdg-cache",
            "xdg-state",
            "system-config",
        ):
            (scratch / name).mkdir(parents=True, exist_ok=True)
        (scratch / "global-config.toml").write_bytes(b"")
        (scratch / "system-config" / "config.toml").write_bytes(b"")
        environment = {
            "HOME": str(scratch / "home"),
            "USERPROFILE": str(scratch / "home"),
            "APPDATA": str(scratch / "appdata"),
            "LOCALAPPDATA": str(scratch / "appdata"),
            "XDG_CONFIG_HOME": str(scratch / "xdg-config"),
            "XDG_DATA_HOME": str(scratch / "xdg-data"),
            "XDG_CACHE_HOME": str(scratch / "xdg-cache"),
            "XDG_STATE_HOME": str(scratch / "xdg-state"),
            "MISE_CONFIG_DIR": str(scratch / "config"),
            "MISE_SYSTEM_CONFIG_DIR": str(scratch / "system-config"),
            "MISE_SYSTEM_CONFIG_FILE": str(scratch / "system-config" / "config.toml"),
            "MISE_TMP_DIR": str(scratch / "tmp"),
            "TMPDIR": str(scratch / "tmp"),
            "TMP": str(scratch / "tmp"),
            "TEMP": str(scratch / "tmp"),
            "MISE_DATA_DIR": str(storage),
            "MISE_CACHE_DIR": str(storage / "cache"),
            "MISE_STATE_DIR": str(storage / "state"),
            "MISE_INSTALLS_DIR": str(storage / "installs"),
            "MISE_SHIMS_DIR": str(storage / "shims"),
            "UV_CACHE_DIR": str(storage / "uv-cache"),
            "MISE_TRUSTED_CONFIG_PATHS": str(stage),
            "MISE_LOCKFILE": "true",
            "MISE_LOCKED": "true",
            "MISE_QUIET": "1",
            "MISE_NETRC": "false",
            "MISE_HTTP_RETRIES": "0",
            "MISE_MINIMUM_RELEASE_AGE": cooldown,
            "MISE_LOCKFILE_PLATFORMS": platforms,
            "GIT_TERMINAL_PROMPT": "0",
            "LANG": "C",
            "LC_ALL": "C",
            "PATH": "/usr/bin:/bin",
        }
        token = u.Cli.env_read("GITHUB_TOKEN", dict(os.environ)).unwrap()
        if token:
            environment["GITHUB_TOKEN"] = token
        return environment

    @classmethod
    def _run(
        cls,
        runtime: Path,
        arguments: list[str],
        environment: t.StrDict,
    ) -> str:
        """Run one isolated Mise command; warnings and failures escape loudly.

        Returns:
            The resulting ``str``.

        Raises:
            ValueError: If Mise exited; or if Mise warned during.
        """
        completed = cls._checked("Mise", [str(runtime), *arguments], environment)
        if "mise WARN" in completed.stdout or "mise WARN" in completed.stderr:
            msg = f"Mise warned during {' '.join(arguments)}; reconcile stopped"
            raise ValueError(msg)
        return completed.stdout.strip()

    @classmethod
    def _probe_stage(
        cls,
        runtime: Path,
        stage: Path,
        environment: t.StrDict,
    ) -> tuple[bool, str]:
        """Prove the staged lock installs without mutating tools.

        Returns:
            The resulting ``tuple[bool, str]``: satisfaction and the raw probe
            diagnostics.
        """
        completed = cls._spawn(
            [str(runtime), "-C", str(stage), "install", "--dry-run"],
            environment,
        )
        return (
            u.Cli.process_succeeded(completed.outcome),
            completed.stdout + completed.stderr,
        )

    @classmethod
    def _staged_lock_satisfies(
        cls,
        runtime: Path,
        stage: Path,
        environment: t.StrDict,
    ) -> bool:
        """Prove the staged lock satisfies the manifest without mutating tools.

        Returns:
            The resulting ``bool``.
        """
        satisfied, _ = cls._probe_stage(runtime, stage, environment)
        return satisfied

    @staticmethod
    def failing_install_tools(probe_output: str) -> list[tuple[str, str]]:
        """Extract the ``selector@version`` pairs a failed install probe named.

        Returns:
            The resulting ``list[tuple[str, str]]`` of failing tool selectors
            and their (``v``-stripped) versions, in the order Mise named them.

        Raises:
            ValueError: If the probe diagnostics name no failing tool.
        """
        tools: list[tuple[str, str]] = []
        for line in probe_output.splitlines():
            marker = "Failed to install tools:"
            if marker not in line:
                continue
            for item in line.split(marker, 1)[1].split(","):
                selector, _, version = item.strip().rpartition("@")
                version = version.strip().lstrip("v")
                if selector and version and version[0].isdigit():
                    tools.append((selector, version))
        if not tools:
            msg = (
                "staged install failed but named no failing tool:"
                f" {probe_output.strip()[:400]}"
            )
            raise ValueError(msg)
        return tools

    @classmethod
    def remote_release_candidates(
        cls,
        runtime: Path,
        environment: t.StrDict,
        selector: str,
        failed_version: str,
        limit: int = 8,
    ) -> list[str]:
        """List install candidates strictly older than the failed release.

        Returns:
            The resulting ``list[str]`` of semantic releases, newest first,
            capped at ``limit``.

        Raises:
            ValueError: If Mise exited or warned during the listing.
        """

        def release_key(version: str) -> tuple[int, ...] | None:
            try:
                return tuple(int(part) for part in version.split("."))
            except ValueError:
                return None

        failed = release_key(failed_version)
        candidates: list[str] = []
        listing = cls._run(runtime, ["ls-remote", selector], environment)
        for line in listing.splitlines():
            version = line.strip().lstrip("v")
            parsed = release_key(version)
            if parsed is None:
                continue
            if failed is not None and parsed >= failed:
                continue
            candidates.append(version)
        return candidates[:limit]

    @staticmethod
    def hold_manifest_version(manifest: Path, selector: str, version: str) -> None:
        """Rewrite one tool's declared version inside a staged manifest copy.

        The committed manifest keeps its policy (``latest`` or pin); the hold
        lives only in the staged manifest that produces the published lock, so
        the next ``upg`` resolves the newest release afresh.

        Raises:
            ValueError: If the manifest has no declared version for the tool.
        """
        lines = manifest.read_text(encoding="utf-8").splitlines(keepends=True)
        header_exact = f'[tools."{selector}"]'
        header_bare = f"[tools.{selector}]"
        in_section = False
        for index, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("[tools."):
                in_section = stripped in (header_exact, header_bare)
                continue
            if in_section and stripped.startswith("version") and "=" in stripped:
                lines[index] = f'version = "{version}"\n'
                manifest.write_text("".join(lines), encoding="utf-8")
                return
        msg = f"Mise manifest has no declared version to hold: {selector}"
        raise ValueError(msg)

    @classmethod
    def _hold_stage_tools(
        cls,
        runtime: Path,
        storage: Path,
        stage: Path,
        cooldown: str,
        platforms: str,
        failed_tools: list[tuple[str, str]],
    ) -> t.StrDict:
        """Hold every failing tool at its newest installable release, in stage.

        Candidates walk ``ls-remote`` newest-first below the failed release;
        each candidate is resolved into the staged lock and proven by the same
        dry-run gate the publication requires. Every hold is announced loudly;
        nothing is silently skipped.

        Returns:
            The resulting ``t.StrDict`` of held ``selector -> version``.

        Raises:
            ValueError: If any failing tool has no installable candidate below
                its failed release, or if Mise exited or warned during.
        """
        holds: t.StrDict = {}
        scratch = Path(tempfile.mkdtemp(prefix="mise-hold."))
        try:
            environment = cls._mise_environment(
                storage,
                stage,
                scratch,
                cooldown,
                platforms,
            )
            for selector, failed_version in failed_tools:
                held: str | None = None
                for candidate in cls.remote_release_candidates(
                    runtime,
                    environment,
                    selector,
                    failed_version,
                ):
                    cls.hold_manifest_version(
                        stage / ".mise.toml",
                        selector,
                        candidate,
                    )
                    try:
                        cls._run(runtime, ["-C", str(stage), "lock"], environment)
                    except ValueError as error:
                        if "refusing to replace locked version" in str(error):
                            continue
                        raise
                    satisfied, _ = cls._probe_stage(runtime, stage, environment)
                    if satisfied:
                        held = candidate
                        break
                if held is None:
                    msg = (
                        f"no installable release found below {failed_version}"
                        f" for {selector}; upgrade needs an operator decision"
                    )
                    raise ValueError(msg)
                holds[selector] = held
                print(
                    f"hold: {selector} held at {held}: release {failed_version}"
                    " failed install; the next upg retries the newest release",
                )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        return holds

    @classmethod
    def reconcile(cls, project: Path, release: str) -> None:
        """Rebuild a mise.lock the pinned Mise release satisfies, and publish it.

        A dirty tree — a mixed-generation merge, an interrupted ``upg``, or a
        lock written by a different Mise release — recovers here. Seeds are
        tried in order, each proven by a staged dry-run install before
        publication: the working lock, the committed Git lock (its retained
        pins survive the cooldown), a fresh resolution, and finally a fresh
        resolution with every broken-release tool held at its newest
        installable release. Publication
        is atomic and parks an unreadable prior state inside the stage. This is
        the reconcile phase ``make setup`` invokes; it never bumps a tool
        beyond the declared cooldown.

        Raises:
            ValueError: Always; or if missing Mise manifest.
        """
        cls._physical_directory(project)
        manifest = project / ".mise.toml"
        if not manifest.is_file():
            msg = f"missing Mise manifest: {manifest}"
            raise ValueError(msg)
        storage = cls._mise_storage_root()
        for relative in STORAGE_DIRECTORIES:
            (storage / relative).mkdir(parents=True, exist_ok=True)
        runtime = cls._pinned_runtime(storage, release)
        cooldown, platforms = cls._manifest_settings(manifest)
        seeds: list[tuple[str, bytes | None]] = [
            ("working", cls._bytes(project / "mise.lock")),
        ]
        head_lock = cls._git_output(project, "show", "HEAD:mise.lock")
        if head_lock is not None:
            seeds.append(("git-head", head_lock))
        seeds.append(("fresh", None))
        failures: list[str] = []
        for name, payload in seeds:
            stage = Path(
                tempfile.mkdtemp(
                    prefix=f".{project.name}.mise-lock-stage.",
                    dir=project.parent,
                ),
            )
            scratch = Path(tempfile.mkdtemp(prefix="mise-reconcile."))
            try:
                shutil.copyfile(manifest, stage / ".mise.toml")
                if payload is not None:
                    (stage / "mise.lock").write_bytes(payload)
                environment = cls._mise_environment(
                    storage,
                    stage,
                    scratch,
                    cooldown,
                    platforms,
                )
                try:
                    cls._run(runtime, ["-C", str(stage), "lock"], environment)
                except ValueError as error:
                    if "refusing to replace locked version" not in str(error):
                        failures.append(f"{name}: lock failed: {error}")
                        continue
                    # Mise refused a cooldown-admissible version whose release
                    # lacks platform coverage and kept the locked version; the
                    # staged dry-run below remains the publication gate (the
                    # same tolerance the upg lock stage ships).
                if not cls._staged_lock_satisfies(runtime, stage, environment):
                    failures.append(
                        f"{name}: staged lock does not satisfy the manifest",
                    )
                    continue
                staged_python = cls._run(
                    runtime,
                    ["-C", str(stage), "which", "python"],
                    environment,
                )
                if not staged_python or not os.access(staged_python, os.X_OK):
                    failures.append(f"{name}: staged Mise Python is not executable")
                    continue
                try:
                    cls.publish(project, stage)
                except ValueError:
                    parked = stage / "reconcile-parked"
                    parked.mkdir()
                    if (project / "mise.lock").exists():
                        Path(project / "mise.lock").replace(parked / "mise.lock")
                    locks = project / ".mise" / "locks"
                    if locks.exists():
                        Path(locks).replace(parked / "locks")
                    cls.publish(project, stage)
                print(
                    f"reconcile: published the {name} mise.lock "
                    f"Mise {release} satisfies",
                )
                return
            finally:
                shutil.rmtree(scratch, ignore_errors=True)
                if (
                    stage.exists()
                    and not (stage / c.Infra.MISE_LOCK_JOURNAL_FILENAME).exists()
                ):
                    shutil.rmtree(stage, ignore_errors=True)
        held_stage = Path(
            tempfile.mkdtemp(
                prefix=f".{project.name}.mise-lock-stage.",
                dir=project.parent,
            ),
        )
        try:
            scratch = Path(tempfile.mkdtemp(prefix="mise-reconcile."))
            try:
                shutil.copyfile(manifest, held_stage / ".mise.toml")
                environment = cls._mise_environment(
                    storage,
                    held_stage,
                    scratch,
                    cooldown,
                    platforms,
                )
                try:
                    cls._run(runtime, ["-C", str(held_stage), "lock"], environment)
                except ValueError as error:
                    if "refusing to replace locked version" not in str(error):
                        raise
                satisfied, probe_output = cls._probe_stage(
                    runtime,
                    held_stage,
                    environment,
                )
                if not satisfied:
                    holds = cls._hold_stage_tools(
                        runtime,
                        storage,
                        held_stage,
                        cooldown,
                        platforms,
                        cls.failing_install_tools(probe_output),
                    )
                    satisfied, _ = cls._probe_stage(
                        runtime,
                        held_stage,
                        environment,
                    )
                    if not satisfied:
                        msg = f"held lock still fails install: {sorted(holds)}"
                        raise ValueError(msg)
                try:
                    cls.publish(project, held_stage)
                except ValueError:
                    parked = held_stage / "reconcile-parked"
                    parked.mkdir()
                    if (project / "mise.lock").exists():
                        Path(project / "mise.lock").replace(parked / "mise.lock")
                    locks = project / ".mise" / "locks"
                    if locks.exists():
                        Path(locks).replace(parked / "locks")
                    cls.publish(project, held_stage)
                print(
                    f"reconcile: published the held mise.lock Mise {release} satisfies",
                )
                return
            finally:
                shutil.rmtree(scratch, ignore_errors=True)
        except ValueError as held_error:
            failures.append(f"held: {held_error}")
        finally:
            if (
                held_stage.exists()
                and not (held_stage / c.Infra.MISE_LOCK_JOURNAL_FILENAME).exists()
            ):
                shutil.rmtree(held_stage, ignore_errors=True)
        msg = (
            "reconcile: no seed produced a lock the pinned Mise satisfies ("
            + "; ".join(failures)
            + "); run make upg at the runtime root"
        )
        raise ValueError(msg)

    @classmethod
    def converge(cls, project: Path, stage: Path, release: str) -> None:
        """Hold failing tools in an ``upg`` lock stage at installable releases.

        The ``upg`` lock stage already carries the bumped lock; a broken
        upstream release fails its staged install. This probes the stage,
        parses the failing tools, holds each at its newest installable release
        inside the staged manifest, and re-proves the whole stage. The caller
        then retries the staged install and publishes. The committed manifest
        never changes, so the next ``upg`` resolves the newest release afresh.

        Raises:
            ValueError: If the stage has no manifest, no failing tool is
                parseable, no installable candidate exists, or the held lock
                still fails its install probe.
        """
        cls._physical_directory(stage)
        manifest = stage / ".mise.toml"
        if not manifest.is_file():
            msg = f"missing staged Mise manifest: {manifest}"
            raise ValueError(msg)
        storage = cls._mise_storage_root()
        runtime = cls._pinned_runtime(storage, release)
        cooldown, platforms = cls._manifest_settings(manifest)
        scratch = Path(tempfile.mkdtemp(prefix="mise-converge."))
        try:
            environment = cls._mise_environment(
                storage,
                stage,
                scratch,
                cooldown,
                platforms,
            )
            satisfied, probe_output = cls._probe_stage(
                runtime,
                stage,
                environment,
            )
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        if satisfied:
            print("converge: staged lock installs; nothing to hold")
            return
        holds = cls._hold_stage_tools(
            runtime,
            storage,
            stage,
            cooldown,
            platforms,
            cls.failing_install_tools(probe_output),
        )
        scratch = Path(tempfile.mkdtemp(prefix="mise-converge."))
        try:
            environment = cls._mise_environment(
                storage,
                stage,
                scratch,
                cooldown,
                platforms,
            )
            satisfied, _ = cls._probe_stage(runtime, stage, environment)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
        if not satisfied:
            msg = f"converge: held lock still fails install: {sorted(holds)}"
            raise ValueError(msg)
        print(f"converge: staged lock installs with holds {sorted(holds)}")


__all__: list[str] = ["STORAGE_DIRECTORIES", "FlextInfraBootstrapMiseMixin"]
