"""Structural protocols for the external Rope runtime boundary.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, Protocol, runtime_checkable

if TYPE_CHECKING:
    # This boundary also supplies t.Infra's aliases, so it cannot depend on them.
    from flext_core import p, t


@runtime_checkable
class FlextInfraProtocolsRopeRuntime(Protocol):
    """Rope object contracts used instead of importing untyped Rope classes."""

    @runtime_checkable
    class RopeRoot(Protocol):
        """Rope project root shape."""

        @property
        def real_path(self) -> str: ...

        def get_child(
            self,
            name: str,
        ) -> FlextInfraProtocolsRopeRuntime.RopeResource: ...

        def has_child(self, name: str) -> bool: ...

    @runtime_checkable
    class RopeResource(Protocol):
        """Rope project resource shape shared by files and folders."""

        @property
        def path(self) -> str: ...

        @property
        def real_path(self) -> str: ...

        @property
        def parent(self) -> FlextInfraProtocolsRopeRuntime.RopeRoot: ...

    @runtime_checkable
    class RopeFile(Protocol):
        """Rope file resource with content access."""

        @property
        def path(self) -> str: ...

        @property
        def real_path(self) -> str: ...

        @property
        def parent(self) -> FlextInfraProtocolsRopeRuntime.RopeRoot: ...

        def read(self) -> str: ...

        def write(self, contents: str) -> None: ...

    @runtime_checkable
    class RopePyObject(Protocol):
        """Rope semantic object shape."""

        def get_attribute(
            self,
            name: str,
        ) -> FlextInfraProtocolsRopeRuntime.RopePyName: ...

        def get_attributes(
            self,
        ) -> t.MappingKV[str, FlextInfraProtocolsRopeRuntime.RopePyName]: ...

        def get_doc(self) -> str | None: ...

        def get_name(self) -> str: ...

        def get_module(self) -> FlextInfraProtocolsRopeRuntime.RopePyModule | None: ...

        def get_kind(self) -> str: ...

        def get_scope(self) -> FlextInfraProtocolsRopeRuntime.RopeScope | None: ...

        def get_superclasses(
            self,
        ) -> t.SequenceOf[FlextInfraProtocolsRopeRuntime.RopePyObject]: ...

        def get_type(self) -> FlextInfraProtocolsRopeRuntime.RopePyObject: ...

    @runtime_checkable
    class NativeClassMetadata(Protocol):
        """CPython class metadata published by Rope's builtin class object."""

        __module__: str
        __qualname__: str
        __base__: FlextInfraProtocolsRopeRuntime.NativeClassMetadata | None
        __bases__: tuple[FlextInfraProtocolsRopeRuntime.NativeClassMetadata, ...]

    @runtime_checkable
    class RopeBuiltinClass(Protocol):
        """Rope's exact native class identity, not an inferred instance type."""

        builtin: FlextInfraProtocolsRopeRuntime.NativeClassMetadata

    @runtime_checkable
    class RopeAstNode(Protocol):
        """Raw AST node shape from ``RopePyModule.get_ast()``.

        Minimal contract for Python ``ast.AST`` nodes as exposed by Rope.
        Consumers access attributes via ``getattr``/``hasattr``; the protocol
        declares the common fields that appear across all node types.
        """

        _fields: ClassVar[t.VariadicTuple[str]]

    @runtime_checkable
    class RopeSourceLines(Protocol):
        """Native source line text and character offsets used by refactors."""

        def get_line(self, lineno: int) -> str: ...

        def get_line_start(self, lineno: int) -> int: ...

        def get_line_end(self, lineno: int) -> int: ...

    @runtime_checkable
    class RopeAssignment(Protocol):
        """Rope assignment shape."""

        ast_node: FlextInfraProtocolsRopeRuntime.RopeAstNode

    @runtime_checkable
    class RopePyName(Protocol):
        """Rope semantic name shape."""

        def get_object(self) -> FlextInfraProtocolsRopeRuntime.RopePyObject: ...

        def get_definition_location(
            self,
        ) -> tuple[FlextInfraProtocolsRopeRuntime.RopePyModule | None, int | None]: ...

    @runtime_checkable
    class RopeAssignedName(RopePyName, Protocol):
        """Rope assigned-name marker shape."""

        assignments: t.SequenceOf[FlextInfraProtocolsRopeRuntime.RopeAssignment]

    @runtime_checkable
    class RopeImportedModule(RopePyName, Protocol):
        """Declared import provenance, before its module is evaluated."""

        importing_module: FlextInfraProtocolsRopeRuntime.RopePyModule
        module_name: str | None
        level: int
        resource: FlextInfraProtocolsRopeRuntime.RopeResource | None

    @runtime_checkable
    class RopeImportedName(RopePyName, Protocol):
        """Import binding with its declaring module and original symbol."""

        imported_module: FlextInfraProtocolsRopeRuntime.RopeImportedModule
        imported_name: str

    @runtime_checkable
    class RopeScope(Protocol):
        """Rope semantic scope shape."""

        def get_scopes(
            self,
        ) -> t.SequenceOf[FlextInfraProtocolsRopeRuntime.RopeScope]: ...

        def get_names(
            self,
        ) -> t.MappingKV[str, FlextInfraProtocolsRopeRuntime.RopePyName]: ...

        def get_defined_names(
            self,
        ) -> t.MappingKV[str, FlextInfraProtocolsRopeRuntime.RopePyName]: ...

        def get_kind(self) -> str | None: ...

        def get_start(self) -> int: ...

        def get_end(self) -> int: ...

        @property
        def pyobject(self) -> FlextInfraProtocolsRopeRuntime.RopePyObject: ...

    @runtime_checkable
    class RopePyModule(Protocol):
        """Rope parsed module shape."""

        source_code: str

        def get_module(self) -> FlextInfraProtocolsRopeRuntime.RopePyModule | None: ...

        def get_attribute(
            self,
            name: str,
        ) -> FlextInfraProtocolsRopeRuntime.RopePyName: ...

        def get_name(self) -> str: ...

        def get_doc(self) -> str | None: ...

        # NOTE (multi-agent, flext-f8vk / kimi): rope returns None for
        # string-parsed modules (pycore.get_string_module(resource=None));
        # the widened contract keeps every consumer None guard live.
        def get_resource(
            self,
        ) -> FlextInfraProtocolsRopeRuntime.RopeFile | None: ...

        def get_attributes(
            self,
        ) -> t.MappingKV[str, FlextInfraProtocolsRopeRuntime.RopePyName]: ...

        def get_ast(self) -> FlextInfraProtocolsRopeRuntime.RopeAstNode: ...

        def get_scope(self) -> FlextInfraProtocolsRopeRuntime.RopeScope | None: ...

    @runtime_checkable
    class RopeProject(Protocol):
        """Rope project shape used by flext-infra."""

        @property
        def address(self) -> str: ...

        @property
        def root(self) -> FlextInfraProtocolsRopeRuntime.RopeRoot: ...

        def get_resource(
            self,
            resource_name: str,
        ) -> FlextInfraProtocolsRopeRuntime.RopeResource: ...

        def get_pymodule(
            self,
            resource: FlextInfraProtocolsRopeRuntime.RopeResource,
        ) -> FlextInfraProtocolsRopeRuntime.RopePyModule: ...

        def get_source_folders(
            self,
        ) -> t.SequenceOf[FlextInfraProtocolsRopeRuntime.RopeResource]: ...

        def find_module(
            self,
            modname: str,
            folder: FlextInfraProtocolsRopeRuntime.RopeRoot | None = None,
        ) -> FlextInfraProtocolsRopeRuntime.RopeFile | None: ...

        def find_relative_module(
            self,
            modname: str,
            folder: FlextInfraProtocolsRopeRuntime.RopeRoot,
            level: int,
        ) -> FlextInfraProtocolsRopeRuntime.RopeResource | None: ...

        def get_module(
            self,
            name: str,
            folder: FlextInfraProtocolsRopeRuntime.RopeRoot | None = None,
        ) -> FlextInfraProtocolsRopeRuntime.RopePyModule: ...

        def get_python_files(
            self,
        ) -> t.SequenceOf[FlextInfraProtocolsRopeRuntime.RopeFile]: ...

        def do(self, changes: FlextInfraProtocolsRopeRuntime.RopeChangeSet) -> None: ...

        def validate(
            self,
            folder: FlextInfraProtocolsRopeRuntime.RopeRoot | None = None,
        ) -> None: ...

        def close(self) -> None: ...

    @runtime_checkable
    class RopeLocation(Protocol):
        """Rope occurrence location shape."""

        # flext-j47u (codex): detectors consume Rope's semantic occurrence
        # coordinates directly instead of rediscovering references textually.
        resource: FlextInfraProtocolsRopeRuntime.RopeResource | None
        offset: int
        lineno: int

    @runtime_checkable
    class RopeImportInfo(Protocol):
        """Common Rope import-info shape."""

        names_and_aliases: t.SequenceOf[tuple[str, str | None]]

    @runtime_checkable
    class RopeFromImport(RopeImportInfo, Protocol):
        """Rope from-import marker shape."""

        module_name: str
        level: int

    @runtime_checkable
    class RopeNormalImport(RopeImportInfo, Protocol):
        """Rope normal-import marker shape."""

    @runtime_checkable
    class RopeImportStatement(Protocol):
        """Rope import statement shape."""

        import_info: FlextInfraProtocolsRopeRuntime.RopeImportInfo
        start_line: int
        end_line: int

    @runtime_checkable
    class RopeWorder(Protocol):
        """Rope word/call classifier consumed by the static fact engine."""

        def get_primary_at(self, offset: int) -> str: ...

        def is_a_function_being_called(self, offset: int) -> bool: ...

        def get_word_parens_range(self, offset: int) -> tuple[int, int]: ...

        def is_function_keyword_parameter(self, offset: int) -> bool: ...

    @runtime_checkable
    class RopeChangeSet(Protocol):
        """Rope change set shape."""

        changes: list[p.AttributeProbe]

    @runtime_checkable
    class RopeChangeContents(Protocol):
        """A planned Rope content replacement with no applied effect."""

        resource: FlextInfraProtocolsRopeRuntime.RopeResource
        new_contents: str

    @runtime_checkable
    class RopeRestructure(Protocol):
        """Public semantic restructuring planner at the Rope runtime boundary."""

        def get_changes(
            self,
            *,
            resources: list[FlextInfraProtocolsRopeRuntime.RopeResource],
        ) -> FlextInfraProtocolsRopeRuntime.RopeChangeSet: ...

    @runtime_checkable
    class RopeModuleImports(Protocol):
        """Rope mutable module-import collection shape."""

        imports: list[FlextInfraProtocolsRopeRuntime.RopeImportStatement]

        def add_import(
            self,
            import_info: FlextInfraProtocolsRopeRuntime.RopeImportInfo,
        ) -> None: ...

        def remove_duplicates(self) -> None: ...

        def sort_imports(self) -> None: ...

        def get_changed_source(self) -> str: ...

    @runtime_checkable
    class RopeImportOrganizer(Protocol):
        """Rope import organizer shape."""

        def organize_imports(
            self,
            resource: FlextInfraProtocolsRopeRuntime.RopeResource,
        ) -> FlextInfraProtocolsRopeRuntime.RopeChangeSet | None: ...

    @runtime_checkable
    class RopeMoveGlobal(Protocol):
        """Rope MoveGlobal refactoring shape."""

        def get_changes(
            self,
            target: FlextInfraProtocolsRopeRuntime.RopeResource,
            resources: t.SequenceOf[FlextInfraProtocolsRopeRuntime.RopeResource,]
            | None = None,
        ) -> FlextInfraProtocolsRopeRuntime.RopeChangeSet: ...

    @runtime_checkable
    class RopeOccurrence(Protocol):
        """Rope occurrence shape."""

        offset: int

        lineno: int

        def get_word_range(self) -> tuple[int, int]: ...

        def is_defined(self) -> bool: ...

    @runtime_checkable
    class RopeOccurrenceFinder(Protocol):
        """Rope occurrence finder shape."""

        def find_occurrences(
            self,
            *,
            resource: FlextInfraProtocolsRopeRuntime.RopeResource,
        ) -> t.SequenceOf[FlextInfraProtocolsRopeRuntime.RopeOccurrence]: ...


__all__: list[str] = ["FlextInfraProtocolsRopeRuntime"]
