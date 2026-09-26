"""Detected repository identity and integration-branch resolution utilities.

flext-infra ships no provider registry: every repository's provider identity
is detected from that repository's own declarations (its workspace manifest,
its live Git origin, and its declared dependency sources), and every branch
is detected from live Git or declared explicitly by a caller.
"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from flext_core import r
from flext_infra import c, m, p, t

from ._git.worktree_discovery import FlextInfraUtilitiesGitWorktreeDiscoveryMixin
from .dependencies import FlextInfraUtilitiesDependencies

_GIT_URL_SCHEME_PREFIX = "git+"


class FlextInfraUtilitiesRepository:
    """Resolve detected identity and branch policy for one governed repository."""

    @staticmethod
    def declared_git_source(requirement: str) -> p.Result[t.Pair[str, str]]:
        """Parse one requirement's declared direct Git source.

        Returns ``(canonical_url, ref)`` for a requirement that declares
        ``name @ git+URL@REF``, or the empty pair when the requirement declares
        no direct source at all. The declared line is the only authority for the
        dependency's canonical URL and branch: canonicalization normalizes the
        transport scheme (``ssh://``, SCP-style, ``http``) to ``https`` and
        never invents an organization, host, or ref. A declared source that is
        not a Git URL, or a Git URL without a ref, fails loudly.
        """
        requirement_part, _, _ = requirement.partition(";")
        head_match = c.Infra.PEP621_REQUIREMENT_HEAD_RE.match(requirement_part.strip())
        if head_match is None:
            return r[t.Pair[str, str]].fail(f"invalid requirement head: {requirement}")
        _, at_separator, source = requirement_part.partition("@")
        if not at_separator:
            # Plain workspace requirement: no direct git source is declared.
            # Success payloads are never None (flext-core result law), so the
            # caller reads the empty pair as "no declared source".
            return r[t.Pair[str, str]].ok(("", ""))
        source = source.strip()
        if not source.startswith(_GIT_URL_SCHEME_PREFIX):
            return r[t.Pair[str, str]].fail(
                f"internal dependency direct source must be a git URL: {requirement}"
            )
        url, ref_separator, ref = source.rpartition("@")
        url = url.removeprefix(_GIT_URL_SCHEME_PREFIX).strip()
        ref = ref.strip()
        if not ref_separator or not ref:
            return r[t.Pair[str, str]].fail(
                f"internal dependency git source must declare a branch or ref: "
                f"{requirement}"
            )
        if url.startswith("https://"):
            canonical = url
        elif url.startswith("http://"):
            canonical = f"https://{url.removeprefix('http://')}"
        elif url.startswith("ssh://"):
            canonical = f"https://{url.removeprefix('ssh://').removeprefix('git@')}"
        elif url.startswith("git@") and ":" in url:
            host, _, path = url.removeprefix("git@").partition(":")
            canonical = f"https://{host}/{path}"
        else:
            return r[t.Pair[str, str]].fail(
                f"internal dependency git source scheme is not canonicalizable "
                f"to HTTPS: {requirement}"
            )
        return r[t.Pair[str, str]].ok((canonical, ref))

    @classmethod
    def configured_repository_ref(
        cls, *, codegen: m.Infra.CodegenConfigSpec, repository_root: Path
    ) -> p.Result[m.Infra.RepositoryRef]:
        """Detect one reference for the infrastructure distribution.

        The URL is detected — never looked up in a catalog — from the first
        declaration the checkout carries: its own project identity (the
        checkout is the infrastructure repository, so its live Git origin
        speaks), a declared direct Git dependency source for the distribution,
        or its workspace manifest ``repository``/``members`` declaration. A
        checkout that declares none fails loudly.
        """
        source = codegen.infra_repository
        distribution = source.distribution
        line = cls.flext_integration_line(
            codegen=codegen, repository_root=repository_root
        )
        if line.failure:
            return r[m.Infra.RepositoryRef].from_failure(line)
        return r[m.Infra.RepositoryRef].ok(
            m.Infra.RepositoryRef(
                name=distribution,
                distribution=distribution,
                url=f"{line.value.base_url}/{distribution}.git",
                path=Path(distribution),
                role=c.Infra.MakeProfile.STANDALONE,
                provider=source.provider,
                kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
                codegen=c.Infra.CodegenKind.CONFORM,
                package=True,
                editable=True,
                read_only=False,
            )
        )

    @classmethod
    def flext_integration_line(
        cls,
        *,
        codegen: m.Infra.CodegenConfigSpec,
        repository_root: Path,
        bootstrap_source: m.Infra.CodegenBootstrapSource | None = None,
    ) -> p.Result[m.Infra.WorkspaceIntegrationSpec]:
        """Detect the FLEXT line (provider base URL and branch) a checkout consumes.

        The line is a fact of the infrastructure dependency, never of the
        consumer's own identity: every internal ``flext-*`` floor renders from
        it, so a repository living in another organization still resolves the
        whole family from one source. It is detected, never cataloged, from the
        first declaration the checkout carries — the infrastructure checkout's
        own origin and integration branch, a declared direct Git source for
        the distribution (URL and ref), or the owning workspace manifest's
        member entry on that workspace's integration branch. Two declared
        sources that disagree, or none at all, fail loudly.

        A fully explicit caller declaration (``declared`` carrying both
        organization and base URL) outranks detection: ``codegen new`` has no
        checkout to detect from — the caller declares the provider and
        integration branch up front, and that declaration is the line. A
        provider key plus branch alone is NOT a line (a consumer's own
        provider identity never fabricates one) and detection still runs.
        """
        from flext_infra import u

        source = codegen.infra_repository
        distribution = source.distribution
        preference = codegen.branch_policy.integration_branch_preference
        if bootstrap_source is not None:
            if (repository_root / c.PYPROJECT_FILENAME).exists():
                return r[m.Infra.WorkspaceIntegrationSpec].fail(
                    "bootstrap provenance cannot replace existing project sources"
                )
            canonical = cls._canonical_https_url(bootstrap_source.url)
            if canonical.failure:
                return r[m.Infra.WorkspaceIntegrationSpec].from_failure(canonical)
            detected = r[t.Pair[str, str]].ok((canonical.value, bootstrap_source.ref))
        else:
            detected = cls._detected_infra_source(
                repository_root=repository_root,
                distribution=distribution,
                preference=preference,
            )
        if detected.failure:
            return r[m.Infra.WorkspaceIntegrationSpec].from_failure(detected)
        url, ref = detected.value
        # The detected source arrives in either canonical form (with or
        # without the .git suffix — GitHub checkouts omit it); normalize
        # before comparing so URL spelling never fails the line detection.
        normalized_url = url.removesuffix(".git")
        suffix = f"/{distribution}"
        if not normalized_url.endswith(suffix):
            return r[m.Infra.WorkspaceIntegrationSpec].fail(
                f"infrastructure source must be the {distribution} repository: {url}"
            )
        organization, separator, _ = u.Infra.git_remote_identity(url).partition("/")
        if not separator:
            return r[m.Infra.WorkspaceIntegrationSpec].fail(
                f"infrastructure source must name an owner and repository: {url}"
            )
        return r[m.Infra.WorkspaceIntegrationSpec].ok(
            m.Infra.WorkspaceIntegrationSpec(
                provider=source.provider,
                branch=ref,
                organization=organization,
                base_url=normalized_url.removesuffix(suffix),
            )
        )

    @classmethod
    def _detected_infra_source(
        cls, *, repository_root: Path, distribution: str, preference: t.StrSequence
    ) -> p.Result[t.Pair[str, str]]:
        """Detect the infrastructure distribution's canonical URL and ref."""
        from flext_infra import u

        metadata = u.Infra.read_project_metadata_result(repository_root)
        if metadata.success and metadata.value.project.name == distribution:
            origin = u.Infra.git_remote_url(
                m.Infra.GitRemoteUrlRequest(
                    repo_root=repository_root, remote=c.Infra.GIT_DEFAULT_REMOTE
                )
            )
            if origin.failure or not origin.value.text.strip():
                return r[t.Pair[str, str]].fail(
                    "the infrastructure checkout must publish a Git origin: "
                    f"{repository_root}"
                )
            branch = cls.resolve_integration_branch(
                repository_root, preference=preference
            )
            if branch.failure:
                return r[t.Pair[str, str]].from_failure(branch)
            canonical = cls._canonical_https_url(origin.value.text.strip())
            if canonical.failure:
                return r[t.Pair[str, str]].from_failure(canonical)
            return r[t.Pair[str, str]].ok((canonical.value, branch.value))
        pyproject_path = repository_root / c.PYPROJECT_FILENAME
        if pyproject_path.is_file():
            declared = cls._declared_dependency_source(
                pyproject_path=pyproject_path,
                distribution=distribution,
                prefix=f"{distribution.partition('-')[0]}-",
            )
            if declared.failure:
                return r[t.Pair[str, str]].from_failure(declared)
            if declared.value[0]:
                return declared
        manifest = cls._manifest_declared_url(
            repository_root=repository_root, distribution=distribution
        )
        if manifest.failure:
            return r[t.Pair[str, str]].from_failure(manifest)
        if manifest.value:
            branch = cls.resolve_integration_branch(
                repository_root, preference=preference
            )
            if branch.failure:
                return r[t.Pair[str, str]].from_failure(branch)
            return r[t.Pair[str, str]].ok((manifest.value, branch.value))
        return r[t.Pair[str, str]].fail(
            f"infrastructure repository {distribution} is undeclared by this "
            f"checkout: no project identity, no direct git dependency source, "
            f"and no workspace manifest entry: {repository_root}"
        )

    @classmethod
    def validate_git_remote_url(cls, url: str) -> p.Result[str]:
        """Return the canonical HTTPS form of one declared Git remote URL.

        A bootstrap declares its remotes before any project metadata exists,
        so an unusable URL must fail here — before a directory or Git effect —
        instead of surfacing later as a generated dependency source.
        """
        return cls._canonical_https_url(url.strip())

    @staticmethod
    def _canonical_https_url(url: str) -> p.Result[str]:
        """Canonicalize one Git remote URL to its HTTPS form, fail loud."""
        if url.startswith("https://"):
            candidate = url
        elif url.startswith("http://"):
            candidate = f"https://{url.removeprefix('http://')}"
        elif url.startswith("ssh://"):
            candidate = f"https://{url.removeprefix('ssh://').removeprefix('git@')}"
        elif url.startswith("git@") and ":" in url:
            host, _, path = url.removeprefix("git@").partition(":")
            candidate = f"https://{host}/{path}"
        else:
            return r[str].fail(f"git remote url is not canonicalizable to HTTPS: {url}")
        # A URL without a host (``https:///repo``) or without a repository
        # path (``https://host``) carries no origin identity: reject it as a
        # declared remote rather than letting a generated source point at it.
        parsed = urlparse(candidate)
        if not parsed.netloc or not parsed.path.strip("/"):
            return r[str].fail(
                f"git remote url must name a host and repository path: {url}"
            )
        return r[str].ok(candidate)

    @classmethod
    def _declared_dependency_source(
        cls, *, pyproject_path: Path, distribution: str, prefix: str
    ) -> p.Result[t.Pair[str, str]]:
        """Return the family line the pyproject declares, as a source for one member.

        Every declared direct Git source of an internal ``{prefix}*``
        dependency names the same line: one provider base URL and one ref. A
        plain (source-less) requirement names a workspace dependency whose URL
        the workspace manifest owns, so it is not a failure here. Members
        declared from different lines in one document are a loud failure —
        the family renders from one source — and the detected line is
        returned as the source of ``distribution``.
        """
        from flext_infra import u

        from .pyproject_conform import FlextInfraUtilitiesPyprojectConform

        # Identity detection consumes the same owner-recovered declaration as
        # metadata and template composition. Raw projection bytes may still
        # carry managed merge blocks while the transaction is only planning.
        text = u.Infra.live_pyproject_text(pyproject_path)
        if text.failure:
            return r[t.Pair[str, str]].from_failure(text)
        payload = u.Cli.toml_mapping_from_text(text.value)
        if payload is None:
            return r[t.Pair[str, str]].fail(
                f"pyproject is not valid TOML: {pyproject_path}"
            )
        requirements: list[str] = []
        project = payload.get(c.Infra.PROJECT)
        if isinstance(project, dict):
            for key in (c.Infra.DEPENDENCIES, c.Infra.OPTIONAL_DEPENDENCIES):
                requirements.extend(
                    FlextInfraUtilitiesPyprojectConform.raw_requirement_values(
                        project.get(key)
                    )
                )
        groups = payload.get(c.Infra.DEPENDENCY_GROUPS)
        if isinstance(groups, dict):
            for group in groups.values():
                requirements.extend(
                    FlextInfraUtilitiesPyprojectConform.raw_requirement_values(group)
                )
        lines: dict[t.Pair[str, str], str] = {}
        for requirement in requirements:
            name = FlextInfraUtilitiesDependencies.dep_name(requirement)
            if name is None or not name.startswith(prefix):
                continue
            parsed = cls.declared_git_source(requirement)
            if parsed.failure:
                return r[t.Pair[str, str]].from_failure(parsed)
            url, ref = parsed.value
            if not url:
                continue
            if not url.startswith("https://"):
                return r[t.Pair[str, str]].fail(
                    "declared internal dependency provenance must be HTTPS: "
                    f"{requirement}"
                )
            suffix = f"/{name}.git"
            if not url.endswith(suffix):
                return r[t.Pair[str, str]].fail(
                    f"internal dependency source must be the {name} repository: "
                    f"{requirement}"
                )
            lines.setdefault((url.removesuffix(suffix), ref), requirement)
        if len(lines) > 1:
            declared = "; ".join(sorted(lines.values()))
            return r[t.Pair[str, str]].fail(
                f"{pyproject_path.name} declares conflicting {prefix}* line sources "
                f"(one family, one provider and ref): {declared}"
            )
        if lines:
            (base_url, ref), _ = next(iter(lines.items()))
            return r[t.Pair[str, str]].ok((f"{base_url}/{distribution}.git", ref))
        # No declared source: absence is an EMPTY payload, never None.
        return r[t.Pair[str, str]].ok(("", ""))

    @staticmethod
    def _manifest_declared_url(
        *, repository_root: Path, distribution: str
    ) -> p.Result[str]:
        """Return the workspace manifest's declared URL for one distribution."""
        from flext_infra.workspace.detector import FlextInfraWorkspaceDetector

        loaded = FlextInfraWorkspaceDetector.load_workspace_manifest(repository_root)
        if loaded.failure:
            return r[str].from_failure(loaded)
        if not loaded.value:
            return r[str].ok("")
        manifest = loaded.value[0]
        candidates = (manifest.repository, *manifest.members)
        for repository in candidates:
            if repository.distribution == distribution:
                return r[str].ok(repository.url)
        # Absence is an EMPTY payload, never None (flext-core result law).
        return r[str | None].ok("")

    @staticmethod
    def repository_provider(
        repository: p.Infra.RepositoryRef,
    ) -> p.Result[m.Infra.ProviderIdentitySpec]:
        """Detect the provider identity a repository declares for itself.

        The name is the key the repository's own manifest declares and the
        organization and base URL are read from that same declaration's
        canonical URL through the ``git_remote_identity`` normalizer. Nothing
        is matched against configured rows and no branch is fabricated here.
        """
        from flext_infra import u

        url = repository.url.strip()
        organization, separator, _ = u.Infra.git_remote_identity(url).partition("/")
        if not separator:
            return r[m.Infra.ProviderIdentitySpec].fail(
                f"repository url must name an owner and repository: {url}"
            )
        if not url.startswith("https://"):
            return r[m.Infra.ProviderIdentitySpec].fail(
                f"provider identity requires a canonical HTTPS declaration url: {url}"
            )
        return r[m.Infra.ProviderIdentitySpec].ok(
            m.Infra.ProviderIdentitySpec(
                name=repository.provider,
                organization=organization,
                base_url=url.removesuffix(".git").rsplit("/", 1)[0],
            )
        )

    @classmethod
    def repository_page_url(cls, repository: p.Infra.RepositoryRef) -> p.Result[str]:
        """Return the provider HTTPS page of one repository, whatever its transport.

        CI rewrites member origins to SSH deploy-key URLs, so the clone URL is
        never a page URL: the page is the declared provider base URL plus the
        repository segment of the transport-stable ``owner/repository`` identity.
        """
        provider = cls.repository_provider(repository)
        if provider.failure:
            return r[str].from_failure(provider)
        owner, separator, name = (
            FlextInfraUtilitiesGitWorktreeDiscoveryMixin.git_remote_identity(
                repository.url
            ).partition("/")
        )
        if not separator or not name or owner != provider.value.organization.casefold():
            return r[str].fail(
                "repository URL does not identify a repository of provider "
                f"{provider.value.name}: {repository.name}"
            )
        return r[str].ok(f"{provider.value.base_url.rstrip('/')}/{name}")

    @classmethod
    def resolve_integration_branch(
        cls,
        repository_root: Path,
        *,
        preference: t.StrSequence,
        declared: str | None = None,
    ) -> p.Result[str]:
        """Return the integration branch one repository integrates on.

        Precedence, every declaration before any Git probe: the repository's
        own manifest (``config/workspace.yaml`` ``integration.branch``); then
        ``declared`` — the declaration that governs this checkout when it
        carries none of its own (its in-memory spec before the manifest is
        written, or the workspace a governed member follows); then the
        published integration line — the local remote-tracking ref, tried in
        the declared preference order — a Git fact independent of the
        checkout. When none exists the failure is loud and no default is
        invented.
        """
        from flext_infra.workspace.detector import FlextInfraWorkspaceDetector

        manifest = FlextInfraWorkspaceDetector.load_workspace_manifest(repository_root)
        if manifest.success and manifest.value:
            integration = manifest.value[0].integration
            if integration is not None:
                return r[str].ok(integration.branch)
        if declared and declared.strip():
            return r[str].ok(declared.strip())
        # The branch a checkout happens to carry is never the answer: a lane
        # rendering its own name into the CI trigger list can never reach a
        # generation fixed point (ADR-018 p.10 — derive from the declaration
        # and from published Git facts, never from the environment).
        baseline = cls.repository_baseline_branch(
            repository_root, preference=tuple(preference) or None
        )
        if baseline.success:
            return r[str].ok(baseline.value)
        return r[str].fail(
            "integration branch must be published by Git: "
            f"{repository_root}: {baseline.error}"
        )

    @staticmethod
    def gitmodule_branch_is_governed(
        declared_branch: str, *, integration_branch: str | None = None
    ) -> bool:
        """Accept follow-superproject (``.``) or the detected integration line."""
        if declared_branch == c.Infra.FOLLOW_SUPERPROJECT_BRANCH:
            return True
        return integration_branch is not None and declared_branch == integration_branch

    @classmethod
    def repository_baseline_branch(
        cls,
        repository_root: Path,
        fallback: str | None = None,
        preference: t.VariadicTuple[str] | None = None,
    ) -> p.Result[str]:
        """Return the integration baseline the repository actually publishes.

        Managed repositories under the same provider legitimately integrate
        on different branches. The baseline is therefore derived from live
        Git: the published remote-tracking integration branch wins.

        ``preference`` is the ordered set of names to try, owned by
        ``codegen.branch_policy.integration_branch_preference`` so a workspace
        declares its own release line instead of asking for a constant in this
        package. Omitting it uses the built-in conventional ordering.

        ``fallback`` carries an explicitly declared default for a repository
        that cannot have published anything yet (project creation). Without
        it, a checkout with no integration branch fails closed instead of
        guessing.
        """
        from flext_infra import u

        candidates = preference or c.Infra.INTEGRATION_BRANCH_PREFERENCE
        for candidate in candidates:
            reference = f"refs/remotes/origin/{candidate}"
            resolved = u.Infra.git_ref_exists(
                m.Infra.GitRefRequest(repo_root=repository_root, reference=reference)
            )
            if resolved.success and resolved.value.value:
                return r[str].ok(candidate)
        if fallback:
            return r[str].ok(fallback)
        return r[str].fail(
            "repository publishes no integration branch "
            f"({', '.join(candidates)}): {repository_root}"
        )

    @staticmethod
    def workspace_spec_load(repository_root: Path) -> p.Result[m.Infra.WorkspaceSpec]:
        """Load governed topology and derive observed external Git dependencies."""
        from flext_infra.workspace.detector import FlextInfraWorkspaceDetector

        return FlextInfraWorkspaceDetector.load_workspace_spec(repository_root)

    @staticmethod
    def repository_conform_target(
        repository_root: Path, workspace: m.Infra.WorkspaceSpec | None = None
    ) -> p.Result[m.Infra.RepositoryConformTarget]:
        """Return typed effective policy inferred from live repository topology."""
        from flext_infra.workspace.detector import FlextInfraWorkspaceDetector

        resolved_workspace = workspace
        if resolved_workspace is None:
            loaded = FlextInfraWorkspaceDetector.load_workspace_spec(repository_root)
            if loaded.failure:
                return r[m.Infra.RepositoryConformTarget].from_failure(loaded)
            resolved_workspace = loaded.value
        return FlextInfraWorkspaceDetector.conform_target(
            repository_root, resolved_workspace
        )


__all__: t.VariadicTuple[str] = ("FlextInfraUtilitiesRepository",)
