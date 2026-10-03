"""Per-project namespace enforcement — extracted concern of the namespace enforcer.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, u
from flext_infra.codemod.batch_gates import FlextInfraModGateEngine

if TYPE_CHECKING:
    from collections.abc import MutableMapping

    from flext_infra import t


class FlextInfraNamespaceEnforcerProjectMixin:
    """Run the rule catalog's relocations over one project and report the rest.

    The rule catalog owns detection: every namespace law is a rule document
    the one scan engine evaluates. A rule that a rope relocation repairs
    names it under ``metadata.relocation``; this pass runs those relocations
    over what the rules captured and reports the findings that remain.
    """

    if TYPE_CHECKING:
        _repository_root: Path
        _rope_project: t.Infra.RopeProject

    def _enforce_project(
        self,
        *,
        project_root: Path,
        project_name: str,
        apply: bool,
        gates: t.StrSequence | None = None,
    ) -> m.Infra.ProjectEnforcementReport:
        """Run the relocations of one project and report what remains.

        Returns:
            The resulting ``m.Infra.ProjectEnforcementReport``.

        """
        py_files = self._collect_py_files(project_root=project_root)
        return m.Infra.ProjectEnforcementReport(
            project=project_name,
            project_root=str(project_root),
            relocation_findings=self._relocate_rule_findings(
                project_root=project_root,
                py_files=py_files,
                apply=apply,
                gates=gates,
            ),
            files_scanned=len(py_files),
        )

    @staticmethod
    def _collect_py_files(*, project_root: Path) -> t.SequenceOf[Path]:
        """Collect Python files for scanning.

        Returns:
            The resulting ``t.SequenceOf[Path]``.

        Raises:
            RuntimeError: If ``py_files_result.failure``.

        """
        py_files_result = u.Infra.iter_python_files(
            m.Infra.SourceScanRequest(project_roots=(project_root,)),
        )
        if py_files_result.failure:
            msg = py_files_result.error or (
                f"failed to collect Python files for {project_root}"
            )
            raise RuntimeError(msg)
        declared = u.Infra.namespace_meta(project_root).get("scan_dirs")
        if not isinstance(declared, list) or not declared:
            return py_files_result.value
        scope = frozenset(str(item).strip() for item in declared if str(item).strip())
        return tuple(
            path
            for path in py_files_result.value
            if path.relative_to(project_root).parts[0] in scope
        )

    def _relocate_rule_findings(
        self,
        *,
        project_root: Path,
        py_files: t.SequenceOf[Path],
        apply: bool,
        gates: t.StrSequence | None,
    ) -> t.NonNegativeInt:
        """Run the rope relocation each finding's rule declares; count the rest.

        With ``apply`` the relocations run once over the captured values and
        the catalog is scanned again; the returned count is what remains.

        Returns:
            The resulting ``t.NonNegativeInt``.

        """
        findings = self._relocation_findings(project_root, py_files)
        if not (apply and findings):
            return len(findings)
        names: MutableMapping[
            c.Infra.CodemodRelocation,
            MutableMapping[Path, set[str]],
        ] = defaultdict(lambda: defaultdict(set))
        spans: MutableMapping[Path, list[t.IntPair]] = defaultdict(list)
        imports: MutableMapping[Path, MutableMapping[t.StrPair, set[str]]] = (
            defaultdict(lambda: defaultdict(set))
        )
        classes: list[tuple[Path, str, str, int]] = []
        own_package = u.Infra.project_package_name(project_root)
        for relocation, finding in findings:
            file_path = project_root / finding.file
            match relocation:
                case c.Infra.CodemodRelocation.MODULE_IMPORT:
                    spans[file_path].append(self._finding_lines(finding))
                case c.Infra.CodemodRelocation.FUTURE_ANNOTATIONS:
                    names[relocation].setdefault(file_path, set())
                case c.Infra.CodemodRelocation.PACKAGE_ROOT_IMPORT:
                    module = self._captured(
                        finding,
                        c.Infra.CODEMOD_RULE_MODULE_METAVARIABLE,
                    )
                    imports[file_path][module, module.split(".", maxsplit=1)[0]].add(
                        self._captured(finding, c.Infra.CODEMOD_RULE_NAME_METAVARIABLE),
                    )
                case c.Infra.CodemodRelocation.OWN_PACKAGE_IMPORT:
                    module = self._captured(
                        finding,
                        c.Infra.CODEMOD_RULE_MODULE_METAVARIABLE,
                    )
                    imports[file_path][module, own_package].add(
                        self._captured(finding, c.Infra.CODEMOD_RULE_NAME_METAVARIABLE),
                    )
                case c.Infra.CodemodRelocation.FACADE_CLASS:
                    classes.append((
                        file_path,
                        self._captured(finding, c.Infra.CODEMOD_RULE_NAME_METAVARIABLE),
                        self._captured(
                            finding,
                            c.Infra.CODEMOD_RULE_FAMILY_METAVARIABLE,
                        ),
                        self._finding_lines(finding)[0],
                    ))
                case _:
                    names[relocation][file_path].add(
                        self._captured(finding, c.Infra.CODEMOD_RULE_NAME_METAVARIABLE),
                    )
        for file_path, statement_lines in spans.items():
            u.Infra.hoist_inline_imports(file_path, statement_lines)
        self._rebind_imports(imports)
        self._move_classes(project_root, classes)
        for relocation, names_by_file in names.items():
            match relocation:
                case c.Infra.CodemodRelocation.PROTOCOL:
                    u.Infra.rewrite_manual_protocol_violations(
                        project_root=project_root,
                        py_files=py_files,
                        names_by_file=names_by_file,
                        gates=gates,
                    )
                case c.Infra.CodemodRelocation.TYPING_ALIAS:
                    u.Infra.rewrite_manual_typing_alias_violations(
                        project_root=project_root,
                        names_by_file=names_by_file,
                        gates=gates,
                    )
                case c.Infra.CodemodRelocation.FUTURE_ANNOTATIONS:
                    u.Infra.rewrite_missing_future_annotations(
                        py_files=tuple(names_by_file),
                    )
        self._rope_project.validate(self._rope_project.root)
        return len(self._relocation_findings(project_root, py_files))

    def _rebind_imports(
        self,
        imports: t.MappingKV[Path, t.MappingKV[t.StrPair, set[str]]],
    ) -> None:
        """Move each captured name from its source import to its target module.

        Raises:
            ValueError: If import relocation target is not a rope resource.

        """
        for file_path, moves in imports.items():
            resource = u.Infra.fetch_python_resource(self._rope_project, file_path)
            if resource is None:
                msg = f"import relocation target is not a rope resource: {file_path}"
                raise ValueError(msg)
            for (source_module, target_module), aliases in sorted(moves.items()):
                u.Infra.relocate_from_import_aliases(
                    self._rope_project,
                    resource,
                    source_module=source_module,
                    target_module=target_module,
                    aliases=tuple(sorted(aliases)),
                )

    def _move_classes(
        self,
        project_root: Path,
        classes: t.SequenceOf[tuple[Path, str, str, int]],
    ) -> None:
        """Move each captured class to the module of its facade family.

        Raises:
            ValueError: If facade-class relocation requires a project layout.

        """
        if not classes:
            return
        layout = u.Infra.layout(project_root)
        if layout is None:
            msg = f"facade-class relocation requires a project layout: {project_root}"
            raise ValueError(msg)
        for source_file, class_name, family, line in sorted(
            classes,
            key=itemgetter(0, 3),
            reverse=True,
        ):
            u.Infra.move_class(
                m.Infra.ClassMoveRequest(
                    rope_project=self._rope_project,
                    source_file=source_file,
                    target_file=u.Infra.class_target_file(
                        package_dir=layout.package_dir,
                        source_file=source_file,
                        class_name=class_name,
                        family=family,
                    ),
                    class_name=class_name,
                    line=line,
                    apply=True,
                ),
            )

    @staticmethod
    def _relocation_findings(
        project_root: Path,
        py_files: t.SequenceOf[Path],
    ) -> t.VariadicTuple[t.Pair[c.Infra.CodemodRelocation, m.Infra.ModScanFinding]]:
        """Return the engine's relocation findings inside the enforcer's file scope.

        The scope is the project's namespace file set (its declared scan
        directories), so a relocation never reaches a file the namespace pass
        does not govern.

        Returns:
            The engine's relocation findings inside the enforcer's file scope.

        """
        relocation_by_rule = {
            rule.id: rule.relocation
            for rule in u.Infra.codemod_rule_plan(project_root).unwrap().rules
            if rule.relocation is not None
        }
        scoped = frozenset(path.resolve() for path in py_files)
        report = FlextInfraModGateEngine.scan(project_root, fix=False).unwrap()
        return tuple(
            (relocation_by_rule[entry.rule_id], entry)
            for entry in report.entries
            if entry.rule_id in relocation_by_rule
            and (project_root / entry.file).resolve() in scoped
        )

    @staticmethod
    def _finding_lines(finding: m.Infra.ModScanFinding) -> t.IntPair:
        """Return the 1-based inclusive line span of one finding.

        Returns:
            The 1-based inclusive line span of one finding.

        Raises:
            TypeError: If ast-grep finding without a line range; or if ast-grep finding
                with a non-integer line.

        """
        start = finding.range["start"]
        end = finding.range["end"]
        if not (isinstance(start, Mapping) and isinstance(end, Mapping)):
            msg = f"ast-grep finding without a line range: {finding.rule_id}"
            raise TypeError(msg)
        start_line = start["line"]
        end_line = end["line"]
        if not (isinstance(start_line, int) and isinstance(end_line, int)):
            msg = f"ast-grep finding with a non-integer line: {finding.rule_id}"
            raise TypeError(msg)
        return start_line + 1, end_line + 1

    @staticmethod
    def _captured(finding: m.Infra.ModScanFinding, variable: str) -> str:
        """Return one metavariable a relocation rule captured or derived.

        Returns:
            One metavariable a relocation rule captured or derived.

        Raises:
            TypeError: If ast-grep finding without metaVariables; or if relocation rule.

        """
        metavariables = finding.payload["metaVariables"]
        if not isinstance(metavariables, Mapping):
            msg = f"ast-grep finding without metaVariables: {finding.rule_id}"
            raise TypeError(msg)
        single = metavariables.get("single")
        transformed = metavariables.get("transformed")
        captured = single.get(variable) if isinstance(single, Mapping) else None
        if captured is None and isinstance(transformed, Mapping):
            captured = transformed.get(variable)
        text = captured.get("text") if isinstance(captured, Mapping) else captured
        if not isinstance(text, str) or not text:
            msg = f"relocation rule {finding.rule_id} did not capture ${variable}"
            raise TypeError(msg)
        return text


__all__: list[str] = ["FlextInfraNamespaceEnforcerProjectMixin"]
