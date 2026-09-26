"""Configuration-backed docs scope policy and classification helpers."""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path

from flext_cli import u

from flext_infra import c, t

from ._docs_scope_state import FlextInfraUtilitiesDocsScopeStateMixin
from .workspace_manifest import FlextInfraUtilitiesWorkspaceManifest


class FlextInfraUtilitiesDocsScopePolicyMixin(FlextInfraUtilitiesDocsScopeStateMixin):
    """Interpret the authenticated docs policy for one project or workspace."""

    @staticmethod
    def config_path(repository_root: Path) -> Path:
        """Return the minimal docs policy settings path."""
        dir_docs: str = c.Infra.DIR_DOCS
        docs_config: str = c.Infra.DOCS_CONFIG_FILENAME
        return repository_root / dir_docs / docs_config

    @staticmethod
    def load_config(repository_root: Path) -> t.JsonMapping:
        """Load the minimal docs policy settings if present."""
        path = FlextInfraUtilitiesDocsScopePolicyMixin.config_path(repository_root)
        # An absent optional config has no parent identity to authenticate. A
        # present parent is delegated to the atomic owner, which still rejects
        # symlinks, unsafe identities, and every real read failure.
        if not path.parent.exists():
            return {}
        state = u.Cli.atomic_read_binary_file_state(path, required=False)
        if state.failure:
            raise ValueError(state.error or f"docs config is unsafe: {path}")
        if state.value.content is None:
            return {}
        parsed = u.Cli.json_loads(state.value.content)
        if parsed.failure:
            raise ValueError(parsed.error or f"docs config JSON is invalid: {path}")
        value = parsed.value
        if not isinstance(value, dict):
            msg = f"docs config root must be a mapping: {path}"
            raise TypeError(msg)
        validated = t.Infra.INFRA_MAPPING_ADAPTER.validate_python(value)
        return dict(validated)

    @staticmethod
    def manifest_excluded_roots(repository_root: Path) -> t.Infra.StrSet:
        """Return directory names excluded by the workspace topology manifest.

        ``config/workspace.yaml`` is the handwritten topology SSOT and its own
        header instructs the operator to "declare members/exclusions here", but
        discovery used to consult only the docs-scope config, so a declared
        exclusion did nothing and a non-PEP621 subtree (a vendored directory, a
        Poetry-native submodule) made ``make gen`` fail with "missing [project]
        table" and offered no working escape hatch.

        The manifest is read with the same primitive its own owner uses
        (``workspace/detector.py``) and is treated as optional and advisory
        here: this helper only narrows discovery, so a repository with no
        manifest, or one whose manifest is being edited, must degrade to "no
        extra exclusions" rather than break every docs and deps phase. The
        manifest's authoritative validation stays in its owner, which fails
        loud.
        """
        manifest_path = FlextInfraUtilitiesWorkspaceManifest.workspace_manifest_path(
            repository_root
        )
        if not manifest_path.is_file():
            return set()
        loaded = u.Cli.config_load(manifest_path, expand_env=False)
        if loaded.failure:
            # A present-but-unreadable manifest must never read as "no
            # exclusions": that would silently widen the docs scope.
            raise ValueError(
                loaded.error or f"cannot load workspace manifest: {manifest_path}"
            )
        data = loaded.value.data
        if not isinstance(data, dict):
            return set()
        declared = data.get("exclusions")
        if not isinstance(declared, list):
            return set()
        names: set[str] = set()
        for item in declared:
            if not isinstance(item, dict):
                continue
            raw = item.get("path")
            if raw is None:
                continue
            # Discovery filters on the directory name, so a nested declaration
            # such as "vendor/upstream" contributes the leaf it can match.
            name = Path(str(raw).strip()).name
            if name:
                names.add(name)
        return names

    @staticmethod
    def excluded_roots(repository_root: Path) -> t.Infra.StrSet:
        """Return every explicitly excluded root directory.

        Union of the docs-scope config and the workspace topology manifest, so
        one declaration works wherever an operator makes it. Two independent
        exclusion owners is what let a declared exclusion be silently ignored.
        """
        owner = FlextInfraUtilitiesDocsScopePolicyMixin
        excluded_names = owner.manifest_excluded_roots(repository_root)
        payload = owner.load_config(repository_root)
        scope = payload.get("scope")
        if not isinstance(scope, dict):
            return excluded_names
        excluded = scope.get("exclude_roots")
        if not isinstance(excluded, list):
            return excluded_names
        return excluded_names | {
            str(item).strip() for item in excluded if str(item).strip()
        }

    @staticmethod
    def project_docs_meta(project_root: Path) -> t.JsonMapping:
        """Return optional ``tool.flext.docs`` metadata from a project pyproject."""
        return FlextInfraUtilitiesDocsScopePolicyMixin.project_state(
            project_root
        ).docs_meta

    @staticmethod
    def docs_meta_list(project_root: Path, key: str) -> t.StrSequence:
        """Return one normalized string-list value from ``tool.flext.docs``."""
        docs_meta = FlextInfraUtilitiesDocsScopePolicyMixin.project_docs_meta(
            project_root
        )
        raw = docs_meta.get(key)
        if not isinstance(raw, list):
            return ()
        return [str(item).strip() for item in raw if str(item).strip()]

    @staticmethod
    def is_excluded_doc_path(project_root: Path, relative_path: Path) -> bool:
        """Return whether a relative docs path is excluded by ``tool.flext.docs``."""
        candidate = relative_path.as_posix()
        for pattern in FlextInfraUtilitiesDocsScopePolicyMixin.docs_meta_list(
            project_root, "exclude_docs"
        ):
            if fnmatch(candidate, pattern):
                return True
        return False

    @staticmethod
    def is_governed_project(project_name: str, repository_root: Path) -> bool:
        """Return whether a project belongs to the governed FLEXT docs scope."""
        project_root = repository_root / project_name
        docs_meta = FlextInfraUtilitiesDocsScopePolicyMixin.project_docs_meta(
            project_root
        )
        is_enabled = FlextInfraUtilitiesDocsScopePolicyMixin.docs_scope_enabled(
            docs_meta
        )
        return (
            project_name.startswith(c.Infra.PKG_PREFIX_HYPHEN)
            and project_name
            not in FlextInfraUtilitiesDocsScopePolicyMixin.excluded_roots(
                repository_root
            )
            and is_enabled
        )

    @staticmethod
    def classify_project_from_meta(project_name: str, docs_meta: t.JsonMapping) -> str:
        """Classify a project using pre-loaded docs metadata (avoids re-parsing).

        Project-prefix heuristics derive from ``c.Infra.INTEGRATION_CLASS_PREFIXES``
        (SSOT for integration project family) so adding a new family member
        requires editing only the canonical class-prefix tuple.
        """
        configured = docs_meta.get("project_class")
        if isinstance(configured, str) and configured.strip():
            return configured.strip()
        integration_prefixes = tuple(
            f"{c.Infra.PKG_PREFIX_HYPHEN}{prefix.removeprefix('Flext').lower()}-"
            for prefix in c.Infra.INTEGRATION_CLASS_PREFIXES
        )
        if project_name.startswith(integration_prefixes):
            return "integration"
        if project_name == f"{c.Infra.PKG_PREFIX_HYPHEN}infra":
            return "infra"
        if project_name == f"{c.Infra.PKG_PREFIX_HYPHEN}tests":
            return "test"
        return "domain"

    @staticmethod
    def required_project_files() -> t.StrSequence:
        """Return the required standard docs contract for FLEXT projects."""
        return [
            "README.md",
            "docs/index.md",
            "docs/guides/README.md",
            "docs/api-reference/README.md",
            "docs/api-reference/generated/overview.md",
            "docs/api-reference/generated/public-api.md",
            "docs/api-reference/generated/modules/index.md",
            "mkdocs.yml",
        ]


__all__: list[str] = ["FlextInfraUtilitiesDocsScopePolicyMixin"]
