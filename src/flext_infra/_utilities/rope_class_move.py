"""Atomic, fail-fast Rope class relocation for ``u.Infra``."""

from __future__ import annotations

from pathlib import Path

from flext_cli import u

from flext_infra import c, m, p, t

from ._rope_core_pymodule import FlextInfraUtilitiesRopeCorePyModuleMixin
from .rope_runtime import FlextInfraUtilitiesRopeRuntime


class FlextInfraUtilitiesRopeClassMove:
    """Own the single semantic implementation of class relocation."""

    @classmethod
    def move_class(cls, request: m.Infra.ClassMoveRequest) -> Path:
        """Move one top-level class or return its validated preview target."""
        target_file, mover = cls._class_mover(request)
        root = Path(request.rope_project.root.real_path).resolve()
        if not request.apply:
            return target_file

        created_target = not target_file.exists()
        move_completed = False
        if created_target:
            u.Cli.atomic_write_text_file(
                target_file, f"{c.Infra.FUTURE_ANNOTATIONS}\n"
            ).unwrap()
        try:
            request.rope_project.validate()
            target_resource = cls._resource(request.rope_project, root, target_file)
            changes = mover.get_changes(target_resource)
            request.rope_project.do(changes)
            move_completed = True
            return target_file
        finally:
            if created_target and not move_completed and target_file.exists():
                target_file.unlink()

    @classmethod
    def plan_class_move(
        cls, request: m.Infra.ClassMoveRequest, *, sources: t.MappingKV[Path, str]
    ) -> t.VariadicTuple[m.Infra.SemanticMigrationEdit]:
        """Preview one identity-preserving move inside a closed source inventory."""
        if request.apply:
            msg = "immutable class move planning requires apply=False"
            raise ValueError(msg)
        target_file, mover = cls._class_mover(request)
        root = Path(request.rope_project.root.real_path).resolve()
        if request.source_file.resolve() not in sources or target_file not in sources:
            msg = "class move owners are absent from the governed source inventory"
            raise ValueError(msg)
        resources = [
            cls._resource(request.rope_project, root, path) for path in sorted(sources)
        ]
        for resource in resources:
            path = Path(resource.real_path).resolve()
            if resource.read() != sources[path]:
                msg = f"class move source differs from its planning snapshot: {path}"
                raise ValueError(msg)
        changes = mover.get_changes(
            cls._resource(request.rope_project, root, target_file), resources=resources
        )
        edits: list[m.Infra.SemanticMigrationEdit] = []
        for change in changes.changes:
            if not isinstance(change, p.Infra.RopeChangeContents):
                msg = "class move planning produced a non-content effect"
                raise TypeError(msg)
            path = Path(change.resource.real_path).resolve()
            if path not in sources:
                msg = f"class move escaped its governed source inventory: {path}"
                raise ValueError(msg)
            if change.new_contents != sources[path]:
                edits.append(
                    m.Infra.SemanticMigrationEdit(
                        file_path=path,
                        original_source=sources[path],
                        updated_source=change.new_contents,
                        changes=(f"Rope moved {request.class_name} to {target_file}",),
                    )
                )
        return tuple(edits)

    @classmethod
    def _class_mover(
        cls, request: m.Infra.ClassMoveRequest
    ) -> t.Pair[Path, p.Infra.RopeMoveGlobal]:
        """Resolve both execution and planning from the exact original declaration."""
        root = Path(request.rope_project.root.real_path).resolve()
        source_file = cls._owned_path(root, request.source_file)
        target_file = cls._owned_path(root, request.target_file)
        if source_file == target_file:
            msg = f"class move source and target are identical: {source_file}"
            raise ValueError(msg)
        if not source_file.is_file():
            raise FileNotFoundError(source_file)
        if not target_file.parent.is_dir():
            raise FileNotFoundError(target_file.parent)

        source_resource = cls._resource(request.rope_project, root, source_file)
        source = source_resource.read()
        offset = (
            FlextInfraUtilitiesRopeCorePyModuleMixin.find_identifier_offset_in_lines(
                source.splitlines(keepends=True),
                line=request.line,
                symbol=request.class_name,
            )
        )
        if offset is None:
            msg = f"class {request.class_name} was not found at line {request.line}"
            raise ValueError(msg)
        mover = FlextInfraUtilitiesRopeRuntime.create_move(
            request.rope_project, source_resource, offset
        )
        return target_file, mover

    @staticmethod
    def class_family(class_info: m.Infra.ClassInfo) -> str:
        """Derive the canonical FLEXT family from one Rope class fact."""
        terminal_bases = {
            base_name.rsplit(".", maxsplit=1)[-1] for base_name in class_info.bases
        }
        if terminal_bases & c.Infra.PLACEMENT_PYDANTIC_BASE_NAMES:
            return "m"
        if terminal_bases & c.Infra.PLACEMENT_PROTOCOL_BASE_NAMES:
            return "p"
        if terminal_bases & c.Infra.PLACEMENT_ENUM_BASE_NAMES:
            return "c"
        if any(
            class_info.name.endswith(suffix)
            for suffix in c.Infra.PLACEMENT_UTILITY_NAME_SUFFIXES
        ):
            return "u"
        return ""

    @staticmethod
    def class_module_stem(class_name: str) -> str:
        """Derive one module stem from the core CamelCase boundary authority."""
        return c.CAMEL_TO_SNAKE_RE.sub(r"\1_\2", class_name).lower()

    @classmethod
    def class_target_file(
        cls, *, package_dir: Path, source_file: Path, class_name: str, family: str
    ) -> Path:
        """Derive a canonical destination without a project-owned registry."""
        module_stem = cls.class_module_stem(class_name)
        if family:
            family_dir = c.Infra.FAMILY_DIRECTORIES[family]
            return package_dir / family_dir / f"{module_stem}.py"
        return source_file.parent / f"_{source_file.stem}_{module_stem}.py"

    @staticmethod
    def _owned_path(root: Path, candidate: Path) -> Path:
        resolved = candidate.resolve()
        if not resolved.is_relative_to(root):
            msg = f"class move path is outside Rope project {root}: {resolved}"
            raise ValueError(msg)
        return resolved

    @staticmethod
    def _resource(
        rope_project: t.Infra.RopeProject, root: Path, file_path: Path
    ) -> t.Infra.RopeResource:
        relative_path = file_path.relative_to(root).as_posix()
        return rope_project.get_resource(relative_path)


__all__: list[str] = ["FlextInfraUtilitiesRopeClassMove"]
