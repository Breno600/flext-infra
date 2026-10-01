"""Per-project namespace enforcement — extracted concern of the namespace enforcer."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, u
from flext_infra.codemod.batch_gates import FlextInfraModGateEngine
from flext_infra.detectors.class_placement_detector import (
    FlextInfraClassPlacementDetector,
)
from flext_infra.detectors.compatibility_alias_detector import (
    FlextInfraCompatibilityAliasDetector,
)
from flext_infra.detectors.cyclic_import_detector import FlextInfraCyclicImportDetector
from flext_infra.detectors.import_alias_detector import FlextInfraImportAliasDetector
from flext_infra.detectors.internal_import_detector import (
    FlextInfraInternalImportDetector,
)
from flext_infra.detectors.loose_object_detector import FlextInfraLooseObjectDetector
from flext_infra.detectors.namespace_source_detector import (
    FlextInfraNamespaceSourceDetector,
)
from flext_infra.detectors.private_import_bypass_detector import (
    FlextInfraPrivateImportBypassDetector,
)
from flext_infra.detectors.runtime_alias_detector import FlextInfraRuntimeAliasDetector
from flext_infra.refactor.classvar_constant_autofix import (
    FlextInfraRefactorClassvarConstantAutofix,
)

if TYPE_CHECKING:
    from collections.abc import Callable, MutableMapping

    from flext_infra import t


class FlextInfraNamespaceEnforcerProjectMixin:
    """Run every detector over one project and build its enforcement report.

    Composed alongside the phases/orchestration mixins into the concrete
    enforcer; ``self`` provides facade scan / file-collection / detect-apply
    helpers through the concrete's FLEXT.
    """

    if TYPE_CHECKING:
        _repository_root: Path
        _rope_project: t.Infra.RopeProject

        def _detect_and_apply[V](
            self,
            *,
            py_files: t.SequenceOf[Path],
            detect_fn: Callable[[Path], t.SequenceOf[V]],
            rewrite_fn: Callable[[t.MutableSequenceOf[V]], None] | None,
            apply: bool,
        ) -> t.MutableSequenceOf[V]: ...

        @staticmethod
        def _scan_facades(
            *,
            project: t.Pair[Path, str],
            rope_project: t.Infra.RopeProject,
            apply: bool,
            repository_root: Path,
        ) -> t.SequenceOf[m.Infra.FacadeStatus]: ...

        @staticmethod
        def _collect_py_files(*, project_root: Path) -> t.SequenceOf[Path]: ...

    def _enforce_project(
        self,
        *,
        project_root: Path,
        project_name: str,
        apply: bool,
        gates: t.StrSequence | None = None,
    ) -> m.Infra.ProjectEnforcementReport:
        """Enforce project."""
        return self._enforce_project_with_rope(
            project_root=project_root,
            project_name=project_name,
            apply=apply,
            gates=gates,
            rope_project=self._rope_project,
        )

    @staticmethod
    def _detector_context(
        *,
        file_path: Path,
        rope_project: t.Infra.RopeProject,
        parse_failures: t.MutableSequenceOf[m.Infra.ParseFailureViolation],
        project_name: str = "",
        project_root: Path | None = None,
    ) -> m.Infra.DetectorContext:
        """Build the canonical detector context for one file."""
        return m.Infra.DetectorContext(
            file_path=file_path,
            rope_project=rope_project,
            parse_failures=parse_failures,
            project_name=project_name,
            project_root=project_root,
        )

    def _enforce_project_with_rope(
        self,
        *,
        project_root: Path,
        project_name: str,
        apply: bool,
        gates: t.StrSequence | None,
        rope_project: t.Infra.RopeProject,
    ) -> m.Infra.ProjectEnforcementReport:
        """Enforce project using the Rope project scoped to ``project_root``."""
        parse_failures: t.MutableSequenceOf[m.Infra.ParseFailureViolation] = []
        facade_statuses = self._scan_facades(
            project=(project_root, project_name),
            rope_project=rope_project,
            apply=apply,
            repository_root=self._repository_root,
        )
        py_files = self._collect_py_files(project_root=project_root)
        project_layout = u.Infra.layout(project_root)
        package_name = project_layout.package_name if project_layout is not None else ""

        loose_objects = self._detect_and_apply(
            py_files=py_files,
            detect_fn=lambda f: FlextInfraLooseObjectDetector.detect_file(
                self._detector_context(
                    file_path=f,
                    rope_project=rope_project,
                    parse_failures=parse_failures,
                    project_name=project_name,
                    project_root=project_root,
                ),
            ),
            rewrite_fn=lambda vs: u.Infra.rewrite_loose_object_violations(
                project_root=project_root,
                violations=vs,
                parse_failures=parse_failures,
                gates=gates,
            ),
            apply=apply,
        )
        import_violations = self._detect_and_apply(
            py_files=py_files,
            detect_fn=lambda f: FlextInfraImportAliasDetector.detect_file(
                self._detector_context(
                    file_path=f,
                    rope_project=rope_project,
                    parse_failures=parse_failures,
                ),
            ),
            rewrite_fn=lambda _vs: u.Infra.rewrite_import_violations(
                py_files=py_files,
                project_package=package_name,
            ),
            apply=apply,
        )
        namespace_source_violations = self._detect_and_apply(
            py_files=py_files,
            detect_fn=lambda f: FlextInfraNamespaceSourceDetector.detect_file(
                self._detector_context(
                    file_path=f,
                    rope_project=rope_project,
                    parse_failures=parse_failures,
                    project_name=project_name,
                    project_root=project_root,
                ),
            ),
            rewrite_fn=lambda vs: u.Infra.rewrite_namespace_source_violations(
                violations=vs,
                parse_failures=parse_failures,
                gates=gates,
            ),
            apply=apply,
        )
        cyclic_imports = FlextInfraCyclicImportDetector.scan_project(
            project_root=project_root,
            rope_project=rope_project,
        )
        internal_import_violations = self._detect_and_apply(
            py_files=py_files,
            detect_fn=lambda f: FlextInfraInternalImportDetector.detect_file(
                self._detector_context(
                    file_path=f,
                    rope_project=rope_project,
                    parse_failures=parse_failures,
                    project_root=project_root,
                ),
            ),
            rewrite_fn=None,
            apply=apply,
        )
        private_import_bypass_violations = self._detect_and_apply(
            py_files=py_files,
            detect_fn=lambda f: FlextInfraPrivateImportBypassDetector.detect_file(
                self._detector_context(
                    file_path=f,
                    rope_project=rope_project,
                    parse_failures=parse_failures,
                    project_root=project_root,
                ),
            ),
            rewrite_fn=lambda vs: u.Infra.rewrite_private_import_bypass_violations(
                rope_project=rope_project,
                violations=tuple(v for v in vs if v.symbol_exported),
                parse_failures=parse_failures,
            ),
            apply=apply,
        )
        runtime_alias_violations = self._detect_and_apply(
            py_files=py_files,
            detect_fn=lambda f: FlextInfraRuntimeAliasDetector.detect_file(
                self._detector_context(
                    file_path=f,
                    rope_project=rope_project,
                    parse_failures=parse_failures,
                    project_name=project_name,
                    project_root=project_root,
                ),
                policy=u.Infra.policy(f, rope_project=rope_project),
            ),
            rewrite_fn=lambda _vs: u.Infra.rewrite_runtime_alias_violations(
                py_files=py_files,
                gates=gates,
            ),
            apply=apply,
        )
        relocation_findings = self._relocate_rule_findings(
            project_root=project_root, py_files=py_files, apply=apply, gates=gates
        )
        compatibility_alias_violations = self._detect_and_apply(
            py_files=py_files,
            detect_fn=lambda f: FlextInfraCompatibilityAliasDetector.detect_file(
                self._detector_context(
                    file_path=f,
                    rope_project=rope_project,
                    parse_failures=parse_failures,
                ),
            ),
            rewrite_fn=lambda vs: u.Infra.rewrite_compatibility_alias_violations(
                violations=vs,
                parse_failures=parse_failures,
                gates=gates,
            ),
            apply=apply,
        )
        (compatibility_alias_violations, foreign_canonical_alias_violations) = (
            self._split_compatibility_alias_violations(
                compatibility_alias_violations,
                package_name=package_name,
            )
        )
        class_placement_violations = self._detect_and_apply(
            py_files=py_files,
            detect_fn=lambda f: FlextInfraClassPlacementDetector.detect_file(
                self._detector_context(
                    file_path=f,
                    rope_project=rope_project,
                    parse_failures=parse_failures,
                ),
            ),
            rewrite_fn=lambda vs: self._relocate_class_placements(
                vs, project_layout=project_layout, rope_project=rope_project
            ),
            apply=apply,
        )
        return m.Infra.ProjectEnforcementReport(
            project=project_name,
            project_root=str(project_root),
            facade_statuses=facade_statuses,
            loose_objects=list(loose_objects),
            import_violations=list(import_violations),
            namespace_source_violations=list(namespace_source_violations),
            internal_import_violations=list(internal_import_violations),
            private_import_bypass_violations=list(private_import_bypass_violations),
            cyclic_imports=list(cyclic_imports),
            runtime_alias_violations=list(runtime_alias_violations),
            relocation_findings=relocation_findings,
            compatibility_alias_violations=list(compatibility_alias_violations),
            foreign_canonical_alias_violations=list(foreign_canonical_alias_violations),
            class_placement_violations=list(class_placement_violations),
            parse_failures=list(parse_failures),
            files_scanned=len(py_files),
        )

    @staticmethod
    def _relocate_class_placements(
        violations: t.SequenceOf[m.Infra.ClassPlacementViolation],
        *,
        project_layout: m.Infra.RopeProjectLayout | None,
        rope_project: t.Infra.RopeProject,
    ) -> None:
        """Repair the class placements the detector marks as relocatable.

        A ClassVar constant outside ``_constants`` moves to the package's
        ``_constants`` module (ENFORCE-079); a fixable misplaced facade class
        moves to its family module. Any other action stays a reported finding.
        A failed relocation escapes with its cause.
        """
        relocatable = tuple(
            violation
            for violation in violations
            if violation.action in {"classvar_relocation", "relocate_facade_class"}
        )
        if not relocatable:
            return
        if project_layout is None:
            msg = "class placement relocation requires a resolved project layout"
            raise ValueError(msg)
        constants_module = f"{project_layout.package_name}._constants"
        for violation in sorted(
            relocatable, key=lambda item: (item.file, item.line), reverse=True
        ):
            source_file = Path(violation.file)
            if violation.action == "classvar_relocation":
                module_parts = source_file.relative_to(project_layout.src_dir).with_suffix(
                    ""
                ).parts
                if module_parts[-1] == "__init__":
                    module_parts = module_parts[:-1]
                FlextInfraRefactorClassvarConstantAutofix.apply(
                    repository_root=project_layout.project_root,
                    class_full_name=".".join((*module_parts, violation.base_class)),
                    constant_name=violation.name,
                    constants_module=constants_module,
                )
                continue
            if not (violation.fixable and violation.family):
                continue
            u.Infra.move_class(
                m.Infra.ClassMoveRequest(
                    rope_project=rope_project,
                    source_file=source_file,
                    target_file=u.Infra.class_target_file(
                        package_dir=project_layout.package_dir,
                        source_file=source_file,
                        class_name=violation.name,
                        family=violation.family,
                    ),
                    class_name=violation.name,
                    line=violation.line,
                    apply=True,
                )
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

        The rule catalog owns detection: a detection-only rule names the rope
        relocation that repairs it (``metadata.relocation``) and captures the
        relocated symbol as ``$NAME``. With ``apply`` the engine's relocations
        run once over the captured names and the catalog is scanned again; the
        returned count is what remains.
        """
        findings = self._relocation_findings(project_root, py_files)
        if not (apply and findings):
            return len(findings)
        names: MutableMapping[
            c.Infra.CodemodRelocation, MutableMapping[Path, set[str]]
        ] = defaultdict(lambda: defaultdict(set))
        spans: MutableMapping[Path, list[t.IntPair]] = defaultdict(list)
        for relocation, finding in findings:
            file_path = project_root / finding.file
            match relocation:
                case c.Infra.CodemodRelocation.MODULE_IMPORT:
                    spans[file_path].append(self._finding_lines(finding))
                case c.Infra.CodemodRelocation.FUTURE_ANNOTATIONS:
                    names[relocation].setdefault(file_path, set())
                case _:
                    names[relocation][file_path].add(self._captured_name(finding))
        for file_path, statement_lines in spans.items():
            u.Infra.hoist_inline_imports(file_path, statement_lines)
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
                        py_files=tuple(names_by_file)
                    )
        self._rope_project.validate(self._rope_project.root)
        return len(self._relocation_findings(project_root, py_files))

    @staticmethod
    def _relocation_findings(
        project_root: Path, py_files: t.SequenceOf[Path]
    ) -> t.VariadicTuple[t.Pair[c.Infra.CodemodRelocation, m.Infra.ModScanFinding]]:
        """Return the engine's relocation findings inside the enforcer's file scope.

        The scope is the project's namespace file set (its declared scan
        directories), so a relocation never reaches a file the namespace pass
        does not govern.
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
        """Return the 1-based inclusive line span of one finding."""
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
    def _captured_name(finding: m.Infra.ModScanFinding) -> str:
        """Return the ``$NAME`` metavariable a relocation rule captured."""
        metavariables = finding.payload["metaVariables"]
        if not isinstance(metavariables, Mapping):
            msg = f"ast-grep finding without metaVariables: {finding.rule_id}"
            raise TypeError(msg)
        single = metavariables["single"]
        if not isinstance(single, Mapping):
            msg = f"ast-grep finding without single captures: {finding.rule_id}"
            raise TypeError(msg)
        captured = single[c.Infra.CODEMOD_RULE_NAME_METAVARIABLE]
        if not isinstance(captured, Mapping):
            msg = f"relocation rule {finding.rule_id} did not capture $NAME"
            raise TypeError(msg)
        text = captured["text"]
        if not isinstance(text, str) or not text:
            msg = f"relocation rule {finding.rule_id} captured an empty $NAME"
            raise TypeError(msg)
        return text

    @staticmethod
    def _split_compatibility_alias_violations(
        violations: t.SequenceOf[m.Infra.CompatibilityAliasViolation],
        *,
        package_name: str,
    ) -> t.Pair[
        list[m.Infra.CompatibilityAliasViolation],
        list[m.Infra.CompatibilityAliasViolation],
    ]:
        """Split legacy compatibility aliases from foreign canonical imports."""
        compatibility_aliases: list[m.Infra.CompatibilityAliasViolation] = []
        foreign_canonical_aliases: list[m.Infra.CompatibilityAliasViolation] = []
        for violation in violations:
            action = FlextInfraCompatibilityAliasDetector.fix_action_for(
                violation,
                current_project=package_name,
            )
            if action == "rewrite_foreign_canonical_alias":
                foreign_canonical_aliases.append(violation)
                continue
            compatibility_aliases.append(violation)
        return compatibility_aliases, foreign_canonical_aliases


__all__: list[str] = ["FlextInfraNamespaceEnforcerProjectMixin"]
