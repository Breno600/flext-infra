"""Typed Make and project render context projection."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from flext_core import r

from ... import c, config, m, p, t, u
from ...deps import FlextInfraEnsureRuffConfigPhase
from .pyproject_policy import FlextInfraCodegenConformPyprojectPolicy


class FlextInfraCodegenConformContextRender(FlextInfraCodegenConformPyprojectPolicy):
    """Typed Make and project render context projection."""

    def make_render_context(
        self,
        repository: m.Infra.RepositoryRef,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        *,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
        repository_root: Path,
    ) -> p.Result[m.Infra.MakeRenderContext]:
        """Build the typed context consumed by the generated Makefile."""
        profile = target.make_profile
        subprojects = (
            tuple(workspace.subprojects)
            if profile is c.Infra.MakeProfile.WORKSPACE
            else ()
        )
        gitlinks = self._managed_gitlinks(
            workspace, codegen, repository_root=repository_root
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
                mypy_memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
                mypy_timeout_seconds=c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT,
                mypy_timeout_exit_code=c.Infra.PROCESS_TIMEOUT_EXIT_CODE,
                mypy_signal_exit_offset=c.Infra.PROCESS_SIGNAL_EXIT_OFFSET,
                prlimit_command=c.Infra.PRLIMIT_COMMAND,
                prlimit_address_space_option=c.Infra.PRLIMIT_ADDRESS_SPACE_OPTION,
                timeout_command=c.Infra.TIMEOUT_COMMAND,
                timeout_kill_after_seconds=c.Infra.TIMEOUT_KILL_AFTER_SECONDS,
                tooling_runtime=tooling_runtime,
                dist=repository.distribution,
                infra_cli=config.Infra.name,
                python_version=codegen.toolchain.python_version,
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
            )
        )

    @staticmethod
    def _project_spec_from_existing(
        repository: m.Infra.RepositoryRef,
        repository_root: Path,
        codegen: m.Infra.CodegenConfigSpec,
    ) -> p.Result[m.Infra.ProjectSpec]:
        """Derive scaffold ProjectSpec from live PEP 621 metadata for existing trees."""
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
                f"existing pyproject is missing author name/email: {repository_root}"
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
                f"dependencies exactly once at {repository_root}: {tuple(direct)}"
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
            )
        )

    def _project_render_context(
        self,
        repository: m.Infra.RepositoryRef,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        *,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
        repository_root: Path,
        managed_artifacts: m.Infra.ProjectManagedArtifactsResolution | None = None,
        use_committed_artifacts: bool = True,
    ) -> p.Result[m.Infra.ProjectRenderContext]:
        """Build the complete typed context consumed by project templates."""
        if workspace.project is None:
            # Existing checkouts declare no scaffold metadata: derive the render
            # identity from the live project metadata instead of failing, so
            # conforming a governed repository never depends on scaffold-only
            # declarations.
            derived = self._project_spec_from_existing(
                repository, repository_root, codegen
            )
            if derived.failure:
                return r[m.Infra.ProjectRenderContext].from_failure(derived)
            project = derived.value
        else:
            project = workspace.project
        if workspace.namespace_scan_dirs and not project.namespace_scan_dirs:
            # The manifest-level declaration is the repository's production scope
            # for the namespace validator (cosmos-3flk9 decision A), so a
            # checkout that derives its project metadata declares it once at the
            # workspace root instead of freezing a full scaffold spec. An
            # explicit project-level declaration stays the more specific owner.
            project = project.model_copy(
                update={"namespace_scan_dirs": workspace.namespace_scan_dirs}
            )
        rows = u.Infra.dependency_profile_rows(
            codegen.scaffold.project.dependency_profiles,
            upstream=project.upstream,
            distribution=repository.distribution,
        )
        if not rows:
            return r[m.Infra.ProjectRenderContext].fail(
                f"unsupported scaffold upstream: {project.upstream}"
            )
        dependency_profile, *additions = rows
        if additions:
            dependency_profile = m.Infra.ScaffoldDependencyProfileSpec.model_validate({
                **dependency_profile.model_dump(),
                "runtime": tuple(
                    dict.fromkeys((
                        *dependency_profile.runtime,
                        *(
                            requirement
                            for item in additions
                            for requirement in item.runtime
                        ),
                    ))
                ),
                "codegen": tuple(
                    dict.fromkeys((
                        *dependency_profile.codegen,
                        *(
                            requirement
                            for item in additions
                            for requirement in item.codegen
                        ),
                    ))
                ),
            })
        if project.license not in codegen.scaffold.project.supported_licenses:
            supported = ", ".join(codegen.scaffold.project.supported_licenses)
            return r[m.Infra.ProjectRenderContext].fail(
                f"unsupported scaffold license: {project.license}; "
                f"supported licenses: {supported}"
            )
        profile = target.make_profile
        make_context = self.make_render_context(
            repository,
            target,
            workspace,
            codegen,
            tooling_runtime=tooling_runtime,
            repository_root=repository_root,
        )
        if make_context.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(make_context)
        repository_provider = u.Infra.repository_provider(repository)
        if repository_provider.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(repository_provider)
        # The repository's declaration wins; otherwise the published baseline.
        # A checkout's HEAD is never consulted (ADR-018 p.10).
        integration_branch = u.Infra.resolve_integration_branch(
            repository_root,
            preference=codegen.branch_policy.integration_branch_preference,
            declared=(
                workspace.integration.branch
                if workspace.integration is not None
                else None
            ),
        )
        if integration_branch.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(integration_branch)
        # Internal flext-* floors render from the FLEXT line the checkout
        # consumes (the infrastructure dependency's own source), never from
        # the consumer's organization or branch: a repository in another org
        # otherwise renders a mixed family and uv rejects conflicting URLs.
        flext_line = u.Infra.flext_integration_line(
            codegen=codegen,
            repository_root=repository_root,
            bootstrap_source=(
                workspace.flext_source
                if not (repository_root / c.PYPROJECT_FILENAME).exists()
                else None
            ),
        )
        if flext_line.failure:
            return r[m.Infra.ProjectRenderContext].from_failure(flext_line)
        flext_git_base_url = flext_line.value.base_url
        if flext_git_base_url is None:
            return r[m.Infra.ProjectRenderContext].fail(
                "detected FLEXT line carries no provider base URL"
            )
        # A data dir already shipped inside the package (``src/<pkg>/<dir>``)
        # must not also be force-included from the repo root: both map to the
        # same wheel path and hatchling rejects the duplicate archive entry.
        # Force-include stays reserved for root data that the package does not
        # already carry (mirrors the ensure-packaging phase rule).
        package_root = repository_root / c.Infra.DEFAULT_SRC_DIR / project.package_name
        packaged_data_dirs = (
            tuple(
                data_dir
                for data_dir in config.Infra.tooling.tools.hatch.packaged_data_dirs
                if any(
                    profile in entry.profiles
                    and Path(entry.destination).parts
                    and Path(entry.destination).parts[0] == data_dir
                    for entry in codegen.templates.entries
                )
                and not (package_root / data_dir).is_dir()
            )
            if profile is not c.Infra.MakeProfile.WORKSPACE
            else ()
        )
        catalog_artifacts = managed_artifacts
        if use_committed_artifacts:
            committed = u.Infra.load_committed_project_managed_artifacts(
                repository_root
            )
            if committed.failure:
                return r[m.Infra.ProjectRenderContext].from_failure(committed)
            catalog_artifacts = committed.value
        project_patterns: t.StrSequence = (
            catalog_artifacts.artifacts.Gitignore.patterns
            if catalog_artifacts is not None
            else ()
        )
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
                # Why: the fleet policy alone is not the effective Ruff contract.
                # A repository may carry an operator-authorized exemption in its
                # committed ``config/*.yaml`` ManagedArtifacts catalog, and
                # ensure_ruff composes the two when it edits a pyproject in
                # place. The template rendered only the fleet map, so a full
                # render silently dropped the local overlay -- flext-infra's
                # own _rope exemption disappeared on every conform and returned
                # 12 SLF001 findings the operator had already ruled on. Compose
                # from the commit catalog so both paths produce the same
                # effective map and concurrent worktree WIP cannot change a
                # projection.
                ruff_per_file_ignores=(
                    FlextInfraEnsureRuffConfigPhase.compose_per_file_ignores(
                        repository_root, managed_artifacts=catalog_artifacts
                    )
                ),
                environment_path_prepends=(codegen.toolchain.environment_path_prepends),
                beads=workspace.beads,
                canonical_project_name=target.canonical_project_name,
                const_name=project.constant_name,
                package_name=project.package_name,
                packaged_data_dirs=packaged_data_dirs,
                namespace_scan_dirs=project.namespace_scan_dirs,
                workspace_integration=workspace.integration,
                # NOTE (multi-agent, flext-get3j): carry only the validated
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
                root_modules=project.root_modules,
                runtime_dependency_overlay=project.runtime_dependency_overlay,
                description=project.description,
                version=version_result.value,
                license=project.license,
                python_required_version=codegen.toolchain.python_required_version,
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
                # A workspace root owns sources only for its actual members.
                # External FLEXT dependencies still need their own Git source.
                workspace_dependency_distributions=(
                    tuple(member.distribution for member in workspace.subprojects)
                    if profile is c.Infra.MakeProfile.WORKSPACE
                    else ()
                ),
                year=project.year,
            )
        )

    @staticmethod
    def _managed_gitlinks(
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        *,
        repository_root: Path,
    ) -> p.Result[t.VariadicTuple[m.Infra.ManagedGitlinkSpec]]:
        """Resolve detected member baselines only for mutable governed subprojects."""
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
                    branch
                )
            resolved.append(
                m.Infra.ManagedGitlinkSpec(repository=repository, branch=branch.value)
            )
        return r[t.VariadicTuple[m.Infra.ManagedGitlinkSpec]].ok(tuple(resolved))

    @staticmethod
    def _repository_root_rel(workspace: m.Infra.WorkspaceSpec) -> str:
        """Return the environment root owned by the inferred target."""
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
        strand every clone's identity — the same class of loss as rig gmn's
        2b1a0582. When identity.toml is absent, read the id back from the
        existing marker so an unminted checkout preserves the identity it
        cloned instead of clobbering it.
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
