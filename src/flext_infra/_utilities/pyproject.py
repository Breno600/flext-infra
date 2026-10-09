"""Pyproject.toml parsing helpers for flext-infra utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
import shutil
from collections.abc import Mapping, Sequence
from functools import cache, lru_cache
from pathlib import Path

from flext_cli import u

from flext_infra import c, config, m, p, r, t
from flext_infra._utilities import (
    FlextInfraUtilitiesGit,
    FlextInfraUtilitiesManagedConflicts,
)


class FlextInfraUtilitiesPyproject:
    """Static helpers for reading and normalizing ``pyproject.toml`` payloads."""

    @staticmethod
    def managed_mise_binary(
        name: str,
        owner_root: Path,
        *,
        timeout_seconds: int = c.Infra.TIMEOUT_SHORT,
    ) -> p.Result[Path]:
        """Resolve a locked managed executable before entering a consumer cwd.

        Returns:
            An authenticated absolute binary, never a PATH shim or global default.
        """
        tool = next(
            (
                item
                for item in config.Infra.codegen.toolchain.tools
                if item.name == name
            ),
            None,
        )
        if tool is None:
            return r[Path].fail(f"tool is not declared by the toolchain owner: {name}")
        pinned = FlextInfraUtilitiesPyproject._locked_mise_version(
            owner_root,
            tool.selector or tool.name,
            config.Infra.codegen.toolchain.tool_versions[name],
        )
        if pinned.failure:
            return r[Path].from_failure(pinned)
        reader = FlextInfraUtilitiesPyproject.managed_mise_self(owner_root)
        if reader.failure:
            return reader
        located = FlextInfraUtilitiesPyproject._managed_mise_path(
            tool.version_probe.binary, owner_root, reader.value
        )
        if located.failure:
            return located
        return FlextInfraUtilitiesPyproject._managed_binary_identity(
            located.value,
            pinned.value,
            owner_root,
            tool.version_probe,
            timeout_seconds,
        )

    @staticmethod
    def managed_mise_self(owner_root: Path) -> p.Result[Path]:
        """Qualify the physical Mise reader before it loads project locks.

        Returns:
            The installed self-managed executable, never a tool shim.
        """
        toolchain = config.Infra.codegen.toolchain
        pinned = FlextInfraUtilitiesPyproject._locked_mise_version(
            owner_root, toolchain.mise_selector, toolchain.mise_version
        )
        if pinned.failure:
            return r[Path].from_failure(pinned)
        selected = shutil.which(c.Infra.MISE)
        if selected is None:
            return r[Path].fail("Mise executable is absent; run make setup")
        reader = FlextInfraUtilitiesPyproject._mise_self_identity(
            Path(selected), pinned.value, owner_root
        )
        if reader.failure:
            return reader
        installed = FlextInfraUtilitiesPyproject._managed_mise_path(
            c.Infra.MISE, owner_root, reader.value
        )
        if installed.failure:
            return installed
        return FlextInfraUtilitiesPyproject._mise_self_identity(
            installed.value, pinned.value, owner_root
        )

    @staticmethod
    def _mise_self_identity(
        binary: Path, pinned: str, owner_root: Path
    ) -> p.Result[Path]:
        """Check the physical reader without invoking a lock-consuming command.

        Returns:
            The physical executable matching the committed self pin.
        """
        binary = binary.resolve(strict=True)
        identity = u.Cli.run_raw(
            (str(binary), "--version"),
            cwd=owner_root,
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        if identity.failure:
            return r[Path].from_failure(identity)
        output = identity.value
        if not u.Cli.process_succeeded(output.outcome) or output.stderr.strip():
            return r[Path].fail(output.stderr or output.stdout)
        if output.stdout.split()[:1] != [pinned]:
            return r[Path].fail(
                f"Mise reader {binary} differs from lock: expected={pinned} "
                f"observed={output.stdout.strip()}; run make setup"
            )
        return r[Path].ok(binary)

    @staticmethod
    def _managed_mise_path(name: str, owner_root: Path, reader: Path) -> p.Result[Path]:
        located = u.Cli.run_raw(
            (str(reader), "-C", str(owner_root), "which", name),
            cwd=owner_root,
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        if located.failure:
            return r[Path].from_failure(located)
        if (
            not u.Cli.process_succeeded(located.value.outcome)
            or located.value.stderr.strip()
        ):
            return r[Path].fail(located.value.stderr or located.value.stdout)
        binary = Path(located.value.stdout.strip())
        if not binary.is_absolute() or not binary.is_file():
            return r[Path].fail(f"managed executable is not an absolute file: {binary}")
        return r[Path].ok(binary.resolve(strict=True))

    @staticmethod
    def _managed_binary_identity(
        binary: Path,
        pinned: str,
        owner_root: Path,
        probe: m.Infra.MiseToolVersionProbe,
        timeout_seconds: int,
    ) -> p.Result[Path]:
        identified = u.Cli.run_raw(
            (str(binary), *probe.arguments),
            cwd=owner_root,
            timeout=timeout_seconds,
        )
        if identified.failure:
            return r[Path].from_failure(identified)
        if (
            not u.Cli.process_succeeded(identified.value.outcome)
            or identified.value.stderr.strip()
        ):
            return r[Path].fail(identified.value.stderr or identified.value.stdout)
        pattern = probe.pattern.replace(
            c.Infra.MISE_VERSION_PLACEHOLDER, re.escape(pinned)
        )
        if re.search(pattern, identified.value.stdout, re.MULTILINE) is None:
            return r[Path].fail(
                f"managed executable differs from lock: expected={pinned} "
                f"observed={identified.value.stdout.strip()}",
            )
        return r[Path].ok(binary)

    @staticmethod
    def recover_live_pyproject_text(raw: str) -> p.Result[str]:
        """Return live pyproject text with merge-control lines resolved.

        Unconflicted text is returned unchanged. A conflict is resolved only
        inside owner-declared managed TOML sections
        (``config.Infra.codegen.managed_files``) via
        ``FlextInfraUtilitiesManagedConflicts.recover_managed_toml``; a
        conflict outside those sections fails loud through that utility's
        own contract. Read-only: no file is written here.

        Returns:
            Live pyproject text with merge-control lines resolved.

        """
        spec_result = FlextInfraUtilitiesManagedConflicts.pyproject_managed_file()
        if spec_result.failure:
            return r[str].from_failure(spec_result)
        return FlextInfraUtilitiesManagedConflicts.recover_managed_toml(
            raw,
            conflict_sections=spec_result.value.conflict_sections,
        )

    @staticmethod
    def live_pyproject_text(
        pyproject_path: Path,
        *,
        regenerate_managed_tools: bool = False,
    ) -> p.Result[str]:
        """Read one live pyproject and resolve managed merge conflicts.

        Returns:
            The resulting ``p.Result[str]``.

        """
        raw = u.Cli.atomic_read_binary_file_state(pyproject_path, required=True)
        if raw.failure:
            return r[str].from_failure(raw)
        content = raw.value.content
        if content is None:
            return r[str].fail(f"pyproject is absent: {pyproject_path}")
        live = FlextInfraUtilitiesPyproject.recover_live_pyproject_text(
            content.decode(c.Cli.ENCODING_DEFAULT),
        )
        if live.failure or not regenerate_managed_tools:
            return live
        return FlextInfraUtilitiesManagedConflicts.pyproject_regeneration_source(
            live.value,
        )

    @staticmethod
    def read_project_metadata_result(project_root: Path) -> p.Result[p.ProjectMetadata]:
        """Read one project's metadata through the canonical owner chain.

        flext-core retired its Result-returning compatibility wrapper; this is
        the consuming project's typed ingress, keeping every metadata reader on
        one failure contract instead of three ad-hoc try/except blocks. The
        declared contract is the canonical structural protocol (the producer
        builds the exact model behind it), matching every ``p.ProjectMetadata``
        consumer.

        The document is the live text with managed merge conflicts resolved
        (``live_pyproject_text``); the file is never written here.

        Returns:
            The resulting ``p.Result[p.ProjectMetadata]``.

        """
        live = FlextInfraUtilitiesPyproject.live_pyproject_text(
            project_root / c.PYPROJECT_FILENAME,
        )
        if live.failure:
            return r[p.ProjectMetadata].from_failure(live)
        # The facade returns None for unparseable text rather than raising, so
        # the invalid case is named here instead of reaching model_validate as
        # a None that fails with a shape error about the wrong subject.
        payload = u.Cli.toml_mapping_from_text(live.value)
        if payload is None:
            return r[p.ProjectMetadata].fail(
                f"cannot read project metadata from {project_root}: "
                f"{c.PYPROJECT_FILENAME} is not valid TOML",
            )
        try:
            document = u.PyprojectDocument.model_validate(payload)
            metadata = u.build_project_metadata(project_root, document)
        except (OSError, ValueError) as exc:
            return r[p.ProjectMetadata].fail(
                f"cannot read project metadata from {project_root}: {exc}",
                exception=exc,
            )
        return r[p.ProjectMetadata].ok(metadata)

    @staticmethod
    def validate_infra_payload(payload: p.AttributeProbe) -> t.JsonMapping:
        """Validate one plain mapping through the infra adapter.

        Centralizes the adapter choice so every caller validates through the
        same typed boundary; validation failures escape with the precise
        pydantic error instead of a sentinel.

        Returns:
            The resulting ``t.JsonMapping``.

        """
        result: t.JsonMapping = t.Infra.INFRA_MAPPING_ADAPTER.validate_python(payload)
        return result

    @classmethod
    def format_toml_source(
        cls,
        source: str,
        *,
        path: Path,
        toolchain_root: Path,
        taplo_version: str,
        process_timeout_seconds: int = c.Infra.TIMEOUT_DEFAULT,
    ) -> p.Result[str]:
        """Format TOML through the configured workspace Taplo toolchain.

        ``taplo_version`` is the declared selector; the one mise.lock owner
        (``_locked_mise_version``, nearest lock at or above the execution root)
        resolves it before any shim runs, so generation formats with the locked
        release and never asks a tool manager to resolve a version mid-run.

        Returns:
            The resulting ``p.Result[str]``.

        """
        config_path = toolchain_root / c.Infra.TAPLO_CONFIG_FILENAME
        config_content = config_path.read_bytes() if config_path.is_file() else b""
        resolved_path = path.resolve()
        resolved_toolchain_root = toolchain_root.resolve()
        execution_root = next(
            candidate
            for candidate in (resolved_toolchain_root, *resolved_toolchain_root.parents)
            if candidate.is_dir()
        )
        relative_path = (
            resolved_path.relative_to(resolved_toolchain_root).as_posix()
            if resolved_path.is_relative_to(resolved_toolchain_root)
            else resolved_path.relative_to(resolved_path.parent).as_posix()
        )
        return cls._format_toml_source_cached(
            source,
            relative_path=relative_path,
            config=(
                config_path.resolve() if config_content else None,
                u.Cli.sha256_bytes(config_content),
            ),
            taplo=(taplo_version, process_timeout_seconds, execution_root),
        )

    @staticmethod
    def _locked_taplo_version(toolchain_root: Path, *, declared: str) -> p.Result[str]:
        """Return the exact Taplo release the committed lock pins.

        The configuration declares the moving selector; only ``make upg``
        resolves it, into ``mise.lock``. Generation therefore reads the pinned
        release and passes it on, and an absent lock entry fails loud instead
        of silently accepting whatever binary the host happens to expose.

        Returns:
            The exact Taplo release the committed lock pins.

        """
        if declared != c.Infra.MISE_MOVING_SELECTOR:
            return r[str].ok(declared)
        return FlextInfraUtilitiesPyproject._locked_tool_version(
            toolchain_root,
            c.Infra.TAPLO_MISE_TOOL_NAME,
        )

    @staticmethod
    def _locked_tool_version(toolchain_root: Path, tool_name: str) -> p.Result[str]:
        """Return one tool's pinned version from ``mise.lock`` at the root.

        Returns:
            One tool's pinned version from ``mise.lock`` at the root.

        """
        lock_path = toolchain_root / c.Infra.MISE_LOCK_FILENAME
        source = u.Cli.files_read_text(lock_path)
        if source.failure:
            return r[str].from_failure(source)
        payload = u.Cli.toml_mapping_from_text(source.value)
        if payload is None:
            return r[str].fail(f"invalid TOML in {lock_path.name}")
        raw_tools = payload.get("tools")
        raw_entry = raw_tools.get(tool_name) if isinstance(raw_tools, Mapping) else None
        if isinstance(raw_entry, Sequence) and not isinstance(raw_entry, str):
            raw_entry = raw_entry[0] if raw_entry else None
        version = raw_entry.get("version") if isinstance(raw_entry, Mapping) else None
        if not isinstance(version, str) or not version.strip():
            return r[str].fail(
                f"{lock_path.name} pins no version for {tool_name}: "
                "run make upg to resolve the lock",
            )
        return r[str].ok(version.strip())

    @staticmethod
    @lru_cache(maxsize=c.Infra.CONTENT_CACHE_MAXSIZE)
    def _format_toml_source_cached(
        source: str,
        *,
        relative_path: str,
        config: t.Pair[Path | None, str],
        taplo: t.Triple[str, int, Path],
    ) -> p.Result[str]:

        taplo_result = FlextInfraUtilitiesPyproject._taplo_binary(*taplo)
        if taplo_result.failure:
            return r[str].from_failure(taplo_result)
        config_path, _config_digest = config
        _taplo_version, process_timeout_seconds, execution_root = taplo
        command = [
            str(taplo_result.value),
            "format",
            "-",
            "--stdin-filepath",
            relative_path,
        ]
        if config_path is not None:
            command.extend(("--config", str(config_path)))
        # Generated content must not pass through normalized text model fields.
        result = u.Cli.run_bytes(
            command,
            cwd=execution_root,
            options=m.Cli.ProcessOptions(
                input_data=source.encode(c.Cli.ENCODING_DEFAULT),
            ),
            timeout=process_timeout_seconds,
        )
        if result.failure:
            return r[str].from_failure(result)
        output = result.value
        if not u.Cli.process_succeeded(output.outcome):
            detail = (
                (output.stderr or output.stdout)
                .decode(c.Cli.ENCODING_DEFAULT, errors="backslashreplace")
                .strip()
            )
            return r[str].fail(
                f"taplo format failed ({output.outcome.raw_return_code}): {detail}",
            )
        try:
            formatted = output.stdout.decode(c.Cli.ENCODING_DEFAULT)
        except UnicodeDecodeError as exc:
            return r[str].fail(
                f"taplo format returned non-UTF-8 output: {exc}",
                exception=exc,
            )
        return r[str].ok(formatted)

    @classmethod
    def _locked_mise_version(
        cls,
        execution_root: Path,
        tool: str,
        selector: str,
    ) -> p.Result[str]:
        """Resolve the selector's pinned version from the committed mise.lock.

        Only ``make upg`` resolves a moving selector and writes mise.lock;
        every other execution must authenticate exactly what the lock pins,
        because a version taken from the selector itself sends the shim's
        resolution over the network on a cold cache.

        Returns:
            The resulting ``p.Result[str]``.

        """
        lock_path = cls._mise_lock_path(execution_root)
        if lock_path is None:
            return r[str].fail(
                f"no {c.Infra.MISE_LOCK_FILENAME} above {execution_root} pins "
                f"{tool}; run make upg so generation stays offline",
            )
        return cls._pinned_mise_lock_version(lock_path, tool=tool, selector=selector)

    @staticmethod
    def _mise_lock_path(execution_root: Path) -> Path | None:
        """Return the nearest committed mise.lock above the execution root.

        Returns:
            The resulting ``Path | None``.

        """
        return next(
            (
                candidate / c.Infra.MISE_LOCK_FILENAME
                for candidate in (execution_root, *execution_root.parents)
                if (candidate / c.Infra.MISE_LOCK_FILENAME).is_file()
            ),
            None,
        )

    @classmethod
    def _pinned_mise_lock_version(
        cls,
        lock_path: Path,
        *,
        tool: str,
        selector: str,
    ) -> p.Result[str]:
        """Authenticate the committed mise.lock version one selector pins.

        Returns:
            The resulting ``p.Result[str]``.

        """
        entries_result = cls._mise_lock_tool_entries(lock_path, tool=tool)
        if entries_result.failure:
            return r[str].from_failure(entries_result)
        for entry in entries_result.value:
            locked = cls._locked_entry_version(entry)
            if locked is None:
                return r[str].fail(
                    f"{lock_path} has a malformed [[tools.{tool}]] entry: {entry!r}",
                )
            pinned, specifiers = locked
            if selector in specifiers or selector == pinned:
                return r[str].ok(pinned)
        return r[str].fail(
            f"{lock_path} pins no {tool} for selector {selector!r}; run make upg",
        )

    @staticmethod
    def _mise_lock_tool_entries(
        lock_path: Path,
        *,
        tool: str,
    ) -> p.Result[t.SequenceOf[t.JsonValue]]:
        """Read one tool's lock entries from the committed mise.lock.

        Returns:
            The resulting ``p.Result[t.SequenceOf[t.JsonValue]]``.

        """
        payload = u.Cli.toml_mapping_from_text(
            lock_path.read_text(encoding=c.Cli.ENCODING_DEFAULT),
        )
        if payload is None:
            return r[t.SequenceOf[t.JsonValue]].fail(f"{lock_path} is not valid TOML")
        tools = payload.get("tools", {})
        if not isinstance(tools, Mapping):
            return r[t.SequenceOf[t.JsonValue]].fail(
                f"{lock_path} has a malformed [tools] table",
            )
        entries = tools.get(tool)
        if not isinstance(entries, list):
            return r[t.SequenceOf[t.JsonValue]].fail(
                f"{lock_path} pins no [[tools.{tool}]] entry",
            )
        return r[t.SequenceOf[t.JsonValue]].ok(entries)

    @staticmethod
    def _locked_entry_version(
        entry: t.JsonValue,
    ) -> t.Pair[str, t.SequenceOf[t.JsonValue]] | None:
        """Return one lock entry's pinned version and specifiers when wellformed.

        Returns:
            The resulting ``t.Pair | None``.

        """
        if not isinstance(entry, Mapping):
            return None
        pinned = entry.get("version")
        specifiers = entry.get("specifiers", ())
        if not isinstance(pinned, str) or not isinstance(specifiers, (list, tuple)):
            return None
        return pinned, specifiers

    @staticmethod
    def _taplo_binary(
        taplo_version: str,
        process_timeout_seconds: int,
        execution_root: Path,
    ) -> p.Result[Path]:
        """Resolve and authenticate Make's config-versioned Taplo executable.

        ``taplo_version`` is the release selector the workspace declares; the
        version that authenticates is the one the committed mise.lock pins for
        it, so no shim run ever resolves a moving selector over the network.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        pinned = FlextInfraUtilitiesPyproject._locked_mise_version(
            execution_root,
            c.Infra.TAPLO_MISE_TOOL_NAME,
            taplo_version,
        )
        if pinned.failure:
            return r[Path].from_failure(pinned)
        u.Cli.info(f"pyproject-tooling: resolve taplo={pinned.value} (mise.lock)")
        return FlextInfraUtilitiesPyproject.managed_mise_binary(
            c.Infra.TAPLO_MISE_TOOL_NAME,
            execution_root,
            timeout_seconds=process_timeout_seconds,
        )

    @staticmethod
    def pyproject_payload(pyproject_path: Path) -> t.JsonMapping:
        """Return one parsed ``pyproject.toml`` payload validated against ``t.Infra``.

        The payload is parsed from the live text with managed merge
        conflicts resolved (``live_pyproject_text``).

        Returns:
            One parsed ``pyproject.toml`` payload validated against ``t.Infra``.

        Raises:
            RuntimeError: If failed to read pyproject payload at; or if pyproject
                payload at.

        """
        if not pyproject_path.is_file():
            return {}
        live = FlextInfraUtilitiesPyproject.live_pyproject_text(pyproject_path)
        if live.failure:
            msg = f"failed to read pyproject payload at {pyproject_path}: {live.error}"
            raise RuntimeError(msg)
        # The parse is memoized by the live text, never by the path alone: a
        # process that rewrites a manifest (gen, mod, a test) reads its new
        # content on the next call instead of a stale parse.
        return FlextInfraUtilitiesPyproject._parsed_pyproject_payload(
            pyproject_path,
            live.value,
        )

    @staticmethod
    @cache
    def _parsed_pyproject_payload(pyproject_path: Path, text: str) -> t.JsonMapping:
        """Parse and validate one manifest text (memoized per exact content).

        Returns:
            The validated ``t.Infra`` payload of ``text``.

        Raises:
            RuntimeError: If ``text`` is not valid TOML.

        """
        payload = u.Cli.toml_mapping_from_text(text)
        if payload is None:
            msg = f"pyproject payload at {pyproject_path} is not valid TOML"
            raise RuntimeError(msg)
        return FlextInfraUtilitiesPyproject.validate_infra_payload(payload)

    @staticmethod
    def normalized_toml_payload(document: t.Cli.TomlDocument) -> t.JsonMapping:
        """Return one TOML document normalized through the infra adapter.

        Returns:
            One TOML document normalized through the infra adapter.

        """
        payload = u.Cli.toml_as_mapping(document)
        if not payload:
            return {}
        return FlextInfraUtilitiesPyproject.validate_infra_payload(payload)

    @staticmethod
    def tool_flext_meta(project_root: Path) -> t.JsonMapping:
        """Return the normalized ``tool.flext`` table from a project root.

        Returns:
            The normalized ``tool.flext`` table from a project root.

        """
        payload = FlextInfraUtilitiesPyproject.pyproject_payload(
            project_root / c.PYPROJECT_FILENAME,
        )
        tool = payload.get(c.Infra.TOOL)
        if not isinstance(tool, dict):
            return {}
        flext = tool.get("flext")
        return flext if isinstance(flext, dict) else {}

    @staticmethod
    def docs_meta_from_payload(payload: t.JsonMapping) -> t.JsonMapping:
        """Extract ``tool.flext.docs`` metadata from an already-parsed payload.

        Returns:
            The resulting ``t.JsonMapping``.

        """
        tool = payload.get(c.Infra.TOOL)
        if not isinstance(tool, dict):
            return {}
        flext = tool.get("flext")
        if not isinstance(flext, dict):
            return {}
        docs = flext.get("docs")
        return docs if isinstance(docs, dict) else {}

    @staticmethod
    def project_name_from_payload(entry: Path, payload: t.JsonMapping) -> str:
        """Return the declared project name from ``[project].name``.

        Returns:
            The declared project name from ``[project].name``.

        Raises:
            TypeError: If ``not isinstance(project_section, dict)``.
            ValueError: If ``not isinstance(raw_name, str) or not raw_name.strip()``.

        """
        project_section = payload.get("project")
        if not isinstance(project_section, dict):
            msg = f"{entry}: missing [project] table in pyproject.toml"
            raise TypeError(msg)
        raw_name = project_section.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            msg = f"{entry}: missing or empty [project].name in pyproject.toml"
            raise ValueError(msg)
        return raw_name.strip()

    @staticmethod
    def _hatch_wheel_package(payload: t.JsonMapping) -> str | None:
        """Return the package name the hatch wheel targets declare.

        Returns:
            The resulting ``str | None``.

        """
        current: t.JsonMapping | None = payload
        for key in (c.Infra.TOOL, "hatch", "build", "targets", "wheel"):
            if current is None:
                break
            candidate = current.get(key)
            current = candidate if isinstance(candidate, dict) else None
        packages = current.get("packages") if current is not None else None
        if not isinstance(packages, list):
            return None
        for item in packages:
            package_path = Path(str(item).strip())
            if package_path.parts:
                return package_path.parts[-1]
        return None

    @staticmethod
    def _src_dir_package(project_root: Path) -> str | None:
        """Return the first ``src`` child package carrying an initializer.

        Returns:
            The resulting ``str | None``.

        """
        src_dir = project_root / c.Infra.DEFAULT_SRC_DIR
        if not src_dir.is_dir():
            return None
        for child in sorted(src_dir.iterdir()):
            if child.is_dir() and (child / c.Infra.INIT_PY).is_file():
                return child.name
        return None

    @staticmethod
    def package_name_from_payload(
        project_root: Path,
        payload: t.JsonMapping,
        docs_meta: t.JsonMapping,
    ) -> str:
        """Return the primary package name using pre-loaded pyproject payload.

        Returns:
            The primary package name using pre-loaded pyproject payload.

        Raises:
            ValueError: If ``project_name.startswith(c.Infra.PKG_PREFIX_HYPHEN)``.

        """
        configured = docs_meta.get("package_name")
        if isinstance(configured, str) and configured.strip():
            return configured.strip()
        wheel_package = FlextInfraUtilitiesPyproject._hatch_wheel_package(payload)
        if wheel_package is not None:
            return wheel_package
        source_package = FlextInfraUtilitiesPyproject._src_dir_package(project_root)
        if source_package is not None:
            return source_package
        project_name = FlextInfraUtilitiesPyproject.project_name_from_payload(
            project_root,
            payload,
        )
        if project_name.startswith(c.Infra.PKG_PREFIX_HYPHEN):
            msg = (
                f"{project_root}: cannot resolve package name — "
                "no [tool.flext.docs].package_name, no hatch wheel packages, "
                "and no src/<pkg>/__init__.py present"
            )
            raise ValueError(msg)
        return ""

    @staticmethod
    def project_package_name(project_root: Path) -> str:
        """Return the primary Python package name for a project root.

        Returns:
            The primary Python package name for a project root.

        """
        payload = FlextInfraUtilitiesPyproject.pyproject_payload(
            project_root / c.PYPROJECT_FILENAME,
        )
        docs_meta = FlextInfraUtilitiesPyproject.docs_meta_from_payload(payload)
        return FlextInfraUtilitiesPyproject.package_name_from_payload(
            project_root,
            payload,
            docs_meta,
        )

    @staticmethod
    @cache
    def workspace_project_paths(repository_root: Path) -> t.StrSequence:
        """Return governed project paths declared by this directory's ``.gitmodules``.

        A missing file denotes a standalone project and therefore an empty
        sequence. A malformed declaration is an invalid workspace contract and
        remains a loud error; no pyproject table or parent directory is used as
        an alternate topology source. A submodule that opts out through
        ``flext-managed`` is not a workspace project, the same contract the
        workspace detector applies; every governed path stays in the sequence
        so a missing or unreadable member pyproject still fails at its reader.

        Returns:
            Governed project paths declared by this directory's ``.gitmodules``.

        Raises:
            ValueError: If ``declared.failure``.

        """
        declared = FlextInfraUtilitiesGit.git_submodule_declarations(repository_root)
        if declared.failure:
            msg = declared.error or f"invalid workspace topology: {repository_root}"
            raise ValueError(msg)
        return tuple(
            item.path.as_posix() for item in declared.value if item.managed is not False
        )


__all__: list[str] = ["FlextInfraUtilitiesPyproject"]
