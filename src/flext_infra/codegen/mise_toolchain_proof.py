"""Fail-loud reality proof of the provisioned Mise toolchain.

``make setup`` installs exactly the declared ``toolchain.tools`` from the
committed ``mise.lock``; this service then proves, tool by tool and stopping
at the first defect, that what runs is what the lock pins:

1. lock identity — the ``mise.lock`` entry exists, names a version the
   toolchain selector accepts and, unless the tool declares that its upstream
   publishes none, carries a checksum for the current platform;
2. install root — ``mise where <key>@<version>`` names the install root;
3. self-containment — ``mise which <binary>`` and every symlink hop it
   resolves through stay inside that root;
4. real version — the tool's declared ``version_probe`` reports the locked
   version.

There is no fallback, retry, or warning-only mode.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import platform
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, override

from flext_infra import c, config, m, r, t, u
from flext_infra.codegen._execution import FlextInfraCodegenExecutionBase

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraCodegenMiseToolchainProof(FlextInfraCodegenExecutionBase[bool]):
    """Prove every declared fleet tool is the self-contained locked release."""

    uv_executable: Annotated[
        Path,
        m.Field(description="Absolute UV executable consumed by the invoking Make"),
    ]

    @staticmethod
    def current_platform() -> p.Result[str]:
        """Name the mise.lock platform of the running host.

        Returns:
            The resulting ``p.Result[str]``.

        """
        system = platform.system()
        base = c.Infra.MISE_PLATFORM_BY_HOST.get((system, platform.machine()))
        if base is None:
            return r[str].fail(
                f"no mise.lock platform for host {system}/{platform.machine()}",
            )
        if system == "Linux" and platform.libc_ver()[0] != "glibc":
            return r[str].ok(base + c.Infra.MISE_MUSL_PLATFORM_SUFFIX)
        return r[str].ok(base)

    @staticmethod
    def _locked_entry(
        entry: m.Infra.MiseToolEntry,
        lock: t.JsonMapping,
    ) -> p.Result[t.JsonMapping]:
        """The single ``[[tools."<key>"]]`` table the lock holds for the tool.

        Returns:
            The resulting ``p.Result[t.JsonMapping]``.

        """
        key = entry.selector or entry.name
        tools = lock.get("tools")
        versions = tools.get(key) if isinstance(tools, Mapping) else None
        if not isinstance(versions, Sequence) or isinstance(versions, str):
            return r[t.JsonMapping].fail(
                f"{entry.name}: mise.lock has no [[tools.{key!r}]]",
            )
        locked = [item for item in versions if isinstance(item, Mapping)]
        if len(locked) != 1:
            return r[t.JsonMapping].fail(
                f"{entry.name}: mise.lock must lock exactly one version of {key}, "
                f"found {len(locked)}",
            )
        return r[t.JsonMapping].ok(locked[0])

    @classmethod
    def lock_identity(
        cls,
        entry: m.Infra.MiseToolEntry,
        lock: t.JsonMapping,
        platform_name: str,
    ) -> p.Result[t.StrPair]:
        """Step 1: the locked version and checksum of one declared tool.

        The effective release selector (pins layered over the entry) decides
        the accepted versions: ``latest`` accepts any locked release; a line
        or exact release must name the locked version.

        Returns:
            The ``(version, checksum)`` pair; checksum is empty only for a
            tool declaring ``lock_checksum: false``.

        """
        locked = cls._locked_entry(entry, lock)
        if locked.failure:
            return r[t.StrPair].from_failure(locked)
        version = locked.value.get("version")
        requested = config.Infra.codegen.toolchain.tool_version_pins.get(
            entry.name,
            entry.version,
        )
        if not isinstance(version, str) or not (
            requested in {c.Infra.MISE_MOVING_SELECTOR, version}
            or version.startswith(f"{requested}.")
        ):
            return r[t.StrPair].fail(
                f"{entry.name}: mise.lock pins {version!r}, the toolchain requests "
                f"{requested}; run make upg",
            )
        if not entry.lock_checksum:
            return r[t.StrPair].ok((version, ""))
        section = locked.value.get(
            c.Infra.MISE_LOCK_PLATFORM_KEY.format(platform=platform_name),
        )
        checksum = section.get("checksum") if isinstance(section, Mapping) else None
        if not isinstance(checksum, str) or not checksum:
            return r[t.StrPair].fail(
                f"{entry.name}: mise.lock {version} carries no checksum for "
                f"{platform_name}; run make upg",
            )
        return r[t.StrPair].ok((version, checksum))

    @staticmethod
    def _contained_binary(
        entry: m.Infra.MiseToolEntry,
        root: Path,
        binary: Path,
    ) -> p.Result[Path]:
        """Step 3: follow every symlink hop, each one inside the install root.

        Returns:
            The physical executable the binary resolves to.

        """
        hop = Path(os.path.normpath(binary.absolute()))
        visited: set[Path] = set()
        while True:
            # The hop's physical location: its directories resolved, the
            # final component kept so a link is inspected, never followed.
            hop = hop.parent.resolve() / hop.name
            if not hop.is_relative_to(root):
                return r[Path].fail(
                    f"{entry.name}: {binary} resolves through {hop} outside its "
                    f"install root {root}",
                )
            if not hop.is_symlink():
                break
            if hop in visited:
                return r[Path].fail(f"{entry.name}: {binary} is a symlink loop")
            visited.add(hop)
            hop = Path(os.path.normpath(hop.parent / hop.readlink()))
        if not hop.is_file():
            return r[Path].fail(f"{entry.name}: {binary} resolves to missing {hop}")
        return r[Path].ok(hop)

    @staticmethod
    def _reported_version(
        entry: m.Infra.MiseToolEntry,
        version: str,
        executable: Path,
    ) -> p.Result[bool]:
        """Step 4: the declared probe reports the locked version.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        probe = entry.version_probe
        run = u.Cli.run_raw(
            (str(executable), *probe.arguments),
            cwd=executable.parent,
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        if run.failure:
            return r[bool].from_failure(run)
        if run.value.stderr.strip():
            return r[bool].fail(run.value.stderr)
        output = f"{run.value.stdout}\n{run.value.stderr}"
        pattern = probe.pattern.replace(
            c.Infra.MISE_VERSION_PLACEHOLDER,
            re.escape(version),
        )
        if not u.Cli.process_succeeded(run.value.outcome) or (
            re.search(pattern, output, re.MULTILINE) is None
        ):
            return r[bool].fail(
                f"{entry.name}: version probe (exit "
                f"{run.value.outcome.raw_return_code}) does not report the locked "
                f"{version} (pattern {probe.pattern!r}): {output.strip()}",
            )
        return r[bool].ok(value=True)

    @classmethod
    def installation(
        cls,
        entry: m.Infra.MiseToolEntry,
        version: str,
        install_root: Path,
        binary: Path,
    ) -> p.Result[str]:
        """Steps 3-4: self-containment of the binary, then its real version.

        Returns:
            The receipt line of the proven tool.

        """
        root = install_root.resolve(strict=True)
        executable = cls._contained_binary(entry, root, binary)
        if executable.failure:
            return r[str].from_failure(executable)
        reported = cls._reported_version(entry, version, executable.value)
        if reported.failure:
            return r[str].from_failure(reported)
        return r[str].ok(f"{entry.name} {version} {root}")

    @classmethod
    def prove(
        cls,
        entry: m.Infra.MiseToolEntry,
        lock: t.JsonMapping,
        platform_name: str,
        location: t.Pair[Path, Path],
    ) -> p.Result[str]:
        """Prove one tool from its resolved (install root, binary), in order.

        Returns:
            The receipt line, or the first defect.

        """
        identity = cls.lock_identity(entry, lock, platform_name)
        if identity.failure:
            return r[str].from_failure(identity)
        version, checksum = identity.value
        install_root, binary = location
        receipt = cls.installation(entry, version, install_root, binary)
        if receipt.failure:
            return receipt
        return r[str].ok(f"{receipt.value} {checksum or 'checksum:none'}")

    def _mise_line(self, mise_binary: Path, *arguments: str) -> p.Result[str]:
        """Run one read-only ``mise -C <root>`` query and return its line.

        Returns:
            The resulting ``p.Result[str]``.

        """
        run = u.Cli.run_raw(
            (str(mise_binary), "-C", str(self.repository_root), *arguments),
            cwd=self.repository_root,
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        if run.failure:
            return r[str].from_failure(run)
        line = run.value.stdout.strip()
        if (
            not u.Cli.process_succeeded(run.value.outcome)
            or run.value.stderr.strip()
            or not line
        ):
            return r[str].fail(
                f"mise {' '.join(arguments)} failed: "
                f"{(run.value.stderr or run.value.stdout).strip()}",
            )
        return r[str].ok(line)

    def _prove_declared(
        self,
        entry: m.Infra.MiseToolEntry,
        lock: t.JsonMapping,
        platform_name: str,
        mise_binary: Path,
    ) -> p.Result[str]:
        """Prove one declared tool against the real Mise resolution.

        Returns:
            The receipt line, or the first defect.

        """
        identity = self.lock_identity(entry, lock, platform_name)
        if identity.failure:
            return r[str].from_failure(identity)
        version, checksum = identity.value
        root = self._mise_line(
            mise_binary, "where", f"{entry.selector or entry.name}@{version}"
        )
        if root.failure:
            return r[str].from_failure(root)
        binary = self._mise_line(mise_binary, "which", entry.version_probe.binary)
        if binary.failure:
            return r[str].from_failure(binary)
        receipt = self.installation(
            entry, version, Path(root.value), Path(binary.value)
        )
        if receipt.failure:
            return receipt
        return r[str].ok(f"{receipt.value} {checksum or 'checksum:none'}")

    @override
    def execute(self) -> p.Result[bool]:
        """Prove every declared tool, stopping at the first defect.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        mise_binary = u.Infra.managed_mise_self(self.repository_root)
        if mise_binary.failure:
            return r[bool].from_failure(mise_binary)
        self.logger.info(
            "mise_reader_qualified",
            executable=str(mise_binary.value),
            sha256=u.Cli.sha256_bytes(mise_binary.value.read_bytes()),
        )
        lock_path = self.repository_root / c.Infra.MISE_LOCK_FILENAME
        source = u.Cli.files_read_text(lock_path)
        if source.failure:
            return r[bool].from_failure(source)
        lock = u.Cli.toml_mapping_from_text(source.value)
        if lock is None:
            return r[bool].fail(f"invalid TOML in {lock_path}")
        self.logger.info(
            "mise_proof_inputs",
            lock_path=str(lock_path),
            lock_sha256=u.Cli.sha256_bytes(source.value.encode(c.Cli.ENCODING_DEFAULT)),
            config_sha256=u.Cli.sha256_bytes(
                config.Infra.codegen.model_dump_json().encode(c.Cli.ENCODING_DEFAULT)
            ),
            uv_executable=str(self.uv_executable),
            python_executable=sys.executable,
            python_base_prefix=sys.base_prefix,
            python_prefix=sys.prefix,
        )
        platform_name = self.current_platform()
        if platform_name.failure:
            return r[bool].from_failure(platform_name)
        toolchain = config.Infra.codegen.toolchain
        runtime_entries = (
            m.Infra.MiseToolEntry(
                name=c.Infra.MISE,
                selector=toolchain.mise_selector,
                version=toolchain.mise_version,
                version_probe=m.Infra.MiseToolVersionProbe(
                    binary=c.Infra.MISE,
                    arguments=("--version",),
                    pattern="^{version} ",
                ),
            ),
            m.Infra.MiseToolEntry(
                name="python",
                version=toolchain.python_version,
                version_probe=m.Infra.MiseToolVersionProbe(
                    binary="python",
                    arguments=("--version",),
                    pattern="^Python {version}$",
                ),
            ),
        )
        for entry in (*runtime_entries, *toolchain.tools):
            receipt = self._prove_declared(
                entry, lock, platform_name.value, mise_binary.value
            )
            if receipt.failure:
                return r[bool].from_failure(receipt)
            self.logger.info("mise_toolchain_proven", receipt=receipt.value)
        return self._prove_runtime(
            lock, runtime_entries[1], mise_binary.value, platform_name.value
        )

    def _prove_uv_consumer(self) -> p.Result[bool]:
        """Compare the actual consumer to the one locked producer.

        Returns:
            Success only for the authenticated physical UV executable.
        """
        uv = u.Infra.managed_mise_binary("uv", self.repository_root)
        if uv.failure:
            return r[bool].from_failure(uv)
        if not self.uv_executable.is_absolute() or not self.uv_executable.is_file():
            return r[bool].fail(
                f"Make UV is not an absolute executable file: {self.uv_executable}"
            )
        actual_uv = self.uv_executable.resolve(strict=True)
        if actual_uv != uv.value:
            return r[bool].fail(
                f"Make UV differs from the locked producer: actual={actual_uv} "
                f"sha256={u.Cli.sha256_bytes(actual_uv.read_bytes())} "
                f"expected={uv.value} "
                f"sha256={u.Cli.sha256_bytes(uv.value.read_bytes())}"
            )
        return r[bool].ok(value=True)

    def _prove_runtime(
        self,
        lock: t.JsonMapping,
        python_entry: m.Infra.MiseToolEntry,
        mise_binary: Path,
        platform_name: str,
    ) -> p.Result[bool]:
        """Prove the invoking consumer, not just separately installed tools.

        Returns:
            Success only for the locked UV and Python-backed project venv.
        """
        uv = self._prove_uv_consumer()
        if uv.failure:
            return uv
        python_version = self.lock_identity(python_entry, lock, platform_name)
        if python_version.failure:
            return r[bool].from_failure(python_version)
        python_root = self._mise_line(
            mise_binary, "where", f"{python_entry.name}@{python_version.value[0]}"
        )
        if python_root.failure:
            return r[bool].from_failure(python_root)
        if (
            Path(sys.base_prefix).resolve() != Path(python_root.value).resolve()
            or sys.prefix == sys.base_prefix
        ):
            return r[bool].fail(
                f"Runtime Python venv ancestry differs from the lock: "
                f"executable={sys.executable} version={sys.version.split()[0]} "
                f"prefix={sys.prefix} base={sys.base_prefix} "
                f"expected-base={python_root.value}"
            )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraCodegenMiseToolchainProof"]
