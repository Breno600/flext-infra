"""Typed shared owners for codegen tests."""

from __future__ import annotations

from typing import ClassVar

from flext_infra import c, config, m, t


class CodegenTestSupport:
    """Own shared typed construction for codegen test contracts."""

    class Ci:
        """Construct GitHub workflow render contracts from canonical config."""

        # Why: ci_trigger_branches is no longer config-owned (flext-jwpyy.1
        # relocated it from BranchPolicySpec to a per-render derivation in
        # FlextInfraCodegenConform._artifact_render_context). Mirror the exact
        # literal baseline conform.py renders so tests stay in lockstep with
        # production without reading a retired config field.
        CI_TRIGGER_BASELINE_BRANCHES: ClassVar[t.VariadicTuple[str]] = (
            "dev",
            "develop",
            "0.12.0-dev",
            "main",
        )

        @classmethod
        def ci_trigger_branches(cls, repository_branch: str) -> t.VariadicTuple[str]:
            """Reproduce conform.py's deduplicated per-render trigger set."""
            return tuple(
                dict.fromkeys((
                    *cls.CI_TRIGGER_BASELINE_BRANCHES[:-1],
                    repository_branch,
                    cls.CI_TRIGGER_BASELINE_BRANCHES[-1],
                ))
            )

        @staticmethod
        def synthetic_private_submodules() -> m.Infra.CiPrivateSubmodulesSpec:
            """One schema-valid deploy-key contract carrying zero org data.

            The private-submodule init mechanism is proven against this
            synthetic contract instead of any real workspace entry: real
            deploy-key contracts are operator-private config living in the
            gitignored local override layer, never in this public repository.
            """
            key = m.Infra.CiPrivateSubmoduleDeployKeySpec.model_validate({
                "secret": "EXAMPLE_SIBLING_DEPLOY_KEY",
                "submodule": "example-sibling",
                "path": "libs/example-sibling",
                "remote": "git@github.com:example-org/example-sibling.git",
            })
            return m.Infra.CiPrivateSubmodulesSpec(
                known_hosts=("github.com ssh-ed25519 AAAA-public-host-key-line",),
                paths=("libs/example-sibling",),
                deploy_keys=(key,),
            )

        @staticmethod
        def workflow_spec(
            *,
            dist: t.NonEmptyStr,
            make_profile: c.Infra.MakeProfile,
            repository_branch: t.NonEmptyStr,
            ci_trigger_branches: t.VariadicTuple[t.NonEmptyStr],
            system_packages: t.VariadicTuple[t.NonEmptyStr] = (),
            custom_steps: str = "",
            has_devcontainer: bool = False,
            workspace_repositories: t.VariadicTuple[m.Infra.RepositoryRef] = (),
        ) -> m.Infra.GithubWorkflowRenderSpec:
            """Build the common strictly typed workflow rendering contract."""
            codegen = config.Infra.codegen
            return m.Infra.GithubWorkflowRenderSpec(
                dist=dist,
                make_profile=make_profile,
                repository_branch=repository_branch,
                ci_trigger_branches=ci_trigger_branches,
                system_packages=system_packages,
                python_version=codegen.toolchain.python_version,
                state_directory_name=codegen.toolchain.state_directory_name,
                github_actions=codegen.github_actions,
                make=codegen.make,
                workspace_repositories=workspace_repositories,
                checkout_submodules=codegen.checkout_submodules,
                custom_steps=custom_steps,
                has_devcontainer=has_devcontainer,
            )
