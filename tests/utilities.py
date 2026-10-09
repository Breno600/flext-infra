"""Test utilities for flext-infra.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from flext_tests import FlextTestsUtilities, tm

from flext_infra import FlextInfraUtilities, config, r
from flext_infra.codegen import FlextInfraCodegenConform
from tests import c, m, p, t
from tests.utilities_codegen import TestsFlextInfraUtilitiesCodegenMixin
from tests.utilities_deps import TestsFlextInfraUtilitiesDepsMixin
from tests.utilities_fixture_docs import TestsFlextInfraUtilitiesDocsFixtureMixin
from tests.utilities_fixture_project import TestsFlextInfraUtilitiesProjectFixtureMixin
from tests.utilities_fixture_tooling import TestsFlextInfraUtilitiesToolingFixtureMixin
from tests.utilities_fixture_workspace import (
    TestsFlextInfraUtilitiesWorkspaceFixtureMixin,
)
from tests.utilities_gates import TestsFlextInfraUtilitiesGatesMixin
from tests.utilities_git import TestsFlextInfraUtilitiesGitMixin
from tests.utilities_hermetic_git import TestsFlextInfraUtilitiesHermeticGitMixin
from tests.utilities_promoted import TestsFlextInfraUtilitiesPromotedMixin
from tests.utilities_release import TestsFlextInfraUtilitiesReleaseMixin
from tests.utilities_toml import TestsFlextInfraUtilitiesTomlMixin
from tests.utilities_workspace_env import TestsFlextInfraUtilitiesWorkspaceEnvMixin


class TestsFlextInfraUtilities(FlextTestsUtilities, FlextInfraUtilities):
    """Typed test utilities for flext-infra."""

    class CodegenTestSupport:
        """Own shared typed construction for codegen test contracts."""

        class Ci:
            """Construct GitHub workflow render contracts from canonical config."""

            @staticmethod
            def ci_trigger_branches(repository_branch: str) -> t.VariadicTuple[str]:
                """Derive the repository trigger set from the configured policy.

                Returns:
                    The resulting ``t.VariadicTuple[str]``.

                """
                return tuple(
                    dict.fromkeys((
                        *config.Infra.codegen.branch_policy.ci_trigger_branches,
                        repository_branch,
                    )),
                )

            @staticmethod
            def synthetic_private_submodules() -> m.Infra.CiPrivateSubmodulesSpec:
                """One schema-valid deploy-key contract carrying zero org data.

                The private-submodule init mechanism is proven against this
                synthetic contract instead of any real workspace entry: real
                deploy-key contracts are operator-private config living in the
                gitignored local override layer, never in this public repository.

                Returns:
                    The resulting ``m.Infra.CiPrivateSubmodulesSpec``.

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
                packages_read: bool = False,
                custom_steps: str = "",
                has_devcontainer: bool = False,
                workspace_repositories: t.VariadicTuple[m.Infra.RepositoryRef] = (),
                cooldown_excluded_dependencies: t.VariadicTuple[t.NonEmptyStr] = (),
            ) -> m.Infra.GithubWorkflowRenderSpec:
                """Build the common strictly typed workflow rendering contract.

                Returns:
                    The resulting ``m.Infra.GithubWorkflowRenderSpec``.

                """
                codegen = config.Infra.codegen
                return m.Infra.GithubWorkflowRenderSpec(
                    dist=dist,
                    make_profile=make_profile,
                    repository_branch=repository_branch,
                    ci_trigger_branches=ci_trigger_branches,
                    system_packages=system_packages,
                    packages_read=packages_read,
                    python_version=codegen.toolchain.python_version,
                    github_actions=codegen.github_actions,
                    make=codegen.make,
                    workspace_repositories=workspace_repositories,
                    checkout_submodules=codegen.checkout_submodules,
                    custom_steps=custom_steps,
                    has_devcontainer=has_devcontainer,
                    dependency_cooldown_days=codegen.toolchain.dependency_cooldown_days,
                    cooldown_excluded_dependencies=cooldown_excluded_dependencies,
                )

            @staticmethod
            def ci_job_steps(rendered: str) -> t.VariadicTuple[t.JsonMapping]:
                """Parse the rendered ci workflow into its ordered job steps.

                One owner for the YAML parse and the jobs/ci/steps navigation every
                CI-contract test shares; consumers assert on the returned steps.

                Returns:
                    The resulting ``t.VariadicTuple[t.JsonMapping]``.

                Raises:
                    TypeError: If workflow job steps must be a sequence.

                """
                document = t.Cli.JSON_MAPPING_ADAPTER.validate_python(
                    tm.ok(u.Cli.yaml_parse(rendered)),
                )
                jobs = t.Cli.JSON_MAPPING_ADAPTER.validate_python(document["jobs"])
                job = t.Cli.JSON_MAPPING_ADAPTER.validate_python(jobs["ci"])
                steps = job["steps"]
                if not isinstance(steps, list):
                    msg = "workflow job steps must be a sequence"
                    raise TypeError(msg)
                return tuple(
                    t.Cli.JSON_MAPPING_ADAPTER.validate_python(step) for step in steps
                )

    class Tests(
        TestsFlextInfraUtilitiesTomlMixin,
        TestsFlextInfraUtilitiesProjectFixtureMixin,
        TestsFlextInfraUtilitiesWorkspaceFixtureMixin,
        TestsFlextInfraUtilitiesToolingFixtureMixin,
        TestsFlextInfraUtilitiesDocsFixtureMixin,
        TestsFlextInfraUtilitiesPromotedMixin,
        TestsFlextInfraUtilitiesReleaseMixin,
        TestsFlextInfraUtilitiesGitMixin,
        TestsFlextInfraUtilitiesHermeticGitMixin,
        TestsFlextInfraUtilitiesGatesMixin,
        TestsFlextInfraUtilitiesCodegenMixin,
        TestsFlextInfraUtilitiesDepsMixin,
        TestsFlextInfraUtilitiesWorkspaceEnvMixin,
        FlextTestsUtilities.Tests,
    ):
        """Canonical test helper namespace."""

        @staticmethod
        def number(value: t.JsonValue) -> float:
            """Narrow one parsed payload value to a real number.

            Returns:
                The resulting ``float``.

            Raises:
                TypeError: If payload value is not a number.

            """
            tm.that(isinstance(value, (int, float)), eq=True)
            if not isinstance(value, (int, float)):
                msg = "payload value is not a number"
                raise TypeError(msg)
            return float(value)

        @staticmethod
        def json_payload(content: str) -> t.JsonMapping:
            """Parse JSON text through the canonical reader and narrow it.

            Returns:
                The resulting ``t.JsonMapping``.

            """
            return TestsFlextInfraUtilitiesTomlMixin.toml_mapping(
                tm.ok(u.Cli.json_loads(content)),
            )

        @staticmethod
        def toml_payload(content: str) -> t.JsonMapping:
            """Parse TOML text through the canonical reader, never ``tomllib``.

            The facade returns an absent mapping for unparseable text; a test
            that asked for a payload has already decided the text is one, so
            the absence is a defect rather than a value to carry forward.

            Returns:
                The resulting ``t.JsonMapping``.

            Raises:
                ValueError: If TOML payload is not parseable.

            """
            parsed = u.Cli.toml_mapping_from_text(content)
            if parsed is None:
                msg = "TOML payload is not parseable"
                raise ValueError(msg)
            return parsed

        @staticmethod
        def render_make_environment(
            tmp_path: Path,
            profile: c.Infra.MakeProfile,
            *,
            bootstrap: bool = False,
            package: bool = True,
            extra_verbs: t.VariadicTuple[m.Infra.MakeVerbSpec] = (),
            script_dispatch: m.Infra.ScriptDispatchSpec | None = None,
        ) -> t.Pair[Path, Path]:
            """Build the generated Make and activation fixture consumed by real verbs.

            Returns:
                The resulting ``t.Pair[Path, Path]``.

            """
            role = c.Infra.MakeProfile(profile.value)
            repository = u.Tests.repository_ref(
                "fixture-project",
                role=role,
            ).model_copy(
                update={
                    "editable": True,
                    "package": package,
                    "extra_verbs": extra_verbs,
                    "script_dispatch": script_dispatch,
                },
            )
            project_root = tmp_path / profile.value / "fixture-project"
            u.Tests.WorktreeFixture.write_python_project(
                project_root,
                repository.distribution,
            )
            # The generated Makefile consumes the tracked Mise launcher for every
            # verb (setup/check/fix/...), not only at bootstrap: the
            # fixture must carry the governed toolchain seeds exactly as a managed
            # repository does, or the very first mise exec dies with exit 127.
            u.Tests.copy_tracked_mise_seeds(project_root)
            if bootstrap:
                tm.ok(
                    u.Cli.atomic_write_text_file(
                        project_root / config.Infra.codegen.scaffold.project.readme,
                        "# Bootstrap environment contract\n",
                    ),
                )
            beads = u.Tests.beads_project(repository.distribution)
            u.Tests.write_beads_project(
                project_root,
                workspace=beads.workspace,
                database=beads.database,
                issue_prefix=beads.issue_prefix,
            )
            u.Tests.initialize_git_repo(project_root, origin_url=repository.url)
            u.Tests.provider(repository.provider)
            baseline = tm.ok(
                u.Cli.capture(["git", "rev-parse", "HEAD"], cwd=project_root),
            )
            tm.ok(
                u.Cli.run_checked(
                    ["git", "config", "remote.origin.skipDefaultUpdate", "true"],
                    cwd=project_root,
                ),
            )
            tm.ok(
                u.Cli.run_checked(
                    [
                        "git",
                        "update-ref",
                        f"refs/remotes/origin/{u.Tests.provider_branch()}",
                        baseline,
                    ],
                    cwd=project_root,
                ),
            )
            repository_root = project_root
            workspace = u.Tests.workspace_spec(
                repository,
                project=u.Tests.project_spec("fixture-project"),
            )
            request = u.Tests.conform_request(
                project_root,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.CHECK,
            )
            plan = tm.ok(
                FlextInfraCodegenConform(
                    repository_root=repository_root,
                    request=request,
                    initial_workspace=workspace,
                ).plan(request),
            )
            # Materialize the complete activation contract through its guarded
            # publisher, including Beads metadata consumed by the generated .envrc
            # and the Mise lock publisher the generated upg recipe runs.
            paths = {
                project_root / c.Infra.MAKEFILE_FILENAME,
                project_root / ".envrc",
                project_root / "bin" / "mise-lock-transaction.py",
                project_root / "bin" / "mise-lock-converge.py",
            }
            if bootstrap:
                paths.update(
                    project_root / name
                    for name in (c.PYPROJECT_FILENAME, c.Infra.MISE_TOML_FILENAME)
                )
            artifacts = tuple(
                file
                for file in plan.files
                if file.path in paths
                or (
                    c.Infra.BEADS_DIRNAME in file.path.parts
                    and project_root in file.path.parents
                    and file.desired_content is not None
                )
            )
            tm.that(paths <= {file.path for file in artifacts}, eq=True)
            tm.ok(
                u.Tests.materialize_codegen_plans(
                    r[tuple[m.Infra.CodegenFilePlan, ...]].ok(artifacts),
                ),
            )
            if bootstrap:
                # Exercise the documented custom-handler/hook boundary with real
                # Python and installed metadata, never a substitute tool executable.
                tm.ok(
                    u.Cli.atomic_write_text_file(
                        project_root / "custom.mk",
                        ".PHONY: pre-setup post-setup _custom-status\n"
                        "pre-setup:\n"
                        '\t@test ! -L "$(RUNTIME_VENV)"\n'
                        "post-setup:\n"
                        '\t@test "$$MAKE_ACTIVATION_PROOF" = "$(PROJECT_ROOT)"\n'
                        '\t@test -x "$(MAKE_COMMAND)"\n'
                        '\t@test "$(MAKE_COMMAND)" = "$(SELF_MAKE_EXECUTABLE)"\n'
                        "\t@$(UV_RUN) python -c 'import importlib.metadata, sys; "
                        "from pathlib import Path; import tomllib; "
                        'project = tomllib.loads(Path("pyproject.toml").read_text())'
                        '["project"]; '
                        'assert Path(sys.prefix) == Path("$(RUNTIME_VENV)"); '
                        'assert importlib.metadata.version(project["name"]) == '
                        'project["version"]; print("installed-runtime-verified")'
                        "'\n"
                        "_custom-status:\n"
                        "\t@printf '%s\\n' "
                        "'FLEXT_INFRA_PYTHON=$(FLEXT_INFRA_PYTHON)' "
                        "'UV_PROJECT_ENVIRONMENT=$(UV_PROJECT_ENVIRONMENT)' "
                        "'VIRTUAL_ENV=$(VIRTUAL_ENV)' 'PATH=$(PATH)'\n"
                        "\t@command -v python\n"
                        "\t@$(UV_RUN) python -c 'import os, sys; "
                        'print(sys.prefix); print(os.environ["UV_PROJECT_ENVIRONMENT"])'
                        "'\n",
                    ),
                )
                (project_root / ".envrc.local").write_text(
                    'export MAKE_ACTIVATION_PROOF="$PROJECT_ROOT"\n',
                    encoding="utf-8",
                )
            else:
                tm.ok(
                    u.Cli.run_checked(
                        ["direnv", "allow", str(project_root)],
                        cwd=project_root,
                    ),
                )
            return project_root, repository_root

        @staticmethod
        def resolved_make_checkout(
            template: Path,
            parent: Path,
            profile: c.Infra.MakeProfile,
        ) -> Path:
            """Check out a resolved ``make upg`` template as a fresh repository.

            The checkout carries the source and locks the upgrade wrote, never
            the template's environment or Git store; frozen setup provisions
            its own environment from those locks.

            Returns:
                The resulting ``Path``.

            """
            root = parent / profile.value / template.name
            shutil.copytree(
                template,
                root,
                symlinks=True,
                ignore=shutil.ignore_patterns(".venv", ".git"),
            )
            u.Tests.initialize_git_repo(
                root,
                origin_url=u.Tests.repository_ref(root.name, role=profile).url,
            )
            tm.ok(
                u.Cli.run_checked(
                    ["git", "config", "remote.origin.skipDefaultUpdate", "true"],
                    cwd=root,
                ),
            )
            tm.that((root / ".venv").exists(), eq=False)
            return root

        @staticmethod
        def hostile_uv_environment(hostile_venv: Path) -> t.StrMapping:
            """Point every uv and interpreter selector at a foreign environment.

            Returns:
                The resulting ``t.StrMapping``.

            """
            hostile_bin = hostile_venv / "bin"
            return {
                "PATH": f"{hostile_bin}:{os.environ['PATH']}",
                "UV": str(hostile_bin / "uv"),
                "UV_BIN": str(hostile_bin / "uv"),
                "UV_PROJECT": str(hostile_venv.parent),
                "UV_PROJECT_ENVIRONMENT": str(hostile_venv),
                "FLEXT_INFRA_PYTHON": str(hostile_bin / "python"),
                "VIRTUAL_ENV": str(hostile_venv),
            }

        @staticmethod
        def command_receipt(path: Path) -> m.Cli.CommandOutput:
            """Read one recorded provisioning command outcome.

            Returns:
                The resulting ``m.Cli.CommandOutput``.

            """
            return m.Cli.CommandOutput.model_validate_json(
                path.read_text(encoding="utf-8"),
            )

        @staticmethod
        def infra_source_checkout(parent: Path) -> Path:
            """Copy this repository's Git-visible inputs into a fresh Git checkout.

            Returns:
                The resulting ``Path``.

            """
            source = Path(__file__).resolve().parents[1]
            root = parent / config.Infra.name
            paths = tm.not_none(u.Infra.git_tracked_scope_paths(source))
            tm.that(bool(paths), eq=True)
            for path in paths:
                destination = root / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                _ = shutil.copy2(path, destination, follow_symlinks=False)
            tm.that((root / ".venv").exists(), eq=False)
            u.Tests.initialize_git_repo(
                root,
                origin_url=u.Tests.repository_ref(config.Infra.name).url,
            )
            return root

        @staticmethod
        def materialize_docs_bundle(
            bundle: m.Infra.DocsGenerationBundle,
        ) -> p.Result[bool]:
            """Publish one immutable docs bundle through atomic file primitives.

            Returns:
                The resulting ``p.Result[bool]``.

            """
            required = u.Infra.docs_required_directories(bundle)
            if required.failure:
                return r[bool].from_failure(required)
            for directory in required.value:
                directory_plan = u.Cli.atomic_plan_directory_chain(directory)
                if directory_plan.failure:
                    return r[bool].from_failure(directory_plan)
                if directory_plan.value.directories:
                    created = u.Cli.atomic_create_directory_chain_guarded(
                        directory_plan.value,
                        permission_mode=0o755,
                    )
                    if created.failure:
                        return r[bool].from_failure(created)
            return TestsFlextInfraUtilities.Tests.materialize_codegen_plans(
                u.Infra.docs_file_plans(bundle),
            )

        @staticmethod
        def write_package_init(directory: Path, content: str) -> Path:
            """Materialize one importable package initializer under a test root.

            Returns:
                The resulting ``Path``.

            """
            directory.mkdir(parents=True, exist_ok=True)
            init_file = directory / c.Infra.INIT_PY
            init_file.write_text(content, encoding=c.Infra.ENCODING_DEFAULT)
            return init_file


u = TestsFlextInfraUtilities

__all__: list[str] = ["TestsFlextInfraUtilities", "u"]
