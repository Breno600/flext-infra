"""Source-level Rope rewrite helpers."""

from __future__ import annotations

import ast
from collections.abc import Iterable
from operator import itemgetter
from pathlib import Path
from typing import ClassVar

from flext_cli import u

from flext_infra import c, m, t

from .discovery import FlextInfraUtilitiesDiscovery
from .rope_core import FlextInfraUtilitiesRopeCore
from .silent_failure_ast import FlextInfraUtilitiesSilentFailureAst


class FlextInfraUtilitiesRopeSource:
    """Text-oriented helpers shared by Rope-backed refactors."""

    _SINGLE_LINE_DOCSTRING_QUOTE_COUNT: ClassVar[int] = 2
    "Triple-quote occurrences on a line that opens and closes a docstring."

    @staticmethod
    def matches_module_toplevel(file_path: Path) -> bool:
        """Determine if a file is at the package root level."""
        parts = file_path.resolve().parts
        try:
            src_idx = parts.index(c.Infra.DEFAULT_SRC_DIR)
            return len(parts) == src_idx + 3
        except ValueError:
            return (file_path.parent / c.Infra.INIT_PY).is_file() and not (
                file_path.parent.parent / c.Infra.INIT_PY
            ).is_file()

    @staticmethod
    def discover_first_party_namespaces(project_dir: Path) -> t.StrSequence:
        """Discover live regular, namespace, and stub packages under ``src/``."""
        src_dir = project_dir / c.Infra.DEFAULT_SRC_DIR
        return [
            name
            for name in FlextInfraUtilitiesDiscovery.discover_python_dirs(
                src_dir, workspace_excluded_top_dirs=frozenset()
            )
            if name.isidentifier()
        ]

    @staticmethod
    def find_import_insert_position(
        lines: t.StrSequence, *, past_existing: bool = True
    ) -> int:
        """Return the module-level line index where an import may be inserted.

        The position is derived from parsed statements rather than scanned
        lines. A line scan cannot see that a match belongs to a continuation or
        to an indented suite, so it returned positions inside a parenthesized
        import list and inside ``if TYPE_CHECKING:``; inserting a column-zero
        statement at either point produced a file that no longer parses.

        Only top-level imports move the position. ``past_existing`` places it
        after the last of them; otherwise it lands after the module docstring
        and the ``__future__`` imports, before the first regular import.

        A module whose first statement is neither a docstring nor an import
        pins the position just above that statement: returning 0 would insert
        above comment-only header lines (shebang, encoding) and corrupt them.

        ``lines`` may or may not carry trailing newlines (callers feed both
        ``splitlines()`` and ``splitlines(keepends=True)``), so separators are
        normalized here: a ``"".join`` collapse would hand ``ast.parse`` one
        broken line.
        """
        source = "\n".join(line.removesuffix("\n") for line in lines)
        module = ast.parse(source)
        position = 0
        for statement in module.body:
            if isinstance(statement, ast.Expr) and isinstance(
                statement.value, ast.Constant
            ):
                if isinstance(statement.value.value, str) and position == 0:
                    position = statement.end_lineno or position
                    continue
                break
            if (
                isinstance(statement, ast.ImportFrom)
                and statement.module == "__future__"
            ):
                position = statement.end_lineno or position
                continue
            if past_existing and isinstance(statement, ast.Import | ast.ImportFrom):
                position = statement.end_lineno or position
                continue
            if position == 0 and statement.lineno:
                position = statement.lineno - 1
            break
        return position

    @staticmethod
    def index_after_docstring_and_future_imports(lines: t.StrSequence) -> int:
        """Return insertion index after module docstring and future imports."""
        return FlextInfraUtilitiesRopeSource.find_import_insert_position(
            lines, past_existing=False
        )

    @staticmethod
    def looks_like_facade_file(*, file_path: Path, source: str) -> bool:
        """Check if a file looks like a namespace facade."""
        family = c.Infra.NAMESPACE_FILE_TO_FAMILY.get(file_path.name)
        if family is None:
            return False
        for line in source.splitlines():
            stripped = line.strip()
            match = c.Infra.FACADE_ALIAS_RE.match(stripped)
            if match is not None and match.group(1) == family:
                return True
        return False

    @staticmethod
    def find_import_line(*, lines: t.StrSequence, module_name: str) -> int:
        """Find the 1-based line number of ``from <module> import ...``."""
        prefix = f"from {module_name} import "
        for index, line in enumerate(lines, start=1):
            if line.strip().startswith(prefix):
                return index
        return 1

    @staticmethod
    def parse_import_names(names_str: str) -> t.StrPairSequence:
        """Parse ``A, B as C`` into ``[(name, bound), ...]``."""
        result: t.MutableSequenceOf[t.StrPair] = []
        for part in names_str.split(","):
            candidate = part.strip().rstrip("\\").strip()
            if not candidate or candidate.startswith(("(", ")")):
                continue
            if " as " in candidate:
                name, alias = candidate.split(" as ", 1)
                result.append((name.strip(), alias.strip()))
                continue
            result.append((candidate, candidate))
        return result

    @staticmethod
    def parse_param_names(params_str: str) -> t.Infra.StrSet:
        """Parse parameter names from a function signature string."""
        names: t.Infra.StrSet = set()
        for part in params_str.split(","):
            item = part.strip()
            if not item or item == "/":
                continue
            name = item.split(":")[0].split("=")[0].strip().lstrip("*")
            if name:
                names.add(name)
        return names

    @staticmethod
    def collect_from_import_bound_names(
        source: str, *, module_name: str
    ) -> t.Infra.StrSet:
        """Collect bound names imported from a target module."""
        bound_names: t.Infra.StrSet = set()
        for pattern in (c.Infra.FROM_IMPORT_RE, c.Infra.FROM_IMPORT_BLOCK_RE):
            for match in pattern.finditer(source):
                if match.group(1) != module_name:
                    continue
                bound_names.update(
                    bound
                    for _, bound in FlextInfraUtilitiesRopeSource.parse_import_names(
                        match.group(2)
                    )
                )
        return bound_names

    @staticmethod
    def parse_forbidden_rules(
        value: t.JsonPayload,
    ) -> t.SequenceOf[m.Infra.ImportModernizerRuleConfig]:
        """Parse and validate forbidden import rule configs."""
        raw_items = u.Cli.json_as_mapping_list(value)
        if not raw_items:
            return []
        normalized: t.SequenceOf[t.JsonMapping] = [
            {
                "module": item.get("module", ""),
                "symbol_mapping": item.get("symbol_mapping", {}),
            }
            for item in raw_items
        ]
        typed_items = t.Infra.CONTAINER_DICT_SEQ_ADAPTER.validate_python(normalized)
        return [
            m.Infra.ImportModernizerRuleConfig.model_validate(item)
            for item in typed_items
        ]

    @staticmethod
    def collect_blocked_aliases(
        source: str, runtime_aliases: t.Infra.StrSet
    ) -> t.Infra.StrSet:
        """Collect aliases blocked by definitions, imports, and assignments."""
        parse = FlextInfraUtilitiesRopeSource.parse_import_names
        candidates: Iterable[str] = (
            n
            for source_iter in (
                (m.group(1) for m in c.Infra.DEF_CLASS_RE.finditer(source)),
                (m.group(1) for m in c.Infra.ASSIGN_RE.finditer(source)),
                (
                    bound
                    for m in c.Infra.IMPORT_RE.finditer(source)
                    for _, bound in parse(m.group(1))
                ),
                (
                    bound
                    for m in c.Infra.FROM_IMPORT_RE.finditer(source)
                    if m.group(1) != c.Infra.PKG_CORE_UNDERSCORE
                    for _, bound in parse(m.group(2))
                ),
            )
            for n in source_iter
        )
        return {n for n in candidates if n in runtime_aliases}

    @staticmethod
    def collect_shadowed_aliases(
        source: str, runtime_aliases: t.Infra.StrSet
    ) -> t.Infra.StrSet:
        """Collect runtime-alias names shadowed inside function bodies."""
        shadowed: t.Infra.StrSet = set()
        for match in c.Infra.FUNC_PARAM_RE.finditer(source):
            for param in match.group(1).split(","):
                param_name = param.strip().split(":")[0].split("=")[0].strip()
                if param_name.startswith("*"):
                    param_name = param_name.lstrip("*")
                if param_name in runtime_aliases:
                    shadowed.add(param_name)
        return shadowed

    @staticmethod
    def parse_class_bases(source: str, class_name: str) -> t.StrSequence:
        """Extract terminal base-class names from one class definition."""
        for match in c.Infra.CLASS_WITH_BASES_RE.finditer(source):
            if str(match.group(1)) != class_name:
                continue
            base_group = str(match.group(2))
            return [
                terminal
                for base_part in base_group.split(",")
                if (stripped := base_part.strip())
                if (
                    terminal := stripped
                    .split("[", maxsplit=1)[0]
                    .strip()
                    .rsplit(".", maxsplit=1)[-1]
                )
            ]
        return []

    @staticmethod
    def remove_module_level_aliases(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        *,
        allow: t.Infra.StrSet | None = None,
        apply: bool = True,
    ) -> t.StrSequencePair:
        """Remove module-level ``X = Y`` identity aliases."""
        _ = rope_project
        allow_set = allow or set()
        source = resource.read()
        kept: list[str] = []
        removed: list[str] = []
        alias_pattern = c.Infra.MODULE_ALIAS_RE
        scope_depth = 0
        for line in source.splitlines(keepends=True):
            stripped = line.strip()
            if stripped.startswith(("class ", "def ")):
                scope_depth += 1
            if scope_depth > 0:
                kept.append(line)
                continue
            match = alias_pattern.match(stripped)
            if match is None:
                kept.append(line)
                continue
            target, value = match.group(1), match.group(2)
            if (
                target != value
                or target in allow_set
                or target in {c.Infra.DUNDER_VERSION, c.Infra.DUNDER_ALL}
            ):
                kept.append(line)
            else:
                removed.append(f"{target} = {value}")
        if not removed:
            return source, []
        new_source = "".join(kept)
        if apply:
            resource.write(new_source)
        return new_source, removed

    @staticmethod
    def batch_replace_annotations(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        replacements: t.StrMapping,
        *,
        apply: bool = True,
    ) -> t.StrIntPair:
        """Apply multiple annotation replacements in one pass."""
        _ = rope_project
        source = resource.read()
        total = 0
        for old_annotation, new_annotation in replacements.items():
            pattern = c.Infra.compile_word(old_annotation)
            source, count = pattern.subn(new_annotation, source)
            total += count
        if total > 0 and apply and source != resource.read():
            resource.write(source)
        return source, total

    @staticmethod
    def remove_redundant_cast(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        *,
        apply: bool = True,
    ) -> t.StrIntPair:
        """Remove ``cast(Type, value)`` calls, replacing with just ``value``."""
        _ = rope_project
        source = resource.read()
        new_source, count = c.Infra.CAST_CALL_RE.subn(r"\1", source)
        if count > 0 and apply and new_source != source:
            resource.write(new_source)
        return new_source, count

    @staticmethod
    def rewrite_source_at_offsets(
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        changes: t.SequenceOf[t.Triple[int, int, str]],
        *,
        apply: bool = True,
    ) -> str:
        """Apply offset-based edits (start, end, replacement) to source."""
        _ = rope_project
        source: str = resource.read()
        for start, end, replacement in sorted(changes, key=itemgetter(0), reverse=True):
            source = source[:start] + replacement + source[end:]
        if apply and source != resource.read():
            resource.write(source)
        return source

    @classmethod
    def fix_silent_failure_sentinels(
        cls,
        rope_project: t.Infra.RopeProject,
        resource: t.Infra.RopeResource,
        *,
        apply: bool = True,
        kinds: set[str] | frozenset[str] | None = None,
    ) -> t.Infra.TransformResult:
        """Fix silent failure sentinels using rope-backed AST detection.

        Only deterministic replacements (guard / except-sentinel with an
        inferrable ``r[T]`` / ``Result[T]`` return type) are rewritten.
        """
        source = resource.read()
        try:
            pymodule = FlextInfraUtilitiesRopeCore.resolve_pymodule(rope_project, resource)
            tree = pymodule.get_ast()
        except c.EXC_BROAD_RUNTIME as exc:
            msg = f"silent failure sentinel AST collection failed for {resource.path}"
            raise RuntimeError(msg) from exc
        if not isinstance(tree, ast.Module):
            msg = (
                f"silent failure sentinel AST collection returned {type(tree).__name__}"
            )
            raise TypeError(msg)
        changes = FlextInfraUtilitiesSilentFailureAst.collect_silent_failure_fixes(
            tree, source, kinds=kinds
        )
        if not changes:
            return source, []
        updated = cls.rewrite_source_at_offsets(
            rope_project, resource, changes, apply=apply
        )
        return updated, [f"Replaced {len(changes)} silent failure sentinel return(s)"]

    @classmethod
    def apply_transformer_to_source(
        cls, source: str, file_path: Path, transformer_fn: t.Infra.RopeTransformFn
    ) -> t.StrSequencePair:
        """Run a rope transformer against source text via a temporary context."""
        repository_root = FlextInfraUtilitiesDiscovery.project_root(file_path)
        if repository_root is None:
            return (source, [])
        file_path = file_path.resolve()
        if not file_path.is_relative_to(repository_root.resolve()):
            msg = f"refusing Rope rewrite outside project: {file_path}"
            raise ValueError(msg)
        original_disk_source = file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        try:
            with FlextInfraUtilitiesRopeCore.open_project(
                repository_root
            ) as rope_project:
                resource = FlextInfraUtilitiesRopeCore.resolve_resource_from_path(
                    rope_project, file_path
                )
                if resource is None:
                    return (source, [])
                if resource.read() != source:
                    resource.write(source)
                new_source, changes = transformer_fn(rope_project, resource)
                return (new_source, list(changes))
        finally:
            if (
                file_path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
                != original_disk_source
            ):
                file_path.write_text(
                    original_disk_source, encoding=c.Cli.ENCODING_DEFAULT
                )


__all__: list[str] = ["FlextInfraUtilitiesRopeSource"]
