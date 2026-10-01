"""Rope-backed autofix for ENFORCE-079 ClassVar constants outside _constants.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import textwrap
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, u

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraRefactorClassvarConstantAutofix:
    """Move a ClassVar constant from a class body to a _constants module.

    The fix keeps the public facade contract intact: consumers inside the
    package access the constant through the canonical ``_constants`` module,
    while external consumers continue to reach it via ``c.Infra.*``.
    """

    @classmethod
    def plan(
        cls,
        repository_root: Path,
        class_full_name: str,
        constant_name: str,
        constants_module: str,
    ) -> m.Infra.ClassvarConstantAutofixPlan:
        """Build an autofix plan without touching disk."""
        with u.Infra.open_project(repository_root) as project:
            return cls._plan_with_project(
                project, class_full_name, constant_name, constants_module
            )

    @classmethod
    def _plan_with_project(
        cls,
        project: t.Infra.RopeProject,
        class_full_name: str,
        constant_name: str,
        constants_module: str,
    ) -> m.Infra.ClassvarConstantAutofixPlan:
        segments = class_full_name.split(".")
        runtime_errors = u.Infra.rope_runtime_errors()
        module_end = len(segments) - 1
        source_mod = None
        class_module = ""
        while module_end > 0:
            class_module = ".".join(segments[:module_end])
            try:
                source_mod = project.get_module(class_module, project.root)
            except runtime_errors:
                module_end -= 1
                continue
            break
        if source_mod is None:
            msg = f"{class_full_name} did not resolve to a module and class"
            raise TypeError(msg)
        class_path = tuple(segments[module_end:])
        source_resource = source_mod.get_resource()
        if not u.Infra.file_resource(source_resource):
            msg = f"{class_module} did not resolve to a file resource"
            raise TypeError(msg)
        pyclass = source_mod.get_attribute(class_path[0]).get_object()
        for segment in class_path[1:]:
            pyclass = pyclass.get_attribute(segment).get_object()
        if not u.Infra.runtime_pyclass(pyclass):
            msg = f"{class_full_name} did not resolve to a class"
            raise TypeError(msg)
        class_name = ".".join(class_path)
        source_text = source_resource.read()
        class_lineno = cls._class_start_lineno(source_text, class_path)
        declaration_line = cls._extract_declaration_line(
            source_text, class_path, constant_name
        )
        target_resource = cls._target_resource_for_module(
            project,
            constants_module,
            class_module=class_module,
            source_resource=source_resource,
        )
        return m.Infra.ClassvarConstantAutofixPlan(
            class_module=class_module,
            class_name=class_name,
            constant_name=constant_name,
            constants_module=constants_module,
            source_resource=source_resource,
            target_resource=target_resource,
            declaration_line=declaration_line,
            class_lineno=class_lineno,
        )

    @classmethod
    def apply(
        cls,
        repository_root: Path,
        class_full_name: str,
        constant_name: str,
        constants_module: str,
        *,
        dry_run: bool = False,
    ) -> m.Infra.ClassvarConstantAutofixResult:
        """Move the constant and rewrite all internal references."""
        with u.Infra.open_project(repository_root) as project:
            plan = cls._plan_with_project(
                project, class_full_name, constant_name, constants_module
            )
            return cls._apply_with_project(project, plan, dry_run=dry_run)

    @classmethod
    def _apply_with_project(
        cls,
        project: t.Infra.RopeProject,
        plan: m.Infra.ClassvarConstantAutofixPlan,
        *,
        dry_run: bool,
    ) -> m.Infra.ClassvarConstantAutofixResult:
        source_text = plan.source_resource.read()
        target_path = Path(plan.target_resource.real_path)
        target_text = plan.target_resource.read()
        touched: set[str] = {plan.source_resource.path, plan.target_resource.path}
        constants_alias = plan.constants_module.split(".")[-1]
        class_path = tuple(plan.class_name.split("."))

        # 1. Remove the ClassVar declaration from the class body.
        new_source = cls._remove_declaration_line(
            source_text, plan.declaration_line, class_path, plan.constant_name
        )

        # 2. Append the constant to the target _constants module, unless the
        # class declaration was only a typed alias to an existing owner.
        if cls._module_declares_name(target_text, plan.constant_name):
            if not cls._declaration_aliases_target_constant(
                plan.declaration_line, constants_alias, plan.constant_name
            ):
                msg = (
                    f"{plan.constants_module} already declares "
                    f"{plan.constant_name}; class declaration is not an owner alias"
                )
                raise TypeError(msg)
            new_target = target_text
        else:
            new_target = cls._append_constant(
                target_text, plan.declaration_line, plan.constants_module
            )

        # 3. Rewrite internal references from Owner.NAME / cls.NAME /
        # self.__class__.NAME to the canonical constants module access.
        class_module_obj = project.get_module(plan.class_module, project.root)
        pyclass = class_module_obj.get_attribute(class_path[0]).get_object()
        for segment in class_path[1:]:
            pyclass = pyclass.get_attribute(segment).get_object()
        pyname = pyclass.get_attribute(plan.constant_name)
        finder = u.Infra.create_occurrence_finder(
            project, plan.constant_name, pyname, imports=True, in_hierarchy=False
        )
        rewrites: MutableMapping[str, list[t.Triple[int, int, str]]] = {}
        # Iterate over concrete project resources to avoid rope crashing when
        # an occurrence cannot be resolved to a resource (resource=None).
        for resource in project.get_python_files():
            for occurrence in finder.find_occurrences(resource=resource):
                offset = occurrence.offset
                source = resource.read()
                prefix = cls._attribute_prefix(source, offset)
                if cls._should_rewrite_prefix(prefix, plan.class_name):
                    start, end = u.Infra.word_primary_range(source, offset)
                    replacement = (
                        f"{plan.constants_module.split('.')[-1]}.{plan.constant_name}"
                    )
                    rewrites.setdefault(resource.path, []).append((
                        start,
                        end,
                        replacement,
                    ))
                    touched.add(resource.path)

        if dry_run:
            source_preview = cls._rewrite_class_access_in_source(
                new_source,
                plan.class_name,
                plan.constant_name,
                plan.constants_module.split(".")[-1],
            )
            return m.Infra.ClassvarConstantAutofixResult(
                touched_files=tuple(sorted(touched)),
                source_text=source_preview,
                target_text=new_target,
                rewrites=dict(rewrites),
            )

        # 4. Rewrite source-module references textually. Rope occurrence offsets
        # target the original source and become stale after the declaration is
        # removed, so the modified source uses the known class-access forms.
        rewrites.pop(plan.source_resource.path, None)
        new_source = cls._rewrite_class_access_in_source(
            new_source, plan.class_name, plan.constant_name, constants_alias
        )
        # 5. Inject ``from . import _constants`` (or equivalent) into the source
        # module so the rewritten references resolve.
        new_source = cls._ensure_constants_import(
            new_source, constants_alias, plan.class_module, plan.constants_module
        )
        Path(plan.source_resource.real_path).write_text(new_source, encoding="utf-8")
        if new_target != target_text:
            target_path.write_text(new_target, encoding="utf-8")

        # 6. Apply remaining rewrites to other resources.
        for resource in project.get_python_files():
            edits = rewrites.get(resource.path)
            if not edits:
                continue
            text = resource.read()
            text = cls._apply_edits(text, edits)
            Path(resource.real_path).write_text(text, encoding="utf-8")

        return m.Infra.ClassvarConstantAutofixResult(
            touched_files=tuple(sorted(touched)), constant_module=plan.constants_module
        )

    @staticmethod
    def _class_node_for_path(
        tree: ast.Module, class_path: tuple[str, ...]
    ) -> ast.ClassDef | None:
        """Follow ``class_path`` through nested ClassDefs from the module body."""
        node: ast.stmt | None = None
        container: ast.stmt | ast.Module = tree
        for segment in class_path:
            candidates = (
                child
                for child in getattr(container, "body", ()) or ()
                if isinstance(child, ast.ClassDef) and child.name == segment
            )
            node = next(candidates, None)
            if node is None:
                return None
            container = node
        return node if isinstance(node, ast.ClassDef) else None

    @classmethod
    def _class_start_lineno(cls, source: str, class_path: tuple[str, ...]) -> int:
        """Return the 1-based line where the final class of ``class_path`` starts."""
        tree = ast.parse(source)
        node = cls._class_node_for_path(tree, class_path)
        if node is None:
            msg = f"Could not locate class {'.'.join(class_path)}"
            raise ValueError(msg)
        return node.lineno

    @classmethod
    def _target_resource_for_module(
        cls,
        project: t.Infra.RopeProject,
        constants_module: str,
        *,
        class_module: str,
        source_resource: t.Infra.RopeResource,
    ) -> t.Infra.RopeResource:
        """Return the existing canonical constants module resource."""
        source_path = Path(source_resource.real_path).resolve()
        class_path = Path(*class_module.split("."))
        source_suffix = next(
            (
                suffix
                for suffix in (
                    class_path.with_suffix(".py"),
                    class_path / "__init__.py",
                )
                if source_path.parts[-len(suffix.parts) :] == suffix.parts
            ),
            None,
        )
        if source_suffix is None:
            msg = f"{class_module} did not resolve inside its import root"
            raise TypeError(msg)
        import_root = source_path
        for _part in source_suffix.parts:
            import_root = import_root.parent
        constants_path = Path(*constants_module.split("."))
        candidates = tuple(
            candidate
            for candidate in (
                import_root / constants_path.with_suffix(".py"),
                import_root / constants_path / "__init__.py",
            )
            if candidate.is_file()
        )
        if not candidates:
            msg = f"constants module {constants_module} does not exist"
            raise TypeError(msg)
        if len(candidates) != 1:
            msg = f"constants module {constants_module} has multiple canonical owners"
            raise TypeError(msg)
        target_resource = u.Infra.resolve_resource_from_path(project, candidates[0])
        if target_resource is None:
            msg = f"constants module {constants_module} is outside the Rope project"
            raise TypeError(msg)
        resource: t.Infra.RopeResource = target_resource
        return resource

    @classmethod
    def _extract_declaration_line(
        cls, source: str, class_path: tuple[str, ...], constant_name: str
    ) -> str:
        """Return the exact source line that declares the class-level constant."""
        tree = ast.parse(source)
        owner = cls._class_node_for_path(tree, class_path)
        if owner is not None:
            for statement in owner.body:
                if not cls._statement_declares_name(statement, constant_name):
                    continue
                segment = ast.get_source_segment(source, statement)
                if segment is not None:
                    return cls._normalize_declaration_source(segment)
                return cls._normalize_declaration_source(
                    cls._statement_source_by_lines(source, statement)
                )
        class_lineno = cls._class_start_lineno(source, class_path)
        class_name = class_path[-1]
        lines = source.splitlines()
        for idx in range(class_lineno, len(lines)):
            line = lines[idx]
            stripped = line.lstrip()
            if stripped.startswith("class "):
                break
            if stripped.startswith((f"{constant_name}:", f"{constant_name} =")):
                return line.rstrip()
        msg = f"Could not find constant declaration for {constant_name} in {class_name}"
        raise ValueError(msg)

    @classmethod
    def _statement_declares_name(cls, statement: ast.stmt, constant_name: str) -> bool:
        """Return whether ``statement`` declares ``constant_name``."""
        if isinstance(statement, ast.AnnAssign):
            return (
                isinstance(statement.target, ast.Name)
                and statement.target.id == constant_name
            )
        if isinstance(statement, ast.Assign):
            return any(
                isinstance(target, ast.Name) and target.id == constant_name
                for target in statement.targets
            )
        return False

    @classmethod
    def _module_declares_name(cls, source: str, constant_name: str) -> bool:
        """Return whether module source already declares ``constant_name``."""
        try:
            tree = ast.parse(source)
        except SyntaxError as exc:
            msg = f"target constants module is not parseable: {exc.msg}"
            raise TypeError(msg) from exc
        return any(
            cls._statement_declares_name(statement, constant_name)
            for statement in tree.body
        )

    @classmethod
    def _declaration_aliases_target_constant(
        cls, declaration_line: str, constants_alias: str, constant_name: str
    ) -> bool:
        """Return whether a class declaration points at the existing constants owner."""
        tree = ast.parse(textwrap.dedent(declaration_line).strip())
        if len(tree.body) != 1:
            return False
        value = cls._assignment_value(tree.body[0])
        return (
            isinstance(value, ast.Attribute)
            and value.attr == constant_name
            and isinstance(value.value, ast.Name)
            and value.value.id == constants_alias
        )

    @classmethod
    def _assignment_value(cls, statement: ast.stmt) -> ast.expr | None:
        """Return the right-hand side expression for supported assignments."""
        if isinstance(statement, ast.AnnAssign):
            return statement.value
        if isinstance(statement, ast.Assign):
            return statement.value
        return None

    @classmethod
    def _statement_source_by_lines(cls, source: str, statement: ast.stmt) -> str:
        """Return statement source using AST line metadata."""
        lines = source.splitlines()
        start = max(getattr(statement, "lineno", 1), 1)
        end = max(getattr(statement, "end_lineno", start), start)
        return "\n".join(lines[start - 1 : end])

    @classmethod
    def _normalize_declaration_source(cls, source: str) -> str:
        """Return declaration source normalized for module-level placement."""
        lines = textwrap.dedent(source.rstrip()).splitlines()
        if len(lines) <= 1 or lines[0].startswith((" ", "\t")):
            return "\n".join(lines)
        tail = lines[1:]
        indents = [len(line) - len(line.lstrip()) for line in tail if line.strip()]
        if not indents:
            return "\n".join(lines)
        trim = min(indents)
        if trim <= 0:
            return "\n".join(lines)
        return "\n".join((
            lines[0],
            *(line[trim:] if line.strip() else line for line in tail),
        ))

    @classmethod
    def _remove_declaration_line(
        cls,
        source: str,
        declaration_line: str,
        class_path: tuple[str, ...],
        constant_name: str,
    ) -> str:
        """Remove the constant declaration from the class body, preserving layout."""
        lines = source.splitlines(keepends=True)
        ast_removed = cls._remove_declaration_by_ast(
            source, lines, class_path, constant_name
        )
        if ast_removed is not None:
            return ast_removed
        class_lineno = cls._class_start_lineno(source, class_path)
        for idx in range(class_lineno - 1, len(lines)):
            if cls._declaration_block_matches(lines, declaration_line, idx):
                # Also remove the blank line that typically precedes it, if any.
                end_idx = idx + len(declaration_line.splitlines())
                if idx > 0 and not lines[idx - 1].strip():
                    del lines[idx - 1 : end_idx]
                else:
                    del lines[idx:end_idx]
                return "".join(lines)
        return source

    @classmethod
    def _remove_declaration_by_ast(
        cls,
        source: str,
        lines: list[str],
        class_path: tuple[str, ...],
        constant_name: str,
    ) -> str | None:
        """Remove a class-body declaration using AST line metadata."""
        tree = ast.parse(source)
        owner = cls._class_node_for_path(tree, class_path)
        if owner is None:
            return None
        for statement in owner.body:
            if not cls._statement_declares_name(statement, constant_name):
                continue
            start = max(statement.lineno - 1, 0)
            end = max(
                getattr(statement, "end_lineno", statement.lineno), statement.lineno
            )
            delete_start = (
                start - 1 if start > 0 and not lines[start - 1].strip() else start
            )
            del lines[delete_start:end]
            return "".join(lines)
        return None

    @classmethod
    def _declaration_block_matches(
        cls, lines: t.SequenceOf[str], declaration_line: str, start: int
    ) -> bool:
        """Return whether source lines at ``start`` match the declaration block."""
        declaration_lines = declaration_line.splitlines()
        if not declaration_lines or start + len(declaration_lines) > len(lines):
            return False
        source_block = "".join(lines[start : start + len(declaration_lines)]).rstrip()
        return source_block == declaration_line or (
            textwrap.dedent(source_block).rstrip()
            == textwrap.dedent(declaration_line).rstrip()
        )

    @classmethod
    def _apply_edits(
        cls, text: str, edits: t.SequenceOf[t.Triple[int, int, str]]
    ) -> str:
        """Apply (start, end, replacement) edits to ``text`` in reverse order."""
        for start, end, replacement in sorted(edits, reverse=True):
            text = text[:start] + replacement + text[end:]
        return text

    @classmethod
    def _append_constant(
        cls, target_text: str, declaration_line: str, constants_module: str
    ) -> str:
        """Append the constant declaration to the target module source."""
        module_declaration = cls._module_level_declaration_source(declaration_line)
        with_imports = cls._ensure_declaration_imports(
            target_text, module_declaration, constants_module
        )
        trimmed = with_imports.rstrip()
        dedented = textwrap.dedent(module_declaration).strip()
        return f"{trimmed}\n\n{dedented}\n"

    @classmethod
    def _module_level_declaration_source(cls, declaration_line: str) -> str:
        """Return a declaration valid at module level."""
        return c.Infra.CLASSVAR_DECLARATION_RE.sub(r"\1\2\3", declaration_line, count=1)

    @classmethod
    def _ensure_declaration_imports(
        cls, target_text: str, declaration_line: str, constants_module: str
    ) -> str:
        """Add imports needed by the moved declaration."""
        stdlib_imports: list[str] = []
        typing_names: list[str] = []
        project_imports: list[str] = []
        if "Mapping[" in declaration_line:
            stdlib_imports.append("from collections.abc import Mapping\n")
        if "MappingProxyType(" in declaration_line:
            stdlib_imports.append("from types import MappingProxyType\n")
        if "ClassVar[" in declaration_line:
            typing_names.append("ClassVar")
        if "Final[" in declaration_line:
            typing_names.append("Final")
        if "t." in declaration_line:
            package_name = constants_module.split(".", maxsplit=1)[0]
            project_imports.append(f"from {package_name}.typings import t\n")
        if typing_names:
            names = ", ".join(sorted(set(typing_names)))
            stdlib_imports.append(f"from typing import {names}\n")
        return cls._insert_missing_import_lines(
            target_text, (*sorted(stdlib_imports), *sorted(project_imports))
        )

    @classmethod
    def _insert_missing_import_lines(
        cls, source: str, import_lines: t.StrSequence
    ) -> str:
        """Insert missing import lines after the module header/future imports."""
        missing = [line for line in import_lines if line.strip() not in source]
        if not missing:
            return source
        lines = source.splitlines(keepends=True)
        insert_after = cls._module_import_insert_after(lines)
        stdlib = [line for line in missing if not cls._is_project_import_line(line)]
        project = [line for line in missing if cls._is_project_import_line(line)]
        block: list[str] = ["\n"]
        block.extend(stdlib)
        if project:
            block.append("\n")
            block.extend(project)
        block.append("\n")
        if insert_after >= 0:
            lines[insert_after + 1 : insert_after + 1] = block
        else:
            lines[0:0] = block
        return "".join(lines)

    @classmethod
    def _is_project_import_line(cls, import_line: str) -> bool:
        """Return whether an import line targets the moved constant package."""
        return ".typings import t" in import_line

    @classmethod
    def _attribute_prefix(cls, source: str, offset: int) -> str:
        """Return the primary expression for an attribute access at ``offset``.

        For ``Foo.BAR`` at the position of ``BAR`` this returns ``"Foo"``.
        For ``cls.BAR`` returns ``"cls"``.  For ``self.__class__.BAR`` returns
        ``"self.__class__"``.  For bare ``BAR`` returns the empty string.
        """
        try:
            return u.Infra.word_primary_at(source, offset)
        except (*u.Infra.rope_runtime_errors(), TypeError, ValueError) as exc:
            msg = (
                f"word primary resolution failed at offset {offset}: "
                f"{type(exc).__name__}: {exc!s}"
            )
            raise RuntimeError(msg) from exc

    @classmethod
    def _should_rewrite_prefix(cls, prefix: str, class_name: str) -> bool:
        """Return whether an attribute prefix should be rewritten to _constants."""
        return prefix in {class_name, "cls"} or prefix.endswith(".__class__")

    @classmethod
    def _ensure_constants_import(
        cls, source: str, constants_alias: str, class_module: str, constants_module: str
    ) -> str:
        """Add an import for the canonical _constants module if absent.

        Computes a relative import from ``class_module`` to ``constants_module``.
        The import binds the module itself so consumers write
        ``_constants.NAME``.
        """
        if constants_module == class_module:
            return source
        class_parts = class_module.split(".")
        constants_parts = constants_module.split(".")
        common = 0
        for a, b in zip(class_parts, constants_parts, strict=False):
            if a != b:
                break
            common += 1
        if common:
            parent = "." * (len(class_parts) - common)
            parent += ".".join(constants_parts[common:-1])
        else:
            parent = ".".join(constants_parts[:-1])
        import_line = f"from {parent} import {constants_alias}\n"

        lines = source.splitlines(keepends=True)
        existing = {line.strip() for line in lines}
        if import_line.strip() in existing:
            return source
        cls._insert_local_import_line(lines, import_line)
        return "".join(lines)

    @classmethod
    def _insert_local_import_line(cls, lines: list[str], import_line: str) -> None:
        """Insert a relative import after the module import block."""
        insert_after = cls._module_import_block_end(lines)
        insert_at = insert_after + 1 if insert_after >= 0 else 0
        block = []
        if insert_at > 0 and lines[insert_at - 1].strip():
            block.append("\n")
        block.append(import_line)
        if insert_at < len(lines) and lines[insert_at].strip():
            block.append("\n")
        lines[insert_at:insert_at] = block

    @classmethod
    def _module_import_block_end(cls, lines: t.StrSequence) -> int:
        """Return the last line index of the module import block."""
        idx = cls._module_import_insert_after(lines) + 1
        last_import = idx - 1
        paren_depth = 0
        while idx < len(lines):
            stripped = lines[idx].strip()
            if paren_depth > 0:
                paren_depth += lines[idx].count("(") - lines[idx].count(")")
                last_import = idx
                idx += 1
                continue
            if not stripped:
                idx += 1
                continue
            if stripped.startswith(("import ", "from ")) and not stripped.startswith(
                "from __future__ import"
            ):
                paren_depth += lines[idx].count("(") - lines[idx].count(")")
                last_import = idx
                idx += 1
                continue
            break
        return last_import

    @classmethod
    def _module_import_insert_after(cls, lines: t.StrSequence) -> int:
        """Return index after module docstring and future imports only."""
        idx = 0
        while idx < len(lines) and not lines[idx].strip():
            idx += 1
        insert_after = -1
        if idx < len(lines):
            stripped = lines[idx].strip()
            if stripped.startswith(('"""', "'''")):
                quote = stripped[:3]
                insert_after = idx
                if stripped.count(quote) < c.Infra.DOCSTRING_DELIMITER_COUNT:
                    idx += 1
                    while idx < len(lines):
                        insert_after = idx
                        if quote in lines[idx]:
                            idx += 1
                            break
                        idx += 1
                else:
                    idx += 1
        while idx < len(lines):
            stripped = lines[idx].strip()
            if not stripped:
                idx += 1
                continue
            if stripped.startswith("from __future__ import"):
                insert_after = idx
                idx += 1
                continue
            break
        return insert_after

    @classmethod
    def _rewrite_class_access_in_source(
        cls, source: str, class_name: str, constant_name: str, constants_alias: str
    ) -> str:
        """Rewrite class-qualified constant access inside the source module itself.

        Rope's occurrence finder binds ``ClassName.NAME`` and ``cls.NAME`` but not
        ``self.__class__.NAME``.  We perform a fast textual pass over the source
        (after the declaration was removed) and rewrite the known patterns.
        """
        patterns = (
            f"{class_name}.{constant_name}",
            f"cls.{constant_name}",
            f"self.{constant_name}",
            f"self.__class__.{constant_name}",
        )
        replacement = f"{constants_alias}.{constant_name}"
        edits: list[t.Triple[int, int, str]] = []
        for pattern in patterns:
            start = 0
            while True:
                idx = source.find(pattern, start)
                if idx < 0:
                    break
                edits.append((idx, idx + len(pattern), replacement))
                start = idx + len(replacement)
        return cls._apply_edits(source, edits)


__all__: list[str] = ["FlextInfraRefactorClassvarConstantAutofix"]
