"""Fresh pyproject-backed state helpers for docs scope.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from flext_cli import u

from flext_infra import c, t
from flext_infra._models.workspace import FlextInfraModelsWorkspace as mw
from flext_infra._utilities._docs_scope_paths import (
    FlextInfraUtilitiesDocsScopePathsMixin,
)
from flext_infra._utilities.dependencies import FlextInfraUtilitiesDependencies
from flext_infra._utilities.pyproject import FlextInfraUtilitiesPyproject


class FlextInfraUtilitiesDocsScopeStateMixin(FlextInfraUtilitiesDocsScopePathsMixin):
    """Load one authenticated pyproject state for every docs decision."""

    @staticmethod
    def _project_state(project_root: Path) -> mw.ProjectPyprojectState:
        """Return project state bound to the current authenticated file bytes.

        When the pyproject is absent or empty, the returned state carries
        empty ``project_name``/``package_name`` (legitimate "not a project"
        signal). When the pyproject is present but missing ``[project]`` or
        ``[project].name``, :meth:`project_name_from_payload` raises — no
        silent fallback to directory-name.

        Returns:
            Project state bound to the current authenticated file bytes.

        Raises:
            ValueError: If ``snapshot.failure``.

        """
        root = FlextInfraUtilitiesDocsScopeStateMixin.absolute_lexical(project_root)
        pyproject_path = root / c.PYPROJECT_FILENAME
        snapshot = u.Cli.atomic_read_binary_file_state(pyproject_path, required=False)
        if snapshot.failure:
            raise ValueError(
                snapshot.error or f"cannot inspect docs pyproject: {pyproject_path}",
            )
        return FlextInfraUtilitiesDocsScopeStateMixin._state_from_content(
            root,
            pyproject_path,
            snapshot.value.content,
        ).model_copy(deep=True)

    @staticmethod
    @lru_cache(maxsize=c.Infra.CONTENT_CACHE_MAXSIZE)
    def _state_from_content(
        root: Path,
        pyproject_path: Path,
        content: bytes | None,
    ) -> mw.ProjectPyprojectState:
        """Parse once per byte-identical canonical pyproject snapshot.

        Returns:
            The resulting ``mw.ProjectPyprojectState``.

        Raises:
            ValueError: If ``recovered.failure``; or if docs pyproject TOML is invalid;
                or if docs pyproject is not valid UTF-8.

        """
        if content is None:
            payload: t.JsonMapping = {}
        else:
            try:
                source = content.decode(c.Cli.ENCODING_DEFAULT)
            except UnicodeDecodeError as exc:
                msg = f"docs pyproject is not valid UTF-8: {pyproject_path}"
                raise ValueError(msg) from exc
            # The live text is read with managed merge conflicts resolved (the
            # same owner the metadata and overlay readers use).
            recovered = FlextInfraUtilitiesPyproject.recover_live_pyproject_text(source)
            if recovered.failure:
                raise ValueError(recovered.error)
            parsed = u.Cli.toml_mapping_from_text(recovered.value)
            if parsed is None:
                msg = f"docs pyproject TOML is invalid: {pyproject_path}"
                raise ValueError(msg)
            validated = FlextInfraUtilitiesPyproject.validate_infra_payload(parsed)
            payload = validated
        docs_meta = FlextInfraUtilitiesDocsScopeStateMixin.docs_meta_from_payload(
            payload,
        )
        dependency_names = tuple(
            FlextInfraUtilitiesDependencies.declared_dependency_names_from_payload(
                payload,
            ),
        )
        if not payload:
            return mw.ProjectPyprojectState(
                project_root=root,
                pyproject_path=pyproject_path,
                payload=payload,
                docs_meta=docs_meta,
                project_name="",
                package_name="",
                dependency_names=dependency_names,
            )
        return mw.ProjectPyprojectState(
            project_root=root,
            pyproject_path=pyproject_path,
            payload=payload,
            docs_meta=docs_meta,
            project_name=(
                FlextInfraUtilitiesDocsScopeStateMixin.project_name_from_payload(
                    root,
                    payload,
                )
            ),
            package_name=(
                FlextInfraUtilitiesDocsScopeStateMixin.package_name_from_payload(
                    root,
                    payload,
                    docs_meta,
                )
            ),
            dependency_names=dependency_names,
        )

    @staticmethod
    def project_state(project_root: Path) -> mw.ProjectPyprojectState:
        """Return one fresh state bound to authenticated pyproject bytes.

        Returns:
            One fresh state bound to authenticated pyproject bytes.

        """
        return FlextInfraUtilitiesDocsScopeStateMixin._project_state(project_root)

    @staticmethod
    def project_name_from_payload(entry: Path, payload: t.JsonMapping) -> str:
        """Return the declared project name from ``[project].name``.

        Returns:
            The declared project name from ``[project].name``.

        """
        return FlextInfraUtilitiesPyproject.project_name_from_payload(entry, payload)

    @staticmethod
    def project_payload(project_root: Path) -> t.JsonMapping:
        """Return a project's ``pyproject.toml`` payload as a plain mapping.

        Returns:
            A project's ``pyproject.toml`` payload as a plain mapping.

        """
        return FlextInfraUtilitiesDocsScopeStateMixin.project_state(
            project_root,
        ).payload

    @staticmethod
    def docs_meta_from_payload(payload: t.JsonMapping) -> t.JsonMapping:
        """Extract ``tool.flext.docs`` metadata from an already-parsed payload.

        Returns:
            The resulting ``t.JsonMapping``.

        """
        return FlextInfraUtilitiesPyproject.docs_meta_from_payload(payload)

    @staticmethod
    def docs_scope_enabled(docs_meta: t.JsonMapping) -> bool:
        """Return the ``enabled`` docs-scope flag for pre-loaded metadata.

        The flag defaults to ``True`` only when the key is absent. A present
        but non-bool value is config drift and fails loud — it must never be
        coerced into silently opting the project in or out.

        Returns:
            The ``enabled`` docs-scope flag for pre-loaded metadata.

        Raises:
            TypeError: If [tool.flext.docs].enabled must be a bool, got.

        """
        enabled = docs_meta.get("enabled", True)
        if not isinstance(enabled, bool):
            msg = f"[tool.flext.docs].enabled must be a bool, got {enabled!r}"
            raise TypeError(msg)
        return enabled

    @staticmethod
    def package_name_from_payload(
        project_root: Path,
        payload: t.JsonMapping,
        docs_meta: t.JsonMapping,
    ) -> str:
        """Return the primary package name using pre-loaded payload.

        Resolution order (no silent fallbacks for flext projects):
          1. Explicit ``[tool.flext.docs].package_name`` override.
          2. ``[tool.hatch.build.targets.wheel.packages]`` first entry.
          3. First ``src/<pkg>/__init__.py`` directory.
          4. Empty string for non-flext projects (roots).

        Raises ``ValueError`` only for flext- projects unable to resolve.

        Returns:
            The primary package name using pre-loaded payload.

        """
        return FlextInfraUtilitiesPyproject.package_name_from_payload(
            project_root,
            payload,
            docs_meta,
        )

    @staticmethod
    def project_package_name(project_root: Path) -> str:
        """Return the primary Python package name for a project.

        Returns:
            The primary Python package name for a project.

        """
        return FlextInfraUtilitiesDocsScopeStateMixin.project_state(
            project_root,
        ).package_name


__all__: list[str] = ["FlextInfraUtilitiesDocsScopeStateMixin"]
