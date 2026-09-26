"""Rope runtime type predicates and exception factories."""

from __future__ import annotations

from typing import TypeGuard

from flext_infra import p, t

from .rope_runtime_base import FlextInfraUtilitiesRopeRuntimeBase


class FlextInfraUtilitiesRopeRuntimeTypes(FlextInfraUtilitiesRopeRuntimeBase):
    """Expose typed predicates for Rope runtime objects."""

    @classmethod
    def is_resource(cls, value: p.AttributeProbe) -> TypeGuard[t.Infra.RopeResource]:
        return isinstance(value, cls.runtime_type("rope.base.resources", "File"))

    @classmethod
    def is_pymodule(cls, value: p.AttributeProbe) -> TypeGuard[t.Infra.RopePyModule]:
        return isinstance(value, cls.runtime_type("rope.base.pyobjectsdef", "PyModule"))

    @classmethod
    def is_from_import(
        cls, value: p.AttributeProbe
    ) -> TypeGuard[t.Infra.RopeFromImport]:
        return isinstance(
            value,
            cls.runtime_type("rope.refactor.importutils.importinfo", "FromImport"),
        )

    @classmethod
    def is_normal_import(
        cls, value: p.AttributeProbe
    ) -> TypeGuard[t.Infra.RopeNormalImport]:
        return isinstance(
            value,
            cls.runtime_type("rope.refactor.importutils.importinfo", "NormalImport"),
        )

    @classmethod
    def is_assigned_name(
        cls, value: p.AttributeProbe
    ) -> TypeGuard[t.Infra.RopeAssignedName]:
        return isinstance(
            value, cls.runtime_type("rope.base.pynamesdef", "AssignedName")
        )

    @classmethod
    def is_runtime_pyclass(
        cls, value: p.AttributeProbe
    ) -> TypeGuard[t.Infra.RopePyObject]:
        return isinstance(value, cls.runtime_type("rope.base.pyobjects", "PyClass"))

    @classmethod
    def is_abstract_class(
        cls, value: p.AttributeProbe
    ) -> TypeGuard[t.Infra.RopePyObject]:
        """Return whether ``value`` is a Rope abstract class object."""
        return isinstance(
            value, cls.runtime_type("rope.base.pyobjects", "AbstractClass")
        )

    @classmethod
    def is_py_function(cls, value: p.AttributeProbe) -> TypeGuard[t.Infra.RopePyObject]:
        """Return whether ``value`` is a Rope Python function object."""
        return isinstance(
            value, cls.runtime_type("rope.base.pyobjectsdef", "PyFunction")
        )

    @classmethod
    def is_defined_name(cls, value: p.AttributeProbe) -> bool:
        """Return whether ``value`` is a Rope defined name."""
        return isinstance(value, cls.runtime_type("rope.base.pynames", "DefinedName"))

    @classmethod
    def is_imported_name(cls, value: p.AttributeProbe) -> bool:
        """Return whether ``value`` is a Rope imported name."""
        return isinstance(value, cls.runtime_type("rope.base.pynames", "ImportedName"))

    @classmethod
    def is_parameter_name(cls, value: p.AttributeProbe) -> bool:
        """Return whether ``value`` is a Rope parameter name."""
        return isinstance(
            value, cls.runtime_type("rope.base.pynamesdef", "ParameterName")
        )

    @classmethod
    def rope_syntax_errors(cls) -> t.VariadicTuple[type[BaseException]]:
        """Return exceptions that signal unparseable Python source."""
        return (
            SyntaxError,
            cls._exception_type("rope.base.exceptions", "ModuleSyntaxError"),
        )

    @classmethod
    def rope_runtime_errors(cls) -> t.VariadicTuple[type[BaseException]]:
        """Return recoverable exceptions raised by Rope operations."""
        return (
            cls._exception_type("rope.base.exceptions", "RefactoringError"),
            cls._exception_type("rope.base.exceptions", "ResourceNotFoundError"),
            AttributeError,
        )

    @classmethod
    def rope_error_types(cls) -> t.VariadicTuple[type[BaseException]]:
        """Return the generic Rope exception boundary."""
        return (cls._exception_type("rope.base.exceptions", "RopeError"),)

    @classmethod
    def rope_module_not_found_error_types(cls) -> t.VariadicTuple[type[BaseException]]:
        """Return Rope exceptions for unresolved importable modules."""
        return (cls._exception_type("rope.base.exceptions", "ModuleNotFoundError"),)


__all__: list[str] = ["FlextInfraUtilitiesRopeRuntimeTypes"]
