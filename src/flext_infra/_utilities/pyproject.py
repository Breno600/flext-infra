"""Pyproject.toml parsing helpers for flext-infra utilities.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shutil
from functools import cache, lru_cache
from pathlib import Path

from flext_cli import u

from flext_core import r
from flext_infra import c, p, t

from .git import FlextInfraUtilitiesGit
from .managed_conflicts import FlextInfraUtilitiesManagedConflicts


class FlextInfraUtilitiesPyproject:
    """Static helpers for reading and normalizing ``pyproject.toml`` payloads."""

    @staticmethod
    def recover_live_pyproject_text(raw: str) -> p.Result[str]:
        """Return live pyproject text with merge-control lines resolved.

        Unconflicted text is returned unchanged. A conflict is resolved only
        inside owner-declared managed TOML sections
        (``config.Infra.codegen.managed_files``) via
        ``FlextInfraUtilitiesManagedConflicts.recover_managed_toml``; a
        conflict outside those sections fails loud through that utility's
        own contract. Read-only: no file is written here.
        """
        spec_result = FlextInfraUtilitiesManagedConflicts.pyproject_managed_file()
        if spec_result.failure:
            return r[str].from_failure(spec_result)
        return FlextInfraUtilitiesManagedConflicts.recover_managed_toml(
            raw, conflict_sections=spec_result.value.conflict_sections
        )

    @staticmethod
    def live_pyproject_text(pyproject_path: Path) -> p.Result[str]:
        """Read one live pyproject and resolve managed merge conflicts."""
        raw = u.Cli.atomic_read_binary_file_state(pyproject_path, required=True)
        if raw.failure:
            return r[str].from_failure(raw)
        content = raw.value.content
        if content is None:
            return r[str].fail(f"pyproject is absent: {pyproject_path}")
        return FlextInfraUtilitiesPyproject.recover_live_pyproject_text(
            content.decode(c.Cli.ENCODING_DEFAULT)
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
        """
        live = FlextInfraUtilitiesPyproject.live_pyproject_text(
            project_root / c.PYPROJECT_FILENAME
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
                f"{c.PYPROJECT_FILENAME} is not valid TOML"
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
        """Format TOML through the configured workspace Taplo toolchain."""
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
            config_path=config_path.resolve() if config_content else None,
            config_digest=u.Cli.sha256_bytes(config_content),
            execution_root=execution_root,
            taplo_version=taplo_version,
            process_timeout_seconds=process_timeout_seconds,
        )

    @staticmethod
    @lru_cache(maxsize=128)
    def _format_toml_source_cached(
        source: str,
        *,
        relative_path: str,
        config_path: Path | None,
        config_digest: str,
        execution_root: Path,
        taplo_version: str,
        process_timeout_seconds: int,
    ) -> p.Result[str]:
        del config_digest
        taplo = FlextInfraUtilitiesPyproject._taplo_binary(
            taplo_version, process_timeout_seconds, execution_root
        )
        if taplo.failure:
            return r[str].from_failure(taplo)
        command = [str(taplo.value), "format", "-", "--stdin-filepath", relative_path]
        if config_path is not None:
            command.extend(("--config", str(config_path)))
        # Generated content must not pass through normalized text model fields.
        result = u.Cli.run_bytes(
            command,
            cwd=execution_root,
            input_data=source.encode(c.Cli.ENCODING_DEFAULT),
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
                f"taplo format failed ({output.outcome.raw_return_code}): {detail}"
            )
        try:
            formatted = output.stdout.decode(c.Cli.ENCODING_DEFAULT)
        except UnicodeDecodeError as exc:
            return r[str].fail(
                f"taplo format returned non-UTF-8 output: {exc}", exception=exc
            )
        return r[str].ok(formatted)

    @staticmethod
    @cache
    def _taplo_binary(
        taplo_version: str, process_timeout_seconds: int, execution_root: Path
    ) -> p.Result[Path]:
        """Resolve and authenticate Make's config-versioned Taplo executable."""
        u.Cli.info(f"pyproject-tooling: resolve taplo={taplo_version}")
        resolved = shutil.which("taplo")
        if resolved is None:
            return r[Path].fail(
                "Taplo executable is absent from the Make-provisioned PATH"
            )
        # Mise shims are executable symlinks whose basename selects the tool.
        # Resolving the link turns ``taplo`` into the Mise binary and changes
        # the invoked program, so preserve the absolute shim path.
        binary = Path(resolved).absolute()
        # Probe where the tool will actually run. A version-managed shim
        # resolves its tool from the working directory's declared toolchain, so
        # probing in the shim's own directory asks for a version nothing there
        # declares: on a runner that provisions taplo per project the probe
        # exits non-zero and the identity check rejects a perfectly good
        # binary. The format call below uses execution_root; so does this.
        identified = u.Cli.run_raw(
            (str(binary), "--version"),
            cwd=execution_root,
            timeout=process_timeout_seconds,
        )
        if identified.failure:
            return r[Path].fail(
                f"Taplo identity check could not run: {binary}: {identified.error}"
            )
        if not u.Cli.process_succeeded(identified.value.outcome):
            # The cause belongs in the message: a shim that resolves but cannot
            # execute reports the same generic text as a genuine version
            # mismatch, and the two need opposite repairs.
            detail = identified.value.stderr.strip() or identified.value.stdout.strip()
            return r[Path].fail(
                f"Taplo identity check failed: {binary} exited "
                f"{identified.value.outcome.raw_return_code}: "
                f"{detail or 'no diagnostic output'}"
            )
        observed = identified.value.stdout.strip()
        identity_matches = (
            "taplo" in observed.lower()
            if taplo_version == "latest"
            else taplo_version in observed
        )
        if not identity_matches:
            return r[Path].fail(
                "resolved Taplo executable version differs: "
                f"expected={taplo_version} observed={observed}"
            )
        return r[Path].ok(binary)

    @staticmethod
    @cache
    def pyproject_payload(pyproject_path: Path) -> t.JsonMapping:
        """Return one parsed ``pyproject.toml`` payload validated against ``t.Infra``.

        The payload is parsed from the live text with managed merge
        conflicts resolved (``live_pyproject_text``).
        """
        if not pyproject_path.is_file():
            return {}
        live = FlextInfraUtilitiesPyproject.live_pyproject_text(pyproject_path)
        if live.failure:
            msg = f"failed to read pyproject payload at {pyproject_path}: {live.error}"
            raise RuntimeError(msg)
        payload = u.Cli.toml_mapping_from_text(live.value)
        if payload is None:
            msg = f"pyproject payload at {pyproject_path} is not valid TOML"
            raise RuntimeError(msg)
        return FlextInfraUtilitiesPyproject.validate_infra_payload(payload)

    @staticmethod
    def normalized_toml_payload(document: t.Cli.TomlDocument) -> t.JsonMapping:
        """Return one TOML document normalized through the infra adapter."""
        payload = u.Cli.toml_as_mapping(document)
        if not payload:
            return {}
        return FlextInfraUtilitiesPyproject.validate_infra_payload(payload)

    @staticmethod
    def tool_flext_meta(project_root: Path) -> t.JsonMapping:
        """Return the normalized ``tool.flext`` table from a project root."""
        payload = FlextInfraUtilitiesPyproject.pyproject_payload(
            project_root / c.PYPROJECT_FILENAME
        )
        tool = payload.get(c.Infra.TOOL)
        if not isinstance(tool, dict):
            return {}
        flext = tool.get("flext")
        return flext if isinstance(flext, dict) else {}

    @staticmethod
    def docs_meta_from_payload(payload: t.JsonMapping) -> t.JsonMapping:
        """Extract ``tool.flext.docs`` metadata from an already-parsed payload."""
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
        """Return the declared project name from ``[project].name``."""
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
    def package_name_from_payload(
        project_root: Path, payload: t.JsonMapping, docs_meta: t.JsonMapping
    ) -> str:
        """Return the primary package name using pre-loaded pyproject payload."""
        configured = docs_meta.get("package_name")
        if isinstance(configured, str) and configured.strip():
            return configured.strip()
        current: t.JsonMapping | None = payload
        for key in (c.Infra.TOOL, "hatch", "build", "targets", "wheel"):
            if current is None:
                break
            candidate = current.get(key)
            current = candidate if isinstance(candidate, dict) else None
        packages = current.get("packages") if current is not None else None
        if isinstance(packages, list):
            for item in packages:
                package_path = Path(str(item).strip())
                if package_path.parts:
                    package_parts: t.VariadicTuple[str] = package_path.parts
                    return package_parts[-1]
        src_dir = project_root / c.Infra.DEFAULT_SRC_DIR
        if src_dir.is_dir():
            for child in sorted(src_dir.iterdir()):
                if child.is_dir() and (child / c.Infra.INIT_PY).is_file():
                    child_path: Path = child
                    return child_path.name
        project_name = FlextInfraUtilitiesPyproject.project_name_from_payload(
            project_root, payload
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
        """Return the primary Python package name for a project root."""
        payload = FlextInfraUtilitiesPyproject.pyproject_payload(
            project_root / c.PYPROJECT_FILENAME
        )
        docs_meta = FlextInfraUtilitiesPyproject.docs_meta_from_payload(payload)
        return FlextInfraUtilitiesPyproject.package_name_from_payload(
            project_root, payload, docs_meta
        )

    @staticmethod
    @cache
    def workspace_project_paths(repository_root: Path) -> t.StrSequence:
        """Return project paths declared by this directory's own ``.gitmodules``.

        A missing file denotes a standalone project and therefore an empty
        sequence. A malformed declaration is an invalid workspace contract and
        remains a loud error; no pyproject table or parent directory is used as
        an alternate topology source.
        """
        declared = FlextInfraUtilitiesGit.git_declared_submodule_paths(repository_root)
        if declared.failure:
            msg = declared.error or f"invalid workspace topology: {repository_root}"
            raise ValueError(msg)
        return tuple(path.as_posix() for path in declared.value)


__all__: list[str] = ["FlextInfraUtilitiesPyproject"]
