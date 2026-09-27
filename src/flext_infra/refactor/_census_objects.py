"""Census object classification, violation building, and impact map — extracted concern."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, u

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraRefactorCensusObjectsMixin:
    """Object classification, violation/key construction, and impact-map results.

    Composed into FlextInfraRefactorCensus via inheritance; self-contained
    (static/cls helpers over report Object/Violation models, no census state).
    """

    @staticmethod
    def _raw_violation(
        *,
        project: str,
        object_name: str,
        object_kind: str,
        kind: str,
        file_path: Path,
        line: int,
        description: str,
        fixable: bool = False,
        fix_action: str = "",
    ) -> m.Infra.Violation:
        """Raw violation."""
        return m.Infra.Violation(
            project=project,
            object_name=object_name,
            object_kind=object_kind,
            kind=kind,
            file_path=str(file_path),
            line=line,
            fixable=fixable,
            fix_action=fix_action,
            description=description,
        )

    @staticmethod
    def _selected_families(family_names: t.StrSequence | None) -> frozenset[str]:
        """Return the selected families."""
        if not family_names:
            return frozenset()
        resolved = {
            c.Infra.FAMILY_SUFFIXES.get(name, name).lower() for name in family_names
        }
        return frozenset(resolved)

    @staticmethod
    def _violation(
        item: m.Infra.Object,
        *,
        kind: str,
        description: str,
        fixable: bool = False,
        fix_action: str = "",
    ) -> m.Infra.Violation:
        """Violation."""
        return FlextInfraRefactorCensusObjectsMixin._raw_violation(
            project=item.project,
            object_name=item.name,
            object_kind=item.kind,
            kind=kind,
            file_path=Path(item.file_path),
            line=item.line,
            description=description,
            fixable=fixable,
            fix_action=fix_action,
        )

    @staticmethod
    def _is_unused(item: m.Infra.Object) -> bool:
        """Is unused."""
        return (
            not item.is_facade_member
            and item.references_count == 0
            and not item.name.startswith("_")
            and not FlextInfraRefactorCensusObjectsMixin._is_pytest_entry_point(item)
            and not FlextInfraRefactorCensusObjectsMixin._is_published_export(item)
        )

    @staticmethod
    def _is_published_export(item: m.Infra.Object) -> bool:
        """Keep package ABI bindings even when Rope sees only typing imports."""
        if item.scope_path != item.name:
            return False
        package_name = item.module_name.rpartition(".")[0]
        package_dir = Path(item.file_path).parent
        while package_name:
            init_path = package_dir / c.Infra.INIT_PY
            if init_path.is_file():
                source = init_path.read_text(encoding="utf-8")
                for export_name in u.Infra.public_export_names_source(source):
                    module_name, original_name = u.Infra.imported_symbol_binding_source(
                        source,
                        current_module=package_name,
                        symbol_name=export_name,
                        package_module=True,
                    )
                    if module_name == item.module_name and original_name == item.name:
                        return True
            package_name = package_name.rpartition(".")[0]
            package_dir = package_dir.parent
        return False

    @staticmethod
    def _is_pytest_entry_point(item: m.Infra.Object) -> bool:
        """Return whether the object is a pytest entry point in a test module.

        Pytest discovers ``test_*`` callables in test modules and executes
        them without any in-repository reference, so a zero reference count
        never makes one a removal candidate: census apply would otherwise
        delete the tests it is asked to validate.
        """
        return (
            item.kind in {"class", "function", "method"}
            and item.name.startswith(c.Infra.NAMESPACE_PYTEST_MODULE_PREFIX)
            and u.Infra.pytest_test_module(Path(item.file_path))
        )

    @classmethod
    def _removal_candidate(
        cls, item: m.Infra.Object, *, include_unused: bool
    ) -> m.Infra.RemovalCandidate | None:
        """Build a removal candidate for an object."""
        if include_unused and cls._is_unused(item):
            reason, suggested_action = "unused", "delete_object_definition"
        else:
            return None
        return m.Infra.RemovalCandidate(
            project=item.project,
            object_name=item.name,
            object_kind=item.kind,
            file_path=item.file_path,
            line=item.line,
            scope_path=item.scope_path,
            reason=reason,
            suggested_action=suggested_action,
            runtime_reference_sites=item.runtime_reference_sites,
            script_reference_sites=item.script_reference_sites,
        )

    @staticmethod
    def _object_key(item: m.Infra.Object) -> str:
        """Object key."""
        return f"{item.file_path}:{item.line}:{item.scope_path}:{item.kind}"

    @staticmethod
    def _fix_key(file_path: Path, object_name: str, action: str = "") -> str:
        """Fix key."""
        suffix = f"::{action}" if action else ""
        return f"{file_path.resolve()}::{object_name}{suffix}"

    @classmethod
    def _impact_map_results(
        cls, report: m.Infra.WorkspaceReport
    ) -> t.VariadicTuple[m.Infra.Result]:
        """Impact map results."""
        changes_by_file: MutableMapping[Path, list[str]] = defaultdict(list)
        for candidate in report.removal_candidates:
            source_path = Path(candidate.file_path)
            cls._append_impact_change(
                changes_by_file,
                source_path,
                f"{candidate.suggested_action}: {candidate.object_name} ({candidate.reason})",
            )
            for site in cls._reference_sites(candidate):
                cls._append_impact_change(
                    changes_by_file,
                    Path(site.file_path),
                    f"remove reference to {candidate.object_name} at line {site.line} ({site.surface})",
                )
        return tuple(
            m.Infra.Result(
                file_path=file_path,
                success=True,
                modified=True,
                changes=tuple(changes_by_file[file_path]),
            )
            for file_path in sorted(changes_by_file, key=Path.as_posix)
        )

    @staticmethod
    def _append_impact_change(
        changes_by_file: t.MappingKV[Path, t.MutableSequenceOf[str]],
        file_path: Path,
        change: str,
    ) -> None:
        """Append impact change."""
        normalized_path = file_path.resolve()
        if change not in changes_by_file[normalized_path]:
            changes_by_file[normalized_path].append(change)

    @staticmethod
    def _reference_sites(
        candidate: m.Infra.RemovalCandidate,
    ) -> t.VariadicTuple[m.Infra.ReferenceSite]:
        """Return all reference sites for a removal candidate."""
        return (*candidate.runtime_reference_sites, *candidate.script_reference_sites)

    @staticmethod
    def _is_flext_owned(value: p.ModuleOwned) -> bool:
        """Return True iff `value`'s defining module is in the flext package tree.

        Used to filter the parent inventory so that builtin attributes
        inherited by str/int/dict/list constants do not pollute collision
        candidates with names like `count`, `index`, `replace`, etc.
        """
        module_name = getattr(value, "__module__", "")
        if not isinstance(module_name, str):
            return False
        return module_name.startswith(c.Infra.PKG_PREFIX_UNDERSCORE)


__all__: list[str] = ["FlextInfraRefactorCensusObjectsMixin"]
