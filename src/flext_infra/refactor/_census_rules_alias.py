"""Census alias rule scanners (runtime + manual typing) — extracted concern."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, m
from flext_infra.detectors.manual_typing_alias_detector import (
    FlextInfraManualTypingAliasDetector,
)
from flext_infra.detectors.runtime_alias_detector import FlextInfraRuntimeAliasDetector

from ._census_rules_shared import FlextInfraRefactorCensusRulesSharedMixin

if TYPE_CHECKING:
    from pathlib import Path

    from flext_infra import p, t


class FlextInfraRefactorCensusRulesAliasMixin(FlextInfraRefactorCensusRulesSharedMixin):
    """Runtime-alias + manual-typing-alias rule scanners for one module.

    Composed into FlextInfraRefactorCensus via inheritance; borrows the
    detector-context + violation/fix builders from sibling mixins via FLEXT.
    """

    if TYPE_CHECKING:

        @staticmethod
        def _runtime_alias_target(
            convention: m.Infra.RopeModuleConvention,
            objects: t.VariadicTuple[m.Infra.Object] | None,
        ) -> m.Infra.Object | None: ...
        @staticmethod
        def _runtime_alias_target_name(
            convention: m.Infra.RopeModuleConvention,
        ) -> str: ...

    def _rule_runtime_alias(
        self,
        rope: p.Infra.RopeWorkspaceDsl,
        file_path: Path,
        *,
        project_name: str,
        objects: t.VariadicTuple[m.Infra.Object] | None,
        applied: frozenset[str],
        selected_kinds: frozenset[str],
        symbol_index: t.MappingKV[str, t.Pair[str, int]],
        convention: m.Infra.RopeModuleConvention,
    ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]:
        """Detect + plan fixes for runtime-alias re-export violations."""
        ctx = self._detector_context(rope, file_path, convention=convention)
        violations: list[m.Infra.Violation] = []
        fixes: list[m.Infra.Fix] = []
        runtime_target = (
            self._runtime_alias_target(convention, objects)
            if objects is not None
            else None
        )
        runtime_target_name = ""
        runtime_target_kind = "assignment"
        runtime_target_line = 0
        if runtime_target is not None:
            runtime_target_name = runtime_target.name
            runtime_target_kind = runtime_target.kind
            runtime_target_line = runtime_target.line
        else:
            expected_name = self._runtime_alias_target_name(convention)
            expected_symbol = symbol_index.get(expected_name)
            if expected_symbol is not None:
                runtime_target_name = expected_name
                runtime_target_kind, runtime_target_line = expected_symbol
        fixable = runtime_target is not None or runtime_target_kind == "class"
        for detector_violation in FlextInfraRuntimeAliasDetector.detect_file(
            ctx, policy=convention.module_policy
        ):
            if detector_violation.kind == "unbound":
                # A published letter nothing binds is repaired by un-publishing
                # it: binding the family class here would infer the alias from
                # the module's file family, never from the module itself.
                violations.append(
                    self._raw_violation(
                        project=project_name,
                        object_name=detector_violation.alias,
                        object_kind="assignment",
                        kind="runtime_alias",
                        file_path=file_path,
                        line=detector_violation.line,
                        description=detector_violation.detail,
                        fixable=True,
                        fix_action="remove_stale_runtime_alias_export",
                    )
                )
                fixes.append(
                    m.Infra.Fix(
                        object_name=detector_violation.alias,
                        action="remove_stale_runtime_alias_export",
                        source_file=str(file_path),
                        files_changed=1,
                        applied=self._fix_key(
                            file_path,
                            detector_violation.alias,
                            "remove_stale_runtime_alias_export",
                        )
                        in applied,
                    )
                )
                continue
            object_name = runtime_target_name if fixable else detector_violation.alias
            object_kind = runtime_target_kind if fixable else "assignment"
            if selected_kinds and object_kind not in selected_kinds:
                continue
            line = detector_violation.line or (runtime_target_line if fixable else 0)
            action = "rewrite_runtime_alias" if fixable else ""
            violations.append(
                self._raw_violation(
                    project=project_name,
                    object_name=object_name,
                    object_kind=object_kind,
                    kind="runtime_alias",
                    file_path=file_path,
                    line=line,
                    description=detector_violation.detail,
                    fixable=fixable,
                    fix_action=action,
                )
            )
            if fixable:
                fixes.append(
                    m.Infra.Fix(
                        object_name=object_name,
                        action=action,
                        source_file=str(file_path),
                        files_changed=1,
                        applied=self._fix_key(file_path, object_name, action)
                        in applied,
                    )
                )
        return violations, fixes

    def _rule_manual_typing_alias(
        self,
        rope: p.Infra.RopeWorkspaceDsl,
        file_path: Path,
        *,
        project_name: str,
        objects: t.VariadicTuple[m.Infra.Object] | None,
        applied: frozenset[str],
        selected_kinds: frozenset[str],
        convention: m.Infra.RopeModuleConvention,
    ) -> t.Pair[list[m.Infra.Violation], list[m.Infra.Fix]]:
        """Detect + plan fixes for manual typing-alias violations."""
        manual_ctx = self._detector_context(rope, file_path, convention=convention)
        violations: list[m.Infra.Violation] = []
        fixes: list[m.Infra.Fix] = []
        for detector_violation in FlextInfraManualTypingAliasDetector.detect_file(
            manual_ctx
        ):
            matched = (
                self._named_object(objects, detector_violation.name)
                if objects is not None
                else None
            )
            object_kind = matched.kind if matched is not None else "assignment"
            if selected_kinds and object_kind not in selected_kinds:
                continue
            action = (
                "rewrite_manual_typing_alias"
                if manual_ctx.project_root is not None
                else ""
            )
            violations.append(
                self._raw_violation(
                    project=project_name,
                    object_name=detector_violation.name,
                    object_kind=object_kind,
                    kind="manual_typing_alias",
                    file_path=file_path,
                    line=detector_violation.line,
                    description=detector_violation.detail,
                    fixable=bool(action),
                    fix_action=action,
                )
            )
            if action:
                fixes.append(
                    m.Infra.Fix(
                        object_name=detector_violation.name,
                        action=action,
                        source_file=str(file_path),
                        target_file=str(convention.package_dir / c.Infra.TYPINGS_PY),
                        files_changed=2,
                        applied=self._fix_key(
                            file_path, detector_violation.name, action
                        )
                        in applied,
                    )
                )
        return violations, fixes


__all__: list[str] = ["FlextInfraRefactorCensusRulesAliasMixin"]
