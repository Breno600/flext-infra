"""Authenticated input and explicitly declared text surfaces for CSV campaigns.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from pathlib import Path

from flext_infra import FlextInfraConfig, c, config, m, t, u


class FlextInfraRenameSources:
    """Read campaign data and source snapshots without granting write effects."""

    @staticmethod
    def pairs(source: str) -> t.VariadicTuple[t.Pair[str, str]]:
        rows = u.Cli.csv_loads(source).unwrap()
        if not rows or rows[0] != ["old", "new"]:
            msg = "rename CSV header must be exactly 'old,new'"
            raise ValueError(msg)
        pairs: t.MutableMappingKV[str, str] = {}
        for row in rows[1:]:
            if len(row) != len(rows[0]) or not all(value.strip() for value in row):
                msg = "every row must contain non-empty old,new values"
                raise ValueError(msg)
            old, new = (value.strip() for value in row)
            if old == new or (old in pairs and pairs[old] != new):
                msg = f"rename CSV contains identity or conflicting duplicate: {old}"
                raise ValueError(msg)
            pairs[old] = new
        if not pairs:
            msg = "rename CSV must declare at least one change"
            raise ValueError(msg)
        for old, new in pairs.items():
            for other in pairs:
                pattern = rf"\b{re.escape(other)}\b"
                if re.search(pattern, new) or (
                    old != other and re.search(pattern, old)
                ):
                    msg = (
                        f"rename CSV contains overlapping or cascading mappings: "
                        f"{old}, {other}"
                    )
                    raise ValueError(msg)
        return tuple(sorted(pairs.items()))

    @staticmethod
    def inventory(
        roots: t.SequenceOf[Path],
        params: m.Infra.ApplyRenamesInput,
    ) -> t.MappingKV[Path, m.Cli.AtomicFileState]:
        """Index scanned files minus ignored, generated, and driver paths.

        Returns:
            The authenticated file states of every electable rename source.

        Raises:
            ValueError: If rename source disappeared.

        """
        files: t.MutableMappingKV[Path, m.Cli.AtomicFileState] = {}
        ignored = config.Infra.codegen.source_scan_ignored
        generated = {item.path for item in config.Infra.codegen.managed_files}
        templates = u.Infra.codegen_template_sources(config.Infra.codegen)
        config_dir = FlextInfraConfig.ssot_config_dir()
        drivers = {
            Path(params.csv).resolve(),
            *(
                (config_dir / campaign.csv).resolve()
                for campaign in config.Infra.refactor_csv_campaigns.campaigns
            ),
        }
        for root in roots:
            paths = u.Infra.git_tracked_scope_paths(root)
            candidates = root.rglob("*") if paths is None else paths
            for path in sorted(candidates):
                relative = path.relative_to(root)
                if (
                    not path.is_file()
                    or path.resolve() in drivers
                    or relative in generated
                    or any(part in ignored for part in relative.parts)
                    or any(
                        relative.full_match(pattern) for pattern in params.exclude_globs
                    )
                ):
                    continue
                python = path.suffix == c.Infra.EXT_PYTHON
                text = any(
                    relative.full_match(pattern) for pattern in params.text_globs
                )
                if not python and not text:
                    continue
                state = u.Cli.atomic_read_binary_file_state(
                    path,
                    required=True,
                ).unwrap()
                if state.content is None:
                    msg = f"rename source disappeared: {path}"
                    raise ValueError(msg)
                source = state.content.decode(c.Cli.ENCODING_DEFAULT)
                if (
                    source.startswith(c.Infra.AUTOGEN_HEADERS)
                    and path.resolve() not in templates
                ):
                    continue
                if path.suffix.lower() == ".csv" and u.Cli.csv_loads(source).unwrap()[
                    :1
                ] == [["old", "new"]]:
                    continue
                files[path.absolute()] = state
        return files

    @staticmethod
    def text_edits(
        source: str,
        pairs: t.SequenceOf[t.Pair[str, str]],
        *,
        start: int = 0,
    ) -> t.VariadicTuple[m.Infra.SourceRewrite]:
        replacements = dict(pairs)
        pattern = re.compile(
            r"\b(?:" + "|".join(re.escape(old) for old in replacements) + r")\b",
        )
        return tuple(
            m.Infra.SourceRewrite(
                start=start + match.start(),
                end=start + match.end(),
                text=replacements[match.group()],
            )
            for match in pattern.finditer(source)
        )

    @classmethod
    def documentation_edits(
        cls,
        source: str,
        pairs: t.SequenceOf[t.Pair[str, str]],
    ) -> t.VariadicTuple[m.Infra.SourceRewrite]:
        """Select real docstrings and comments; executable literals retain bytes.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.SourceRewrite]``.

        Raises:
            ValueError: If Python docstring lacks an authenticated source span.

        """
        lines = source.splitlines(keepends=True)
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line))
        tree = ast.parse(source)
        docstrings: t.MutableSequenceOf[t.Pair[t.Pair[int, int], t.Pair[int, int]]] = []
        for node in ast.walk(tree):
            if not isinstance(
                node,
                (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                continue
            if not node.body or not isinstance(node.body[0], ast.Expr):
                continue
            value = node.body[0].value
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                column = len(
                    lines[value.lineno - 1]
                    .encode(c.Cli.ENCODING_DEFAULT)[: value.col_offset]
                    .decode(c.Cli.ENCODING_DEFAULT),
                )
                if value.end_lineno is None or value.end_col_offset is None:
                    msg = "Python docstring lacks an authenticated source span"
                    raise ValueError(msg)
                end_column = len(
                    lines[value.end_lineno - 1]
                    .encode(c.Cli.ENCODING_DEFAULT)[: value.end_col_offset]
                    .decode(c.Cli.ENCODING_DEFAULT),
                )
                docstrings.append((
                    (value.lineno, column),
                    (value.end_lineno, end_column),
                ))
        edits: t.MutableSequenceOf[m.Infra.SourceRewrite] = []
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT or (
                token.type == tokenize.STRING
                and any(
                    start <= token.start and token.end <= end
                    for start, end in docstrings
                )
            ):
                edits.extend(
                    cls.text_edits(
                        token.string,
                        pairs,
                        start=offsets[token.start[0] - 1] + token.start[1],
                    ),
                )
        return tuple(edits)


__all__: list[str] = ["FlextInfraRenameSources"]
