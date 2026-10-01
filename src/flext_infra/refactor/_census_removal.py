"""Census removal of unreferenced objects: dry-run preview and apply."""

from __future__ import annotations

from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import m, u
from flext_infra.codegen.lazy_init import FlextInfraCodegenLazyInit

from ._census_apply_formatting import FlextInfraRefactorCensusApplyFormattingMixin

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraRefactorCensusRemovalMixin(
    FlextInfraRefactorCensusApplyFormattingMixin
):
    """Preview and apply the inventory's removal candidates through gates.

    Removal of unreferenced objects is the census's own effect: it acts on
    what the workspace object inventory proved unused, which no code-shape
    rule can see.
    """

    if TYPE_CHECKING:
        dry_run: bool

        @property
        def fail_fast(self) -> bool: ...

        @property
        def root(self) -> Path: ...

        @property
        def dry_run_gate_names(self) -> t.StrSequence: ...

    def _validated_project_reports(
        self,
        rope: p.Infra.RopeWorkspaceDsl,
        project_reports: t.VariadicTuple[m.Infra.ProjectReport],
    ) -> t.VariadicTuple[m.Infra.ProjectReport]:
        """Keep only removal candidates that pass the configured dry-run gates.

        A gate rejection is reported as a ``preview_rejected`` finding of the
        project; with ``fail_fast`` it stops the census instead.
        """
        validated_reports: list[m.Infra.ProjectReport] = []
        # Preview writes are restored before the next candidate, so one shared
        # source cache stays valid for the entire dry-run validation pass.
        source_cache: MutableMapping[Path, str] = {}
        for report in project_reports:
            if not report.removal_candidates:
                validated_reports.append(report)
                continue
            validated_candidates: list[m.Infra.RemovalCandidate] = []
            validated_violations = list(report.violations)
            for candidate in report.removal_candidates:
                preview_result = u.Infra.preview_simple_removal_candidate(
                    rope,
                    self.root,
                    candidate,
                    gates=self.dry_run_gate_names,
                    source_cache=source_cache,
                )
                if preview_result.failure:
                    msg = (
                        f"removal preview rejected {candidate.file_path}:"
                        f"{candidate.line} {candidate.object_name}: "
                        f"{preview_result.error}"
                    )
                    if self.fail_fast:
                        raise RuntimeError(msg)
                    validated_violations.append(
                        m.Infra.Violation(
                            project=report.project,
                            object_name=candidate.object_name,
                            object_kind=candidate.object_kind,
                            kind="preview_rejected",
                            file_path=candidate.file_path,
                            line=candidate.line,
                            description=msg,
                        ),
                    )
                    continue
                if preview_result.unwrap():
                    validated_candidates.append(candidate)
            validated_reports.append(
                report.model_copy(
                    update={
                        "violations": tuple(validated_violations),
                        "violations_total": len(validated_violations),
                        "removal_candidate_count": len(validated_candidates),
                        "removal_candidates": tuple(validated_candidates),
                    }
                )
            )
        return tuple(validated_reports)

    def _apply_removal_candidates(
        self, rope: p.Infra.RopeWorkspaceDsl, report: m.Infra.WorkspaceReport
    ) -> bool:
        """Remove every candidate through its gates; a failed removal escapes.

        Returns whether any file changed. The touched files are normalized and
        the lazy initializers are re-planned before the Rope session reloads.
        """
        touched_paths: set[Path] = set()
        for candidate in report.removal_candidates:
            apply_result = u.Infra.apply_simple_removal_candidate(
                rope, self.root, candidate, gates=self.dry_run_gate_names
            )
            if apply_result.failure:
                msg = (
                    f"removal apply failed for {candidate.file_path}:"
                    f"{candidate.line} {candidate.object_name}: {apply_result.error}"
                )
                raise RuntimeError(msg)
            if apply_result.unwrap():
                touched_paths.add(Path(candidate.file_path).resolve())
                touched_paths.update(
                    Path(site.file_path).resolve()
                    for site in candidate.script_reference_sites
                )
        if not touched_paths:
            return False
        self.normalize_touched_files(touched_paths)
        FlextInfraCodegenLazyInit(repository_root=self.root).plan_files().unwrap()
        rope.reload()
        return True


__all__: list[str] = ["FlextInfraRefactorCensusRemovalMixin"]
