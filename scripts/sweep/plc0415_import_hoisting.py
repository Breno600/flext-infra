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


def _lazy_map_of(init: Path) -> dict[str, str]:
    """Read the ``"Name": ".module"`` lazy-export map of one package init."""
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
    """Resolve one facade-root export to its owning submodule via the lazy map."""
    for depth in range(len(package_parts), 0, -1):
        init = root.joinpath(*package_parts[:depth], "__init__.py")
        if init.is_file() and name in _lazy_map_of(init):
            return _lazy_map_of(init)[name]
    return None


def _header_end(tree: ast.Module) -> int:
    """Line number after the module docstring, __future__, and top imports."""
    end = 0
    body = list(tree.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(
            body[0].value,
            ast.Constant,
        )
    ):
        end = body[0].end_lineno or body[0].lineno
        body = body[1:]
    for node in body:
        if isinstance(node, ast.ImportFrom | ast.Import):
            end = node.end_lineno or node.lineno
        else:
            break
    return end


def _plan(root: Path, path: Path) -> dict[str, object] | None:
    """Plan the hoisting edits for one file without touching it."""
    source = path.read_text()
    tree = ast.parse(source)
    package_parts = [
        part
        for part in path.relative_to(root).parent.parts
        if part not in {"src", "flext_infra"}
    ]
    top_names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom | ast.Import):
            top_names.update(alias.asname or alias.name for alias in node.names)
    deletions: list[tuple[int, int]] = []
    hoists: set[str] = set()
    for function in [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
    ]:
        for node in function.body:
            if not isinstance(node, ast.ImportFrom | ast.Import):
                continue
            span = (node.lineno, node.end_lineno or node.lineno)
            names = node.names
            if isinstance(node, ast.ImportFrom) and all(
                (alias.asname or alias.name) in top_names for alias in names
            ):
                deletions.append(span)
                continue
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith("flext_infra"):
                    target_parts = module.split(".")[1:]
                    for alias in names:
                        if alias.name == "*":
                            return None
                        owner = _module_of_name(root, target_parts, alias.name)
                        resolved = (
                            f"{module}{owner}".lstrip(".")
                            if owner is not None
                            else module
                        )
                        statement = f"from {resolved} import {alias.name}"
                        if alias.asname:
                            statement += f" as {alias.asname}"
                        hoists.add(statement)
                else:
                    statement = ast.get_source_segment(source, node) or ""
                    hoists.add(" ".join(statement.split()))
                deletions.append(span)
            else:
                for alias in names:
                    statement = f"import {alias.name}"
                    if alias.asname:
                        statement += f" as {alias.asname}"
                    hoists.add(statement)
                deletions.append(span)
    if not deletions:
        return None
    return {
        "path": path,
        "deletions": deletions,
        "hoists": sorted(hoists),
        "header_end": _header_end(tree),
    }


def main() -> int:
    """Report or apply the function-body import hoisting across the tree."""
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
    for plan in plans:
        lines = plan["path"].read_text().splitlines()
        for start, end in plan["deletions"]:
            for lineno in range(start, end + 1):
                lines[lineno - 1] = ""
        if plan["hoists"]:
            lines.insert(plan["header_end"], "\n".join(plan["hoists"]))
        plan["path"].write_text("\n".join(lines) + "\n")
    print("applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
