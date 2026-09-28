"""Generated Make environment isolation contract."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m, u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import u as test_u
from tests.unit.workspace import WorktreeFixture

pytestmark = pytest.mark.slow


class TestsCodegenMakeEnvironment:
    """Prove generated operations ignore the caller shell environment."""

    @staticmethod
    def _render_makefile(
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
        *,
        local_infra: bool = False,
        bootstrap: bool = False,
        extra_verbs: tuple[m.Infra.MakeVerbSpec, ...] = (),
        script_dispatch: m.Infra.ScriptDispatchSpec | None = None,
    ) -> tuple[Path, Path]:
        role = c.Infra.MakeProfile(profile.value)
        repository = test_u.Tests.repository_ref(
            "fixture-project", role=role
        ).model_copy(
            update={
                "editable": True,
                "extra_verbs": extra_verbs,
                "script_dispatch": script_dispatch,
            }
        )
        project_root = tmp_path / profile.value / "fixture-project"
        WorktreeFixture.write_python_project(project_root, repository.distribution)
        if bootstrap:
            test_u.Tests.copy_tracked_mise_seeds(project_root)
            tm.ok(
                u.Cli.atomic_write_text_file(
                    project_root / config.Infra.codegen.scaffold.project.readme,
                    "# Bootstrap environment contract\n",
                )
            )
        beads = test_u.Tests.beads_project(repository.distribution)
        test_u.Tests.write_beads_project(
            project_root,
            workspace=beads.workspace,
            database=beads.database,
            issue_prefix=beads.issue_prefix,
        )
        test_u.Tests.initialize_git_repo(project_root, origin_url=repository.url)
        provider = test_u.Tests.provider(repository.provider)
        baseline = tm.ok(u.Cli.capture(["git", "rev-parse", "HEAD"], cwd=project_root))
        tm.ok(
            u.Cli.run_checked(
                ["git", "config", "remote.origin.skipDefaultUpdate", "true"],
                cwd=project_root,
            )
        )
        tm.ok(
            u.Cli.run_checked(
                [
                    "git",
                    "update-ref",
                    f"refs/remotes/origin/{provider.branch}",
                    baseline,
                ],
                cwd=project_root,
            )
        )
        repository_root = project_root
        infra_repositories = (test_u.Tests.repository_ref(config.Infra.name),)
        local_subprojects = (
            (infra_repositories[0].model_copy(update={"path": Path("infra-engine")}),)
            if local_infra
            else ()
        )
        workspace = m.Infra.WorkspaceSpec(
            name="fixture-project",
            beads=test_u.Tests.beads_project("fixture-project"),
            repository=repository,
            project=test_u.Tests.project_spec("fixture-project"),
            subprojects=local_subprojects,
        )
        request = test_u.Tests.conform_request(
            project_root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        plan = tm.ok(
            FlextInfraCodegenConform(
                repository_root=repository_root,
                request=request,
                initial_workspace=workspace,
            ).plan(request)
        )
        makefile = next(
            file for file in plan.files if file.path.name == c.Infra.MAKEFILE_FILENAME
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                project_root / "Makefile", test_u.Tests.codegen_file_text(makefile)
            )
        )
        # The generated project environment is owned by two projections, not
        # one: the Makefile owns the runtime binding of every verb, and .envrc
        # owns the interactive shell's view of the same state roots. Writing
        # only the Makefile made an environment guarantee untestable the moment
        # it moved between the two owners.
        envrc = next(file for file in plan.files if file.path.name == ".envrc")
        tm.ok(
            u.Cli.atomic_write_text_file(
                project_root / ".envrc", test_u.Tests.codegen_file_text(envrc)
            )
        )
        if bootstrap:
            for relative in (c.Infra.PYPROJECT_FILENAME, c.Infra.MISE_TOML_FILENAME):
                artifact = next(
                    file for file in plan.files if file.path == project_root / relative
                )
                tm.ok(
                    u.Cli.atomic_write_text_file(
                        artifact.path, test_u.Tests.codegen_file_text(artifact)
                    )
                )
            # Exercise the documented custom-handler/hook boundary with real
            # Python and installed metadata, never a substitute tool executable.
            tm.ok(
                u.Cli.atomic_write_text_file(
                    project_root / "custom.mk",
                    ".PHONY: pre-setup post-setup _custom-status\n"
                    "pre-setup:\n"
                    '\t@test ! -e "$(RUNTIME_PYTHON)"\n'
                    "post-setup:\n"
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
                )
            )
        return project_root, repository_root

    @pytest.mark.parametrize(
        "profile", [c.Infra.MakeProfile.WORKSPACE, c.Infra.MakeProfile.STANDALONE]
    )
    def test_generated_make_uses_profile_runtime_venv_under_hostile_env(
        self, tmp_path: Path, profile: c.Infra.MakeProfile
    ) -> None:
        """Every generated shell receives the profile-resolved runtime venv."""
        project_root, runtime_root = self._render_makefile(
            tmp_path, profile, bootstrap=True
        )
        if profile == c.Infra.MakeProfile.STANDALONE:
            # Without Make's explicit binding, uv selects this parent's default
            # .venv even when --project names the member checkout.
            tm.ok(
                u.Cli.atomic_write_text_file(
                    project_root.parent / "pyproject.toml",
                    f'[tool.uv.workspace]\nmembers = ["{project_root.name}"]\n',
                )
            )
        setup = tm.ok(
            test_u.Tests.run_isolated_make(
                ["--no-print-directory", "setup", "APPLY=Y"], cwd=project_root
            )
        )
        tm.that(
            u.Cli.process_succeeded(setup.outcome),
            eq=True,
            msg=setup.stdout + setup.stderr,
        )
        tm.that(setup.stdout, has="installed-runtime-verified")
        runtime_bin = runtime_root / ".venv" / "bin"
        runtime_python = runtime_bin / "python"
        tm.that(runtime_python.is_file(), eq=True)
        hostile_venv = tmp_path / "hostile" / ".venv"
        hostile_bin = hostile_venv / "bin"
        hostile_bin.mkdir(parents=True)
        hostile_python = hostile_bin / "python"
        active_env = {
            "FLEXT_INFRA_PYTHON": str(hostile_python),
            "UV_PROJECT_ENVIRONMENT": str(hostile_venv),
            "VIRTUAL_ENV": str(hostile_venv),
            "PATH": f"{hostile_bin}:{os.environ['PATH']}",
        }
        process = tm.ok(
            test_u.Tests.run_isolated_make(
                ["--no-print-directory", "status"], cwd=project_root, env=active_env
            )
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stderr or process.stdout or "make probe failed without output",
        )
        output = process.stdout.strip().splitlines()
        tm.that(output[0], eq=f"FLEXT_INFRA_PYTHON={runtime_python}")
        tm.that(output[1], eq=f"UV_PROJECT_ENVIRONMENT={runtime_root / '.venv'}")
        tm.that(output[2], eq=f"VIRTUAL_ENV={runtime_root / '.venv'}")
        # The generated shell PREPENDS the profile runtime bin and REMOVES the
        # caller's active venv bin, preserving every other caller entry in
        # order. Byte equality with the caller PATH is not the contract and
        # never was: whatever launched make — a tool shim, a wrapper — may
        # legitimately have inserted its own managed bin dir before make read
        # the environment at all, and that entry is not the hostile venv.
        path_entries = output[3].removeprefix("PATH=").split(os.pathsep)
        tm.that(path_entries[0], eq=str(runtime_bin))
        tm.that(str(hostile_bin) in path_entries, eq=False)
        surviving = iter(path_entries[1:])
        tm.that(
            all(
                any(entry == candidate for candidate in surviving)
                for entry in os.environ["PATH"].split(os.pathsep)
            ),
            eq=True,
        )
        tm.that(output[4], eq=str(runtime_python))
        tm.that(output[5:], eq=[str(runtime_root / ".venv")] * 2)
        tm.that(hostile_python.exists(), eq=False)
        tm.that((project_root.parent / ".venv").exists(), eq=False)

    @pytest.mark.parametrize(
        "profile", [c.Infra.MakeProfile.STANDALONE, c.Infra.MakeProfile.WORKSPACE]
    )
    def test_setup_provisions_environment_before_project_runtime(
        self, tmp_path: Path, profile: c.Infra.MakeProfile
    ) -> None:
        """Setup creates the venv and syncs dependencies before any runtime use."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, profile, bootstrap=True
        )
        hostile_venv = tmp_path / "hostile" / ".venv"
        hostile_bin = hostile_venv / "bin"
        hostile_bin.mkdir(parents=True)
        hostile_uv = hostile_bin / "uv"
        sentinel = hostile_venv / "sentinel"
        sentinel.write_text("untouched\n", encoding="utf-8")
        active_env = {
            "PATH": f"{hostile_bin}:{os.environ['PATH']}",
            "UV": str(hostile_uv),
            "UV_BIN": str(hostile_uv),
            "UV_PROJECT": str(hostile_venv.parent),
            "UV_PROJECT_ENVIRONMENT": str(hostile_venv),
            "FLEXT_INFRA_PYTHON": str(hostile_bin / "python"),
            "VIRTUAL_ENV": str(hostile_venv),
        }
        tm.that((project_root / ".venv").exists(), eq=False)
        process = tm.ok(
            test_u.Tests.run_isolated_make(
                ["--no-print-directory", "setup", "APPLY=Y"],
                cwd=project_root,
                env=active_env,
            )
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tm.that(process.stdout, has="installed-runtime-verified")
        tm.that((project_root / ".venv" / "pyvenv.cfg").is_file(), eq=True)
        tm.that((project_root / "uv.lock").is_file(), eq=True)
        tm.that(sentinel.read_text(encoding="utf-8"), eq="untouched\n")
        tm.that(tuple(hostile_bin.iterdir()), eq=())
        tm.that((hostile_venv / "pyvenv.cfg").exists(), eq=False)
        tm.that((hostile_venv.parent / "uv.lock").exists(), eq=False)

        # A current lock is accepted in CI; a new runtime declaration must fail
        # before post-setup, not provision the previous graph via --frozen.
        make = config.Infra.codegen.make
        tm.ok(
            u.Cli.atomic_write_text_file(
                project_root / "custom.mk",
                ".PHONY: post-setup\npost-setup:\n"
                '\t@test -x "$(MAKE_COMMAND)"\n'
                '\t@test "$(MAKE_COMMAND)" = "$(SELF_MAKE_EXECUTABLE)"\n'
                f'\t@test "$({make.apply_variable})" = "{make.apply_value}"\n'
                f'\t@test "$({make.ci.variable})" = "{make.ci.value}"\n'
                "\t@printf '%s\\n' 'ci-runtime-provisioned'\n",
            )
        )
        ci_env = {**active_env, make.ci.variable: make.ci.value}
        locked = tm.ok(
            test_u.Tests.run_isolated_make(
                ["--no-print-directory", "setup", "APPLY=Y"],
                cwd=project_root,
                env=ci_env,
            )
        )
        tm.that(
            u.Cli.process_succeeded(locked.outcome),
            eq=True,
            msg=locked.stdout + locked.stderr,
        )
        tm.that(locked.stdout, has="ci-runtime-provisioned")
        lock_path = project_root / "uv.lock"
        lock_before = lock_path.read_bytes()
        dependency_root = tmp_path / "external-runtime"
        WorktreeFixture.write_python_project(dependency_root, "external-runtime")
        pyproject_path = project_root / c.Infra.PYPROJECT_FILENAME
        document = test_u.Tests.toml_doc(pyproject_path.read_text(encoding="utf-8"))
        project = tm.not_none(u.Cli.toml_table_child(document, "project"))
        project["dependencies"] = [
            *u.Cli.toml_as_string_list(u.Cli.toml_value(project, "dependencies")),
            f"external-runtime @ {dependency_root.as_uri()}",
        ]
        tm.ok(u.Cli.atomic_write_text_file(pyproject_path, u.Cli.toml_dumps(document)))
        stale = tm.ok(
            test_u.Tests.run_isolated_make(
                ["--no-print-directory", "setup", "APPLY=Y"],
                cwd=project_root,
                env=ci_env,
            )
        )
        tm.that(u.Cli.process_succeeded(stale.outcome), eq=False)
        tm.that(stale.stdout + stale.stderr, has="--locked")
        tm.that(stale.stdout, lacks="ci-runtime-provisioned")
        tm.that(lock_path.read_bytes(), eq=lock_before)

    def test_setup_fails_when_the_tracked_mise_launcher_is_missing(
        self, tmp_path: Path
    ) -> None:
        """Never substitute a system Mise for the generated launcher owner."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        tool_bin = tmp_path / "managed-tools" / "bin"
        mise_log = tmp_path / "mise.log"
        mise = tool_bin / "mise"
        test_u.Tests.write_executable(
            mise, f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{mise_log}'\nexit 0\n"
        )

        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "setup"],
                cwd=project_root,
                env={"PATH": f"{tool_bin}:{os.environ['PATH']}"},
                remove_env_keys=(*c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS, "UV"),
            )
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(process.stdout + process.stderr, has="missing generated mise launcher")
        tm.that(mise.is_file(), eq=True)
        tm.that(mise_log.exists(), eq=False)
        tm.that((project_root / ".venv").exists(), eq=False)

    def test_dispatched_runner_preserves_provisioned_external_tools(
        self, tmp_path: Path
    ) -> None:
        """Keep managed tools reachable while removing the hostile active venv."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        hostile_venv = tmp_path / "hostile" / ".venv"
        hostile_bin = hostile_venv / "bin"
        hostile_bin.mkdir(parents=True)
        provisioned_bin = tmp_path / "provisioned" / "bin"
        provisioned_bin.mkdir(parents=True)
        fixture_tool = "managed-tool"
        runtime_python = project_root / ".venv" / "bin" / "python"
        tool_log = tmp_path / "tools.log"
        for bin_root in (hostile_bin, provisioned_bin):
            test_u.Tests.write_executable(
                bin_root / fixture_tool,
                f"#!/bin/sh\nprintf '%s\\n' '{bin_root / fixture_tool}'\n",
            )
        test_u.Tests.write_executable(hostile_bin / "uv", "#!/bin/sh\nexit 99\n")
        test_u.Tests.write_executable(
            provisioned_bin / "uv", f"#!/bin/sh\nexec '{runtime_python}'\n"
        )
        test_u.Tests.write_executable(
            runtime_python,
            (
                "#!/bin/sh\n"
                'test -z "${PROJECT_ROOT+x}" || exit 98\n'
                f"command -v uv > '{tool_log}'\n"
                f"command -v {fixture_tool} >> '{tool_log}'\n"
            ),
        )
        active_env = {
            "PATH": f"{hostile_bin}:{provisioned_bin}:{os.environ['PATH']}",
            "PROJECT_ROOT": str(tmp_path / "hostile-project-root"),
            "VIRTUAL_ENV": str(hostile_venv),
        }

        # `test` declares requires_apply in the typed Make owner, so the verb
        # only runs once the write-enable token is present.
        apply_variable = config.Infra.codegen.make.apply_variable
        apply_value = config.Infra.codegen.make.apply_value
        process = tm.ok(
            u.Cli.run_raw(
                [
                    c.Infra.MAKE,
                    "--no-print-directory",
                    "test",
                    f"{apply_variable}={apply_value}",
                ],
                cwd=project_root,
                env=active_env,
                remove_env_keys=(*c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS, "UV"),
            )
        )

        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tools = tool_log.read_text(encoding="utf-8").splitlines()
        tm.that(
            tools, eq=[str(provisioned_bin / "uv"), str(provisioned_bin / fixture_tool)]
        )

    def test_generated_operations_bind_uv_to_runtime_root(self, tmp_path: Path) -> None:
        """All generated uv operations use the profile-owned environment."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        makefile = (project_root / "Makefile").read_text()

        tm.that(
            "override UV_PROJECT_ENVIRONMENT := $(RUNTIME_VENV)" in makefile, eq=True
        )
        tm.that("UV ?= uv" in makefile, eq=True)
        # UV_RUN's environment binding is exercised by the real runtime test
        # above, including a parent uv workspace with a different default venv.
        toolchain = config.Infra.codegen.toolchain
        # The state root is a SIBLING of the checkout, never a directory inside
        # it: derived from the Makefile's own PROJECT_ROOT so a verb invoked
        # from a foreign CWD still writes beside the tree that owns the verb.
        tm.that(
            (
                "PROJECT_STATE_ROOT := $(abspath $(PROJECT_ROOT)/../"
                f"{toolchain.state_directory_name}/$(notdir $(PROJECT_ROOT)))"
            )
            in makefile,
            eq=True,
        )
        tm.that(
            f"PROJECT_SCRATCH_ROOT := $(PROJECT_STATE_ROOT)/{toolchain.scratch_namespace}"
            in makefile,
            eq=True,
        )
        tm.that('TMPDIR="$$test_tmp" GOTMPDIR="$$test_tmp"' in makefile, eq=True)
        # Every gate the typed owner schedules by default reaches the runtime
        # in ONE `check run --gates` invocation. The Make layer no longer
        # publishes a per-gate selector, so the gate list itself is the
        # reachability proof.
        gates = ",".join(config.Infra.codegen.make.check_gates_default)
        tm.that(makefile, has=f'gates="{gates}"')
        tm.that(
            '$(PROJECT_FLEXT_INFRA) check run --repository-root "$(PROJECT_ROOT)" '
            '--gates "$$gates" --projects .' in makefile,
            eq=True,
        )
        tm.that("$(UV_RUN) actionlint" in makefile, eq=False)
        tm.that('$(UV) sync --project "$(PROJECT_ROOT)"' in makefile, eq=True)
        tm.that('$(UV) build --project "$(PROJECT_ROOT)"' in makefile, eq=True)
        # Bytecode still lands in the project state root and never inside the
        # checkout. The Makefile stopped exporting it because the shell owns
        # the interactive environment now, so the guarantee is proved at .envrc
        # — its current owner — instead of being dropped with the old export.
        envrc = (project_root / ".envrc").read_text(encoding="utf-8")
        tm.that(
            envrc,
            has=(
                "export PYTHONPYCACHEPREFIX="
                f'"${{PROJECT_STATE_ROOT}}/{toolchain.pycache_namespace}"'
            ),
        )

    @pytest.mark.parametrize(
        "profile", [c.Infra.MakeProfile.WORKSPACE, c.Infra.MakeProfile.STANDALONE]
    )
    def test_every_declared_check_gate_reaches_the_runtime(
        self, tmp_path: Path, profile: c.Infra.MakeProfile
    ) -> None:
        """Every declared gate is scheduled by the one check handler, both profiles.

        The Make layer no longer publishes a per-gate `WHAT=` selector with a
        `_builtin_check_<gate>` target behind it; the public boundary accepts
        only APPLY. Reachability is therefore proved where it now lives: the
        single generated handler passes the complete declared gate list to the
        typed `check run` owner, so a gate the owner declares cannot be left
        unscheduled by the projection.
        """
        project_root, _repository_root = self._render_makefile(tmp_path, profile)
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")
        phony_declarations = tuple(
            line.removeprefix(".PHONY:").strip()
            for line in makefile.splitlines()
            if line.startswith(".PHONY:")
        )

        # `check` is phony through the verb vocabulary, and its dispatch target
        # through the generated `_builtin-` prefix expansion of that same list.
        tm.that(
            phony_declarations,
            has="$(PUBLIC_VERBS) $(addprefix _builtin-,$(PUBLIC_VERBS))",
        )
        verbs = tuple(verb.name for verb in config.Infra.codegen.make.verbs)
        tm.that(verbs, has="check")
        # The dispatch chain that carries the declared gate list to the runtime.
        tm.that(makefile, has="_builtin-check: _builtin_check_all")
        tm.that(makefile, has="_builtin_check_all: _builtin_require_environment")
        scheduled = ",".join(config.Infra.codegen.make.check_gates_default)
        if profile == c.Infra.MakeProfile.WORKSPACE:
            # A workspace root schedules gates through the orchestrator; the
            # declared list reaches each member's own `check run` owner from
            # the same config SSOT, so the root Makefile embeds no gate list.
            tm.that(makefile, has="$(WORKSPACE_ORCHESTRATE) --verb check")
        else:
            tm.that(makefile, has=f'gates="{scheduled}"')
            for gate in config.Infra.codegen.make.check_gates_default:
                tm.that(scheduled.split(","), has=gate)
            tm.that(makefile, has='--gates "$$gates" --projects .')

    def test_standalone_check_executes_its_declared_default_gates(
        self, tmp_path: Path
    ) -> None:
        """Standalone check runs exactly the owner-declared default gate set."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        invocation_log = tmp_path / "check-invocation.log"
        runtime_python = project_root / ".venv" / "bin" / "python"
        test_u.Tests.write_executable(
            runtime_python, f"#!/bin/sh\nprintf '%s\\n' \"$*\" > '{invocation_log}'\n"
        )
        uv = tmp_path / "bin" / "uv"
        test_u.Tests.write_executable(uv, "#!/bin/sh\nexit 0\n")

        # APPLY is the ONLY public Make input; the generated boundary rejects
        # every other command-line variable by name, so the uv override that
        # used to ride on the command line is supplied through the environment.
        apply_variable = config.Infra.codegen.make.apply_variable
        apply_value = config.Infra.codegen.make.apply_value
        process = tm.ok(
            u.Cli.run_raw(
                [
                    c.Infra.MAKE,
                    "--no-print-directory",
                    "check",
                    f"{apply_variable}={apply_value}",
                ],
                cwd=project_root,
                env={"UV": str(uv), "PATH": f"{uv.parent}:{os.environ['PATH']}"},
                remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
            )
        )

        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        gates = ",".join(config.Infra.codegen.make.check_gates_default)
        invocation = invocation_log.read_text(encoding="utf-8")
        tm.that(invocation, has="-m flext_infra check run")
        tm.that(invocation, has=f"--gates {gates} --projects .")

    def test_dependency_upgrade_scopes_to_declared_project_locks(
        self, tmp_path: Path
    ) -> None:
        """Upgrade exactly the declared project locks through the deps verb."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        runtime_python = project_root / ".venv" / "bin" / "python"
        test_u.Tests.write_executable(runtime_python, "#!/bin/sh\nexit 0\n")
        uv_log = tmp_path / "uv.log"
        bin_dir = tmp_path / "bin"
        uv = bin_dir / "uv"
        test_u.Tests.write_executable(
            uv, f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{uv_log}'\nexit 0\n"
        )

        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "deps", "APPLY=Y"],
                cwd=project_root,
                # PATH takes the DIRECTORY holding the stub, never the stub
                # itself: pointing it at the executable makes every lookup miss.
                env={"UV": str(uv), "PATH": f"{bin_dir}:{os.environ['PATH']}"},
                remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
            )
        )

        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        commands = uv_log.read_text(encoding="utf-8").splitlines()
        # The upgrade scope is exactly the declared project locks: one pass
        # with the upgrade and refresh flags (branch-tracked git dependencies
        # are moving sources by declaration), then one plain lock verification
        # of the same root.
        tm.that(
            [line for line in commands if line.startswith("lock")],
            eq=(
                f"lock --project {project_root} --upgrade --refresh",
                f"lock --project {project_root} --check",
            ),
        )

    def test_dependency_upgrade_requires_the_write_enable_token(
        self, tmp_path: Path
    ) -> None:
        """Deps applies with zero inputs; APPLY=N remains the explicit opt-out.

        Operator law 2026-09-10 seeds the write-enable token to its apply
        value, so the plain `make deps` invocation must reach uv. Only the
        explicit APPLY=N run keeps the fail-closed write-enable diagnostic.
        """
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        runtime_python = project_root / ".venv" / "bin" / "python"
        test_u.Tests.write_executable(runtime_python, "#!/bin/sh\nexit 0\n")
        uv_log = tmp_path / "uv.log"
        uv = tmp_path / "bin" / "uv"
        test_u.Tests.write_executable(
            uv, f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{uv_log}'\nexit 0\n"
        )
        env = {"UV": str(uv), "PATH": f"{uv.parent}:{os.environ['PATH']}"}

        plain = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "deps"],
                cwd=project_root,
                env=env,
                remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
            )
        )
        authenticated = tm.ok(
            u.Cli.run_raw(
                [
                    c.Infra.MAKE,
                    "--no-print-directory",
                    "deps",
                    f"{config.Infra.codegen.make.apply_variable}=N",
                ],
                cwd=project_root,
                env=env,
                remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
            )
        )

        tm.that(u.Cli.process_succeeded(plain.outcome), eq=True)
        tm.that(uv_log.exists(), eq=True)
        apply_variable = config.Infra.codegen.make.apply_variable
        apply_value = config.Infra.codegen.make.apply_value
        # APPLY is binary now: the apply value is the only valid token, so the
        # explicit opt-out attempt fails at the generated public boundary
        # before any recipe runs, keeping uv off the mutation path.
        tm.that(authenticated.outcome.raw_return_code, ne=0)
        tm.that(
            authenticated.stdout + authenticated.stderr,
            has=f"{apply_variable} must be {apply_value} when enabled",
        )
        tm.that(authenticated.stdout + authenticated.stderr, has="Makefile")

    def test_public_gate_fails_closed_before_managed_environment_exists(
        self, tmp_path: Path
    ) -> None:
        """A public gate preserves the canonical setup-required diagnostic."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )

        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "test"],
                cwd=project_root,
                remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
            )
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(
            process.stdout + process.stderr,
            has=["missing environment interpreter", "make setup creates it"],
        )

    def test_generated_setup_is_self_contained(self, tmp_path: Path) -> None:
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")

        for required in (
            "UV ?= uv",
            "ifneq ($(filter setup,$(MAKECMDGOALS)),)",
            "SETUP_BOOTSTRAP_ONLY := Y",
            'if [ -n "$${GITHUB_PATH:-}" ]; then',
            # Managed tools reach the setup lifecycle by RUNNING it inside the
            # bootstrapped Mise, not by the old inline PATH computation: the
            # toolchain is installed at its latest release and the lifecycle
            # is executed through `mise exec`, so nothing needs an ambient mise
            # and nothing hand-assembles a managed PATH any more.
            ('mise_exec project "$$latest_mise" -C "$$project_root" install --yes'),
            (
                'mise_exec project "$$latest_mise" -C "$$project_root" exec -- env '
                '"SETUP_DIRENV=$$direnv_executable"'
            ),
            '$(UV) venv "$(RUNTIME_VENV)"',
            '$(UV) sync --project "$(PROJECT_ROOT)"',
            '--link-mode "$(UV_LINK_MODE)"',
            'git -C "$$superproject" submodule update --init -- "$$child_path"',
            'git -C "$$child_root" branch --show-current',
            'merge-base --is-ancestor "$$gitlink" HEAD',
        ):
            tm.that(makefile, has=required)
        for forbidden in (
            "mise exec -- uv",
            "uv@",
            "define _setup_submodules",
            "SETUP_BRANCH :=",
            "--no-install-project",
            '--editable "$(PROJECT_ROOT)"',
            "pip install",
        ):
            tm.that(makefile, lacks=forbidden)
        checkout_command = re.search(
            r"(?:^|[;&|]\s*)git(?:\s+-C\s+\S+)?\s+checkout(?:\s|$)",
            makefile,
            flags=re.MULTILINE,
        )
        tm.that(checkout_command is None, eq=True)

    def test_generated_dependency_upgrade_projects_lock_floors(
        self, tmp_path: Path
    ) -> None:
        """Make owns lock upgrade, open-floor projection, and final resolution."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")

        tm.that(makefile, has="deps modernize")
        tm.that(makefile, has="--rewrite-constraints")
        tm.that(makefile, lacks="--constraint-policy")

    def test_generated_boundary_rejects_forbidden_makeflags_overrides(
        self, tmp_path: Path
    ) -> None:
        """Hostile MAKEFLAGS assignments are ignored, never fatal.

        GNU Make propagates any variable on MAKEFLAGS (or the command line) as
        ``command line override`` to every child process. Since operator law
        2026-09-10 ordinary usage must always start with zero variables, so
        the boundary warns about every override that is not a declared public
        input and continues; it can no longer block a run.
        """
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )

        apply_variable = config.Infra.codegen.make.apply_variable
        apply_value = config.Infra.codegen.make.apply_value
        hostile_env = {
            "MAKEFLAGS": f"FORBIDDEN_VAR=hostile {apply_variable}={apply_value}"
        }
        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "help"],
                cwd=project_root,
                env=hostile_env,
                remove_env_keys=tuple(
                    key
                    for key in c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS
                    if key not in hostile_env
                ),
            )
        )

        tm.that(u.Cli.process_succeeded(process.outcome), eq=True)
        tm.that(
            process.stdout + process.stderr,
            has="Ignoring unsupported Make input(s): FORBIDDEN_VAR",
        )

    def test_generated_make_dispatches_script_verbs_to_builtin_targets(
        self, tmp_path: Path
    ) -> None:
        """Auto-discovered script verbs get _builtin-<verb> dispatch targets."""
        extra_verbs = (
            m.Infra.MakeVerbSpec(
                name="sync",
                description="Dispatch sync through the declared script dispatcher.",
                requires_apply=True,
            ),
        )
        script_dispatch = m.Infra.ScriptDispatchSpec(
            dispatcher="scripts/dispatch.py",
            roots=("scripts",),
        )
        project_root, _repository_root = self._render_makefile(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
            extra_verbs=extra_verbs,
            script_dispatch=script_dispatch,
        )
        (project_root / "scripts" / "sync").mkdir(parents=True)
        (project_root / "scripts" / "sync" / "all.sh").write_text(
            "#!/bin/sh\necho sync\n", encoding="utf-8"
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")
        tm.that("_builtin-sync:" in makefile, eq=True)
        tm.that("scripts/dispatch.py" in makefile, eq=True)
        tm.that("sync" in makefile, eq=True)
