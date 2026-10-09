"""Rope runtime type predicates and exception factories.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TypeGuard

from flext_infra import p, t
from flext_infra._utilities.rope_runtime_base import FlextInfraUtilitiesRopeRuntimeBase


class FlextInfraUtilitiesRopeRuntimeTypes(FlextInfraUtilitiesRopeRuntimeBase):
    """Expose typed predicates for Rope runtime objects."""

    @classmethod
    def file_resource(cls, value: p.AttributeProbe) -> TypeGuard[t.Infra.RopeFile]:
        return isinstance(value, cls.runtime_type("rope.base.resources", "File"))

    @classmethod
    def require_file_resource(
        cls,
        value: p.AttributeProbe,
        label: str | Path,
    ) -> t.Infra.RopeFile:
        """Narrow one Rope resource to the file shape or refuse the input.

        Single owner for the ``get_resource`` result consumers read content
        from: every caller that treats a project resource as a module file
        narrows through here instead of restating the predicate and refusal.

        Returns:
            The resulting ``t.Infra.RopeFile``.

        Raises:
            TypeError: If the resource is not a Rope file (folder or absent).

        """
        if not cls.file_resource(value):
            msg = f"expected a Rope file resource: {label}"
            raise TypeError(msg)
        return value

    @classmethod
    def pymodule(cls, value: p.AttributeProbe) -> TypeGuard[t.Infra.RopePyModule]:
        """Accept every rope module-like object: modules and packages.

        ``find_module`` resolves an installed third-party package to its
        folder resource and ``get_pymodule`` returns a ``PyPackage`` for it,
        which is rope's ``_PyModule`` sibling of ``PyModule`` — never a
        ``PyModule`` instance. External base resolution
        (``pydantic.BaseModel`` and friends) must read attributes through
        packages exactly like through modules, so both shapes satisfy the
        contract.

        Returns:
            The resulting ``TypeGuard[t.Infra.RopePyModule]``.
        """
        return isinstance(
            value,
            (
                cls.runtime_type("rope.base.pyobjectsdef", "PyModule"),
                cls.runtime_type("rope.base.pyobjectsdef", "PyPackage"),
            ),
        )

    @classmethod
    def from_import_info(
        cls,
        value: p.AttributeProbe,
    ) -> TypeGuard[t.Infra.RopeFromImport]:
        return isinstance(
            value,
            cls.runtime_type("rope.refactor.importutils.importinfo", "FromImport"),
        )

    @classmethod
    def normal_import_info(
        cls,
        value: p.AttributeProbe,
    ) -> TypeGuard[t.Infra.RopeNormalImport]:
        return isinstance(
            value,
            cls.runtime_type("rope.refactor.importutils.importinfo", "NormalImport"),
        )

    @classmethod
    def assigned_name(
        cls,
        value: p.AttributeProbe,
    ) -> TypeGuard[t.Infra.RopeAssignedName]:
        return isinstance(
            value,
            cls.runtime_type("rope.base.pynamesdef", "AssignedName"),
        )

    @classmethod
    def abstract_class(cls, value: p.AttributeProbe) -> TypeGuard[t.Infra.RopePyObject]:
        """Return whether ``value`` is a Rope abstract class object.

        Returns:
            Whether ``value`` is a Rope abstract class object.

        """
        return isinstance(
            value,
            cls.runtime_type("rope.base.pyobjects", "AbstractClass"),
        )

    @classmethod
    def instance_object(
        cls,
        value: p.AttributeProbe,
    ) -> TypeGuard[t.Infra.RopePyObject]:
        """Return whether ``value`` is a Rope inferred instance of a class.

        Rope infers a typed value (``facade: Facade = Facade()``) as an exact
        ``PyObject`` whose type is the declared class; classes, functions and
        modules are ``PyObject`` subclasses and never match.

        Returns:
            Whether ``value`` is a Rope inferred class instance.

        """
        return type(value) is cls.runtime_type("rope.base.pyobjects", "PyObject")

    @classmethod
    def py_class(cls, value: p.AttributeProbe) -> TypeGuard[t.Infra.RopePyObject]:
        """Return whether ``value`` is a Rope class declared in Python source.

        Builtin classes (``Exception``, ``object``) are abstract classes too,
        but they have no source scope.

        Returns:
            Whether ``value`` is a Rope source-declared class object.

        """
        return isinstance(
            value,
            cls.runtime_type("rope.base.pyobjectsdef", "PyClass"),
        )

    @classmethod
    def py_function(cls, value: p.AttributeProbe) -> TypeGuard[t.Infra.RopePyObject]:
        """Return whether ``value`` is a Rope Python function object.

        Returns:
            Whether ``value`` is a Rope Python function object.

        """
        return isinstance(
            value,
            cls.runtime_type("rope.base.pyobjectsdef", "PyFunction"),
        )

    @classmethod
    def defined_name(cls, value: p.AttributeProbe) -> bool:
        """Return whether ``value`` is a Rope defined name.

        Returns:
            Whether ``value`` is a Rope defined name.

        """
        return isinstance(value, cls.runtime_type("rope.base.pynames", "DefinedName"))

    @classmethod
    def imported_name(cls, value: p.AttributeProbe) -> bool:
        """Return whether ``value`` is a Rope imported name.

        Returns:
            Whether ``value`` is a Rope imported name.

        """
        return isinstance(value, cls.runtime_type("rope.base.pynames", "ImportedName"))

    @classmethod
    def parameter_name(cls, value: p.AttributeProbe) -> bool:
        """Return whether ``value`` is a Rope parameter name.

        Returns:
            Whether ``value`` is a Rope parameter name.

        """
        return isinstance(
            value,
            cls.runtime_type("rope.base.pynamesdef", "ParameterName"),
        )

    @classmethod
    def rope_syntax_errors(cls) -> t.VariadicTuple[type[BaseException]]:
        """Return exceptions that signal unparseable Python source.

        Returns:
            Exceptions that signal unparseable Python source.

        """
        return (
            SyntaxError,
            cls._exception_type("rope.base.exceptions", "ModuleSyntaxError"),
        )

    @classmethod
    def rope_runtime_errors(cls) -> t.VariadicTuple[type[BaseException]]:
        """Return recoverable exceptions raised by Rope operations.

        Returns:
            Recoverable exceptions raised by Rope operations.

        """
        return (
            cls._exception_type("rope.base.exceptions", "RefactoringError"),
            cls._exception_type("rope.base.exceptions", "ResourceNotFoundError"),
            # Module probing (longest-prefix module/class split) treats a
            # missing module as "keep splitting", never as a hard failure.
            cls._exception_type("rope.base.exceptions", "ModuleNotFoundError"),
            AttributeError,
        )

    @classmethod
    def rope_error_types(cls) -> t.VariadicTuple[type[BaseException]]:
        """Return the generic Rope exception boundary.

        Returns:
            The generic Rope exception boundary.

        """
        return (cls._exception_type("rope.base.exceptions", "RopeError"),)

    @classmethod
    def rope_module_not_found_error_types(cls) -> t.VariadicTuple[type[BaseException]]:
        """Return Rope exceptions for unresolved importable modules.

        Returns:
            Rope exceptions for unresolved importable modules.

        """
        return (cls._exception_type("rope.base.exceptions", "ModuleNotFoundError"),)

    @classmethod
    def rope_attribute_not_found_error_types(
        cls,
    ) -> t.VariadicTuple[type[BaseException]]:
        """Return Rope exceptions for statically unresolved attributes.

        Returns:
            Rope exceptions for statically unresolved attributes.

        """
        return (cls._exception_type("rope.base.exceptions", "AttributeNotFoundError"),)


__all__: list[str] = ["FlextInfraUtilitiesRopeRuntimeTypes"]
