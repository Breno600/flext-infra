"""CLI tool to fix Pyrefly configurations across projects.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import override

from flext_infra import c, m, p, r, t, u
from flext_infra.base import FlextInfraServiceBase
from flext_infra.deps._pyrefly_fix_steps import FlextInfraConfigFixerSteps


class FlextInfraConfigFixer(FlextInfraConfigFixerSteps, FlextInfraServiceBase[bool]):
    """Fix pyrefly configuration across workspace projects."""

    _repository_root: Path = u.PrivateAttr()

    def __init__(self, repository_root: Path | None = None) -> None:
        """Initialize pyrefly settings fixer."""
        resolved_root = u.Infra.resolve_repository_root_or_cwd(repository_root)
        super().__init__(repository_root=resolved_root)
        self._repository_root = self.repository_root

    @override
    def execute(self) -> p.Result[bool]:
        """Execute.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        return r[bool].fail("Use execute_command() directly")

    @classmethod
    def execute_payload(cls, params: m.Infra.FixPyreflyConfigCommand) -> p.Result[bool]:
        """Execute pyrefly config repair from the canonical check command payload.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        fixer = cls(repository_root=params.repository_root)
        fix_result = fixer.run(
            projects=params.project_names or [],
            dry_run=params.dry_run,
            verbose=params.verbose,
        )
        if fix_result.failure:
            return r[bool].from_failure(fix_result)
        return r[bool].ok(value=True)

    def process_file(
        self,
        path: Path,
        *,
        dry_run: bool = False,
    ) -> p.Result[t.StrSequence]:
        """Process one pyproject.toml file and apply fixes.

        Returns:
            The resulting ``p.Result[t.StrSequence]``.

        """
        document_result = u.Cli.toml_read_document(path)
        if document_result.failure:
            return r[t.StrSequence].from_failure(document_result)
        doc = document_result.value
        table = self._validated_pyrefly_table(path, doc.unwrap())
        if table.failure:
            return r[t.StrSequence].from_failure(table)
        pyrefly_table, table_present = table.value
        if not table_present or pyrefly_table is None:
            return r[t.StrSequence].ok(())
        pyrefly: MutableMapping[str, t.JsonValue] = pyrefly_table
        original_pyrefly: t.JsonMapping = dict(pyrefly)
        project_dir = path.parent
        fixes = self._sync_pyrefly_fixes(
            pyrefly,
            project_dir,
            is_root=project_dir == self._repository_root,
        )
        if fixes.failure:
            return r[t.StrSequence].from_failure(fixes)
        if fixes.value and not dry_run:
            written = self._write_changed_tables(path, doc, pyrefly, original_pyrefly)
            if written.failure:
                return r[t.StrSequence].from_failure(written)
        return r[t.StrSequence].ok(fixes.value)

    @staticmethod
    def _validated_pyrefly_table(
        path: Path,
        doc_data: t.MappingKV[str, t.JsonValue],
    ) -> p.Result[t.Pair[t.MutableJsonMapping | None, bool]]:
        """Validate the ``[tool.pyrefly]`` table of one parsed document.

        Returns:
            The resulting validated mutable pyrefly table with a presence
            flag (False when the document declares no ``[tool.pyrefly]``
            table).

        """
        tool_data = doc_data.get(c.Infra.TOOL)
        if not isinstance(tool_data, Mapping):
            return r[t.Pair[t.MutableJsonMapping | None, bool]].ok((None, False))
        typed_tool_data: p.Result[t.MutableJsonMapping] = u.validate_value(
            t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER,
            tool_data,
        )
        if typed_tool_data.failure:
            return r[t.Pair[t.MutableJsonMapping | None, bool]].fail_op(
                f"validate {path} [tool]",
                typed_tool_data.error,
            )
        pyrefly_data = typed_tool_data.value.get(c.Infra.PYREFLY)
        if not isinstance(pyrefly_data, Mapping):
            return r[t.Pair[t.MutableJsonMapping | None, bool]].ok((None, False))
        validated_pyrefly: p.Result[t.MutableJsonMapping] = u.validate_value(
            t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER,
            pyrefly_data,
        )
        if validated_pyrefly.failure:
            return r[t.Pair[t.MutableJsonMapping | None, bool]].fail_op(
                f"validate {path} [tool.pyrefly]",
                validated_pyrefly.error,
            )
        return r[t.Pair[t.MutableJsonMapping | None, bool]].ok(
            (validated_pyrefly.value, True),
        )

    def _sync_pyrefly_fixes(
        self,
        pyrefly: MutableMapping[str, t.JsonValue],
        project_dir: Path,
        *,
        is_root: bool,
    ) -> p.Result[t.StrSequence]:
        """Sync search path, includes, sub-config ignores, and excludes.

        Returns:
            The resulting accumulated fix descriptions.

        """
        all_fixes: t.MutableSequenceOf[str] = []
        search_result = self._sync_search_path(pyrefly, project_dir, is_root=is_root)
        if search_result.failure:
            return r[t.StrSequence].from_failure(search_result)
        all_fixes.extend(search_result.value)
        includes_result = self._sync_project_includes(
            pyrefly,
            project_dir,
            is_root=is_root,
        )
        if includes_result.failure:
            return r[t.StrSequence].from_failure(includes_result)
        all_fixes.extend(includes_result.value)
        sub_result = self._strip_ignored_sub_configs(pyrefly)
        if sub_result.failure:
            return r[t.StrSequence].from_failure(sub_result)
        sub_fixes, removed_ignore = sub_result.value
        all_fixes.extend(sub_fixes)
        if removed_ignore or is_root:
            excludes_result = self._sync_project_excludes(pyrefly)
            if excludes_result.failure:
                return r[t.StrSequence].from_failure(excludes_result)
            all_fixes.extend(excludes_result.value)
        return r[t.StrSequence].ok(all_fixes)

    @staticmethod
    def _write_changed_tables(
        path: Path,
        doc: t.Cli.TomlDocument,
        pyrefly: MutableMapping[str, t.JsonValue],
        original_pyrefly: t.JsonMapping,
    ) -> p.Result[bool]:
        """Reassign changed pyrefly keys and write the document back.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        tool_table = doc[c.Infra.TOOL]
        if not isinstance(tool_table, MutableMapping):
            return r[bool].fail(f"invalid {path} [tool] table")
        pyrefly_table = tool_table[c.Infra.PYREFLY]
        if not isinstance(pyrefly_table, MutableMapping):
            return r[bool].fail(f"invalid {path} [tool.pyrefly] table")
        # Reassign only changed keys so an untouched
        # nested table retains adjacent managed comments and TOML trivia.
        for key, value in pyrefly.items():
            if key in original_pyrefly and original_pyrefly[key] == value:
                continue
            pyrefly_table[key] = value
        written = u.Cli.toml_write_document(path, doc)
        if written.failure:
            return r[bool].from_failure(written)
        return r[bool].ok(value=True)

    def run(
        self,
        projects: t.StrSequence,
        *,
        dry_run: bool = False,
        verbose: bool = False,
    ) -> p.Result[t.StrSequence]:
        """Run pyrefly configuration fixes for selected projects.

        Returns:
            The resulting ``p.Result[t.StrSequence]``.

        """
        project_paths = [
            (
                project_path
                if project_path.is_absolute()
                else (self._repository_root / project_path)
            ).resolve()
            for project in projects
            for project_path in [Path(project)]
        ]
        files_result = u.Infra.find_all_pyproject_files(
            self._repository_root,
            project_paths=project_paths or None,
        )
        if files_result.failure:
            return r[t.StrSequence].from_failure(files_result)
        messages: t.MutableSequenceOf[str] = []
        total_fixes = 0
        pyproject_files: t.SequenceOf[Path] = files_result.value
        for path in pyproject_files:
            fixes_result = self.process_file(path, dry_run=dry_run)
            if fixes_result.failure:
                return r[t.StrSequence].from_failure(fixes_result)
            fixes: t.StrSequence = fixes_result.value
            if not fixes:
                continue
            total_fixes += len(fixes)
            if verbose:
                rel = (
                    path.relative_to(self._repository_root)
                    if path.is_relative_to(self._repository_root)
                    else path
                )
                for fix in fixes:
                    line = f"  {('(dry)' if dry_run else '✓')} {rel}: {fix}"
                    self.logger.info("pyrefly_config_fix", detail=line)
                    messages.append(line)
        if verbose and total_fixes == 0:
            self.logger.info("pyrefly_configs_clean")
        return r[t.StrSequence].ok(messages)


if __name__ == "__main__":
    raise SystemExit(0)


__all__: list[str] = ["FlextInfraConfigFixer"]
