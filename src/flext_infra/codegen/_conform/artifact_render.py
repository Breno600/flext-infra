"""Governed artifact rendering and project overlay composition."""

from __future__ import annotations

from pathlib import Path

from flext_core import r

from ... import c, config, m, p, t, u
from .context_render import FlextInfraCodegenConformContextRender


class FlextInfraCodegenConformArtifactRender(FlextInfraCodegenConformContextRender):
    """Governed artifact rendering and project overlay composition."""

    @classmethod
    def compose_project_artifact(
        cls,
        repository_root: Path,
        destination: str,
        rendered: str,
        *,
        managed_artifacts: m.Infra.ProjectManagedArtifactsSnapshot | None = None,
        workspace: m.Infra.WorkspaceSpec | None = None,
        codegen: m.Infra.CodegenConfigSpec | None = None,
        repository: m.Infra.RepositoryRef | None = None,
        target: m.Infra.RepositoryConformTarget | None = None,
    ) -> p.Result[m.Infra.CodegenArtifactComposition]:
        """Apply typed project overlays after canonical template rendering."""
        if destination == c.PYPROJECT_FILENAME:
            live_path = repository_root / c.PYPROJECT_FILENAME
            live: str | None = None
            if live_path.is_file():
                # Overlay reads the live text (managed merge conflicts
                # resolved) and never writes it.
                recovered_live = u.Infra.live_pyproject_text(live_path)
                if recovered_live.failure:
                    return r[m.Infra.CodegenArtifactComposition].from_failure(
                        recovered_live
                    )
                live = recovered_live.value
            overlaid = u.Infra.overlay_preserved(rendered, live)
            if overlaid.failure:
                return r[m.Infra.CodegenArtifactComposition].from_failure(overlaid)
            rendered = overlaid.value
            if workspace is not None and codegen is not None and repository is not None:
                profile = (
                    target.make_profile
                    if target is not None
                    else c.Infra.MakeProfile.STANDALONE
                )
                excludes = (
                    cls.routed_uv_exclude_dependencies(
                        repository=repository,
                        target=target,
                        codegen=codegen,
                        workspace=workspace,
                    )
                    if target is not None
                    else ()
                )
                conformed = cls.conformed_pyproject_source(
                    rendered,
                    repository=repository,
                    workspace=workspace,
                    codegen=codegen,
                    workspace_mode=profile,
                    uv_exclude_dependencies=excludes,
                )
                if conformed.failure:
                    return r[m.Infra.CodegenArtifactComposition].from_failure(conformed)
                rendered = conformed.value
            formatted = u.Infra.format_toml_source(
                rendered,
                path=live_path,
                toolchain_root=repository_root,
                taplo_version=config.Infra.codegen.toolchain.taplo_version,
            )
            if formatted.failure:
                return r[m.Infra.CodegenArtifactComposition].from_failure(formatted)
            # The parse-merge-dump overlay drops every template comment, so
            # this composition owner publishes the one generated-file header
            # (owner, adjustment rule, regeneration verb) on the final bytes.
            # A re-run reads the live file as data, so it never accumulates.
            rendered = f"{c.Infra.BANNER}\n{formatted.value.lstrip()}"
        if destination != c.Infra.MISE_TOML_FILENAME:
            return r[m.Infra.CodegenArtifactComposition].ok(
                m.Infra.CodegenArtifactComposition(rendered=rendered)
            )
        resolved_artifacts = managed_artifacts
        if resolved_artifacts is None:
            snapshot = u.Infra.snapshot_committed_project_managed_artifacts(
                repository_root
            )
            if snapshot.failure:
                return r[m.Infra.CodegenArtifactComposition].from_failure(snapshot)
            resolved_artifacts = snapshot.value
        composed = (
            u.Infra.compose_mise_toml_from_snapshot(
                resolved_artifacts.sources, rendered
            )
            if resolved_artifacts.sources
            else u.Infra.compose_mise_toml_from_resolution(
                resolved_artifacts.resolution, rendered
            )
        )
        if composed.failure:
            return r[m.Infra.CodegenArtifactComposition].from_failure(composed)
        config_sources = u.Infra.snapshot_config_sources(repository_root)
        if config_sources.failure:
            return r[m.Infra.CodegenArtifactComposition].from_failure(config_sources)
        return r[m.Infra.CodegenArtifactComposition].ok(
            m.Infra.CodegenArtifactComposition(
                rendered=composed.value, source_states=config_sources.value
            )
        )

    def _rendered_artifact_source(
        self,
        *,
        templates_root: Path,
        template_relpath: Path,
        failure_prefix: str,
        dist: str,
        repository: m.Infra.RepositoryRef,
        repository_root: Path,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        destination: str,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
        project_context: m.Infra.ProjectRenderContext | None,
        managed_artifacts: m.Infra.ProjectManagedArtifactsResolution | None = None,
    ) -> p.Result[str]:
        """Resolve one artifact render context and render its template source.

        ``failure_prefix`` carries the only difference between the scaffold and
        existing-repository planners: the stage banner the scaffold planner
        prepends to a render failure.
        """
        artifact_context = self._artifact_render_context(
            dist=dist,
            repository=repository,
            repository_root=repository_root,
            target=target,
            workspace=workspace,
            codegen=codegen,
            destination=destination,
            tooling_runtime=tooling_runtime,
            project_context=project_context,
            managed_artifacts=managed_artifacts,
        )
        if artifact_context.failure:
            return r[str].from_failure(artifact_context)
        rendered = u.Cli.template_render(
            templates_root / template_relpath, artifact_context.value
        )
        if rendered.failure:
            return r[str].fail(
                f"{failure_prefix}"
                f"template={template_relpath}: "
                f"{rendered.error or 'template render failed'}"
            )
        return rendered

    def _artifact_render_context(
        self,
        *,
        dist: str,
        repository: m.Infra.RepositoryRef,
        repository_root: Path,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
        destination: str,
        tooling_runtime: m.Infra.ToolingRuntimeContext,
        project_context: m.Infra.ProjectRenderContext | None,
        managed_artifacts: m.Infra.ProjectManagedArtifactsResolution | None = None,
    ) -> p.Result[p.Model]:
        """Resolve one governed artifact to its canonical typed render input."""
        if destination == c.Infra.GITIGNORE:
            project_patterns: t.StrSequence = (
                managed_artifacts.artifacts.Gitignore.patterns
                if managed_artifacts is not None
                else ()
            )
            return r[p.Model].ok(
                m.Infra.GitignoreRenderSpec(
                    gitignore_sections=u.Infra.gitignore_sections(
                        codegen,
                        profile=target.make_profile,
                        # The declared distribution is the project identity; a
                        # scaffold renders before its pyproject exists.
                        project_name=repository.distribution,
                        workspace=workspace,
                        project_patterns=project_patterns,
                    )
                )
            )
        if destination == c.Infra.PRE_COMMIT_CONFIG_FILENAME:
            return r[p.Model].ok(
                m.Infra.MakeWorkflowRenderSpec(dist=dist, make=codegen.make)
            )
        if destination in {
            c.Infra.MARKDOWNLINT_CONFIG_FILENAME,
            c.Infra.MARKDOWNLINT_IGNORE_FILENAME,
            c.Infra.PRETTIER_CONFIG_FILENAME,
            c.Infra.PRETTIER_IGNORE_FILENAME,
            f"{c.Infra.QLTY_CONFIG_DIRNAME}/{c.Infra.QLTY_CONFIG_FILENAME}",
        }:
            return r[p.Model].ok(
                m.Infra.MarkdownLintRenderSpec(tooling=config.Infra.tooling)
            )
        if destination == c.Infra.SONARCLOUD_PROPERTIES_FILENAME:
            # Why: conform itself projects managed tests/fixtures/ci/docker files
            # into every profile, so the tests directory always exists and
            # sonar.tests never names an absent directory.
            return r[p.Model].ok(
                m.Infra.SonarcloudRenderSpec(
                    sonarcloud=codegen.sonarcloud, tests_dir=c.Infra.DIR_TESTS
                )
            )
        if destination == c.Infra.ENVRC_FILENAME:
            # Conform targets always own a governed Beads identity, so the
            # rendered tier is binary here: city server wiring when the
            # repository declares city participation, the repository-local
            # bd base otherwise.
            return r[p.Model].ok(
                m.Infra.EnvrcRenderSpec(
                    repository_root_rel=self._repository_root_rel(workspace),
                    state_directory_name=codegen.toolchain.state_directory_name,
                    scratch_namespace=codegen.toolchain.scratch_namespace,
                    scratch_home_relative=(codegen.toolchain.scratch_home_relative),
                    pycache_namespace=codegen.toolchain.pycache_namespace,
                    environment_path_prepends=(
                        codegen.toolchain.environment_path_prepends
                    ),
                    mise_bootstrap=u.Infra.mise_bootstrap_environment(),
                    gascity=(
                        m.Infra.BeadsWorkspaceEnvironmentSpec()
                        if target.gascity_enabled
                        else m.Infra.BeadsWorkspaceEnvironmentSpec(backend="local")
                    ),
                )
            )
        if destination in {c.Infra.MISE_TOML_FILENAME, c.Infra.PYTHON_VERSION_FILENAME}:
            # Computed toolchain fields are projections, not inputs: filter the
            # dump to the render spec's declared fields before construction.
            toolchain_data = {
                field_name: value
                for field_name, value in codegen.toolchain.model_dump().items()
                if field_name in m.Infra.ToolchainSpec.model_fields
            }
            return r[p.Model].ok(m.Infra.ToolchainSpec(**toolchain_data))

        if destination == c.Infra.BEADS_CONFIG_RELPATH:
            project_types = target.beads.custom_issue_types
            required_types = codegen.toolchain.beads.required_custom_types
            beads = codegen.toolchain.beads
            return r[p.Model].ok(
                m.Infra.BeadsConfigRenderSpec(
                    issue_prefix=target.beads.issue_prefix,
                    endpoint_origin=beads.endpoint_origin,
                    endpoint_status=beads.endpoint_status,
                    gascity_enabled=target.gascity_enabled,
                    custom_issue_types=tuple(
                        dict.fromkeys((*project_types, *required_types))
                    ),
                    dolt_mode=beads.dolt_mode,
                    export_auto=beads.export_auto,
                    backup_enabled=beads.backup_enabled,
                    dolt_disable_event_flush=beads.dolt_disable_event_flush,
                )
            )
        if destination == c.Infra.BEADS_METADATA_RELPATH:
            # Why: this marker is regenerated on every `make gen`, but the
            # ledger identity inside it is owned by the checkout, not by the
            # fleet SSOT. Rendering without it stripped the key, and Beads then
            # minted a NEW identity on next access — rig gmn lost
            # 2b1a0582-… that way (commit 3e7ba1e). Read it back so a
            # regeneration is identity-preserving.
            return r[p.Model].ok(
                m.Infra.BeadsMetadataRenderSpec(
                    database=target.beads.database,
                    dolt_mode=codegen.toolchain.beads.dolt_mode,
                    project_id=self._beads_project_id(repository_root),
                )
            )
        if destination.startswith(".github/"):
            workspace_repositories = (
                tuple(workspace.subprojects)
                if target.make_profile is c.Infra.MakeProfile.WORKSPACE
                else ()
            )
            # Why: ci.yml.j2 iterates this to build its push/pull_request branch
            # filters, so an unsupplied value fails the render outright. The
            # repository's own integration branch is the only branch this layer
            # can name from resolved data; a fleet-wide list hardcoded here would
            # make every repository trigger on branches it does not have.
            branch = u.Infra.resolve_integration_branch(
                repository_root,
                preference=codegen.branch_policy.integration_branch_preference,
                declared=(
                    workspace.integration.branch
                    if workspace.integration is not None
                    else None
                ),
            )
            if branch.failure:
                return r[p.Model].from_failure(branch)
            return r[p.Model].ok(
                m.Infra.GithubWorkflowRenderSpec(
                    dist=dist,
                    make_profile=target.make_profile,
                    gascity_enabled=target.gascity_enabled,
                    repository_branch=branch.value,
                    ci_trigger_branches=tuple(
                        dict.fromkeys((
                            *codegen.branch_policy.ci_trigger_branches,
                            branch.value,
                        ))
                    ),
                    python_version=codegen.toolchain.python_version,
                    state_directory_name=codegen.toolchain.state_directory_name,
                    github_actions=codegen.github_actions,
                    make=codegen.make,
                    workspace_repositories=workspace_repositories,
                    # Why: dependabot.yml.j2 branches on this and the model
                    # declares it, but the .github/ spec never supplied it, so
                    # every render died with "'has_devcontainer' is undefined".
                    # Dependabot rejects its ENTIRE config when an ecosystem
                    # names a directory that is absent, so this is read from the
                    # checkout rather than declared: a stale flag would silently
                    # disable Dependabot for the repository.
                    has_devcontainer=(repository_root / ".devcontainer").is_dir(),
                    dependabot_cooldown_days=codegen.dependabot_cooldown_days.get(
                        dist, 0
                    ),
                    checkout_submodules=codegen.checkout_submodules_overrides.get(
                        dist, codegen.checkout_submodules
                    ),
                    custom_steps=self._custom_ci_steps(repository_root),
                    private_submodules=codegen.ci_private_submodules.get(dist),
                    private_dependency_auth=codegen.ci_private_dependency_auth.get(
                        dist
                    ),
                    system_packages=tuple(codegen.ci_system_packages.get(dist, ())),
                )
            )
        destination_path = Path(destination)
        if (
            destination_path.parent.as_posix() == "tests/fixtures/ci/docker"
            and destination_path.suffix == ".Dockerfile"
        ):
            return r[p.Model].ok(
                m.Infra.DistroDockerRenderSpec(
                    package_name=dist.replace("-", "_"),
                    python_version=codegen.toolchain.python_version,
                    make=codegen.make,
                    mise_bootstrap=u.Infra.mise_bootstrap_environment(),
                )
            )
        if destination == c.Infra.RELEASE_GITLEAKS_CONFIG_PATH:
            # Why (flext-to3n7): the release build phase snapshots the gitleaks
            # policy from the repository; it is fleet policy owned by
            # config/infra.yaml, never scaffold-only project metadata.
            return r[p.Model].ok(
                m.Infra.ReleasePolicySpec(
                    build_constraints=config.Infra.release.build_constraints
                )
            )
        if destination == c.Infra.MAKEFILE_FILENAME:
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
                return r[p.Model].from_failure(gitlinks)
            return r[p.Model].ok(
                m.Infra.MakefileRenderSpec(
                    pytest=config.Infra.tooling.tools.pytest,
                    mise_bootstrap=u.Infra.mise_bootstrap_environment(),
                    dist=dist,
                    state_directory_name=codegen.toolchain.state_directory_name,
                    scratch_namespace=codegen.toolchain.scratch_namespace,
                    scratch_home_relative=codegen.toolchain.scratch_home_relative,
                    infra_cli=config.Infra.name,
                    make_profile=profile,
                    makefile_custom_include=c.Infra.MAKEFILE_CUSTOM_INCLUDE,
                    repository_root_rel=self._repository_root_rel(workspace),
                    workspace_subprojects=tuple(
                        item.path.as_posix() for item in workspace.subprojects
                    ),
                    workspace_repositories=subprojects,
                    workspace_gitlinks=gitlinks.value,
                    uv_link_mode=self.link_mode(repository, codegen.toolchain),
                    uv_version=codegen.toolchain.uv_version,
                    mise_lockfile_platforms=codegen.toolchain.mise_lockfile_platforms,
                    qlty_selector=codegen.toolchain.qlty_selector,
                    jscpd_selector=codegen.toolchain.jscpd_selector,
                    prettier_selector=codegen.toolchain.prettier_selector,
                    scc_selector=codegen.toolchain.scc_selector,
                    waza_selector=codegen.toolchain.waza_selector,
                    make=codegen.make,
                    extra_verbs=(
                        self._merge_extra_verbs(
                            repository.extra_verbs,
                            (
                                ()
                                if repository.script_dispatch is None
                                else self._discover_script_verbs(repository_root)
                            ),
                            frozenset(verb.name for verb in codegen.make.verbs),
                        )
                    ),
                    script_dispatch=repository.script_dispatch,
                    workspace_cli_group=c.Infra.CLI_GROUP_WORKSPACE,
                    mypy_memory_limit_mb=c.Infra.MYPY_MEMORY_LIMIT_MB_DEFAULT,
                    mypy_timeout_seconds=c.Infra.MYPY_TIMEOUT_SECONDS_DEFAULT,
                    mypy_timeout_exit_code=c.Infra.PROCESS_TIMEOUT_EXIT_CODE,
                    mypy_signal_exit_offset=c.Infra.PROCESS_SIGNAL_EXIT_OFFSET,
                    prlimit_command=c.Infra.PRLIMIT_COMMAND,
                    prlimit_address_space_option=(c.Infra.PRLIMIT_ADDRESS_SPACE_OPTION),
                    timeout_command=c.Infra.TIMEOUT_COMMAND,
                    timeout_kill_after_seconds=c.Infra.TIMEOUT_KILL_AFTER_SECONDS,
                    pytest_process_timeout_seconds=(
                        config.Infra.tooling.tools.pytest.process_timeout_seconds
                    ),
                )
            )
        if destination == c.Infra.CUSTOM_MAKE_FILENAME:
            # Existing repositories project custom routes from the same typed
            # Make contract as Makefile; they do not require scaffold-only
            # project metadata.
            make_context = self.make_render_context(
                repository,
                target,
                workspace,
                codegen,
                tooling_runtime=tooling_runtime,
                repository_root=repository_root,
            )
            if make_context.failure:
                return r[p.Model].from_failure(make_context)
            return r[p.Model].ok(make_context.value)
        if project_context is not None:
            return r[p.Model].ok(project_context)
        context_result = self._project_render_context(
            repository,
            target,
            workspace,
            codegen,
            tooling_runtime=tooling_runtime,
            repository_root=repository_root,
            managed_artifacts=managed_artifacts,
            use_committed_artifacts=project_context is None,
        )
        if context_result.failure:
            return r[p.Model].from_failure(context_result)
        return r[p.Model].ok(context_result.value)

    @staticmethod
    def _custom_ci_steps(repository_root: Path) -> str:
        """Read the project-owned workflow steps, if the project declares any.

        This is the CI counterpart of ``custom.mk``: the generator injects the
        block verbatim and never interprets it, so a project extends its own
        pipeline without the generator learning that project's concerns.
        """
        source: Path = repository_root / c.Infra.CUSTOM_CI_STEPS_FILENAME
        if not source.is_file():
            return ""
        return source.read_text(encoding=c.DEFAULT_ENCODING).rstrip("\n")


__all__: list[str] = ["FlextInfraCodegenConformArtifactRender"]
