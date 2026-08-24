"""Artifact projections validated against the typed production SSOT."""

from __future__ import annotations

from pathlib import Path

import pytest

from flext_infra import c, config, t, u
from flext_infra.services.codegen import FlextInfraCodegen
from flext_tests import tm

CodegenSpec = type(config.Infra.codegen)


@pytest.fixture(scope="module")
def codegen() -> CodegenSpec:
    """Return the production configuration consumed by every projection."""
    return config.Infra.codegen


class TestsCodegenArtifactSsot:
    """Property contracts that remain valid for arbitrary configured artifacts."""

    def test_artifact_names_are_unique(self, codegen: CodegenSpec) -> None:
        """Reject ambiguous projection keys at the typed owner."""
        names = tuple(artifact.name for artifact in codegen.artifacts)
        tm.that(bool(names), eq=True)
        tm.that(len(names), eq=len(set(names)))
        tm.that(all(names), eq=True)

    def test_vscode_maps_are_exact_projections(self, codegen: CodegenSpec) -> None:
        """Derive every expected mapping from the same typed artifact records."""
        expected_files = {
            f"**/{artifact.name}": True
            for artifact in codegen.artifacts
            if artifact.vscode_exclude
        }
        expected_watchers = {
            f"**/{artifact.name}/**": True
            for artifact in codegen.artifacts
            if artifact.watch_exclude
        }
        tm.that(dict(codegen.vscode_files_exclude_map), eq=expected_files)
        tm.that(dict(codegen.vscode_search_exclude_map), eq=expected_files)
        tm.that(dict(codegen.vscode_watcher_exclude_map), eq=expected_watchers)

    def test_source_scan_is_exact_projection(self, codegen: CodegenSpec) -> None:
        """Derive ignored source names from their owner flags."""
        expected = tuple(
            artifact.name
            for artifact in codegen.artifacts
            if artifact.source_scan_ignore
        )
        tm.that(codegen.source_scan_ignored, eq=expected)
        tm.that(len(expected), eq=len(set(expected)))

    def test_gitignore_artifacts_are_exact_projection(
        self, codegen: CodegenSpec
    ) -> None:
        """Preserve configured order while rendering directory suffixes."""
        expected = tuple(
            f"{artifact.name}/" if artifact.is_dir else artifact.name
            for artifact in codegen.artifacts
            if artifact.gitignore
        )
        tm.that(codegen.gitignore_artifact_patterns, eq=expected)
        tm.that(len(expected), eq=len(set(expected)))

    def test_gitignore_sections_account_for_every_artifact(
        self, codegen: CodegenSpec
    ) -> None:
        """Require every derived pattern to be governed or appended."""
        emitted = {
            pattern
            for section in codegen.gitignore_sections
            for pattern in section.patterns
        }
        governed = {
            pattern.lstrip("!")
            for section in codegen.scaffold.gitignore_sections
            for pattern in section.patterns
        }
        unaccounted = tuple(
            pattern
            for pattern in codegen.gitignore_artifact_patterns
            if pattern not in emitted and pattern not in governed
        )
        tm.that(unaccounted, eq=())

    def test_makefile_has_one_owner_for_every_declared_profile(
        self, codegen: CodegenSpec
    ) -> None:
        """Cover repository profiles through one generic template entry."""
        entries = tuple(
            entry
            for entry in codegen.templates.entries
            if entry.destination == c.Infra.MAKEFILE_FILENAME
        )
        tm.that(entries, len=1)
        declared_profiles = {
            c.Infra.MakeProfile.WORKSPACE_ROOT,
            c.Infra.MakeProfile.STANDALONE,
        }
        tm.that(set(entries[0].profiles), eq=declared_profiles)

    def test_hook_workflow_contexts_partition_mutation_and_validation(
        self, codegen: CodegenSpec
    ) -> None:
        """Pre-push runs every commit-stage verb plus the deferred full gates."""
        workflow = codegen.make.workflow
        pre_commit = tuple(step for step in workflow if "pre_commit" in step.contexts)
        pre_push = tuple(step for step in workflow if "pre_push" in step.contexts)

        tm.that(bool(pre_commit), eq=True)
        tm.that(bool(pre_push), eq=True)
        commit_verbs = {step.verb for step in pre_commit}
        push_verbs = {step.verb for step in pre_push}
        tm.that(commit_verbs.issubset(push_verbs), eq=True)
        tm.that(bool(push_verbs - commit_verbs), eq=True)
        tm.that(
            push_verbs.issubset({verb.name for verb in codegen.make.verbs}), eq=True
        )

    def test_rendered_vscode_document_consumes_projection_maps(
        self, tmp_path: Path, codegen: CodegenSpec
    ) -> None:
        """Validate the public renderer output instead of private implementation."""
        rendered = tm.ok(FlextInfraCodegen.render_vscode_settings(tmp_path))
        parsed = tm.ok(u.Cli.json_parse(rendered))
        settings = t.Cli.JSON_MAPPING_ADAPTER.validate_python(parsed)
        tm.that(settings["files.exclude"], eq=dict(codegen.vscode_files_exclude_map))
        tm.that(settings["search.exclude"], eq=dict(codegen.vscode_search_exclude_map))
        tm.that(
            settings["files.watcherExclude"],
            eq=dict(codegen.vscode_watcher_exclude_map),
        )
