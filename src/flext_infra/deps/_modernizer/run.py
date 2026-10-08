"""Select workspace pyprojects, modernize them, and verify the build backend.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, r, t, u
from flext_infra.deps._floor_profile_writer import FlextInfraDepsFloorProfileWriter

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from flext_infra import p


class FlextInfraPyprojectModernizerRun:
    """Drive file selection, modernization, reporting, and post-write checks."""

    if TYPE_CHECKING:
        # Members supplied by the composed modernizer service.
        audit: bool
        check_only: bool
        skip_check: bool
        skip_comments: bool
        rewrite_constraints: bool

        @property
        def root(self) -> Path: ...

        @property
        def effective_dry_run(self) -> bool: ...

        @property
        def project_names(self) -> t.StrSequence | None: ...

        def _read_document_state(
            self,
            path: Path,
            *,
            source: str | None = None,
        ) -> p.Result[m.Infra.PyprojectDocumentState]: ...

        def _process_document_state(
            self,
            state: m.Infra.PyprojectDocumentState,
            *,
            canonical_dev: t.StrSequence,
            dry_run: bool,
            skip_comments: bool,
        ) -> p.Result[t.StrSequence]: ...

    def _selected_project_paths(self) -> p.Result[t.SequenceOf[Path]]:
        """Resolve selected names by path, directory basename, or declared name.

        Returns:
            The resulting ``p.Result[t.SequenceOf[Path]]``.

        """
        result_type = r[t.SequenceOf[Path]]
        declared = {
            name: self.root / name
            for name in u.Infra.workspace_project_paths(self.root)
        }
        resolved_root = self.root.resolve()
        outside = sorted(
            name
            for name, path in declared.items()
            if not path.resolve().is_relative_to(resolved_root)
        )
        if outside:
            return result_type.fail(
                f"workspace subprojects outside root: {', '.join(outside)}",
            )
        aliases: MutableMapping[str, t.MutableSequenceOf[Path]] = {}
        for path in declared.values():
            aliases.setdefault(path.name, []).append(path)
            # A declared subproject whose pyproject cannot be read or named
            # would otherwise vanish from the alias map and resurface as a
            # false "missing" or "ambiguous" project further down.
            state = self._read_document_state(path / c.PYPROJECT_FILENAME)
            if state.failure:
                # A declared member's unreadable pyproject is a broken
                # workspace contract, not a selectable absence: the canonical
                # docs-scope reader owns the typed error for invalid TOML and
                # names the offending file, and that raise must leave the run
                # instead of being demoted into an exit-code log line.
                _ = u.Infra.project_state(path)
                return result_type.fail(
                    f"workspace subproject {path} has an unreadable pyproject: "
                    f"{state.error}",
                )
            name = u.Infra.project_name_from_payload(
                state.value.pyproject_path,
                state.value.payload,
            )
            if path not in aliases.setdefault(name, []):
                aliases[name].append(path)
        selected = [name for name in self.project_names or () if name != "."]
        paths: t.MutableSequenceOf[Path] = []
        missing: t.MutableSequenceOf[str] = []
        ambiguous: t.MutableSequenceOf[str] = []
        for name in selected if self.project_names else declared:
            matches = [declared[name]] if name in declared else aliases.get(name, [])
            if len(matches) > 1:
                ambiguous.append(name)
            elif not matches or not matches[0].is_dir():
                missing.append(name)
            else:
                paths.append(matches[0])
        if ambiguous:
            return result_type.fail(
                f"ambiguous projects: {', '.join(sorted(ambiguous))}",
            )
        if missing:
            return result_type.fail(f"unknown projects: {', '.join(sorted(missing))}")
        return result_type.ok(paths)

    def run(self) -> int:
        """Run pyproject modernization for the workspace.

        Returns:
            The resulting ``int``.

        """
        check_mode = self.audit or self.check_only
        dry_run = check_mode or self.effective_dry_run
        # Modernization writes only the requested repository root and its
        # declared subprojects, never siblings.
        include_root = not self.project_names or "." in self.project_names
        project_paths = self._selected_project_paths()
        if project_paths.failure:
            u.Cli.error(project_paths.error or "project selection failed")
            return 2
        root_pyproject = self.root / c.PYPROJECT_FILENAME
        validated = self._validated_root(root_pyproject, include_root=include_root)
        if validated.failure:
            return 2
        if self.rewrite_constraints:
            return self._rewrite_constraints(validated.value, dry_run=dry_run)
        found = u.Infra.find_all_pyproject_files(
            self.root,
            skip_dirs=c.Infra.PYPROJECT_SKIP_DIRS,
            project_paths=project_paths.value,
        )
        files = {*(() if found.failure else found.value)}
        if include_root and root_pyproject.is_file():
            files.add(root_pyproject)
        canonical_dev: t.StrSequence = t.Infra.STR_SEQ_ADAPTER.validate_python(
            u.Infra.canonical_dev_dependencies_from_payload(validated.value.payload),
        )
        scanned = self._scan_documents(
            sorted(files),
            validated,
            root_pyproject,
            canonical_dev=canonical_dev,
            dry_run=dry_run,
        )
        if scanned.failure:
            u.Cli.error(scanned.error or "document scan failed")
            return 2
        violations, states, invalid_paths = scanned.value
        total = self._report_violations(violations, dry_run=dry_run)
        if check_mode and total > 0:
            return 1
        return (
            0
            if dry_run or self.skip_check
            else self._run_build_check(states, invalid_paths=invalid_paths)
        )

    @staticmethod
    def _report_violations(
        violations: t.MappingKV[str, t.StrSequence],
        *,
        dry_run: bool,
    ) -> int:
        """Emit every change grouped by file with the closing total.

        Returns:
            The total change count across all files.

        """
        total = sum(len(changes) for changes in violations.values())
        for rel_path, changes in violations.items():
            u.Cli.info(f"{rel_path}:")
            for change in changes:
                u.Cli.info(f"  - {change}")
        if violations:
            u.Cli.info(f"Total: {total} change(s) across {len(violations)} file(s)")
            if dry_run:
                u.Cli.info("(dry-run — no files modified)")
        return total

    def _validated_root(
        self,
        root_pyproject: Path,
        *,
        include_root: bool,
    ) -> p.Result[m.Infra.PyprojectDocumentState]:
        """Read and validate the root document state for the requested scope.

        Returns:
            The resulting validated root document state.

        """
        root_state = self._read_document_state(root_pyproject)
        if root_state.failure:
            return root_state
        if include_root:
            try:
                _ = u.Infra.project_name_from_payload(
                    root_pyproject,
                    root_state.value.payload,
                )
            except c.EXC_TYPE_VALIDATION as exc:
                u.Cli.error(str(exc))
                return r[m.Infra.PyprojectDocumentState].fail(str(exc), exception=exc)
        return root_state

    def _scan_documents(
        self,
        ordered: t.SequenceOf[Path],
        root_state: p.Result[m.Infra.PyprojectDocumentState],
        root_pyproject: Path,
        *,
        canonical_dev: t.StrSequence,
        dry_run: bool,
    ) -> p.Result[
        t.Triple[
            t.MappingKV[str, t.StrSequence],
            t.SequenceOf[m.Infra.PyprojectDocumentState],
            t.SequenceOf[Path],
        ]
    ]:
        """Process every ordered pyproject and collect the modernization scan.

        Returns:
            The resulting ``(violations, states, invalid_paths)`` triple.

        """
        outcome = r[
            t.Triple[
                t.MappingKV[str, t.StrSequence],
                t.SequenceOf[m.Infra.PyprojectDocumentState],
                t.SequenceOf[Path],
            ]
        ]
        violations: MutableMapping[str, t.StrSequence] = {}
        states: t.MutableSequenceOf[m.Infra.PyprojectDocumentState] = []
        invalid_paths: t.MutableSequenceOf[Path] = []
        drift_reported = False
        for index, file_path in enumerate(ordered, start=1):
            u.Cli.progress(index, len(ordered), str(file_path), c.Infra.CLI_GROUP_DEPS)
            state = (
                root_state
                if file_path.resolve() == root_pyproject.resolve()
                else self._read_document_state(file_path)
            )
            if state.failure:
                invalid_paths.append(file_path)
                changes: t.StrSequence = ("invalid TOML",)
            else:
                processed = self._process_document_state(
                    state.value,
                    canonical_dev=canonical_dev,
                    dry_run=dry_run,
                    skip_comments=self.skip_comments,
                )
                if processed.failure:
                    return outcome.from_failure(processed)
                changes = processed.value
                if changes and not drift_reported:
                    drift_reported = True
                    diff_lines = u.Infra.unified_diff_lines(
                        state.value.original_rendered,
                        state.value.rendered,
                        fromfile=f"{file_path}:before",
                        tofile=f"{file_path}:after",
                        max_lines=c.Infra.EDIT_DIFF_PREVIEW_MAX_LINES,
                    )
                    u.Cli.info(
                        "deps: first rendered drift\n" + "".join(diff_lines).rstrip(),
                    )
                states.append(state.value)
            if changes:
                resolved = file_path.resolve()
                violations[
                    str(resolved.relative_to(self.root.resolve()))
                    if resolved.is_relative_to(self.root.resolve())
                    else str(resolved)
                ] = changes
        return outcome.ok((dict(violations), tuple(states), tuple(invalid_paths)))

    def _rewrite_constraints(
        self,
        root_state: m.Infra.PyprojectDocumentState,
        *,
        dry_run: bool,
    ) -> int:
        """Write runtime-resolved floors to the codegen SSOT.

        Returns:
            The resulting ``int``.

        """
        try:
            root_project_name = u.Infra.project_name_from_payload(
                root_state.pyproject_path,
                root_state.payload,
            )
        except c.EXC_TYPE_VALIDATION as exc:
            u.Cli.error(str(exc))
            return 2
        if dry_run:
            return 0
        profile_changes = (
            FlextInfraDepsFloorProfileWriter.rewrite_profiles_from_resolution(
                root=self.root,
                resolved_versions=u.Infra.resolved_dependency_versions(),
                internal_names=tuple(
                    sorted({
                        *u.Infra.workspace_project_paths(self.root),
                        root_project_name,
                    }),
                ),
            )
        )
        if profile_changes:
            u.Cli.info(
                "deps: dependency_profiles floors updated from the provisioned runtime",
            )
            for change in profile_changes:
                u.Cli.info(f"  - {change}")
        return 0

    @staticmethod
    def _run_build_check(
        states: t.SequenceOf[m.Infra.PyprojectDocumentState],
        *,
        invalid_paths: t.SequenceOf[Path],
    ) -> int:
        """Validate every pyproject declares the hatchling build backend.

        Returns:
            The resulting ``int``.

        """
        warnings = [f"{path}: invalid TOML" for path in invalid_paths]
        for state in states:
            build_system = u.Cli.toml_mapping_child(state.payload, "build-system")
            backend = (
                None
                if build_system is None
                else u.norm_str(str(build_system.get("build-backend", "")))
            )
            if backend is None:
                warnings.append(f"{state.pyproject_path}: missing [build-system]")
            elif backend != "hatchling.build":
                warnings.append(
                    f"{state.pyproject_path}: expected hatchling.build, got {backend}",
                )
        for warning in warnings:
            u.Cli.info(warning)
        return 1 if warnings else 0


__all__: list[str] = ["FlextInfraPyprojectModernizerRun"]
