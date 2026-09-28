"""Path and publication helpers for lazy-init generation."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraCodegenGenerationPathsMixin:
    """Path and root-publication helper methods."""

    # flext-i6nq.10: Only canonical path/publication decisions remain here.
    @staticmethod
    def _is_module_or_package_export(attr_name: str) -> bool:
        """Return whether an entry exports a module or package name."""
        return not attr_name

    @staticmethod
    def _is_private_subpackage_source(module_path: str) -> bool:
        """Return whether a symbol's owner lives in a private subpackage."""
        return any(
            segment.startswith("_")
            and not segment.startswith("__")
            and segment not in c.Infra.LOCAL_INFERRED_SEGMENTS
            for segment in module_path.split(".")[1:]
        )

    @staticmethod
    def _should_publish_root_export(
        export_name: str, lazy_filtered: t.LazyAliasMap
    ) -> bool:
        """Return whether a root export belongs in the frozen ``__all__`` ABI."""
        if export_name in c.Infra.INFRA_ONLY_EXPORTS | c.Infra.PUBLISHED_ALL_EXCLUDE:
            return False
        target = lazy_filtered.get(export_name)
        if target is None:
            return True
        module_path, attr_name = target
        if FlextInfraCodegenGenerationPathsMixin._is_module_or_package_export(
            attr_name
        ):
            return export_name in c.Infra.PUBLIC_ROOT_MODULE_EXPORTS
        if not FlextInfraCodegenGenerationPathsMixin._is_private_subpackage_source(
            module_path
        ):
            return True
        return (
            export_name in c.Infra.ALIAS_NAMES
            or export_name in c.Infra.TEST_RUNTIME_ALIAS_TARGETS
        )

    @staticmethod
    def _is_root_namespace_package(current_pkg: str) -> bool:
        """Return whether a package name is a root namespace."""
        return bool(current_pkg) and "." not in current_pkg

    @staticmethod
    def _is_public_api_root_namespace(current_pkg: str) -> bool:
        """Return whether ``current_pkg`` owns a generated facade-root contract."""
        return FlextInfraCodegenGenerationPathsMixin._is_root_namespace_package(
            current_pkg
        ) and (
            current_pkg not in c.Infra.NON_PUBLIC_LAZY_ROOTS
            or current_pkg == c.Infra.DIR_TESTS
        )

    @staticmethod
    def _is_local_module(mod: str, root_name: str) -> bool:
        """Return whether ``mod`` is local to ``root_name``."""
        return (
            mod.startswith(".")
            or not root_name
            or mod.split(".", maxsplit=1)[0] == root_name
        )

    @staticmethod
    def _relative_owned_module(current_pkg: str, mod: str) -> str:
        """Resolve a same-owner ancestor or sibling without a private absolute import."""
        current_parts = current_pkg.split(".")
        module_parts = mod.split(".")
        common = 0
        for current, target in zip(current_parts, module_parts, strict=False):
            if current != target:
                break
            common += 1
        return "." * (len(current_parts) - common + 1) + ".".join(module_parts[common:])

    @staticmethod
    def _compact_lazy_module_path(current_pkg: str, mod: str) -> str:
        """Compact a lazy module path relative to ``current_pkg`` when valid."""
        if not current_pkg or mod.startswith("."):
            return mod
        if mod.split(".", maxsplit=1)[0] == current_pkg.split(".", maxsplit=1)[0]:
            return FlextInfraCodegenGenerationPathsMixin._relative_owned_module(
                current_pkg, mod
            )
        if mod.startswith("_"):
            return f".{mod}"
        root_pkg = current_pkg.split(".", maxsplit=1)[0]
        first_segment = mod.split(".", maxsplit=1)[0]
        internal_segments = frozenset(current_pkg.split(".")[1:])
        if internal_segments & c.Infra.LOCAL_INFERRED_SEGMENTS:
            return mod
        if first_segment in internal_segments or (
            current_pkg == root_pkg
            and "." in mod
            and first_segment in c.Infra.LOCAL_INFERRED_SEGMENTS
        ):
            return f".{mod}"
        return mod

    @staticmethod
    def _normalize_type_checking_module_path(
        mod: str, local_package_root: str | None
    ) -> str:
        """Normalize local TYPE_CHECKING owners to package-relative imports."""
        if not local_package_root:
            return mod
        if mod.startswith("."):
            return mod
        root_pkg = local_package_root.split(".", maxsplit=1)[0]
        first_segment = mod.split(".", maxsplit=1)[0]
        if first_segment == root_pkg:
            return FlextInfraCodegenGenerationPathsMixin._relative_owned_module(
                local_package_root, mod
            )
        internal_segments = frozenset(local_package_root.split(".")[1:])
        if (
            mod.startswith("_")
            or first_segment in internal_segments
            or (
                local_package_root == root_pkg
                and "." in mod
                and first_segment in c.Infra.LOCAL_INFERRED_SEGMENTS
            )
        ):
            return f".{mod}"
        return mod

    @staticmethod
    def _reject_noncanonical_type_checking_import(
        mod: str, local_package_root: str | None, items: t.StrPairSequence
    ) -> None:
        """Reject a relative TYPE_CHECKING import with no local package context.

        Same-project sibling, ancestor, and cousin owners use the same relative
        path in static declarations and the runtime lazy map. Cross-project
        owners remain absolute. Relative imports require a package context so
        Python can resolve their declared owner.
        """
        if mod.startswith(".") and not local_package_root:
            exports = ", ".join(name for name, _ in items)
            msg = (
                f"relative TYPE_CHECKING import {mod!r} has no local package "
                f"(exports: {exports})"
            )
            raise ValueError(msg)

    @staticmethod
    def _format_root_package_docstring(current_pkg: str) -> str:
        """Format a generated package docstring."""
        label = current_pkg.replace("_", " ").replace("-", " ").strip()
        package_name = " ".join(word.capitalize() for word in label.split())
        return f'"""{package_name} package."""'


__all__: list[str] = ["FlextInfraCodegenGenerationPathsMixin"]
