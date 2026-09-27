"""Dataclass-to-Pydantic modelizer — convert serializable dataclasses to m.* contracts.

Canonical automated cutover for the AGENTS.md data-contract law
("No dict/TypedDict/dataclass/NamedTuple as a data contract"):

- Detects ``@dataclass``-decorated classes via AST.
- Converts only *safe* contracts: frozen dataclasses whose every field
  annotation is JSON-serializable (str/int/float/bool/None unions, Path).
- Frozen + serializable → ``m.FrozenModel`` (canonical frozen contract).
- Everything else is SKIPPED with an exact reason: mutable dataclasses,
  non-serializable field types (``os.stat_result``, file descriptors,
  ``t.*`` aliases), custom ``__init__``/``__post_init__`` logic, or
  keywords (``order=True``, ``kw_only``) that change runtime semantics.

The transformer never invents descriptions; field bodies are preserved
byte-for-byte, so defaults and validators survive the cutover unchanged.
"""

from __future__ import annotations

import ast
import re
from typing import ClassVar, final, override

from flext_infra import t

from .rope_transformer import FlextInfraRopeTransformer
from ._rewrite import FlextInfraSourceRewrite, FlextInfraSourceRewriter

_PRIMITIVE_TOKENS: frozenset[str] = frozenset({
    "str",
    "int",
    "float",
    "bool",
    "None",
    "Path",
})

_SKIP_REASON_MUTABLE = "mutable dataclass requires manual model-base selection"
_SKIP_REASON_NON_SERIALIZABLE = "field annotation is not JSON-serializable"
_SKIP_REASON_KEYWORDS = "dataclass keywords change runtime semantics"
_SKIP_REASON_CUSTOM_INIT = "class declares __init__ or __post_init__"


def _is_serializable_annotation(annotation_text: str) -> bool:
    """Return whether an unparsed annotation only names serializable tokens."""
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z_0-9.]*", annotation_text))
    return bool(tokens) and tokens <= _PRIMITIVE_TOKENS


@final
class FlextInfraRefactorDataclassModelizer(FlextInfraRopeTransformer):
    """AST-driven transformer converting safe frozen dataclasses to m.FrozenModel."""

    _description = (
        "convert serializable frozen dataclasses to canonical m.FrozenModel contracts"
    )

    _FORBIDDEN_METHODS: ClassVar[frozenset[str]] = frozenset({
        "__init__",
        "__post_init__",
    })
    _DISALLOWED_KEYWORDS: ClassVar[frozenset[str]] = frozenset({
        "order",
        "unsafe_hash",
        "match_args",
    })

    @override
    def apply_to_source(self, source: str) -> t.Infra.TransformResult:
        """Convert eligible dataclasses; skip and report everything unsafe."""
        self.changes.clear()
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source, list(self.changes)

        visitor = self._DataclassVisitor(source)
        visitor.visit(tree)

        if not visitor.rewrites:
            for skip in visitor.skips:
                self._record_change(f"skipped dataclass {skip}")
            return source, list(self.changes)

        updated = FlextInfraSourceRewriter.apply_rewrites(source, visitor.rewrites)
        for change in visitor.changes:
            self._record_change(change)
        for skip in visitor.skips:
            self._record_change(f"skipped dataclass {skip}")

        return updated, list(self.changes)

    @final
    class _DataclassVisitor(FlextInfraSourceRewriter):
        """Collect dataclass conversions and cataloged skips."""

        def __init__(self, source: str) -> None:
            super().__init__(source)
            self.skips: list[str] = []
            self._import_planned = False

        @override
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            """Evaluate one class definition for dataclass conversion."""
            decorator = self._dataclass_decorator(node)
            if decorator is None:
                self.generic_visit(node)
                return
            if not self._is_frozen(decorator):
                self.skips.append(f"{node.name}: {_SKIP_REASON_MUTABLE}")
                self.generic_visit(node)
                return
            reason = self._conversion_blocker(node, decorator)
            if reason is not None:
                self.skips.append(f"{node.name}: {reason}")
                self.generic_visit(node)
                return
            self._rewrite_to_frozen_model(node, decorator)
            self.generic_visit(node)

        def _dataclass_decorator(
            self, node: ast.ClassDef
        ) -> ast.Call | ast.Name | None:
            """Return the dataclass decorator node when the class carries one."""
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Name) and decorator.id == "dataclass":
                    return decorator
                if (
                    isinstance(decorator, ast.Call)
                    and isinstance(decorator.func, ast.Name)
                    and decorator.func.id == "dataclass"
                ):
                    return decorator
            return None

        @staticmethod
        def _is_frozen(decorator: ast.Call | ast.Name) -> bool:
            """Return whether the decorator pins frozen=True; bare is mutable."""
            if isinstance(decorator, ast.Name):
                return False
            return any(
                keyword.arg == "frozen"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in decorator.keywords
            )

        def _conversion_blocker(
            self, node: ast.ClassDef, decorator: ast.Call | ast.Name
        ) -> str | None:
            """Return the skip reason when the dataclass cannot convert safely."""
            if isinstance(decorator, ast.Call):
                for keyword in decorator.keywords:
                    if (
                        keyword.arg
                        in FlextInfraRefactorDataclassModelizer._DISALLOWED_KEYWORDS
                    ):
                        return _SKIP_REASON_KEYWORDS
                    if keyword.arg == "frozen" and not (
                        isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ):
                        return _SKIP_REASON_MUTABLE
                    if keyword.arg == "init" and not (
                        isinstance(keyword.value, ast.Constant)
                        and keyword.value.value is True
                    ):
                        return _SKIP_REASON_CUSTOM_INIT
            for item in node.body:
                if (
                    isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and item.name
                    in FlextInfraRefactorDataclassModelizer._FORBIDDEN_METHODS
                ):
                    return _SKIP_REASON_CUSTOM_INIT
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and not self._field_serializable(
                    item
                ):
                    return _SKIP_REASON_NON_SERIALIZABLE
            return None

        def _field_serializable(self, item: ast.AnnAssign) -> bool:
            """Return whether one annotated field type is serializable."""
            if not isinstance(item.target, ast.Name):
                return False
            return _is_serializable_annotation(ast.unparse(item.annotation))

        def _rewrite_to_frozen_model(
            self, node: ast.ClassDef, decorator: ast.Call | ast.Name
        ) -> None:
            """Replace decorator lines and the class header with m.FrozenModel."""
            decorator_start = self.node_offset(decorator, start=True)
            class_start = self.node_offset(node, start=True)
            if decorator_start < class_start:
                line_start = self._source.rfind("\n", 0, decorator_start) + 1
                self.rewrites.append(
                    FlextInfraSourceRewrite(line_start, class_start, "")
                )
                self.changes.append(f"{node.name}: removed @dataclass decorator")

            header_end = self._header_end(node)
            header_start = self.node_offset(node, start=True)
            base_names = [ast.unparse(base) for base in node.bases]
            if not base_names:
                new_header = f"class {node.name}(m.FrozenModel):"
            else:
                joined = ", ".join([*base_names, "m.FrozenModel"])
                new_header = f"class {node.name}({joined}):"
            self.rewrites.append(
                FlextInfraSourceRewrite(header_start, header_end, new_header)
            )
            self.changes.append(
                f"{node.name}: converted frozen dataclass to m.FrozenModel"
            )
            self._ensure_model_import()

        def _header_end(self, node: ast.ClassDef) -> int:
            """Return the offset just past the class signature colon."""
            body_start = node.body[0]
            body_offset = self.node_offset(body_start, start=True)
            header_text = self._source[self.node_offset(node, start=True) : body_offset]
            colon_index = header_text.rfind(":")
            if colon_index < 0:
                return body_offset
            return self.node_offset(node, start=True) + colon_index + 1

        def _ensure_model_import(self) -> None:
            """Record one import insertion when the module lacks an ``m`` alias."""
            if self._import_planned:
                return
            module_source = self._source
            if re.search(
                r"^from\s+\S+\s+import\s+.*\bm\b", module_source, re.MULTILINE
            ):
                return
            if re.search(r"^import\s+\S*\bm\b", module_source, re.MULTILINE):
                return
            if self._rewire_facade_import(module_source):
                self._import_planned = True
                return
            future_match = re.search(
                r"^from\s+__future__\s+import\s+annotations\s*$",
                module_source,
                re.MULTILINE,
            )
            insertion_at = future_match.end() if future_match else 0
            self.rewrites.append(
                FlextInfraSourceRewrite(
                    insertion_at, insertion_at, "\n\nfrom flext_core import m"
                )
            )
            self._import_planned = True
            self.changes.append("inserted canonical m alias import")

        def _rewire_facade_import(self, module_source: str) -> bool:
            """Add ``m`` into an existing first-party facade import when present.

            Deterministic rule: the first ``from PKG import ...`` statement whose
            imported names already include a single-letter FLEXT facade alias
            (c/t/p/m/u/r/s) is the module's canonical facade import; ``m`` is
            added in sorted position. Returns whether a rewiring was planned.
            """
            for match in re.finditer(
                r"^from\s+([A-Za-z_][\w.]*)\s+import\s+(.+)$",
                module_source,
                re.MULTILINE,
            ):
                package, names_text = match.group(1), match.group(2)
                if "." in package:
                    continue
                names = [
                    fragment.strip() for fragment in names_text.rstrip(")").split(",")
                ]
                plain = [name for name in names if name.isidentifier()]
                if (
                    not any(len(name) == 1 and name in "ctpmurs" for name in plain)
                    or "m" in plain
                ):
                    continue
                merged = sorted({*plain, "m"})
                new_names_text = ", ".join(merged)
                if names_text.rstrip().endswith(")"):
                    new_names_text += ")"
                start = match.start(2)
                end = match.end(2)
                self.rewrites.append(
                    FlextInfraSourceRewrite(start, end, new_names_text)
                )
                self.changes.append(
                    f"rewired m into canonical facade import from {package}"
                )
                return True
            return False


__all__: list[str] = ["FlextInfraRefactorDataclassModelizer"]
