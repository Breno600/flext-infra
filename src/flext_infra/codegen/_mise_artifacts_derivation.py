"""Offline derivation checks for the `make upg`-written Mise pin and launchers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from hashlib import sha256
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, r, t, u

if TYPE_CHECKING:
    from flext_infra import m, p


class FlextInfraMiseArtifactsDerivation:
    """Prove each launcher is mise's own output for the committed release.

    ``make upg`` is the only writer of the triple: it resolves the release,
    runs ``mise generate install-script`` with that release and records the
    pin. Every other verb verifies the triple offline and names ``make upg``
    as the only repair.
    """

    @classmethod
    def validate_packaged(cls, directory: Path) -> p.Result[bool]:
        """Validate the flat packaged copy of one upg-written triple.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        release = cls.pinned_release(directory)
        if release.failure:
            return r[bool].from_failure(release)
        for relative, mode in c.Infra.ARTIFACT_SPECS:
            if relative == c.Infra.MISE_VERSION_PIN_FILENAME:
                continue
            launcher = cls._validate_launcher(
                directory / Path(relative).name,
                relative,
                mode,
                release.value,
            )
            if launcher.failure:
                return launcher
        return r[bool].ok(value=True)

    @classmethod
    def validate(cls, project_root: Path, runtime_root: Path) -> p.Result[bool]:
        """Validate one project's triple and its projection of the runtime root.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        release = cls.pinned_release(project_root)
        if release.failure:
            return r[bool].from_failure(release)
        for relative, mode in c.Infra.ARTIFACT_SPECS:
            if relative == c.Infra.MISE_VERSION_PIN_FILENAME:
                continue
            launcher = cls._validate_launcher(
                project_root / relative,
                relative,
                mode,
                release.value,
            )
            if launcher.failure:
                return launcher
        sidecars = cls._validate_aube_sidecars(project_root)
        if sidecars.failure:
            return sidecars
        if project_root.resolve() == runtime_root.resolve():
            return r[bool].ok(value=True)
        for relative, _mode in c.Infra.ARTIFACT_SPECS:
            projected = cls._read(project_root / relative)
            if projected.failure:
                return r[bool].from_failure(projected)
            owner = cls._read(runtime_root / relative)
            if owner.failure:
                return r[bool].from_failure(owner)
            if projected.value != owner.value:
                return r[bool].fail(
                    f"{project_root / relative} differs from the runtime root "
                    f"{runtime_root / relative}; run make upg in {runtime_root}",
                )
        return r[bool].ok(value=True)

    @classmethod
    def pinned_release(cls, root: Path) -> p.Result[str]:
        """Return the release recorded by ``root``'s ``mise.version``.

        Returns:
            The release recorded by ``root``'s ``mise.version``.

        """
        path = root / c.Infra.MISE_VERSION_PIN_FILENAME
        content = cls._read(path)
        if content.failure:
            return r[str].from_failure(content)
        release = u.Infra.mise_pinned_release(content.value)
        if release.failure:
            return r[str].fail(f"{path}: {release.error}; run make upg")
        return release

    @classmethod
    def _validate_aube_sidecars(cls, project_root: Path) -> p.Result[bool]:
        """Require every aube sidecar ``mise.lock`` references to exist and match.

        ``make upg``'s ``mise lock`` writes the npm sidecar directories beside
        ``mise.lock``. A lock committed without its sidecar (or with a drifted
        one) fails only in a distant ``mise install`` with "dependency sidecar
        ... No such file or directory"; this check rejects both defects
        offline, while the repair is still a local ``make upg``. A root without
        ``mise.lock`` (a transaction stage carries only the declaration and
        launchers) has no sidecar contract to prove, so it passes.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        lock_path = project_root / c.Infra.MISE_LOCK_FILENAME
        if not lock_path.is_file():
            return r[bool].ok(value=True)
        source = cls._read(lock_path)
        if source.failure:
            return r[bool].from_failure(source)
        payload = u.Cli.toml_mapping_from_text(source.value)
        if payload is None:
            return r[bool].fail(f"invalid TOML in {c.Infra.MISE_LOCK_FILENAME}")
        raw_tools = payload.get("tools")
        if not isinstance(raw_tools, Mapping):
            return r[bool].fail(
                f"{c.Infra.MISE_LOCK_FILENAME} must declare a [tools] section",
            )
        for selector, raw_tool in sorted(raw_tools.items()):
            entries = raw_tool if isinstance(raw_tool, list) else (raw_tool,)
            for raw_entry in entries:
                if not isinstance(raw_entry, Mapping):
                    continue
                sidecar = raw_entry.get("aube")
                if not isinstance(sidecar, Mapping):
                    continue
                annotated = cls._sidecar_annotation(selector, sidecar)
                if annotated.failure:
                    return r[bool].from_failure(annotated)
                relative, digest = annotated.value
                lockfile = project_root / relative / "aube-lock.yaml"
                mismatch = cls._sidecar_digest(lockfile, digest)
                if mismatch.failure:
                    return r[bool].fail(
                        f"{c.Infra.MISE_LOCK_FILENAME} tool {selector} references "
                        f"the aube sidecar {relative}: {mismatch.error}; run make upg",
                    )
        return r[bool].ok(value=True)

    @staticmethod
    def _sidecar_annotation(
        selector: str,
        sidecar: Mapping[str, t.JsonValue],
    ) -> p.Result[tuple[str, str]]:
        """Return one tool's ``(sidecar path, digest)`` from its aube table.

        Returns:
            One tool's ``(sidecar path, digest)`` from its aube table.

        """
        relative = sidecar.get("path")
        digest = sidecar.get("digest")
        if not isinstance(relative, str) or not relative.strip():
            return r[tuple[str, str]].fail(
                f"tool {selector} carries an aube annotation without a path",
            )
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            return r[tuple[str, str]].fail(
                f"tool {selector} carries an aube annotation without a sha256 digest",
            )
        return r[tuple[str, str]].ok((relative, digest.removeprefix("sha256:")))

    @staticmethod
    def _sidecar_digest(lockfile: Path, digest: str) -> p.Result[bool]:
        """Verify one sidecar's ``aube-lock.yaml`` digest against the lock.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if not lockfile.is_file():
            return r[bool].fail(f"{lockfile} is absent")
        actual = sha256(lockfile.read_bytes().replace(b"\r\n", b"\n")).hexdigest()
        if actual != digest:
            return r[bool].fail(
                f"{lockfile} digest {actual} differs from the locked {digest}",
            )
        return r[bool].ok(value=True)

    @staticmethod
    def resolves_at_run_time(artifacts: m.Infra.MiseToolchainArtifactSet) -> bool:
        """Report launchers that resolve the latest release when they run.

        Only the pre-bake projection (before ``make upg`` generated the
        launchers) has this shape; a launcher ``mise`` generated for one
        release never contains the live-resolution endpoint.

        Returns:
            The resulting ``bool``.

        """
        marker = c.Infra.MISE_LATEST_RESOLUTION_MARKER.encode()
        return any(
            marker in state.content
            for state in (artifacts.unix_launcher, artifacts.windows_launcher)
            if state.content is not None
        )

    @classmethod
    def _validate_launcher(
        cls,
        path: Path,
        relative: str,
        mode: int,
        release: str,
    ) -> p.Result[bool]:
        """Require the generator's baked release, no live resolution, and mode.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        content = cls._read(path)
        if content.failure:
            return r[bool].from_failure(content)
        if c.Infra.MISE_LATEST_RESOLUTION_MARKER in content.value:
            return r[bool].fail(
                f"{path} resolves {c.Infra.MISE_LATEST_RESOLUTION_MARKER} at run "
                "time instead of baking a release; run make upg",
            )
        pattern = c.Infra.MISE_LAUNCHER_BAKED_RELEASE_PATTERNS[relative]
        baked = sorted({
            match.group("release") for match in re.finditer(pattern, content.value)
        })
        if baked != [release]:
            return r[bool].fail(
                f"{path} bakes Mise {', '.join(baked) or 'no release'} but "
                f"{c.Infra.MISE_VERSION_PIN_FILENAME} records {release}; run make upg",
            )
        if mode & 0o100 and not path.stat().st_mode & 0o100:
            return r[bool].fail(f"{path} is not executable; run make upg")
        return r[bool].ok(value=True)

    @staticmethod
    def _read(path: Path) -> p.Result[str]:
        """Read one committed artifact, naming ``make upg`` when it is absent.

        Returns:
            The resulting ``p.Result[str]``.

        """
        content = u.Cli.files_read_text(path)
        if content.failure:
            return r[str].fail(f"{path}: {content.error}; run make upg")
        return content


__all__: list[str] = ["FlextInfraMiseArtifactsDerivation"]
