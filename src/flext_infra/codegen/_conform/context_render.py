"""Typed Make and project render context projection.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from flext_infra import c, config, m, p, r, t, u
from flext_infra.codegen._conform.pyproject_policy import (
    FlextInfraCodegenConformPyprojectPolicy,
)
from flext_infra.deps import FlextInfraEnsurePackagingPhase


class FlextInfraCodegenConformContextRender(FlextInfraCodegenConformPyprojectPolicy):
    """Typed Make and project render context projection."""

    @staticmethod
    def resolve_render_inputs(
        *,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
        managed_artifacts: m.Infra.ProjectManagedArtifactsSnapshot,
    ) -> m.Infra.CodegenRenderInputs:
        """Resolve every input shared by one repository's renders exactly once.

        The integration branch probes the manifest and, undeclared, the
        published Git line; the project context and every workflow template
        read this one resolution instead of repeating the probe per render.
        An unresolved branch stays absent here: only a render that consumes it
        fails, through ``render_integration_branch``, exactly as before.

        Returns:
            The resulting ``m.Infra.CodegenRenderInputs``.

        """
        branch = FlextInfraCodegenConformContextRender._resolve_integration_branch(
            target=target,
            workspace=workspace,
            codegen=codegen,
        )
        return m.Infra.CodegenRenderInputs(
            target=target,
            workspace=workspace,
            codegen=codegen,
            tooling_runtime=tooling_runtime,
            managed_artifacts=managed_artifacts,
            integration_branch=branch.value if branch.success else None,
        )

    @staticmethod
    def render_integration_branch(
        render_inputs: m.Infra.CodegenRenderInputs,
    ) -> p.Result[str]:
        """Return the plan's integration branch, or the resolver's own failure.

        Returns:
            The plan's integration branch, or the resolver's own failure.

        """
        if render_inputs.integration_branch is not None:
            return r[str].ok(render_inputs.integration_branch)
        return FlextInfraCodegenConformContextRender._resolve_integration_branch(
            target=render_inputs.target,
            workspace=render_inputs.workspace,
            codegen=render_inputs.codegen,
        )

    @staticmethod
    def _resolve_integration_branch(
        *,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
    ) -> p.Result[str]:
        """Resolve the repository's integration branch from its declarations.

        The repository's declaration wins; otherwise the published baseline.
        A checkout's HEAD is never consulted (ADR-018 p.10).

        Returns:
            The resulting ``p.Result[str]``.

        """
        return u.Infra.resolve_integration_branch(
            target.root,
            preference=codegen.branch_policy.integration_branch_preference,
            declared=(
                workspace.integration.branch
                if workspace.integration is not None
                else None
            ),
        )

    def make_render_context(
        self,
        render_inputs: m.Infra.CodegenRenderInputs,
    ) -> p.Result[m.Infra.MakeRenderContext]:
        """Build the typed context consumed by the generated Makefile.

        Returns:
            The resulting ``p.Result[m.Infra.MakeRenderContext]``.

        """
        target = render_inputs.target
        workspace = render_inputs.workspace
        codegen = render_inputs.codegen
        repository = target.repository
        repository_root = target.root
        profile = target.make_profile
        subprojects = (
            tuple(workspace.subprojects)
            if profile is c.Infra.MakeProfile.WORKSPACE
            else ()
        )
        gitlinks = self._managed_gitlinks(
            workspace,
            codegen,
            repository_root=repository_root,
        )
        if gitlinks.failure:
            return r[m.Infra.MakeRenderContext].from_failure(gitlinks)
        extra_verbs = self._merge_extra_verbs(
            repository.extra_verbs,
            (
                ()
                if repository.script_dispatch is None
                else self._discover_script_verbs(repository_root)
            ),
            frozenset(verb.name for verb in codegen.make.verbs),
        )
        return r[m.Infra.MakeRenderContext].ok(
            m.Infra.MakeRenderContext(
                pytest=config.Infra.tooling.tools.pytest,
                mise_bootstrap=u.Infra.mise_bootstrap_environment(),
                make=codegen.make,
                mypy_timeout_exit_code=c.Infra.PROCESS_TIMEOUT_EXIT_CODE,
                timeout_command=c.Infra.TIMEOUT_COMMAND,
                timeout_kill_after_seconds=c.Infra.TIMEOUT_KILL_AFTER_SECONDS,
                tooling_runtime=render_inputs.tooling_runtime,
                dist=repository.distribution,
                infra_cli=config.Infra.name,
                python_version=codegen.toolchain.python_version,
                worktree_environment_directory=(
                    codegen.toolchain.worktree_environment_directory
                ),
                uv_link_mode=self.link_mode(repository, codegen.toolchain),
                # ProjectRenderContext replaces this with the composed map.
                # Pass the neutral value explicitly so Pydantic never deep-copies
                # the MappingProxyType model default while building the base.
                ruff_per_file_ignores={},
                make_profile=profile,
                workspace_cli_group=c.Infra.CLI_GROUP_WORKSPACE,
                repository_root_rel=self._repository_root_rel(workspace),
                makefile_custom_include=c.Infra.MAKEFILE_CUSTOM_INCLUDE,
                workspace_subprojects=tuple(
                    item.path.as_posix() for item in workspace.subprojects
                ),
                workspace_repositories=subprojects,
                workspace_gitlinks=gitlinks.value,
                extra_verbs=extra_verbs,
                script_dispatch=repository.script_dispatch,
            ),
        )

    @staticmethod
    def _project_spec_from_existing(
        repository: m.Infra.RepositoryRef,
        repository_root: Path,
        codegen: m.Infra.CodegenConfigSpec,
    ) -> p.Result[m.Infra.ProjectSpec]:
        """Derive scaffold ProjectSpec from live PEP 621 metadata for existing trees.

        Returns:
            The resulting ``p.Result[m.Infra.ProjectSpec]``.

        """
        metadata = u.Infra.read_project_metadata_result(repository_root)
        if metadata.failure:
            return r[m.Infra.ProjectSpec].from_failure(metadata)
        pep621 = metadata.value.project
        package_name = metadata.value.package_name
        class_stem = metadata.value.class_stem
        alias = u.Infra.package_alias(package_name=package_name)
        namespace = class_stem.removeprefix("Flext") or class_stem
        author = pep621.authors[0] if pep621.authors else None
        author_name = author.name if author is not None and author.name else ""
        author_email = author.email if author is not None and author.email else ""
        if not author_name or not author_email:
            return r[m.Infra.ProjectSpec].fail(
                f"existing pyproject is missing author name/email: {repository_root}",
            )
        homepage = pep621.urls.homepage or repository.url.removesuffix(".git")
        documentation = pep621.urls.documentation or homepage
        runtime_names = {
            name for item in pep621.dependencies if (name := u.Infra.dep_name(item))
        }
        direct = u.Infra.dependency_profile_upstreams(
            codegen.scaffold.project.dependency_profiles,
            distribution=repository.distribution,
            runtime_names=runtime_names,
        )
        if len(direct) != 1:
            return r[m.Infra.ProjectSpec].fail(
                "scaffold.project.dependency_profiles.upstream must match live "
                f"dependencies exactly once at {repository_root}: {tuple(direct)}",
            )
        upstream = direct[0]
        licenses = codegen.scaffold.project.supported_licenses
        return r[m.Infra.ProjectSpec].ok(
            m.Infra.ProjectSpec(
                package_name=package_name,
                class_stem=class_stem,
                namespace=namespace,
                constant_name=repository.distribution,
                namespace_attribute=alias,
                alias=alias,
                environment_prefix=f"{package_name.upper()}_",
                description=pep621.description or repository.distribution,
                license=licenses[0],
                author_name=author_name,
                author_email=author_email,
                upstream=upstream,
                homepage=homepage,
                documentation=documentation,
                repository_root_rel=".",
                year=codegen.scaffold.project.copyright_year,
                cli_module=(
                    repository_root
                    / c.Infra.DEFAULT_SRC_DIR
                    / package_name
                    / c.Infra.CODEGEN_CLI_MODULE_FILENAME
                ).is_file(),
            ),
        )

    def _project_render_context(
        self,
        render_inputs: m.Infra.CodegenRenderInputs,
        *,
        planned_data_files: t.StrSequence = (),
    ) -> p.Result[m.Infra.ProjectRenderContext]:
        """Build the complete typed context consumed by project templates.

        Returns:
            The resulting ``p.Result[m.Infra.ProjectRenderContext]``.

        """
        target = render_inputs.target
        workspace = render_inputs.workspace
        codegen = render_inputs.codegen
        repository = target.repository
        repository_root = target.root
        if workspace.project is None:
            # Existing checkouts declare no scaffold metadata: derive the render
            # identity from the live project metadata instead of failing, so
            # conforming a governed repository never depends on scaffold-only
            # declarations.
            derived = self._project_spec_from_existing(
                repository,
                repository_root,
                codegen,
            )
            if derived.failure:
                return r[m.Infra.ProjectRenderContext].from_failure(derived)
            project = derived.value
        else:
            project = workspace.project
        if workspace.namespace_scan_dirs and not project.namespace_scan_dirs:
            # The manifest-level declaration is the repository's production scope
            # for the namespace validator, so a
            # checkout that derives its project metadata declares it once at the
            # workspace root instead of freezing a full scaffold spec. An
            # explicit project-level declaration stays the more specific owner.
            project = project.model_copy(
                update={"namespace_scan_dirs": workspace.namespace_scan_dirs},
            )
        dependency_profile = u.Infra.composed_dependency_profile(
            codegen.scaffold.project.dependency_profiles,
            upstream=project.upstream,
            distribution=repository.distribution,
        )
        if dependency_profile is None:
            return r[m.Infra.ProjectRenderContext].fail(
                f"unsupported scaffold upstream: {project.upstream}",
            )
        if project.license not in codegen.scaffold.project.supported_licenses:
            supported = ", ".join(codegen.scaffold.project.supported_licenses)
            return r[m.Infra.ProjectRenderContext].fail(
                f"unsupported scaffold license: {project.license}; "
                f"supported licenses: {supported}",
            )
        profile = target.make_profile
        make_context = self.make_render_context(render_inputs)
        if make_context.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(make_context)
        repository_provider = u.Infra.repository_provider(repository)
        if repository_provider.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(repository_provider)
        integration_branch = self.render_integration_branch(render_inputs)
        if integration_branch.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(integration_branch)
        # Internal flext-* floors render from the FLEXT line the checkout
        # consumes (the infrastructure dependency's own source), never from
        # the consumer's organization or branch: a repository in another org
        # otherwise renders a mixed family and uv rejects conflicting URLs.
        flext_line = u.Infra.flext_integration_line_for_checkout(
            codegen=codegen,
            repository_root=repository_root,
            workspace=workspace,
        )
        if flext_line.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(flext_line)
        flext_git_base_url = flext_line.value.base_url
        if flext_git_base_url is None:
            return r[m.Infra.ProjectRenderContext].fail(
                "detected FLEXT line carries no provider base URL",
            )
        packaged_data_paths = (
            FlextInfraEnsurePackagingPhase.resolve_data_paths(
                repository_root,
                project.package_name,
                project.packaged_data_paths,
                planned_data_files,
            )
            if profile is not c.Infra.MakeProfile.WORKSPACE
            else m.Infra.PackagedDataSelection()
        )
        # The planner resolved the catalog once per repository: the committed
        # HEAD catalog for an existing tree, the empty one for a scaffold.
        catalog_artifacts = render_inputs.managed_artifacts.resolution
        project_patterns: t.StrSequence = catalog_artifacts.artifacts.Gitignore.patterns
        # The repository's own pyproject.toml is the version SSOT; the release
        # protocol is its only writer, so conform reads it and never syncs it.
        # A tree that has no pyproject yet is being created: it starts at the
        # typed initial version and the protocol owns every change after that.
        version_result = (
            u.Infra.current_workspace_version(repository_root)
            if (repository_root / c.PYPROJECT_FILENAME).is_file()
            else r[str].ok(config.Infra.initial_project_version)
        )
        if version_result.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(version_result)
        return r[m.Infra.ProjectRenderContext].ok(
            m.Infra.ProjectRenderContext(
                docs_audit=workspace.docs_audit,
                **make_context.value.model_dump(
                    by_alias=True,
                    exclude={"mise_bootstrap", "ruff_per_file_ignores"},
                    exclude_computed_fields=True,
                ),
                mise_bootstrap=u.Infra.mise_bootstrap_environment(),
                scaffold=codegen.scaffold,
                gitignore_sections=u.Infra.gitignore_sections(
                    codegen,
                    profile=profile,
                    # The declared distribution is the project identity: a
                    # scaffold renders before its pyproject exists, so the
                    # render never reads it back from disk.
                    project_name=repository.distribution,
                    workspace=workspace,
                    project_patterns=project_patterns,
                ),
                dependency_profile=dependency_profile,
                tooling=config.Infra.tooling,
                # The in-place pyproject edit and this render read the same
                # fleet exemption map, unchanged for every project.
                ruff_per_file_ignores=(
                    config.Infra.tooling.tools.ruff.lint.per_file_ignores
                ),
                environment_path_prepends=(codegen.toolchain.environment_path_prepends),
                beads=workspace.beads,
                canonical_project_name=target.canonical_project_name,
                const_name=project.constant_name,
                package_name=project.package_name,
                packaged_data_paths=(
                    *packaged_data_paths.files,
                    *packaged_data_paths.directories,
                ),
                packaged_data_files=packaged_data_paths.files,
                packaged_data_excludes=(
                    FlextInfraEnsurePackagingPhase.resolve_data_excludes(
                        repository_root,
                        packaged_data_paths,
                        project.packaged_data_excludes,
                    )
                    if profile is not c.Infra.MakeProfile.WORKSPACE
                    else ()
                ),
                namespace_scan_dirs=project.namespace_scan_dirs,
                workspace_integration=workspace.integration,
                # Carry only the validated
                # project declaration; conform owns no inferred Hatch hook.
                hatch_build_hook_path=project.hatch_build_hook_path,
                class_stem=project.class_stem,
                ns=project.namespace,
                ns_attr=project.namespace_attribute,
                alias=project.alias,
                env_prefix=project.environment_prefix,
                upstream=project.upstream,
                # Scaffolded facades extend the class each upstream letter names
                # in the __all__ that declares it, never the letter itself.
                upstream_facades=u.Infra.facade_classes(project.upstream),
                inherited_facets=project.inherited_facets,
                root_packages=project.root_packages,
                repository_namespace_packages=project.repository_namespace_packages,
                root_modules=project.root_modules,
                cli_module=project.cli_module,
                runtime_dependency_overlay=project.runtime_dependency_overlay,
                description=project.description,
                version=version_result.value,
                license=project.license,
                python_required_version=codegen.toolchain.python_required_version,
                dependency_cooldown_days=codegen.toolchain.dependency_cooldown_days,
                kubectl_version=codegen.toolchain.kubectl_version,
                helm_version=codegen.toolchain.helm_version,
                kind_version=codegen.toolchain.kind_version,
                direnv_version=codegen.toolchain.direnv_version,
                uv_version=codegen.toolchain.uv_version,
                qlty_version=codegen.toolchain.qlty_version,
                node_version=codegen.toolchain.node_version,
                jscpd_version=codegen.toolchain.jscpd_version,
                waza_version=codegen.toolchain.waza_version,
                taplo_version=codegen.toolchain.taplo_version,
                ast_grep_selector=codegen.toolchain.ast_grep_selector,
                ast_grep_version=codegen.toolchain.ast_grep_version,
                gitleaks_version=codegen.toolchain.gitleaks_version,
                scc_version=codegen.toolchain.scc_version,
                kubeconform_version=codegen.toolchain.kubeconform_version,
                go_version=codegen.toolchain.go_version,
                make_version=codegen.toolchain.make_version,
                author_name=project.author_name,
                author_email=project.author_email,
                repository=project.homepage,
                homepage=project.homepage,
                documentation=project.documentation,
                flext_git_base_url=flext_git_base_url,
                flext_git_branch=flext_line.value.branch,
                repository_provider=repository.provider,
                repository_git_url=repository.url,
                repository_branch=integration_branch.value,
                year=project.year,
            ),
        )

    @staticmethod
    def _managed_gitlinks(
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        *,
        repository_root: Path,
    ) -> p.Result[t.VariadicTuple[m.Infra.ManagedGitlinkSpec]]:
        """Resolve detected member baselines only for mutable governed subprojects.

        Returns:
            The resulting ``p.Result[t.VariadicTuple[m.Infra.ManagedGitlinkSpec]]``.

        """
        resolved: list[m.Infra.ManagedGitlinkSpec] = []
        for repository in workspace.subprojects:
            # A governed member follows its workspace's declared line unless
            # its own manifest declares otherwise (the ``.`` gitmodule branch).
            branch = u.Infra.resolve_integration_branch(
                repository_root / repository.path,
                preference=codegen.branch_policy.integration_branch_preference,
                declared=(
                    workspace.integration.branch
                    if workspace.integration is not None
                    else None
                ),
            )
            if branch.failure:
                return r[t.VariadicTuple[m.Infra.ManagedGitlinkSpec]].from_failure(
                    branch,
                )
            resolved.append(
                m.Infra.ManagedGitlinkSpec(repository=repository, branch=branch.value),
            )
        return r[t.VariadicTuple[m.Infra.ManagedGitlinkSpec]].ok(tuple(resolved))

    @staticmethod
    def _repository_root_rel(workspace: m.Infra.WorkspaceSpec) -> str:
        """Return the environment root owned by the inferred target.

        Returns:
            The environment root owned by the inferred target.

        """
        if workspace.project is not None:
            project_root_rel: str = workspace.project.repository_root_rel
            return project_root_rel
        return "."

    @staticmethod
    def _beads_project_id(repository_root: Path) -> str | None:
        """Return the checkout's own ledger identity, or None if unminted.

        `.beads/identity.toml` is the canonical owner (`[project] id`); the
        generated marker is its projection. An absent file is not a failure —
        it means Beads has not minted an identity for this checkout yet.

        Why the marker read-back: identity.toml is a gitignored per-checkout
        file, so CI clones and fresh runners run unminted while the TRACKED
        marker still carries the ledger identity the repository was cloned
        with. Rendering ``project_id: null`` over it dirties the tree (the
        generated-drift check goes red) and, worse, a pushed rewrite would
        strand every clone's identity — the same class of loss already
        observed in a consumer rig. When identity.toml is absent, read the id
        back from the existing marker so an unminted checkout preserves the
        identity it cloned instead of clobbering it.

        Returns:
            The checkout's own ledger identity, or None if unminted.

        Raises:
            RuntimeError: If failed to read beads identity at.
            ValueError: If beads identity at.

        """
        identity = repository_root / c.Infra.BEADS_DIRNAME / "identity.toml"
        if identity.is_file():
            source = u.Cli.files_read_text(identity)
            if source.failure:
                msg = f"failed to read beads identity at {identity}: {source.error}"
                raise RuntimeError(msg)
            payload = u.Cli.toml_mapping_from_text(source.value)
            if payload is None:
                msg = f"beads identity at {identity} is not valid TOML"
                raise ValueError(msg)
            project = payload.get("project")
            if not isinstance(project, Mapping):
                return None
            value = project.get("id")
            return value.strip() if isinstance(value, str) and value.strip() else None
        marker = repository_root / c.Infra.BEADS_METADATA_RELPATH
        if not marker.is_file():
            return None
        document = u.Cli.json_loads(marker.read_text(encoding="utf-8"))
        if document.failure or not isinstance(document.value, dict):
            return None
        value = document.value.get("project_id")
        return value.strip() if isinstance(value, str) and value.strip() else None


__all__: list[str] = ["FlextInfraCodegenConformContextRender"]
