"""Session binding of an external consumer onto one flext worktree.

An external project declares flext packages by pinned git URL, so it always
validates PUBLISHED code. A cross-project change therefore could not be reviewed
until it was published, which inverts the order of work.

The explicit ``workspace flext-binding`` CLI rebinds the consumer's physical
environment onto that checkout for the session. The consumer's
``pyproject.toml`` is never modified; running canonical setup restores its
declared resolution. This operation requires the provisioned consumer Python
and rejects CI before reading or changing the consumer environment.

Like canonical setup, binding considers all declared extras and dependency
groups. Consumer interpreter markers select active requirements; unrelated
dependencies constrain resolution without being installed as new roots.

The rebind set is derived from the intersection of what the consumer declares
and what the worktree actually provides, read from the worktree's own manifest —
never a hardcoded package list.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import sysconfig
from collections.abc import MutableMapping
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import TYPE_CHECKING

from flext_infra import c, config, m, r, t, u
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraFlextBindingService:
    """Resolve and apply one session binding onto a flext worktree."""

    @staticmethod
    def _consumer_environment(consumer_root: Path, python: Path) -> p.Result[Path]:
        """Require a physical consumer environment while permitting base Python links.

        Returns:
            The resulting ``p.Result[Path]``.

        """
        environment = u.Infra.runtime_environment_dir(consumer_root)
        scripts = Path(
            sysconfig.get_path(
                "scripts",
                scheme="venv",
                vars={"base": str(environment), "platbase": str(environment)},
            ),
        )
        expected = scripts / c.Infra.PromotedSelector.VENV_PYTHON
        # A composed member's own environment path must not borrow another
        # checkout's environment either, even when the workspace owns the runtime.
        for path in (
            environment,
            scripts,
            consumer_root / c.Infra.ENVIRONMENT_DIRECTORY,
        ):
            if path.is_symlink():
                return r[Path].fail(
                    f"binding requires a physical consumer environment: {path}",
                )
        if python.absolute() != expected.absolute():
            return r[Path].fail(
                f"binding interpreter must belong to the consumer: "
                f"expected={expected}, actual={python}",
            )
        if not (environment / c.Infra.ENVIRONMENT_METADATA).is_file() or not os.access(
            expected,
            os.X_OK,
        ):
            return r[Path].fail(
                f"binding requires the consumer's provisioned environment: "
                f"{environment}; run make setup",
            )
        return r[Path].ok(environment)

    @classmethod
    def consumer_marker_environment(
        cls,
        *,
        consumer_root: Path,
        python: Path,
    ) -> p.Result[t.StrMapping]:
        """Read PEP 508 facts from the authenticated consumer interpreter.

        Returns:
            The resulting ``p.Result[t.StrMapping]``.

        """
        environment = cls._consumer_environment(consumer_root, python)
        if environment.failure:
            return r[t.StrMapping].from_failure(environment)
        outcome = u.Cli.run(
            (str(python), "-I", "-c", c.Infra.BINDING_MARKER_SCRIPT),
            cwd=consumer_root,
        )
        if outcome.failure:
            return r[t.StrMapping].from_failure(outcome)
        facts = m.Infra.DependencyMarkerEnvironment.model_validate_json(
            outcome.value.stdout,
        )
        if facts.prefix.resolve() != environment.value.resolve():
            return r[t.StrMapping].fail(
                "binding interpreter reports a foreign environment",
            )
        return r[t.StrMapping].ok({
            key: str(value) for key, value in facts.model_dump().items()
        })

    @staticmethod
    def _document(consumer_root: Path) -> t.Cli.TomlDocument:
        """Read the consumer declaration through its canonical parser.

        Returns:
            The resulting ``t.Cli.TomlDocument``.

        Raises:
            ValueError: If consumer dependency declaration is not valid TOML.

        """
        document = u.Cli.toml_parse_text(
            u.Cli.files_read_text(consumer_root / c.PYPROJECT_FILENAME).unwrap(),
        )
        if document is None:
            msg = "consumer dependency declaration is not valid TOML"
            raise ValueError(msg)
        return document

    @staticmethod
    def _binding_paths(
        *,
        requirements: t.StrSequence,
        flext_root: Path,
    ) -> p.Result[t.MappingKV[str, Path]]:
        """Return the distributions this worktree can supply to the consumer.

        Fails closed when ``flext_root`` is not a flext workspace, so a mistyped
        path can never silently bind nothing and leave the consumer on its pins.

        Returns:
            The distributions this worktree can supply to the consumer.

        """
        workspace = FlextInfraWorkspaceDetector.load_workspace_spec(flext_root)
        if workspace.failure:
            return r[t.MappingKV[str, Path]].fail(
                f"FLEXT is not a flext workspace: {flext_root}: "
                f"{workspace.error or 'manifest unreadable'}",
            )
        available: MutableMapping[str, Path] = {}
        for repository in (workspace.value.repository, *workspace.value.subprojects):
            if not repository.package:
                continue
            name = u.Infra.dep_name(repository.distribution)
            if name is None or name in available:
                return r[t.MappingKV[str, Path]].fail(
                    f"binding supplier has an invalid or duplicate "
                    f"distribution: {repository.distribution}",
                )
            available[name] = (flext_root / repository.path).resolve()
        names = {u.Infra.dep_name(item) for item in requirements}
        selected = {
            name: available[name] for name in sorted(available) if name in names
        }
        if not selected:
            return r[t.MappingKV[str, Path]].fail(
                "requested binding selects no active declared dependency",
            )
        for path in selected.values():
            if not (path / c.PYPROJECT_FILENAME).is_file():
                return r[t.MappingKV[str, Path]].fail(
                    f"binding supplier package is not provisioned: {path}",
                )
        return r[t.MappingKV[str, Path]].ok(selected)

    @classmethod
    def plan_targets(
        cls,
        *,
        consumer_root: Path,
        flext_root: Path,
        python: Path,
    ) -> p.Result[t.VariadicTuple[str]]:
        """Resolve targets with marker facts from the consumer's interpreter.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[str]]``.

        """
        environment = cls.consumer_marker_environment(
            consumer_root=consumer_root,
            python=python,
        )
        if environment.failure:
            return r[t.VariadicTuple[str]].from_failure(environment)
        requirements = u.Infra.active_session_requirements(
            cls._document(consumer_root),
            environment=environment.value,
        )
        return cls._binding_paths(requirements=requirements, flext_root=flext_root).map(
            tuple,
        )

    @classmethod
    def apply(
        cls,
        *,
        consumer_root: Path,
        flext_root: Path,
        python: Path,
    ) -> p.Result[int]:
        """Rebind the consumer environment onto the worktree for this session.

        Returns:
            The resulting ``p.Result[int]``.

        """
        ci = config.Infra.codegen.make.ci
        if u.Infra.env_value(ci.variable) == ci.value:
            return r[int].fail(
                f"local editable binding is prohibited with {ci.variable}={ci.value}",
            )
        environment = cls.consumer_marker_environment(
            consumer_root=consumer_root,
            python=python,
        )
        if environment.failure:
            return r[int].from_failure(environment)
        document = cls._document(consumer_root)
        requirements = u.Infra.active_session_requirements(
            document,
            environment=environment.value,
        )
        planned = cls._binding_paths(requirements=requirements, flext_root=flext_root)
        if planned.failure:
            return r[int].from_failure(planned)
        paths = planned.value
        resolution = u.Infra.session_dependency_requirements(
            document,
            requirements=requirements,
            selected=tuple(paths),
            environment=environment.value,
        )
        if resolution.failure:
            return r[int].from_failure(resolution)
        editables: list[str] = []
        for name, path in paths.items():
            editables.extend((
                "--editable",
                str(path) + u.Infra.dependency_extras(requirements, name),
            ))
        owned_environment = cls._consumer_environment(consumer_root, python).unwrap()
        with TemporaryDirectory(dir=owned_environment) as directory:
            arguments: list[str] = []
            for (option, filename), lines in zip(
                c.Infra.BINDING_RESOLUTION_FILES,
                (resolution.value.overrides, resolution.value.constraints),
                strict=True,
            ):
                if lines:
                    path = Path(directory) / filename
                    u.Cli.files_write_text(path, "\n".join(lines) + "\n").unwrap()
                    arguments.extend((option, str(path)))
            installed = u.Cli.run_checked(
                (
                    c.Infra.UV,
                    "pip",
                    "install",
                    # Why: the binding already translated the consumer's
                    # [tool.uv] overrides/constraints into the files above;
                    # uv would otherwise rediscover them from the cwd project
                    # and re-apply an override to the bound editable, sending
                    # its name to the registry instead of the worktree path.
                    "--no-config",
                    "--python",
                    str(python),
                    *arguments,
                    *editables,
                ),
                cwd=consumer_root,
            )
            if installed.failure:
                return r[int].from_failure(installed)
        u.Cli.info(
            f"flext binding: {len(paths)} package(s) bound to {flext_root} "
            f"({', '.join(paths)}); consumer_python={python}",
        )
        return r[int].ok(0)


__all__: list[str] = ["FlextInfraFlextBindingService"]
