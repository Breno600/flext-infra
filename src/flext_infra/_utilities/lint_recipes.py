"""Repairs for lint findings Ruff reports without a fix of its own.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT

The tooling owner maps each Ruff rule code to one recipe
(``tools.ruff.lint.fix-recipes``); ``make fix`` applies Ruff's own fixes and
then these recipes to the findings left. Every repair is derived from the
source itself: a docstring section from the signature, the summary and the
raise statement, a summary from the declared name, the notice from the
project's declared author and copyright year. A finding the recipe cannot
place raises; nothing is skipped.
"""

from __future__ import annotations

import ast
import re
import textwrap
from collections.abc import MutableMapping
from pathlib import Path

from flext_infra import c, config, m, t
from flext_infra._utilities.pyproject import FlextInfraUtilitiesPyproject


class FlextInfraUtilitiesLintRecipes:
    """Apply the declared recipe of each lint finding to one module source."""

    @staticmethod
    def copyright_notice(pkg_dir: Path) -> str:
        """Render the copyright notice of the project that owns ``pkg_dir``.

        The author is the manifest's first declared author and the year is the
        scaffold copyright year, the same owners the scaffold templates
        render.

        Returns:
            The two-line notice: the copyright line and the SPDX line.

        Raises:
            ValueError: If the path is outside any project manifest or the
                manifest declares no author name.

        """
        for candidate in (pkg_dir, *pkg_dir.parents):
            if not (candidate / c.PYPROJECT_FILENAME).is_file():
                continue
            authors = (
                FlextInfraUtilitiesPyproject
                .read_project_metadata_result(candidate)
                .unwrap()
                .project.authors
            )
            author = authors[0].name if authors else None
            if not author:
                msg = f"project manifest declares no author name: {candidate}"
                raise ValueError(msg)
            scaffold = config.Infra.codegen.scaffold.project
            return (
                f"Copyright (c) {scaffold.copyright_year} {author}. "
                "All rights reserved.\n"
                f"SPDX-License-Identifier: {scaffold.supported_licenses[0]}"
            )
        msg = f"package is outside any project manifest: {pkg_dir}"
        raise ValueError(msg)

    @classmethod
    def apply_lint_recipes(
        cls,
        source: str,
        issues: t.SequenceOf[m.Infra.Issue],
        *,
        path: Path,
        recipes: t.MappingKV[str, c.Infra.LintFixRecipe],
        notice: str,
    ) -> str:
        """Return ``source`` with the declared recipe of every issue applied.

        ``path`` names the module in every refusal; a module without a
        docstring receives one, summarized from its name, to carry the notice.

        Returns:
            The repaired module source.

        Raises:
            ValueError: If an issue's code has no recipe or its recipe cannot
                be placed in the module.

        """
        tree = ast.parse(source)
        lines = source.splitlines(keepends=True)
        sections: MutableMapping[
            ast.FunctionDef | ast.AsyncFunctionDef,
            MutableMapping[str, list[str]],
        ] = {}
        summaries: MutableMapping[
            ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
            str,
        ] = {}
        wants_notice = False
        for issue in issues:
            recipe = recipes.get(issue.code)
            if recipe is None:
                msg = f"{path}: lint finding {issue.code} has no declared fix recipe"
                raise ValueError(msg)
            match recipe:
                case c.Infra.LintFixRecipe.RETURNS_SECTION:
                    function = cls._documented_at(tree, issue.line, path)
                    sections.setdefault(function, {}).setdefault("Returns", []).append(
                        cls._returns_entry(function),
                    )
                case c.Infra.LintFixRecipe.YIELDS_SECTION:
                    function = cls._documented_at(tree, issue.line, path)
                    sections.setdefault(function, {}).setdefault("Yields", []).append(
                        cls._yields_entry(function),
                    )
                case c.Infra.LintFixRecipe.RAISES_SECTION:
                    function = cls._enclosing_function(tree, issue.line, path)
                    sections.setdefault(function, {}).setdefault("Raises", []).append(
                        cls._raises_entry(function, issue, path),
                    )
                case c.Infra.LintFixRecipe.SUMMARY_DOCSTRING:
                    definition = cls._defined_at(tree, issue.line, path)
                    summaries[definition] = cls._summary_for(definition)
                case c.Infra.LintFixRecipe.COPYRIGHT_NOTICE:
                    wants_notice = True
        edits: list[t.Triple[int, int, str]] = []
        for function, wanted in sections.items():
            docstring = cls._docstring_expr(function)
            if docstring is None:
                msg = f"{path}: function at line {function.lineno} has no docstring"
                raise ValueError(msg)
            start, end, raw = cls._literal(lines, docstring, path)
            edits.append((
                start,
                end,
                cls._with_sections(raw, " " * docstring.col_offset, wanted),
            ))
        for definition, text in summaries.items():
            first = definition.body[0]
            decorators = (
                first.decorator_list
                if isinstance(
                    first,
                    ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
                )
                else []
            )
            first_line = min((first.lineno, *(item.lineno for item in decorators)))
            offset = cls._offset(lines, first_line, 0)
            edits.append((offset, offset, f'{" " * first.col_offset}"""{text}"""\n'))
        if wants_notice:
            module_docstring = cls._docstring_expr(tree)
            if module_docstring is None:
                offset = len(lines[0]) if lines and lines[0].startswith("#!") else 0
                stem = path.parent.name if path.stem == "__init__" else path.stem
                summary = stem.strip("_").replace("_", " ").capitalize()
                edits.append((
                    offset,
                    offset,
                    f'"""{summary} module.\n\n{notice}\n"""\n\n',
                ))
            else:
                start, end, raw = cls._literal(lines, module_docstring, path)
                edits.append((start, end, cls._with_notice(raw, notice)))
        rewritten = source
        for start, end, text in sorted(edits, key=lambda edit: edit[0], reverse=True):
            rewritten = f"{rewritten[:start]}{text}{rewritten[end:]}"
        return rewritten

    @staticmethod
    def _docstring_expr(
        node: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> ast.Expr | None:
        """Return the docstring statement of a module, class or function.

        Returns:
            The docstring statement of a module, class or function.

        """
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            return first
        return None

    @classmethod
    def _documented_at(
        cls,
        tree: ast.Module,
        line: int,
        path: Path,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef:
        """Return the function whose docstring starts at ``line``.

        Returns:
            The function whose docstring starts at ``line``.

        Raises:
            ValueError: Always.

        """
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                docstring = cls._docstring_expr(node)
                if docstring is not None and docstring.lineno == line:
                    return node
        msg = f"{path}: no function docstring starts at line {line}"
        raise ValueError(msg)

    @staticmethod
    def _enclosing_function(
        tree: ast.Module,
        line: int,
        path: Path,
    ) -> ast.FunctionDef | ast.AsyncFunctionDef:
        """Return the innermost function whose body spans ``line``.

        Returns:
            The innermost function whose body spans ``line``.

        Raises:
            ValueError: If ``not enclosing``.

        """
        enclosing = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
            and node.lineno <= line <= (node.end_lineno or node.lineno)
        ]
        if not enclosing:
            msg = f"{path}: no function encloses line {line}"
            raise ValueError(msg)
        return max(enclosing, key=lambda node: node.lineno)

    @staticmethod
    def _defined_at(
        tree: ast.Module,
        line: int,
        path: Path,
    ) -> ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef:
        """Return the class or function defined at ``line``.

        Returns:
            The class or function defined at ``line``.

        Raises:
            ValueError: Always; or if ``node.body[0].lineno == node.lineno``.

        """
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
                and node.lineno == line
            ):
                if node.body[0].lineno == node.lineno:
                    msg = f"{path}: definition at line {line} has its body inline"
                    raise ValueError(msg)
                return node
        msg = f"{path}: no class or function is defined at line {line}"
        raise ValueError(msg)

    @staticmethod
    def _offset(lines: t.StrSequence, lineno: int, col_offset: int) -> int:
        """Convert an AST position (1-based line, UTF-8 column) to a str index.

        Returns:
            The resulting ``int``.

        """
        prefix = sum(len(text) for text in lines[: lineno - 1])
        column = len(
            lines[lineno - 1]
            .encode(c.Cli.ENCODING_DEFAULT)[:col_offset]
            .decode(c.Cli.ENCODING_DEFAULT),
        )
        return prefix + column

    @classmethod
    def _literal(
        cls,
        lines: t.StrSequence,
        docstring: ast.Expr,
        path: Path,
    ) -> t.Triple[int, int, str]:
        (
            """Return the span and text of one triple-double-quoted docstring.

        Returns:
            The span and text of one triple-double-quoted docstring.

        Raises:
            ValueError: If ``not (body.startswith('"""
            ") and body.endswith("
            """') and
                (len(body) >= 6))``.
        """
        )
        value = docstring.value
        start = cls._offset(lines, value.lineno, value.col_offset)
        end = cls._offset(
            lines,
            value.end_lineno or value.lineno,
            value.end_col_offset or 0,
        )
        raw = "".join(lines)[start:end]
        body = raw.lstrip("rRuU")
        if not (body.startswith('"""') and body.endswith('"""') and len(body) >= 6):
            msg = f'{path}: docstring at line {value.lineno} is not a """ literal'
            raise ValueError(msg)
        return start, end, raw

    @staticmethod
    def _split_literal(raw: str) -> t.Pair[str, str]:
        """Split a docstring literal into its string prefix and inner text.

        Returns:
            The resulting ``t.Pair[str, str]``.

        """
        prefix = raw[: len(raw) - len(raw.lstrip("rRuU"))]
        # A blank line inside a docstring carries no indentation.
        inner = re.sub(r"(?m)^[ \t]+$", "", raw[len(prefix) + 3 : -3])
        return prefix, inner

    @staticmethod
    def _returns_entry(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Describe the returned value: the summary's object, else its type.

        Returns:
            The resulting ``str``.

        """
        summary = (ast.get_docstring(function) or "").splitlines()[0]
        match = re.match(r"(?i)returns?\s+(?P<rest>.+)", summary.strip().rstrip("."))
        if match:
            rest = match.group("rest")
            return f"{rest[:1].upper()}{rest[1:]}."
        if function.returns is None:
            return "The resulting value."
        return f"The resulting ``{ast.unparse(function.returns)}``."

    @staticmethod
    def _yields_entry(function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
        """Describe each yielded value by the iterator's element type.

        Returns:
            The resulting ``str``.

        """
        if isinstance(function.returns, ast.Subscript):
            element = function.returns.slice
            if isinstance(element, ast.Tuple) and element.elts:
                element = element.elts[0]
            return f"Each ``{ast.unparse(element)}``."
        return "Each yielded value."

    @classmethod
    def _raises_entry(
        cls,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        issue: m.Infra.Issue,
        path: Path,
    ) -> str:
        """Name the raised exception and the conditions that raise it.

        Every ``raise`` of the named exception in the function contributes
        its condition: the static text its message states, else the ``if``
        test that guards it.

        Returns:
            The ``Raises`` entry for the exception.

        Raises:
            ValueError: If the finding names no exception, or no raise of it
                in the function states or is guarded by a condition.

        """
        named = re.search(r"`(?P<name>[^`]+)`", issue.message)
        if named is None:
            msg = f"{path}: raise finding names no exception: {issue.message}"
            raise ValueError(msg)
        name = named.group("name")
        parents = {
            child: node
            for node in ast.walk(function)
            for child in ast.iter_child_nodes(node)
        }
        clauses = [
            cls._raise_condition(function, raised, parents)
            for raised in ast.walk(function)
            if isinstance(raised, ast.Raise)
            and name.rsplit(".", maxsplit=1)[-1] in cls._raised_names(raised, parents)
        ]
        if not clauses:
            msg = f"{path}: {function.name} holds no raise of {name}"
            raise ValueError(msg)
        joined = "; or ".join(dict.fromkeys(clauses))
        return f"{name}: {joined[:1].upper()}{joined[1:]}."

    @staticmethod
    def _raised_names(
        raised: ast.Raise,
        parents: t.MappingKV[ast.AST, ast.AST],
    ) -> frozenset[str]:
        """Return the exception names one ``raise`` statement raises.

        A bare ``raise`` re-raises what its enclosing handler caught.

        Returns:
            The unqualified names of the raised exception classes.

        """
        if raised.exc is not None:
            target = raised.exc.func if isinstance(raised.exc, ast.Call) else raised.exc
            return frozenset({ast.unparse(target).rsplit(".", maxsplit=1)[-1]})
        node: ast.AST = raised
        while (parent := parents.get(node)) is not None:
            if isinstance(parent, ast.ExceptHandler) and parent.type is not None:
                caught = (
                    parent.type.elts
                    if isinstance(parent.type, ast.Tuple)
                    else (parent.type,)
                )
                return frozenset(
                    ast.unparse(item).rsplit(".", maxsplit=1)[-1] for item in caught
                )
            node = parent
        return frozenset()

    @classmethod
    def _raise_condition(
        cls,
        function: ast.FunctionDef | ast.AsyncFunctionDef,
        raised: ast.Raise,
        parents: t.MappingKV[ast.AST, ast.AST],
    ) -> str:
        """Return the clause under which one ``raise`` statement runs.

        Returns:
            ``if`` and the static text of the raised message up to its first
            colon; else ``if`` and the nearest guarding ``if`` test or caught
            exception; else ``always``, for a raise the body always reaches.

        """
        if isinstance(raised.exc, ast.Call) and raised.exc.args:
            message = raised.exc.args[0]
            if isinstance(message, ast.Name):
                assigned = [
                    node.value
                    for node in ast.walk(function)
                    if isinstance(node, ast.Assign)
                    and node.lineno < raised.lineno
                    and any(
                        isinstance(target, ast.Name) and target.id == message.id
                        for target in node.targets
                    )
                ]
                if assigned:
                    message = max(assigned, key=lambda value: value.lineno)
            stated = cls._static_text(message).split(":", maxsplit=1)[0]
            if stated.strip().rstrip("."):
                return f"if {stated.strip().rstrip('.')}"
        node: ast.AST = raised
        while (parent := parents.get(node)) is not None and parent is not function:
            if isinstance(parent, ast.If):
                test = ast.unparse(parent.test)
                return (
                    f"if ``{test}``" if node in parent.body else f"if ``not ({test})``"
                )
            if isinstance(parent, ast.ExceptHandler) and parent.type is not None:
                return f"if a ``{ast.unparse(parent.type)}`` is caught"
            node = parent
        return "always"

    @staticmethod
    def _static_text(node: ast.expr) -> str:
        """Return the literal prefix of a string or f-string expression.

        Returns:
            The literal prefix of a string or f-string expression.

        """
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            prefix: list[str] = []
            for part in node.values:
                if not (isinstance(part, ast.Constant) and isinstance(part.value, str)):
                    break
                prefix.append(part.value)
            return "".join(prefix)
        return ""

    @staticmethod
    def _summary_for(
        definition: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
    ) -> str:
        """Derive a one-line summary from a definition's declared name.

        Returns:
            The resulting ``str``.

        """
        name = definition.name
        if isinstance(definition, ast.ClassDef):
            return (
                f"Tests for ``{name.removeprefix('Tests')}``."
                if name.startswith("Tests") and name != "Tests"
                else f"Define ``{name}``."
            )
        if name.startswith("test_"):
            return f"Test {name.removeprefix('test_').replace('_', ' ')}."
        return f"Provide ``{name}``."

    @classmethod
    def _with_sections(
        cls,
        raw: str,
        indent: str,
        wanted: t.MappingKV[str, t.StrSequence],
    ) -> str:
        """Return the docstring literal with the wanted sections appended.

        Returns:
            The docstring literal with the wanted sections appended.

        """
        width = config.Infra.tooling.tools.ruff.line_length
        prefix, inner = cls._split_literal(raw)
        inner = inner.rstrip()
        appended: list[str] = []
        for header in ("Returns", "Yields", "Raises"):
            entries = wanted.get(header)
            if not entries:
                continue
            block = [
                wrapped
                for entry in dict.fromkeys(entries)
                for wrapped in textwrap.wrap(
                    entry,
                    width=width,
                    initial_indent=f"{indent}    ",
                    subsequent_indent=f"{indent}        ",
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            ]
            existing = re.search(
                rf"^{re.escape(indent)}{header}:\s*$", inner, re.MULTILINE
            )
            if existing is None:
                appended.append("\n".join((f"{indent}{header}:", *block)))
                continue
            following = re.search(
                rf"^{re.escape(indent)}\S[^\n]*:\s*$",
                inner[existing.end() :],
                re.MULTILINE,
            )
            cut = existing.end() + following.start() if following else len(inner)
            inner = f"{inner[:cut].rstrip()}\n" + "\n".join(block) + inner[cut:]
        if appended:
            inner = f"{inner}\n\n" + "\n\n".join(appended)
        return f'{prefix}"""{inner}\n{indent}"""'

    @classmethod
    def _with_notice(cls, raw: str, notice: str) -> str:
        """Return the module docstring with the notice after its summary.

        Returns:
            The module docstring with the notice after its summary.

        """
        prefix, inner = cls._split_literal(raw)
        summary, _, rest = inner.partition("\n")
        remainder = rest.strip("\n")
        if remainder.strip():
            return f'{prefix}"""{summary}\n\n{notice}\n\n{remainder}\n"""'
        return f'{prefix}"""{summary.rstrip()}\n\n{notice}\n"""'


__all__: list[str] = ["FlextInfraUtilitiesLintRecipes"]
