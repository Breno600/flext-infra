"""Governed artifact rendering and project overlay composition.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, config, m, p, r, t, u
from flext_infra.codegen._conform.context_render import (
    FlextInfraCodegenConformContextRender,
)


class FlextInfraCodegenConformArtifactRender(FlextInfraCodegenConformContextRender):
    """Governed artifact rendering and project overlay composition."""

    @staticmethod
    def with_planned_pyproject(
        render_inputs: m.Infra.CodegenRenderInputs,
        composed: str,
    ) -> p.Result[m.Infra.CodegenRenderInputs]:
        """Record the direct-reference requirements of the pyproject just planned.

        Planners compose the pyproject before every other destination, so a
        scaffold (no pyproject on disk yet) and a conformance that changes the
        requirements both render from the planned bytes, never stale ones.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenRenderInputs]``.

        """
        document = u.Cli.toml_parse_text(composed)
        if document is None:
            return r[m.Infra.CodegenRenderInputs].fail(
                "planned pyproject is not valid TOML",
            )
        names = u.Infra.direct_source_names(document)
        if names.failure:
            return r[m.Infra.CodegenRenderInputs].from_failure(names)
        return r[m.Infra.CodegenRenderInputs].ok(
            render_inputs.model_copy(update={"planned_direct_sources": names.value}),
        )

    @staticmethod
    def direct_sources(
        render_inputs: m.Infra.CodegenRenderInputs,
    ) -> p.Result[t.VariadicTuple[str]]:
        """Return the planned direct-reference names, else the committed ones.

        Returns:
            The planned direct-reference names, else the committed ones.

        """
        if render_inputs.planned_direct_sources is not None:
            return r[t.VariadicTuple[str]].ok(render_inputs.planned_direct_sources)
        document = u.Cli.toml_read_document(
            render_inputs.target.root / c.PYPROJECT_FILENAME,
        )
        if document.failure:
            return r[t.VariadicTuple[str]].from_failure(document)
        return u.Infra.direct_source_names(document.value)

    @classmethod
    def compose_project_artifact(
        cls,
        repository_root: Path,
        destination: str,
        rendered: str,
        *,
        render_inputs: m.Infra.CodegenRenderInputs | None = None,
    ) -> p.Result[m.Infra.CodegenArtifactComposition]:
        """Apply typed project overlays after canonical template rendering.

        Without ``render_inputs`` the committed project catalog overlays the
        render and no pyproject conformance runs.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenArtifactComposition]``.

        """
        if destination == c.Infra.GITIGNORE:
            overlay = cls._composed_gitignore_overlay(
                repository_root,
                rendered,
                render_inputs,
            )
            if overlay.failure:
                return r[m.Infra.CodegenArtifactComposition].from_failure(overlay)
            rendered = overlay.value
        if destination == c.PYPROJECT_FILENAME:
            return cls._composed_pyproject_overlay(
                repository_root,
                rendered,
                render_inputs,
            )
        if destination != c.Infra.MISE_TOML_FILENAME:
            return r[m.Infra.CodegenArtifactComposition].ok(
                m.Infra.CodegenArtifactComposition(rendered=rendered),
            )
        return cls._composed_mise_overlay(repository_root, rendered, render_inputs)

    @classmethod
    def _composed_gitignore_overlay(
        cls,
        repository_root: Path,
        rendered: str,
        render_inputs: m.Infra.CodegenRenderInputs | None,
    ) -> p.Result[str]:
        """Preserve the live gitignore's owned blocks in the render.

        Returns:
            The resulting ``p.Result[str]``.

        """
        if render_inputs is None:
            resolved = u.Infra.load_project_managed_artifacts(repository_root)
            if resolved.failure:
                return r[str].from_failure(resolved)
            artifacts = resolved.value.artifacts
        else:
            artifacts = render_inputs.managed_artifacts.resolution.artifacts
        return u.Infra.preserve_project_gitignore_blocks(
            rendered,
            repository_root,
            artifacts.Gitignore.preserved_blocks,
        )

    @classmethod
    def _composed_pyproject_overlay(
        cls,
        repository_root: Path,
        rendered: str,
        render_inputs: m.Infra.CodegenRenderInputs | None,
    ) -> p.Result[m.Infra.CodegenArtifactComposition]:
        """Overlay, conform, and format the pyproject render.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenArtifactComposition]``.

        """
        result_type = r[m.Infra.CodegenArtifactComposition]
        live_path = repository_root / c.PYPROJECT_FILENAME
        live: str | None = None
        if live_path.is_file():
            # Overlay reads the live text (managed merge conflicts
            # resolved) and never writes it.
            recovered_live = u.Infra.live_pyproject_text(live_path)
            if recovered_live.failure:
                return result_type.from_failure(recovered_live)
            live = recovered_live.value
        overlaid = u.Infra.overlay_preserved(rendered, live)
        if overlaid.failure:
            return result_type.from_failure(overlaid)
        composed_rendered = overlaid.value
        if render_inputs is not None:
            conformed = cls.conformed_pyproject_source(
                composed_rendered,
                render_inputs=render_inputs,
            )
            if conformed.failure:
                return result_type.from_failure(conformed)
            composed_rendered = conformed.value
        formatted = u.Infra.format_toml_source(
            composed_rendered,
            path=live_path,
            toolchain_root=repository_root,
            taplo_version=config.Infra.codegen.toolchain.tool_versions["taplo"],
        )
        if formatted.failure:
            return result_type.from_failure(formatted)
        # The parse-merge-dump overlay drops every template comment, so
        # this composition owner publishes the one generated-file header
        # (owner, adjustment rule, regeneration verb) on the final bytes.
        # A re-run reads the live file as data, so it never accumulates.
        return result_type.ok(
            m.Infra.CodegenArtifactComposition(
                rendered=f"{c.Infra.BANNER}\n{formatted.value.lstrip()}",
            ),
        )

    @classmethod
    def _composed_mise_overlay(
        cls,
        repository_root: Path,
        rendered: str,
        render_inputs: m.Infra.CodegenRenderInputs | None,
    ) -> p.Result[m.Infra.CodegenArtifactComposition]:
        """Compose the mise declaration from the resolved artifact catalog.

        Returns:
            The resulting ``p.Result[m.Infra.CodegenArtifactComposition]``.

        """
        result_type = r[m.Infra.CodegenArtifactComposition]
        if render_inputs is None:
            snapshot = u.Infra.snapshot_committed_project_managed_artifacts(
                repository_root,
            )
            if snapshot.failure:
                return result_type.from_failure(snapshot)
            resolved_artifacts = snapshot.value
        else:
            resolved_artifacts = render_inputs.managed_artifacts
        composed = (
            u.Infra.compose_mise_toml_from_snapshot(
                resolved_artifacts.sources,
                rendered,
            )
            if resolved_artifacts.sources
            else u.Infra.compose_mise_toml_from_resolution(
                resolved_artifacts.resolution,
                rendered,
            )
        )
        if composed.failure:
            return result_type.from_failure(composed)
        config_sources = u.Infra.snapshot_config_sources(repository_root)
        if config_sources.failure:
            return result_type.from_failure(config_sources)
        return result_type.ok(
            m.Infra.CodegenArtifactComposition(
                rendered=composed.value,
                source_states=config_sources.value,
            ),
        )

    def _rendered_artifact_source(
        self,
        render_inputs: m.Infra.CodegenRenderInputs,
        *,
        template_relpath: Path,
        destination: str,
        failure_prefix: str,
        project_context: m.Infra.ProjectRenderContext | None,
    ) -> p.Result[str]:
        """Resolve one artifact render context and render its template source.

        ``failure_prefix`` carries the only difference between the scaffold and
        existing-repository planners: the stage banner the scaffold planner
        prepends to a render failure.

        Returns:
            The resulting ``p.Result[str]``.

        """
        artifact_context = self._artifact_render_context(
            render_inputs,
            destination=destination,
            project_context=project_context,
        )
        if artifact_context.failure:
            return r[str].from_failure(artifact_context)
        rendered = u.Cli.template_render(
            u.Infra.codegen_templates_root(render_inputs.codegen) / template_relpath,
            artifact_context.value,
        )
        if rendered.failure:
            return r[str].fail(
                f"{failure_prefix}"
                f"template={template_relpath}: "
                f"{rendered.error or 'template render failed'}",
            )
        return rendered

    def _artifact_render_context(
        self,
        render_inputs: m.Infra.CodegenRenderInputs,
        *,
        destination: str,
        project_context: m.Infra.ProjectRenderContext | None,
    ) -> p.Result[p.Model]:
        """Resolve one governed artifact to its canonical typed render input.

        Returns:
            The resulting ``p.Result[p.Model]``.

        """
        repository_context = self._repo_config_context(render_inputs, destination)
        if repository_context is not None:
            return repository_context
        static_context = self._static_spec_context(render_inputs, destination)
        if static_context is not None:
            return static_context
        beads_context = self._beads_context(render_inputs, destination)
        if beads_context is not None:
            return beads_context
        github_context = self._github_context(render_inputs, destination)
        if github_context is not None:
            return github_context
        makefile_context = self._makefile_group_context(render_inputs, destination)
        if makefile_context is not None:
            return makefile_context
        return self._project_or_pass_context(render_inputs, project_context)

    def _repo_config_context(
        self,
        render_inputs: m.Infra.CodegenRenderInputs,
        destination: str,
    ) -> p.Result[p.Model] | None:
        """Resolve the repository-shaped config specs (gitignore/sonar/qlty/envrc).

        Returns:
            The resulting ``p.Result[p.Model] | None`` where None marks a
            destination outside this group.

        """
        target = render_inputs.target
        workspace = render_inputs.workspace
        codegen = render_inputs.codegen
        repository = target.repository
        if destination == c.Infra.GITIGNORE:
            project_patterns: t.StrSequence = (
                render_inputs.managed_artifacts.resolution.artifacts.Gitignore.patterns
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
                    ),
                ),
            )
        if destination == c.Infra.SONARCLOUD_PROPERTIES_FILENAME:
            # Why: conform itself projects managed tests/fixtures/ci/docker files
            # into every profile, so the tests directory always exists and
            # sonar.tests never names an absent directory.
            return r[p.Model].ok(
                m.Infra.SonarcloudRenderSpec(
                    sonarcloud=codegen.sonarcloud,
                    tests_dir=c.Infra.DIR_TESTS,
                    # Why: a workspace root checks its members out in place, and
                    # each member is a separate repository analysed by its own
                    # SonarCloud project; scanning them again from the root
                    # double-counts their code as root duplication.
                    workspace_subprojects=(
                        tuple(item.path.as_posix() for item in workspace.subprojects)
                        if target.make_profile is c.Infra.MakeProfile.WORKSPACE
                        else ()
                    ),
                    generated_source_globs=codegen.generated_source_globs,
                ),
            )
        if destination == (
            f"{c.Infra.QLTY_CONFIG_DIRNAME}/{c.Infra.QLTY_CONFIG_FILENAME}"
        ):
            # Generated source trees are tracked, so Git ignore rules no
            # longer keep them out of the smells scan.
            return r[p.Model].ok(
                m.Infra.QltyRenderSpec(
                    generated_source_globs=codegen.generated_source_globs,
                ),
            )
        if destination == c.Infra.ENVRC_FILENAME:
            # The workspace declaration owns whether a Beads route exists.
            # A repository without one must not render ledger activation.
            return r[p.Model].ok(
                m.Infra.EnvrcRenderSpec(
                    repository_root_rel=self._repository_root_rel(workspace),
                    environment_path_prepends=(
                        codegen.toolchain.environment_path_prepends
                    ),
                ),
            )
        return None

    @classmethod
    def _static_spec_context(
        cls,
        render_inputs: m.Infra.CodegenRenderInputs,
        destination: str,
    ) -> p.Result[p.Model] | None:
        """Resolve the fleet-static and toolchain specs.

        Returns:
            The resulting ``p.Result[p.Model] | None`` where None marks a
            destination outside this group.

        """
        codegen = render_inputs.codegen
        dist = render_inputs.target.repository.distribution
        if destination == c.Infra.PRE_COMMIT_CONFIG_FILENAME:
            return r[p.Model].ok(
                m.Infra.MakeWorkflowRenderSpec(dist=dist, make=codegen.make),
            )
        if destination in {
            c.Infra.MARKDOWNLINT_CONFIG_FILENAME,
            c.Infra.MARKDOWNLINT_IGNORE_FILENAME,
        }:
            return r[p.Model].ok(
                m.Infra.MarkdownLintRenderSpec(tooling=config.Infra.tooling),
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
        if destination == c.Infra.RELEASE_GITLEAKS_CONFIG_PATH:
            # Why: the release build phase snapshots the gitleaks
            # policy from the repository; it is fleet policy owned by
            # config/infra.yaml, never scaffold-only project metadata.
            return r[p.Model].ok(
                m.Infra.ReleasePolicySpec(
                    build_constraints=config.Infra.release.build_constraints,
                ),
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
                ),
            )
        return None

    @classmethod
    def _beads_context(
        cls,
        render_inputs: m.Infra.CodegenRenderInputs,
        destination: str,
    ) -> p.Result[p.Model] | None:
        """Resolve the Beads config and identity-marker specs.

        Returns:
            The resulting ``p.Result[p.Model] | None`` where None marks a
            destination outside this group.

        """
        target = render_inputs.target
        codegen = render_inputs.codegen
        if destination == c.Infra.BEADS_CONFIG_RELPATH:
            if target.beads is None:
                return r[p.Model].fail(
                    "Beads rendering requires enabled Beads identity",
                )
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
                        dict.fromkeys((*project_types, *required_types)),
                    ),
                    dolt_mode=beads.dolt_mode,
                    export_auto=beads.export_auto,
                    backup_enabled=beads.backup_enabled,
                    dolt_disable_event_flush=beads.dolt_disable_event_flush,
                ),
            )
        if destination == c.Infra.BEADS_METADATA_RELPATH:
            if target.beads is None:
                return r[p.Model].fail(
                    "Beads rendering requires enabled Beads identity",
                )
            # Why: this marker is regenerated on every `make gen`, but the
            # ledger identity inside it is owned by the checkout, not by the
            # fleet SSOT. Rendering without it stripped the key, and Beads then
            # minted a NEW identity on next access — a consumer rig lost its
            # identity that way. Read it back so a
            # regeneration is identity-preserving.
            return r[p.Model].ok(
                m.Infra.BeadsMetadataRenderSpec(
                    database=target.beads.database,
                    dolt_mode=codegen.toolchain.beads.dolt_mode,
                    project_id=cls._beads_project_id(render_inputs.target.root),
                ),
            )
        return None

    def _github_context(
        self,
        render_inputs: m.Infra.CodegenRenderInputs,
        destination: str,
    ) -> p.Result[p.Model] | None:
        """Resolve the GitHub workflow render spec for ``.github/`` targets.

        Returns:
            The resulting ``p.Result[p.Model] | None`` where None marks a
            destination outside this group.

        """
        if not destination.startswith(".github/"):
            return None
        target = render_inputs.target
        workspace = render_inputs.workspace
        codegen = render_inputs.codegen
        repository_root = target.root
        dist = target.repository.distribution
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
        resolved_branch = self.render_integration_branch(render_inputs)
        if resolved_branch.failure:
            return r[p.Model].from_failure(resolved_branch)
        branch = resolved_branch.value
        # Forks and local projects never enter the cooldown: they are the
        # requirements this project takes by direct git reference.
        excluded = self.direct_sources(render_inputs)
        if excluded.failure:
            return r[p.Model].from_failure(excluded)
        return r[p.Model].ok(
            m.Infra.GithubWorkflowRenderSpec(
                dist=dist,
                owns_workspace_manifest=(
                    repository_root / "config/workspace.yaml"
                ).is_file(),
                make_profile=target.make_profile,
                gascity_enabled=target.gascity_enabled,
                repository_branch=branch,
                ci_trigger_branches=tuple(
                    dict.fromkeys((
                        *codegen.branch_policy.ci_trigger_branches,
                        branch,
                    )),
                ),
                python_version=codegen.toolchain.python_version,
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
                dependency_cooldown_days=codegen.toolchain.dependency_cooldown_days,
                cooldown_excluded_dependencies=excluded.value,
                checkout_submodules=codegen.checkout_submodules_overrides.get(
                    dist,
                    codegen.checkout_submodules,
                ),
                custom_steps=self._custom_ci_steps(repository_root),
                private_submodules=codegen.ci_private_submodules.get(dist),
                private_dependency_auth=codegen.ci_private_dependency_auth.get(
                    dist,
                ),
                system_packages=tuple(codegen.ci_system_packages.get(dist, ())),
                packages_read=dist in codegen.ci_package_registry_read,
            ),
        )

    def _makefile_group_context(
        self,
        render_inputs: m.Infra.CodegenRenderInputs,
        destination: str,
    ) -> p.Result[p.Model] | None:
        """Resolve the Makefile and custom-Make render specs.

        Returns:
            The resulting ``p.Result[p.Model] | None`` where None marks a
            destination outside this group.

        """
        if destination == c.Infra.MAKEFILE_FILENAME:
            makefile = self._makefile_render_spec(
                render_inputs.target,
                render_inputs.workspace,
                render_inputs.codegen,
            )
            if makefile.failure:
                return r[p.Model].from_failure(makefile)
            return r[p.Model].ok(makefile.value)
        if destination == c.Infra.CUSTOM_MAKE_FILENAME:
            # Existing repositories project custom routes from the same typed
            # Make contract as Makefile; they do not require scaffold-only
            # project metadata.
            make_context = self.make_render_context(render_inputs)
            if make_context.failure:
                return r[p.Model].from_failure(make_context)
            return r[p.Model].ok(make_context.value)
        return None

    def _project_or_pass_context(
        self,
        render_inputs: m.Infra.CodegenRenderInputs,
        project_context: m.Infra.ProjectRenderContext | None,
    ) -> p.Result[p.Model]:
        """Pass a supplied project context through, or derive one on demand.

        Returns:
            The resulting ``p.Result[p.Model]``.

        """
        if project_context is not None:
            return r[p.Model].ok(project_context)
        context_result = self._project_render_context(render_inputs)
        if context_result.failure:
            return r[p.Model].from_failure(context_result)
        return r[p.Model].ok(context_result.value)

    def _makefile_render_spec(
        self,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        codegen: m.Infra.CodegenConfigSpec,
    ) -> p.Result[m.Infra.MakefileRenderSpec]:
        """Resolve Makefile inputs directly from the declared repository topology.

        Returns:
            The resulting ``p.Result[m.Infra.MakefileRenderSpec]``.

        """
        gitlinks = self._managed_gitlinks(
            workspace,
            codegen,
            repository_root=target.root,
        )
        if gitlinks.failure:
            return r[m.Infra.MakefileRenderSpec].from_failure(gitlinks)
        pytest = config.Infra.tooling.tools.pytest
        run_timeout_seconds = pytest.run_timeout_overrides.get(
            target.canonical_project_name,
            pytest.run_timeout_seconds,
        )
        return r[m.Infra.MakefileRenderSpec].ok(
            m.Infra.MakefileRenderSpec(
                pytest=pytest,
                dist=target.repository.distribution,
                infra_cli=config.Infra.name,
                make_profile=target.make_profile,
                package=target.repository.package,
                makefile_custom_include=c.Infra.MAKEFILE_CUSTOM_INCLUDE,
                repository_root_rel=self._repository_root_rel(workspace),
                workspace_subprojects=tuple(
                    item.path.as_posix() for item in workspace.subprojects
                ),
                workspace_gitlinks=gitlinks.value,
                uv_link_mode=self.link_mode(target.repository, codegen.toolchain),
                mise_selector=codegen.toolchain.mise_selector,
                mise_version=codegen.toolchain.mise_version,
                mise_install_tools=codegen.toolchain.mise_install_keys,
                python_version=codegen.toolchain.python_version,
                make=codegen.make,
                extra_verbs=(
                    self._merge_extra_verbs(
                        target.repository.extra_verbs,
                        (
                            ()
                            if target.repository.script_dispatch is None
                            else self._discover_script_verbs(target.root)
                        ),
                        frozenset(verb.name for verb in codegen.make.verbs),
                    )
                ),
                script_dispatch=target.repository.script_dispatch,
                workspace_cli_group=c.Infra.CLI_GROUP_WORKSPACE,
                mypy_timeout_exit_code=c.Infra.PROCESS_TIMEOUT_EXIT_CODE,
                timeout_command=c.Infra.TIMEOUT_COMMAND,
                timeout_kill_after_seconds=c.Infra.TIMEOUT_KILL_AFTER_SECONDS,
                pytest_process_timeout_seconds=(
                    run_timeout_seconds + (pytest.termination_grace_seconds * 2)
                ),
            ),
        )

    @staticmethod
    def _custom_ci_steps(repository_root: Path) -> str:
        """Read the project-owned workflow steps, if the project declares any.

        This is the CI counterpart of ``custom.mk``: the generator injects the
        block verbatim and never interprets it, so a project extends its own
        pipeline without the generator learning that project's concerns.

        Returns:
            The resulting ``str``.

        """
        source: Path = repository_root / c.Infra.CUSTOM_CI_STEPS_FILENAME
        if not source.is_file():
            return ""
        return source.read_text(encoding=c.DEFAULT_ENCODING).rstrip("\n")


__all__: list[str] = ["FlextInfraCodegenConformArtifactRender"]
