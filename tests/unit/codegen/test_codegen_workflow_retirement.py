"""Public conformance preserves authored workflows and release capability."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m, u
from flext_infra.codegen import FlextInfraCodegenConform
from flext_infra.workspace import FlextInfraWorkspaceDetector
from tests import u as test_u

from .conform_support import TestsFlextInfraConformSupport

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenWorkflowRetirement:
    """Exercise scaffold and existing-tree conformance through the public facade."""

    @staticmethod
    def _declared_workspace(
        root: Path, *, publishes_release: bool
    ) -> m.Infra.WorkspaceSpec:
        """Declare release capability through the real repository manifest."""
        TestsFlextInfraConformSupport.seed_infra_package_tree(root)
        manifest_path = test_u.Tests.write_standalone_workspace_manifest(
            root, config.Infra.name
        )
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        manifest = m.Infra.WorkspaceManifestSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=workspace.name,
            repository=workspace.repository.model_copy(
                update={"publishes_release": publishes_release}
            ),
            project=workspace.project,
        )
        tm.ok(u.Cli.yaml_dump(manifest_path, manifest.model_dump(mode="json")))
        return tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))

    @pytest.mark.parametrize("declared_release", [False, True])
    @pytest.mark.parametrize("marker", [None, *c.Infra.TEMPLATE_GENERATED_MARKERS])
    def test_retirement_requires_both_exclusion_and_codegen_authorship(
        self, infra_git_repo: Path, *, declared_release: bool, marker: str | None
    ) -> None:
        """Effective target policy and current markers determine desired presence."""
        root = infra_git_repo
        workspace = self._declared_workspace(root, publishes_release=declared_release)
        target = tm.ok(FlextInfraWorkspaceDetector.conform_target(root, workspace))
        tm.that(target.publishes_release, eq=declared_release)
        codegen = config.Infra.codegen
        managed = {item.path.as_posix() for item in codegen.managed_files}
        workflows = tuple(
            entry
            for entry in codegen.templates.entries
            if entry.delegate == "render"
            and entry.destination in managed
            and Path(entry.destination).parts[:2] == (".github", "workflows")
        )
        content = "name: Repository workflow\non: workflow_dispatch\njobs: {}\n"
        if marker is not None:
            content = f"# {marker}\n{content}"
        for entry in workflows:
            workflow = root / entry.destination
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_text(content, encoding=c.Cli.ENCODING_DEFAULT)

        request = test_u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        plan = tm.ok(FlextInfraCodegenConform(repository_root=root).plan(request))

        workflow_paths = {root / entry.destination for entry in workflows}
        retired = {
            file.path
            for file in plan.files
            if file.path in workflow_paths and file.desired_content is None
        }
        expected = {
            root / entry.destination
            for entry in workflows
            if marker is not None
            and (
                target.make_profile not in entry.profiles
                or (entry.requires_release_protocol and not target.publishes_release)
            )
        }
        tm.that(retired, eq=expected)
        for path in workflow_paths:
            tm.that(path.read_text(encoding=c.Cli.ENCODING_DEFAULT), eq=content)

    @pytest.mark.parametrize("declared_release", [False, True])
    def test_release_workflows_converge_from_scaffold_to_existing_repository(
        self, infra_git_repo: Path, *, declared_release: bool
    ) -> None:
        """Both public apply routes preserve the declared release capability."""
        root = infra_git_repo
        workspace = self._declared_workspace(root, publishes_release=declared_release)
        request = test_u.Tests.conform_request(
            root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.APPLY,
        )
        tm.ok(FlextInfraCodegenConform.execute_request(request, workspace))
        target = tm.ok(FlextInfraWorkspaceDetector.conform_target(root))
        tm.that(target.publishes_release, eq=declared_release)
        releases = tuple(
            entry
            for entry in config.Infra.codegen.templates.entries
            if entry.delegate == "render"
            and entry.requires_release_protocol
            and Path(entry.destination).parts[:2] == (".github", "workflows")
        )
        for entry in releases:
            tm.that(
                (root / entry.destination).is_file(),
                eq=declared_release and target.make_profile in entry.profiles,
            )
        scaffold_content = {
            root / entry.destination: (root / entry.destination).read_bytes()
            for entry in releases
            if (root / entry.destination).is_file()
        }

        conformed = tm.ok(FlextInfraCodegenConform.execute_request(request))

        release_paths = {root / entry.destination for entry in releases}
        tm.that(release_paths.intersection(conformed.written_files), empty=True)
        for path in release_paths:
            if path in scaffold_content:
                tm.that(path.read_bytes(), eq=scaffold_content[path])
            else:
                tm.that(path.exists(), eq=False)
