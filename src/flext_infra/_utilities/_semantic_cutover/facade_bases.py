"""Semantic facade-base cutover: extend the parent by its declared class name.

A facade module that imports its parent's short letter, subclasses it, and then
rebinds the same letter to the subclass binds that letter twice. Type checkers
then read the letter as a variable, so every ``m.X`` annotation reached through
the facade resolves to Unknown. An annotated rebind (``m: type[X] = X``) has the
same effect. This phase extends the class the parent declares for the letter in
its own ``__all__`` and keeps the letter a plain alias of the facade.
"""

from __future__ import annotations

import ast
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import m, t

from ..private_import_facades import FlextInfraUtilitiesPrivateImportFacades
from .edits import FlextInfraUtilitiesSemanticCutoverEdits
from .facade_base_cst import FlextInfraUtilitiesSemanticCutoverFacadeBaseCst
from .facade_owners import FlextInfraUtilitiesSemanticCutoverFacadeOwners

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from pathlib import Path

    from flext_infra import p


class FlextInfraUtilitiesSemanticCutoverFacadeBases(
    FlextInfraUtilitiesSemanticCutoverFacadeBaseCst,
    FlextInfraUtilitiesSemanticCutoverFacadeOwners,
    FlextInfraUtilitiesSemanticCutoverEdits,
):
    """Rewire a facade that extends its parent's letter to the declared class."""

    @classmethod
    def _plan_facade_bases(
        cls,
        root: Path,
        sources: t.MappingKV[Path, str],
        findings: t.SequenceOf[m.Infra.ModScanFinding],
    ) -> p.Result[t.VariadicTuple[m.Infra.SemanticMigrationEdit]]:
        """Plan the class-name base for every facade the detector selected."""
        selected = frozenset((root / finding.file).resolve() for finding in findings)
        items = tuple(
            item for item in cls._editable_sources(sources) if item[0] in selected
        )
        shapes = {
            path: found
            for path, source in items
            if (
                found := cls._facade_shapes(path, ast.parse(source, filename=str(path)))
            )
        }
        if not shapes:
            return r[t.VariadicTuple[m.Infra.SemanticMigrationEdit]].ok(())
        modules = FlextInfraUtilitiesPrivateImportFacades.source_modules(
            sources,
            tuple(
                f"from {shape[0]} import {shape[1]}"
                for found in shapes.values()
                for shape in found
            ),
        )

        def rewrite(path: Path, source: str) -> t.Infra.TransformResult:
            # A facade may compose several parents by their letters (``class
            # X(c, api_c)``); each base is rewired in turn against the source
            # the previous one produced, so every import, base and eager read
            # lands in one edit.
            rewritten = source
            changes: list[str] = []
            for shape in shapes[path]:
                tree = ast.parse(rewritten, filename=str(path))
                owner = cls._facade_declared_owner(modules, shape[0], shape[1])
                bound = cls._facade_bound_imports(tree, shape[0])
                if owner in cls._facade_module_bindings(tree) - bound:
                    msg = f"{owner} is already bound locally in {path}"
                    raise ValueError(msg)
                explicit = (
                    cls._explicit_parent_reads(rewritten, tree, shape[1], owner)
                    if shape[1] == shape[2]
                    else rewritten
                )
                rewritten = cls._rewrite_facade_base_source(
                    explicit, shape=shape, owner=owner, owner_bound=owner in bound
                )
                changes.append(f"extended {shape[0]}.{owner} in {shape[3]}")
            if cls._facade_shapes(path, ast.parse(rewritten)):
                msg = f"facade base cutover left residue in {path}"
                raise ValueError(msg)
            return rewritten, tuple(changes)

        return cls._semantic_edits(
            tuple(item for item in items if item[0] in shapes), rewrite
        )

    @staticmethod
    def _facade_shapes(
        path: Path, tree: ast.Module
    ) -> t.VariadicTuple[t.Quad[str, str, str, str]]:
        """Return every ``(module, letter, local, facade)`` rebound letter base.

        One facade may extend several parents by their letters; the shapes
        are ordered by parent module so the rewrite is deterministic.
        """
        imports: MutableMapping[str, t.Triple[str, str, int]] = {}
        rebinds: MutableMapping[str, str] = {}
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                for imported in node.names:
                    imports[imported.asname or imported.name] = (
                        node.module or "",
                        imported.name,
                        node.level,
                    )
            elif (
                isinstance(node, ast.Assign)
                and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and isinstance(node.value, ast.Name)
            ):
                rebinds[node.targets[0].id] = node.value.id
            elif (
                isinstance(node, ast.AnnAssign)
                and isinstance(node.target, ast.Name)
                and isinstance(node.value, ast.Name)
            ):
                rebinds[node.target.id] = node.value.id
        shapes = {
            (module, imported, base.id, node.name, level)
            for node in tree.body
            if isinstance(node, ast.ClassDef)
            for base in node.bases
            if isinstance(base, ast.Name) and base.id in imports
            for module, imported, level in (imports[base.id],)
            if rebinds.get(imported) == node.name
        }
        if any(level for *_rest, level in shapes):
            msg = f"relative facade base import is not a declared owner in {path}"
            raise ValueError(msg)
        return tuple(
            (module, imported, local, facade)
            for module, imported, local, facade, _level in sorted(shapes)
        )

    @staticmethod
    def _explicit_parent_reads(
        source: str, tree: ast.Module, letter: str, owner: str
    ) -> str:
        """Spell the parent class wherever the letter is read before its rebind.

        Until the rebind executes, every eager read of the letter (class
        bases, class bodies, decorators, defaults) evaluates the imported
        parent, so writing the parent class there keeps runtime identical.
        Function and lambda bodies run after the rebind and keep the letter.
        """
        rebind_line = max(
            node.lineno
            for node in tree.body
            if isinstance(node, ast.Assign | ast.AnnAssign)
            and any(
                isinstance(target, ast.Name) and target.id == letter
                for target in (
                    node.targets if isinstance(node, ast.Assign) else (node.target,)
                )
            )
        )
        reads: list[t.Pair[int, int]] = []
        pending: list[ast.AST] = list(tree.body)
        while pending:
            node = pending.pop()
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                pending.extend(node.decorator_list)
                pending.extend(node.args.defaults)
                pending.extend(
                    default for default in node.args.kw_defaults if default is not None
                )
                continue
            if isinstance(node, ast.Lambda):
                continue
            if (
                isinstance(node, ast.Name)
                and node.id == letter
                and isinstance(node.ctx, ast.Load)
                and node.lineno < rebind_line
            ):
                reads.append((node.lineno, node.col_offset))
            pending.extend(ast.iter_child_nodes(node))
        lines = source.splitlines(keepends=True)
        for lineno, column in sorted(reads, reverse=True):
            encoded = lines[lineno - 1].encode()
            lines[lineno - 1] = (
                encoded[:column] + owner.encode() + encoded[column + len(letter) :]
            ).decode()
        return "".join(lines)

    @staticmethod
    def _facade_bound_imports(tree: ast.Module, module: str) -> frozenset[str]:
        """Return names a module already imports unaliased from ``module``."""
        return frozenset(
            imported.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and not node.level
            and node.module == module
            for imported in node.names
            if imported.asname is None
        )

    @staticmethod
    def _facade_module_bindings(tree: ast.Module) -> frozenset[str]:
        """Return every module-scope binding name."""
        names: set[str] = set()
        for node in tree.body:
            if isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                names.add(node.name)
            elif isinstance(node, ast.ImportFrom | ast.Import):
                names.update(
                    imported.asname or imported.name.split(".")[0]
                    for imported in node.names
                )
        return frozenset(names)


__all__: list[str] = ["FlextInfraUtilitiesSemanticCutoverFacadeBases"]
