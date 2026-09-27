"""Session binding of an external consumer onto one flext worktree.

An external project declares flext packages by pinned git URL, so it always
validates PUBLISHED code. A cross-project change therefore could not be reviewed
until it was published, which inverts the order of work.

``FLEXT=<worktree>`` rebinds the consumer's environment onto that checkout for
the session. It is deliberately NOT a declaration: the consumer's
``pyproject.toml`` is never modified, so a local path can never be committed and
running setup without the flag restores the pinned resolution. Persistent,
declared sources remain owned by ``pyproject_conform._sync_uv_sources``; this
service owns only the session override, so the two never overlap.

The rebind set is derived from the intersection of what the consumer declares
and what the worktree actually provides, read from the worktree's own manifest —
never a hardcoded package list.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import sysconfig
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, config, m, t, u

from .detector import FlextInfraWorkspaceDetector

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraFlextBindingService:
    """Resolve and apply one session binding onto a flext worktree."""

    @staticmethod
    def _declared_distributions(
        consumer_root: Path, *, environment: t.StrMapping | None = None
    ) -> p.Result[t.VariadicTuple[str]]:
        """Return the distribution names the consumer declares as dependencies."""
        manifest = consumer_root / c.Infra.PYPROJECT_FILENAME
        if not manifest.is_file():
            return r[t.VariadicTuple[str]].fail(
                f"consumer has no {c.Infra.PYPROJECT_FILENAME}: {consumer_root}"
            )
        document = u.Cli.toml_parse_text(u.Cli.files_read_text(manifest).unwrap())
        if document is None:
            return r[t.VariadicTuple[str]].fail(
                "consumer dependency declaration is not valid TOML"
            )
        return r[t.VariadicTuple[str]].ok(
            tuple(
                sorted({
                    name
                    for item in u.Infra.active_session_requirements(
                        document, environment=environment
                    )
                    if (name := u.Infra.dep_name(item)) is not None
                })
            )
        )

    @classmethod
    def plan_targets(
        cls,
        *,
        consumer_root: Path,
        flext_root: Path,
        environment: t.StrMapping | None = None,
    ) -> p.Result[t.VariadicTuple[str]]:
        """Return the distributions this worktree can supply to the consumer.

        Fails closed when ``flext_root`` is not a flext workspace, so a mistyped
        path can never silently bind nothing and leave the consumer on its pins.
        """
        paths = cls._binding_paths(
            consumer_root=consumer_root, flext_root=flext_root, environment=environment
        )
        if paths.failure:
            return r[t.VariadicTuple[str]].from_failure(paths)
        return r[t.VariadicTuple[str]].ok(tuple(paths.value))

    @classmethod
    def _binding_paths(
        cls,
        *,
        consumer_root: Path,
        flext_root: Path,
        environment: t.StrMapping | None = None,
    ) -> p.Result[t.MappingKV[str, Path]]:
        """Resolve declared dependencies from the supplier root and its members."""
        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(flext_root)
        if workspace.failure:
            return r[t.MappingKV[str, Path]].fail(
                f"FLEXT is not a flext workspace: {flext_root}: "
                f"{workspace.error or 'manifest unreadable'}"
            )
        available = {
            declared_repository.distribution: (
                flext_root / declared_repository.path
            ).resolve()
            for declared_repository in (
                workspace.value.repository,
                *workspace.value.subprojects,
            )
            if declared_repository.package
        }
        declared = cls._declared_distributions(consumer_root, environment=environment)
        if declared.failure:
            return r[t.MappingKV[str, Path]].from_failure(declared)
        selected = {
            name: available[name]
            for name in sorted(declared.value)
            if name in available
        }
        if not selected:
            return r[t.MappingKV[str, Path]].fail(
                f"requested flext binding selects no declared dependency: consumer={consumer_root}, supplier={flext_root}"
            )
        return r[t.MappingKV[str, Path]].ok(selected)

    @staticmethod
    def _validate_consumer_python(consumer_root: Path, python: Path) -> p.Result[bool]:
        """Reject foreign or symlinked environments while allowing base Python links."""
        identity = u.Infra.exact_worktree_root(consumer_root)
        if identity.failure:
            return r[bool].from_failure(identity)
        runtime_root = identity.value.superproject_root or identity.value.repo_root
        environment = (
            runtime_root / config.Infra.tooling.tools.pyright.path_rules.venv_name
        )
        scripts = Path(
            sysconfig.get_path(
                "scripts",
                scheme="venv",
                vars={"base": str(environment), "platbase": str(environment)},
            )
        )
        expected = scripts / (
            "python.exe" if os.name == "nt" else c.Infra.PromotedSelector.VENV_PYTHON
        )
        for path in (environment, scripts, consumer_root / environment.name):
            if path.is_symlink():
                return r[bool].fail(
                    f"flext binding requires a physical consumer environment: {path}"
                )
        if python.absolute() != expected.absolute():
            return r[bool].fail(
                f"flext binding interpreter must belong to the consumer: expected={expected}, actual={python}"
            )
        if not (environment / "pyvenv.cfg").is_file() or not os.access(
            expected, os.X_OK
        ):
            return r[bool].fail(
                f"flext binding requires the consumer's provisioned environment: {environment}; run make setup"
            )
        return r[bool].ok(True)

    @classmethod
    def consumer_marker_environment(
        cls, *, consumer_root: Path, python: Path
    ) -> p.Result[t.StrMapping]:
        """Query complete PEP 508 facts from the validated consumer interpreter."""
        validated = cls._validate_consumer_python(consumer_root, python)
        if validated.failure:
            return r[t.StrMapping].from_failure(validated)
        script = """import json, os, platform, sys
version = sys.implementation.version
implementation_version = '.'.join(str(part) for part in version[:3])
if version.releaselevel != 'final':
    implementation_version += version.releaselevel[0] + str(version.serial)
print(json.dumps({
    'implementation_name': sys.implementation.name,
    'implementation_version': implementation_version,
    'os_name': os.name,
    'platform_machine': platform.machine(),
    'platform_release': platform.release(),
    'platform_system': platform.system(),
    'platform_version': platform.version(),
    'platform_python_implementation': platform.python_implementation(),
    'python_full_version': platform.python_version(),
    'python_version': '.'.join(platform.python_version_tuple()[:2]),
    'sys_platform': sys.platform,
}))
"""
        outcome = u.Cli.run((str(python), "-c", script), cwd=consumer_root)
        if outcome.failure:
            return r[t.StrMapping].from_failure(outcome)
        facts = m.Infra.DependencyMarkerEnvironment.model_validate_json(
            outcome.value.stdout
        )
        return r[t.StrMapping].ok({
            key: str(value) for key, value in facts.model_dump().items()
        })

    @classmethod
    def apply(
        cls, *, consumer_root: Path, flext_root: Path, python: Path
    ) -> p.Result[int]:
        """Install an explicit local candidate into the consumer's own environment.

        The next setup without a binding restores the declared dependency sources.
        CI installation always keeps its declared non-editable branch contract.
        """
        ci = config.Infra.codegen.make.ci
        if u.Infra.env_value(ci.variable) == ci.value:
            return r[int].fail(
                f"local editable flext binding is prohibited with {ci.variable}={ci.value}"
            )
        marker_environment = cls.consumer_marker_environment(
            consumer_root=consumer_root, python=python
        )
        if marker_environment.failure:
            return r[int].from_failure(marker_environment)
        environment = marker_environment.value
        planned = cls._binding_paths(
            consumer_root=consumer_root, flext_root=flext_root, environment=environment
        )
        if planned.failure:
            return r[int].from_failure(planned)
        paths = planned.value
        document = u.Cli.toml_parse_text(
            u.Cli.files_read_text(consumer_root / c.Infra.PYPROJECT_FILENAME).unwrap()
        )
        if document is None:
            return r[int].fail("consumer dependency declaration is not valid TOML")
        consumer = FlextInfraWorkspaceDetector.load_workspace_spec(
            consumer_root
        ).unwrap()
        requirements, constraints = u.Infra.session_dependency_requirements(
            document,
            consumer,
            selected=tuple(paths),
            consumer_root=consumer_root,
            environment=environment,
        ).unwrap()
        local_sources = u.Infra.session_workspace_sources(
            document,
            consumer,
            selected=tuple(paths),
            consumer_root=consumer_root,
            environment=environment,
        ).unwrap()
        identity = u.Infra.exact_worktree_root(consumer_root).unwrap()
        runtime_root = identity.superproject_root or identity.repo_root
        state = u.Infra.external_tool_state_dir(
            runtime_root, consumer_root, "flext-binding"
        )
        state.mkdir(parents=True, exist_ok=True)
        owned = u.Cli.files_create_temporary_directory(parent_path=state).unwrap()
        resolution: list[str] = []
        for option, filename, lines in (
            ("--overrides", "overrides.txt", requirements),
            ("--constraints", "constraints.txt", constraints),
        ):
            if lines:
                path = owned / filename
                u.Cli.files_write_text(path, "\n".join(lines) + "\n").unwrap()
                resolution.extend((option, str(path)))
        editables: list[str] = []
        active_requirements = u.Infra.active_session_requirements(
            document, environment=environment
        )
        for name in paths:
            editables.extend((
                "--editable",
                str(paths[name]) + u.Infra.dependency_extras(active_requirements, name),
            ))
        for member in consumer.subprojects:
            if member.distribution in local_sources:
                if member.editable:
                    editables.append("--editable")
                editables.append(
                    str(local_sources[member.distribution])
                    + u.Infra.dependency_extras(
                        active_requirements, member.distribution
                    )
                )
        installed = u.Cli.run_checked(
            (
                c.Infra.UV,
                "pip",
                "install",
                "--python",
                str(python),
                *resolution,
                *editables,
            ),
            cwd=consumer_root,
        )
        cleanup = u.Cli.files_remove_directory(owned)
        if installed.failure:
            return r[int].from_failure(installed)
        if cleanup.failure:
            return r[int].from_failure(cleanup)
        u.Cli.info(
            f"flext binding: {len(paths)} package(s) bound to {flext_root} "
            f"({', '.join(paths)}); consumer_python={python}"
        )
        return r[int].ok(0)


__all__: list[str] = ["FlextInfraFlextBindingService"]
