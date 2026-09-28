"""Source-specific enforcement violation collectors."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, u

from .collection_base import FlextInfraEnforcementCollectionBase
from .metadata import FlextInfraEnforcementMetadata
from .selection import FlextInfraEnforcementSelection

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraEnforcementSourceCollectors(
    FlextInfraEnforcementMetadata,
    FlextInfraEnforcementSelection,
    FlextInfraEnforcementCollectionBase,
):
    """Collect enforcement probes for supported catalog source kinds."""

    def __init__(self, repository_root: Path) -> None:
        """Bind the repository root used for project discovery and Rope sessions."""
        self._repository_root = repository_root

    def collect_project(
        self, project_dir: Path, rules: t.SequenceOf[m.EnforcementRuleSpec]
    ) -> m.Infra.EnforcementEvaluation:
        """Collect rule probes for one project using one shared dispatcher.

        Tests-tier source kinds (``flext_tests_validator``) never reach this
        dispatcher: selection excludes them because their execution owner is
        the flext-tests pytest dispatcher and flext-infra never imports
        ``flext_tests`` at runtime.
        """
        violations: list[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]] = []
        failures: list[m.Infra.FailedFix] = []
        declarative_rules: list[m.EnforcementRuleSpec] = []
        for rule in rules:
            source = rule.source
            if self.supports_declarative(rule):
                declarative_rules.append(rule)
                continue
            if source.kind in {"flext_infra_detector", "beartype"}:
                collected, errors = self.collect_python_file_probes(project_dir, rule)
            elif source.kind in {"ruff", "code_smell"}:
                violations.extend(self.collect_project_probe(project_dir, rule))
                continue
            else:
                failures.append(
                    self.collection_failure(
                        project_dir,
                        rule,
                        f"unsupported enforcement source kind {source.kind!r}",
                    )
                )
                continue
            violations.extend(collected)
            failures.extend(errors)
        if declarative_rules:
            collected, errors = self.collect_declarative(project_dir, declarative_rules)
            violations.extend(collected)
            failures.extend(errors)
        return m.Infra.EnforcementEvaluation(
            violations=tuple(violations), failures=tuple(failures)
        )

    def collect_python_file_probes(
        self, project_dir: Path, rule: m.EnforcementRuleSpec
    ) -> t.Pair[
        list[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]], list[m.Infra.FailedFix]
    ]:
        """Return one structural probe per Python file for file-wide transformers."""
        files_result = u.Infra.iter_python_files(
            m.Infra.SourceScanRequest(project_roots=(project_dir,))
        )
        if files_result.failure:
            return self._empty_failure(
                project_dir,
                rule,
                files_result.error or "unable to enumerate Python files",
            )
        return ([(rule, self.probe_for_path(path)) for path in files_result.value], [])

    def collect_declarative(
        self, project_dir: Path, rules: t.SequenceOf[m.EnforcementRuleSpec]
    ) -> t.Pair[
        list[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]], list[m.Infra.FailedFix]
    ]:
        """Run catalog-driven declarative rules across one project."""
        files, errors = self.collect_python_file_probes(project_dir, rules[0])
        if errors:
            return [], errors
        file_paths: list[Path] = []
        for _rule, probe in files:
            # Probe payloads are untrusted at this boundary (AttributeProbe is
            # a deliberately empty structural marker): a probe without a
            # usable file_path is a collection failure, never Path("")
            # silently resolving to the project root.
            path_value = getattr(probe, "file_path", None)
            if not isinstance(path_value, str) or not path_value:
                return [], [
                    self.collection_failure(
                        project_dir, rules[0], "probe payload missing file_path"
                    )
                ]
            file_paths.append(Path(path_value))
        if any(self.rule_requires_stub_file(rule) for rule in rules):
            file_paths.extend(self.stub_file_paths(project_dir))
        probes: list[t.Pair[m.EnforcementRuleSpec, p.AttributeProbe]] = []
        failures: list[m.Infra.FailedFix] = []
        with u.Infra.open_project(self._repository_root) as rope_project:
            for file_path in file_paths:
                ctx = m.Infra.DetectorContext(
                    file_path=file_path,
                    rope_project=rope_project,
                    project_name=project_dir.name,
                    project_root=project_dir,
                )
                for rule in rules:
                    try:
                        detected = self.detect_declarative(rule, ctx)
                    except c.EXC_BROAD_RUNTIME as exc:
                        failures.append(
                            self.collection_failure(
                                project_dir, rule, f"declarative engine failed: {exc}"
                            )
                        )
                        continue
                    probes.extend((rule, probe) for probe in detected)
        return probes, failures


__all__: list[str] = ["FlextInfraEnforcementSourceCollectors"]
