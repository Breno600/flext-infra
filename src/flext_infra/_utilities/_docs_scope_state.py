"""Fresh pyproject-backed state helpers for docs scope."""

from __future__ import annotations

from pathlib import Path

from flext_cli import u

from flext_infra import c, t

from .._models.workspace import FlextInfraModelsWorkspace as mw
from .._utilities._docs_scope_paths import FlextInfraUtilitiesDocsScopePathsMixin
from .._utilities.dependencies import FlextInfraUtilitiesDependencies
from .._utilities.pyproject import FlextInfraUtilitiesPyproject


class FlextInfraUtilitiesDocsScopeStateMixin(FlextInfraUtilitiesDocsScopePathsMixin):
    """Load one authenticated pyproject state for every docs decision."""

    @staticmethod
    def _project_state(project_root: Path) -> mw.ProjectPyprojectState:
        """Return freshly parsed pyproject state for one project root.

        When the pyproject is absent or empty, the returned state carries
        empty ``project_name``/``package_name`` (legitimate "not a project"
        signal). When the pyproject is present but missing ``[project]`` or
        ``[project].name``, :meth:`project_name_from_payload` raises — no
        silent fallback to directory-name.
        """
        root = FlextInfraUtilitiesDocsScopeStateMixin.absolute_lexical(project_root)
        pyproject_path = root / c.PYPROJECT_FILENAME
        snapshot = u.Cli.atomic_read_binary_file_state(pyproject_path, required=False)
        if snapshot.failure:
            raise ValueError(
                snapshot.error or f"cannot inspect docs pyproject: {pyproject_path}"
            )
        if snapshot.value.content is None:
            payload: t.JsonMapping = {}
        else:
            try:
                source = snapshot.value.content.decode(c.Cli.ENCODING_DEFAULT)
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
            payload
        )
        dependency_names = tuple(
            FlextInfraUtilitiesDependencies.declared_dependency_names_from_payload(
                payload
            )
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
                    root, payload
                )
            ),
            package_name=(
                FlextInfraUtilitiesDocsScopeStateMixin.package_name_from_payload(
                    root, payload, docs_meta
                )
            ),
            dependency_names=dependency_names,
        )

    @staticmethod
    def project_state(project_root: Path) -> mw.ProjectPyprojectState:
        """Return one fresh state bound to authenticated pyproject bytes."""
        return FlextInfraUtilitiesDocsScopeStateMixin._project_state(project_root)

    @staticmethod
    def project_name_from_payload(entry: Path, payload: t.JsonMapping) -> str:
        """Return the declared project name from ``[project].name``."""
        return FlextInfraUtilitiesPyproject.project_name_from_payload(entry, payload)

    @staticmethod
    def project_payload(project_root: Path) -> t.JsonMapping:
        """Return a project's ``pyproject.toml`` payload as a plain mapping."""
        return FlextInfraUtilitiesDocsScopeStateMixin.project_state(
            project_root
        ).payload

    @staticmethod
    def docs_meta_from_payload(payload: t.JsonMapping) -> t.JsonMapping:
        """Extract ``tool.flext.docs`` metadata from an already-parsed payload."""
        return FlextInfraUtilitiesPyproject.docs_meta_from_payload(payload)

    @staticmethod
    def docs_scope_enabled(docs_meta: t.JsonMapping) -> bool:
        """Return the ``enabled`` docs-scope flag for pre-loaded metadata.

        The flag defaults to ``True`` only when the key is absent. A present
        but non-bool value is config drift and fails loud — it must never be
        coerced into silently opting the project in or out.
        """
        enabled = docs_meta.get("enabled", True)
        if not isinstance(enabled, bool):
            msg = f"[tool.flext.docs].enabled must be a bool, got {enabled!r}"
            raise TypeError(msg)
        return enabled

    @staticmethod
    def package_name_from_payload(
        project_root: Path, payload: t.JsonMapping, docs_meta: t.JsonMapping
    ) -> str:
        """Return the primary package name using pre-loaded payload.

        Resolution order (no silent fallbacks for flext projects):
          1. Explicit ``[tool.flext.docs].package_name`` override.
          2. ``[tool.hatch.build.targets.wheel.packages]`` first entry.
          3. First ``src/<pkg>/__init__.py`` directory.
          4. Empty string for non-flext projects (roots).

        Raises ``ValueError`` only for flext- projects unable to resolve.
        """
        return FlextInfraUtilitiesPyproject.package_name_from_payload(
            project_root, payload, docs_meta
        )

    @staticmethod
    def project_package_name(project_root: Path) -> str:
        """Return the primary Python package name for a project."""
        return FlextInfraUtilitiesDocsScopeStateMixin.project_state(
            project_root
        ).package_name


__all__: list[str] = ["FlextInfraUtilitiesDocsScopeStateMixin"]
