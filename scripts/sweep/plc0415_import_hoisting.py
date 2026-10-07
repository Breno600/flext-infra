"""Hoist function-body imports to module top-level (PLC0415 sweep).

Only imports that are DIRECT children of a function body are hoisted:
conditional/fallback imports under ``try``/``if``/``with``/``for`` keep
their semantics and stay in place. Facade-root imports resolve to their
owning submodule through the package lazy map, which is the sanctioned
cycle-free spelling. Multi-line imports are removed as a whole range.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

_REPORT_ONLY = "report"
_APPLY = "apply"

type _Plan = dict[str, object]


def _lazy_map_of(init: Path) -> dict[str, str]:
    """Read the ``"Name": ".module"`` lazy-export map of one package init.

    Returns:
        The parsed lazy export mapping of the package ``__init__``.

    """
    mapping: dict[str, str] = {}
    try:
        tree = ast.parse(init.read_text())
    except SyntaxError:
        return mapping
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values, strict=False):
            if (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(value, ast.Constant)
                and isinstance(value.value, str)
                and value.value.startswith(".")
            ):
                mapping[key.value] = value.value
    return mapping


def _module_of_name(root: Path, package_parts: list[str], name: str) -> str | None:
    """Resolve one facade-root export to its owning submodule.

    Returns:
        The dotted ``.module`` suffix owning the export, or None.

    """
    for depth in range(len(package_parts), 0, -1):
        init = root.joinpath(*package_parts[:depth], "__init__.py")
        if init.is_file() and name in (found := _lazy_map_of(init)):
            return found[name]
    return None


def _header_end(tree: ast.Module) -> int:
    """Locate the line after the module docstring and top import block.

    Returns:
        The last line number of the header region.

    """
    end = 0
    body = list(tree.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
    ):
        end = body[0].end_lineno or body[0].lineno
        body = body[1:]
    for node in body:
        if isinstance(node, ast.ImportFrom | ast.Import):
            end = node.end_lineno or node.lineno
        else:
            break
    return end


def _build_hoisted(
    root: Path,
    node: ast.ImportFrom,
    top_names: set[str],
) -> str | None:
    """Build one hoisted statement for a ``from`` import.

    Returns:
        The hoisted statement, or None when the import is a re-export of a
        top-level name (deletable) or a star import (unhoistable).

    """
    names = node.names
    if all((alias.asname or alias.name) in top_names for alias in names):
        return None
    module = node.module or ""
    if not module.startswith("flext_infra"):
        statement = ast.get_source_segment("", node) or f"from {module} import"
        return " ".join(statement.split())
    target_parts = module.split(".")[1:]
    statements: list[str] = []
    for alias in names:
        if alias.name == "*":
            return None
        owner = _module_of_name(Path("."), target_parts, alias.name)
        resolved = f"{module}{owner}".lstrip(".") if owner is not None else module
        statement = f"from {resolved} import {alias.name}"
        statements.append(statement + (f" as {alias.asname}" if alias.asname else ""))
    return "\n".join(statements)


def _plan(root: Path, path: Path) -> _Plan | None:
    """Plan the hoisting edits for one file without touching it.

    Returns:
        The plan with deletions and hoisted statements, or None when the
        file carries no hoistable function-body import.

    """
    source = path.read_text()
    tree = ast.parse(source)
    top_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom | ast.Import):
            top_names.update(alias.asname or alias.name for alias in node.names)
    plan: _Plan = {"path": path, "deletions": [], "hoists": set(), "header_end": 0}
    for function in (
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    ):
        if not _plan_function_imports(root, function, top_names, plan):
            return None
    if not plan["deletions"]:
        return None
    plan["header_end"] = _header_end(tree)
    return plan


def _plan_function_imports(
    root: Path,
    function: ast.FunctionDef | ast.AsyncFunctionDef,
    top_names: set[str],
    plan: _Plan,
) -> bool:
    """Plan one function body's direct imports into the plan.

    Returns:
        False when an import is an unhoistable star import; True otherwise.

    """
    for node in function.body:
        if not isinstance(node, ast.ImportFrom | ast.Import):
            continue
        span = (node.lineno, node.end_lineno or node.lineno)
        if isinstance(node, ast.ImportFrom):
            if not _hoist_from_module(root, node, top_names, plan, span):
                return False
            continue
        for alias in node.names:
            statement = f"import {alias.name}"
            if alias.asname:
                statement += f" as {alias.asname}"
            plan["hoists"].add(statement)
        plan["deletions"].append(span)
    return True


def _hoist_from_module(
    root: Path,
    node: ast.ImportFrom,
    top_names: set[str],
    plan: _Plan,
    span: tuple[int, int],
) -> bool:
    """Plan one ``from`` import's hoist, delete, or abort into the plan.

    Returns:
        False when the import is an unhoistable star import; True otherwise.

    """
    hoisted = _build_hoisted(root, node, top_names)
    if hoisted is None and all(
        (alias.asname or alias.name) in top_names for alias in node.names
    ):
        plan["deletions"].append(span)
        return True
    if hoisted is None:
        return False
    plan["hoists"].add(hoisted)
    plan["deletions"].append(span)
    return True


def _apply(plans: list[_Plan]) -> None:
    """Apply hoisting plans: delete mid-code imports, insert hoisted block."""
    for plan in plans:
        lines = plan["path"].read_text().splitlines()
        for start, end in plan["deletions"]:
            for lineno in range(start, end + 1):
                lines[lineno - 1] = ""
        if plan["hoists"]:
            lines.insert(plan["header_end"], "\n".join(plan["hoists"]))
        plan["path"].write_text("\n".join(lines) + "\n")


def main() -> int:
    """Report or apply the function-body import hoisting across the tree.

    Returns:
        Zero on success in either mode.

    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=(_REPORT_ONLY, _APPLY))
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    root = Path(args.root).resolve() / "src"
    plans = [plan for path in sorted(root.rglob("*.py")) if (plan := _plan(root, path))]
    total_deletions = sum(len(p["deletions"]) for p in plans)
    total_hoists = sum(len(p["hoists"]) for p in plans)
    print(f"files={len(plans)} mid-imports={total_deletions} hoisted={total_hoists}")
    if args.mode == _REPORT_ONLY:
        for plan in plans[:5]:
            rel = plan["path"].relative_to(root)
            print(f"  {rel}: -{len(plan['deletions'])} mid, +{len(plan['hoists'])} top")
        return 0
    _apply(plans)
    print("applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
