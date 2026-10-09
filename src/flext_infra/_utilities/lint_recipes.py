"""Repairs for lint findings Ruff reports without a fix of its own.

The tooling owner maps each Ruff rule code to one recipe
(``tools.ruff.lint.fix-recipes``); ``make fix`` applies Ruff's own fixes and
then these recipes to the findings left. Every repair is derived from the
source itself: a docstring section from the signature, the summary and the
raise statement, a summary from the declared name, the notice from the
project's declared author and copyright year, and a static method from a
method Ruff reports as never reading its instance: only its receiver
parameter and its decorator list change, its body keeps every byte. A
finding the recipe cannot place raises; nothing is skipped.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import io
import operator
import re
import textwrap
import tokenize
from collections.abc import MutableMapping
from itertools import pairwise
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
    ) -> str:
        """Return ``source`` with the declared recipe of every issue applied.

        A static-method finding on a hook a subclass overrides is filtered
        out by the caller (``overridden_findings``) and never reaches here.

        ``path`` names the module in every refusal and locates the project
        whose declared author signs the notice; the notice is derived only
        when a copyright finding asks for it. A module without a docstring
        receives one, summarized from its name, to carry the notice.

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
            match cls._recipe_for(issue, recipes, path):
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
                case c.Infra.LintFixRecipe.STATIC_METHOD:
                    # Planned per method below, after duplicates collapse.
                    continue
        edits = list(cls._static_method_plan(source, tree, issues, path, recipes))
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
            notice = cls.copyright_notice(path.parent)
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
        for start, end, text in sorted(edits, key=operator.itemgetter(0), reverse=True):
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

    @classmethod
    def _static_method_plan(
        cls,
        source: str,
        tree: ast.Module,
        issues: t.SequenceOf[m.Infra.Issue],
        path: Path,
        recipes: t.MappingKV[str, c.Infra.LintFixRecipe],
    ) -> t.VariadicTuple[t.Triple[int, int, str]]:
        """Plan the static-method edits of every finding that selects them.

        Returns:
            The decorator insertions and receiver removals, one pair per method.

        """
        lines = source.splitlines(keepends=True)
        methods = dict.fromkeys(
            cls._receiver_method_at(tree, issue, path)[1]
            for issue in issues
            if recipes.get(issue.code) is c.Infra.LintFixRecipe.STATIC_METHOD
        )
        return tuple(
            edit
            for method in methods
            for edit in cls._static_method_edits(source, lines, method, path)
        )

    @staticmethod
    def _recipe_for(
        issue: m.Infra.Issue,
        recipes: t.MappingKV[str, c.Infra.LintFixRecipe],
        path: Path,
    ) -> c.Infra.LintFixRecipe:
        """Return the declared recipe of one finding.

        Returns:
            The recipe the tooling owner maps the finding's rule to.

        Raises:
            ValueError: If the finding's rule has no declared recipe.

        """
        recipe = recipes.get(issue.code)
        if recipe is None:
            msg = f"{path}: lint finding {issue.code} has no declared fix recipe"
            raise ValueError(msg)
        return recipe

    @staticmethod
    def overridden_methods(
        sources: t.SequenceOf[str],
    ) -> frozenset[t.Pair[str, str]]:
        """Return each ``(class, method)`` a subclass in ``sources`` redefines.

        Ruff judges a method alone and cannot see that a subclass overrides
        it; declaring such a hook static would break every override. Bases
        are matched by their declared name, transitively, so an ambiguous
        name only keeps more methods with their owner.

        Returns:
            The overridden ``(class name, method name)`` pairs.

        """
        bases: MutableMapping[str, set[str]] = {}
        methods: MutableMapping[str, set[str]] = {}
        for source in sources:
            for node in ast.walk(ast.parse(source)):
                if not isinstance(node, ast.ClassDef):
                    continue
                bases.setdefault(node.name, set()).update(
                    ast.unparse(base).rsplit(".", maxsplit=1)[-1] for base in node.bases
                )
                methods.setdefault(node.name, set()).update(
                    item.name
                    for item in node.body
                    if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
                )
        ancestors: MutableMapping[str, set[str]] = {}
        for name in bases:
            seen: set[str] = set()
            pending = list(bases[name])
            while pending:
                base = pending.pop()
                if base not in seen:
                    seen.add(base)
                    pending.extend(bases.get(base, ()))
            ancestors[name] = seen
        return frozenset(
            (ancestor, method)
            for name, found in ancestors.items()
            for ancestor in found
            for method in methods[name] & methods.get(ancestor, set())
        )

    @classmethod
    def overridden_findings(
        cls,
        source: str,
        issues: t.SequenceOf[m.Infra.Issue],
        *,
        path: Path,
        recipes: t.MappingKV[str, c.Infra.LintFixRecipe],
        overridden: frozenset[t.Pair[str, str]],
    ) -> t.VariadicTuple[m.Infra.Issue]:
        """Return the static-method findings whose method a subclass overrides.

        Returns:
            The findings the static-method recipe leaves to their owner.

        """
        tree = ast.parse(source)
        return tuple(
            issue
            for issue in issues
            if recipes.get(issue.code) is c.Infra.LintFixRecipe.STATIC_METHOD
            for owner, method in (cls._receiver_method_at(tree, issue, path),)
            if (owner.name, method.name) in overridden
        )

    @staticmethod
    def _receiver_method_at(
        tree: ast.Module,
        issue: m.Infra.Issue,
        path: Path,
    ) -> t.Pair[ast.ClassDef, ast.FunctionDef | ast.AsyncFunctionDef]:
        """Return the class method Ruff reports as never reading its receiver.

        Ruff reports the finding at the method's name on its ``def`` line and
        names the method in its message, so line and name select one method.

        Returns:
            The owning class and the method the finding names.

        Raises:
            ValueError: If no class method with a receiver matches the finding.

        """
        for owner in ast.walk(tree):
            if not isinstance(owner, ast.ClassDef):
                continue
            for method in owner.body:
                if (
                    isinstance(method, ast.FunctionDef | ast.AsyncFunctionDef)
                    and method.lineno == issue.line
                    and f"`{method.name}`" in issue.message
                    and (*method.args.posonlyargs, *method.args.args)
                ):
                    return owner, method
        msg = f"{path}: no class method with a receiver matches line {issue.line}"
        raise ValueError(msg)

    @classmethod
    def _static_method_edits(
        cls,
        source: str,
        lines: t.StrSequence,
        method: ast.FunctionDef | ast.AsyncFunctionDef,
        path: Path,
    ) -> t.VariadicTuple[t.Triple[int, int, str]]:
        """Declare ``method`` static: drop its receiver, add the decorator.

        The receiver is removed with the separator that follows it; a receiver
        that was the only parameter leaves empty parentheses. ``@staticmethod``
        becomes the outermost decorator at the method's own indentation. No
        other byte of the method changes.

        Returns:
            The decorator insertion and the receiver removal.

        Raises:
            ValueError: If a comment or a default sits beside the receiver, or
                the method does not start its own line.

        """
        args = method.args
        receiver = (*args.posonlyargs, *args.args)[0]
        start = cls._offset(lines, receiver.lineno, receiver.col_offset)
        cursor = cls._skip_blank(
            source,
            cls._offset(
                lines,
                receiver.end_lineno or receiver.lineno,
                receiver.end_col_offset or 0,
            ),
            path,
        )
        if source[cursor] == ",":
            cursor = cls._skip_blank(source, cursor + 1, path)
            if args.posonlyargs == [receiver] and source[cursor] == "/":
                cursor = cls._skip_blank(source, cursor + 1, path)
                if source[cursor] == ",":
                    cursor = cls._skip_blank(source, cursor + 1, path)
        elif source[cursor] != ")":
            msg = f"{path}: receiver of {method.name} is not a plain parameter"
            raise ValueError(msg)
        if source[cursor] == ")":
            opening = source.rindex("(", 0, start) + 1
            if source[opening:start].strip():
                msg = f"{path}: signature of {method.name} holds more than its receiver"
                raise ValueError(msg)
            start = opening
        first_line = min((
            method.lineno,
            *(decorator.lineno for decorator in method.decorator_list),
        ))
        head = lines[first_line - 1]
        indent = head[: len(head) - len(head.lstrip(" \t"))]
        if not head.lstrip(" \t").startswith(("@", "def ", "async ")):
            msg = f"{path}: {method.name} does not start its own line"
            raise ValueError(msg)
        line_start = cls._offset(lines, first_line, 0)
        return (
            (line_start, line_start, f"{indent}@staticmethod\n"),
            (start, cursor, ""),
        )

    @staticmethod
    def _skip_blank(source: str, index: int, path: Path) -> int:
        """Return the first index at or after ``index`` that is not blank.

        Returns:
            The index of the next signature token.

        Raises:
            ValueError: If a comment or line continuation sits in the span.

        """
        while source[index] in " \t\r\n":
            index += 1
        if source[index] in "#\\":
            msg = f"{path}: comment or continuation beside a removed receiver"
            raise ValueError(msg)
        return index

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
        """Return the span and text of one triple-double-quoted docstring.

        Returns:
            The span and text of one triple-double-quoted docstring.

        Raises:
            ValueError: If the docstring is not a triple-double-quoted literal.

        """
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
            # The literal prefix of an f-string stops at its first placeholder,
            # which can leave the opener or quote that wrapped it dangling.
            stated = (
                cls
                ._static_text(message)
                .split(":", maxsplit=1)[0]
                .rstrip(" .([{'\"`")
                .strip()
            )
            if stated:
                return f"if {stated}"
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
                    cls._literal_safe(entry, prefix),
                    width=width,
                    initial_indent=f"{indent}    ",
                    subsequent_indent=f"{indent}        ",
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            ]
            existing = re.search(
                rf"^{re.escape(indent)}{header}:\s*$",
                inner,
                re.MULTILINE,
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
    def notice_last(cls, source: str, *, path: Path) -> str:
        """Return ``source`` with its docstring notice paragraph as the last text.

        The notice paragraph starts at the line the declared notice pattern
        (``tools.ruff.lint.copyright-notice-rgx``) matches and runs to the
        next blank line; the other paragraphs keep their order. ``path`` names
        the module in every refusal.

        Returns:
            The rewritten source; ``source`` itself when the notice already
            closes the docstring.

        Raises:
            ValueError: If the module has no docstring or its docstring
                carries no notice.

        """
        docstring = cls._docstring_expr(ast.parse(source, filename=str(path)))
        if docstring is None:
            msg = f"{path}: module has no docstring carrying a notice"
            raise ValueError(msg)
        start, end, raw = cls._literal(
            source.splitlines(keepends=True),
            docstring,
            path,
        )
        prefix, inner = cls._split_literal(raw)
        found = re.search(
            config.Infra.tooling.tools.ruff.lint.copyright_notice_rgx,
            inner,
        )
        if found is None:
            msg = f"{path}: module docstring carries no copyright notice"
            raise ValueError(msg)
        first = inner.rfind("\n", 0, found.start()) + 1
        blank = inner.find("\n\n", found.end())
        last = len(inner) if blank < 0 else blank
        after = inner[last:].strip("\n")
        if not after.strip():
            return source
        before = inner[:first].rstrip("\n")
        text = f"{before}\n\n{after}" if before.strip() else after
        updated = cls._with_notice(f'{prefix}"""{text}"""', inner[first:last].strip())
        rewritten = f"{source[:start]}{updated}{source[end:]}"
        ast.parse(rewritten, filename=str(path))
        return rewritten

    @classmethod
    def _with_notice(cls, raw: str, notice: str) -> str:
        """Return the module docstring with the notice as its last lines.

        Returns:
            The module docstring with the notice as its last lines.

        """
        prefix, inner = cls._split_literal(raw)
        return f'{prefix}"""{inner.strip()}\n\n{notice}\n"""'

    @staticmethod
    def _literal_safe(text: str, prefix: str) -> str:
        r"""Return ``text`` escaped for a ``\"\"\"`` literal with ``prefix``.

        A raw literal keeps backslashes verbatim, so only a run of three
        double quotes is rewritten; a plain literal escapes its backslashes
        and quote runs. Derived text then cannot end or alter the literal it
        is written into.

        Returns:
            ``text`` as it can be written inside the literal.

        """
        if "r" in prefix.lower():
            return text.replace('"""', "'''")
        return text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')

    # -- line-too-long: wrap what Ruff format cannot ---------------------------------

    @classmethod
    def wrap_long_lines(
        cls,
        source: str,
        line_numbers: t.SequenceOf[int],
        *,
        limit: int,
    ) -> str:
        """Return ``source`` with every wrappable long line wrapped.

        Ruff format wraps expressions but never splits a string literal or a
        comment. A long single-line string literal is split after spaces into
        implicit concatenation, inside its enclosing brackets or inside new
        parentheses; a long full-line comment is reflowed at the same indent.
        The parser folds implicit concatenation and drops comments, so the
        repaired module's AST must equal the original one. A line holding
        neither keeps its text and its finding.

        Returns:
            The repaired source.

        Raises:
            ValueError: If a repair would change the module AST.

        """
        before = ast.dump(ast.parse(source))
        lines = source.splitlines(keepends=True)
        tokens = tuple(tokenize.generate_tokens(io.StringIO(source).readline))
        for number in sorted(set(line_numbers), reverse=True):
            line = lines[number - 1]
            if len(line.rstrip("\r\n")) <= limit:
                continue
            replacement = cls._line_wrap_comment(
                line,
                number,
                tokens,
                limit,
            ) or cls._line_wrap_literal(line, number, tokens, limit)
            if replacement is not None:
                lines[number - 1] = replacement
        repaired = "".join(lines)
        if ast.dump(ast.parse(repaired)) != before:
            msg = "line wrap changed the module AST"
            raise ValueError(msg)
        return repaired

    @staticmethod
    def _line_wrap_comment(
        line: str,
        number: int,
        tokens: t.SequenceOf[tokenize.TokenInfo],
        limit: int,
    ) -> str | None:
        """Reflow one full-line comment into lines within the limit.

        Returns:
            The reflowed comment lines, or ``None`` when the line is no
            full-line comment or one of its words alone exceeds the limit.

        """
        comment = next(
            (
                token
                for token in tokens
                if token.start[0] == number and token.type == tokenize.COMMENT
            ),
            None,
        )
        indent = line[: len(line) - len(line.lstrip())]
        if comment is None or comment.start[1] != len(indent):
            return None
        prefix = f"{indent}{comment.string[:1]} "
        wrapped = textwrap.wrap(
            comment.string[1:].strip(),
            width=limit - len(prefix),
            break_long_words=False,
            break_on_hyphens=False,
        )
        if len(wrapped) <= 1 or any(
            len(prefix) + len(part) > limit for part in wrapped
        ):
            return None
        newline = line[len(line.rstrip("\r\n")) :]
        return "".join(f"{prefix}{part}{newline}" for part in wrapped)

    @classmethod
    def _line_wrap_literal(
        cls,
        line: str,
        number: int,
        tokens: t.SequenceOf[tokenize.TokenInfo],
        limit: int,
    ) -> str | None:
        """Split the longest splittable single-line string literal of one line.

        Returns:
            The line with its literal split, or ``None`` when no literal on the
            line can be split within the limit.

        """
        literals = sorted(
            cls._line_wrap_literals(tokens, number),
            key=lambda literal: literal.end - literal.start,
            reverse=True,
        )
        for literal in literals:
            text = line[literal.start : literal.end]
            column = literal.start if literal.bracketed else literal.start + 1
            cuts = cls._line_wrap_cuts(text, literal, column, limit)
            if not cuts:
                continue
            pieces = cls._line_wrap_pieces(text, literal, cuts)
            joined = f"\n{' ' * column}".join(pieces)
            body = joined if literal.bracketed else f"({joined})"
            return f"{line[: literal.start]}{body}{line[literal.end :]}"
        return None

    @staticmethod
    def _line_wrap_cuts(
        text: str,
        literal: m.Infra.LineWrapLiteral,
        column: int,
        limit: int,
    ) -> t.SequenceOf[int]:
        """Pick split offsets after spaces so every piece fits the limit.

        A split never lands inside an escape sequence or an f-string
        replacement field.

        Returns:
            The split offsets, or an empty sequence when the literal cannot fit.

        """
        opening = len(literal.prefix) + len(literal.quote)
        closing = len(literal.quote)
        safe: list[int] = []
        braces = 0
        escaped = False
        for index in range(opening, len(text) - closing):
            char = text[index]
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == "{":
                braces += 1
            elif char == "}":
                braces = max(braces - 1, 0)
            elif char == " " and not braces:
                safe.append(index + 1)
        cuts: list[int] = []
        anchor = 0
        while column + (opening if cuts else 0) + len(text) - anchor > limit:
            reopen = opening if cuts else 0
            fitting = [
                cut
                for cut in safe
                if cut > anchor and column + reopen + cut - anchor + closing <= limit
            ]
            if not fitting:
                return ()
            anchor = fitting[-1]
            cuts.append(anchor)
        return tuple(cuts)

    @staticmethod
    def _line_wrap_pieces(
        text: str,
        literal: m.Infra.LineWrapLiteral,
        cuts: t.SequenceOf[int],
    ) -> t.StrSequence:
        """Split one literal at the given offsets into closed literals.

        Returns:
            The literal pieces, each with its own prefix and quotes.

        """
        reopen = f"{literal.prefix}{literal.quote}"
        bounds = (0, *cuts, len(text))
        return tuple(
            (reopen if index else "")
            + text[start:end]
            + (literal.quote if index < len(bounds) - 2 else "")
            for index, (start, end) in enumerate(pairwise(bounds))
        )

    @classmethod
    def _line_wrap_literals(
        cls,
        tokens: t.SequenceOf[tokenize.TokenInfo],
        number: int,
    ) -> t.SequenceOf[m.Infra.LineWrapLiteral]:
        """Return each single-quoted single-line string literal of one line.

        Returns:
            The literals of the line with their bracket context.

        """
        depths = cls._line_wrap_bracket_depths(tokens, number)
        literals: list[m.Infra.LineWrapLiteral] = []
        for start, end, head in cls._line_wrap_spans(tokens, number):
            body = head.lstrip("rRbBuUfFtT")
            quote = body[:1]
            if body[:3] == quote * 3:
                continue
            literals.append(
                m.Infra.LineWrapLiteral(
                    start=start,
                    end=end,
                    prefix=head[: len(head) - len(body)],
                    quote=quote,
                    bracketed=depths.get(start, 0) > 0,
                ),
            )
        return tuple(literals)

    @staticmethod
    def _line_wrap_bracket_depths(
        tokens: t.SequenceOf[tokenize.TokenInfo],
        number: int,
    ) -> t.MappingKV[int, int]:
        """Map each token column of one line to its bracket nesting depth.

        Returns:
            Column to bracket depth for every token starting on the line.

        """
        depth = 0
        depths: MutableMapping[int, int] = {}
        for token in tokens:
            if token.start[0] > number:
                break
            if token.start[0] == number:
                depths.setdefault(token.start[1], depth)
            if token.type == tokenize.OP and token.string in {"(", "[", "{"}:
                depth += 1
            elif token.type == tokenize.OP and token.string in {")", "]", "}"}:
                depth -= 1
        return depths

    @staticmethod
    def _line_wrap_spans(
        tokens: t.SequenceOf[tokenize.TokenInfo],
        number: int,
    ) -> t.SequenceOf[t.Triple[int, int, str]]:
        """Return the column span and opening text of each literal on one line.

        Returns:
            ``(start, end, opening)`` per plain or f-string literal of the line.

        """
        spans: list[t.Triple[int, int, str]] = []
        opened: tokenize.TokenInfo | None = None
        for token in tokens:
            if token.type == tokenize.FSTRING_START:
                opened = token
            elif token.type == tokenize.FSTRING_END and opened is not None:
                if opened.start[0] == token.end[0] == number:
                    spans.append((opened.start[1], token.end[1], opened.string))
                opened = None
            elif (
                opened is None
                and token.type == tokenize.STRING
                and token.start[0] == token.end[0] == number
            ):
                spans.append((token.start[1], token.end[1], token.string))
        return tuple(spans)


__all__: list[str] = ["FlextInfraUtilitiesLintRecipes"]
