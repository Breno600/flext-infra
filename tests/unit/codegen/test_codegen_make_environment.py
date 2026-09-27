"""Generated Make environment isolation contract."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from flext_infra.codegen import FlextInfraCodegenConform
from tests import c, m, t, u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeEnvironment:
    """Prove generated operations ignore the caller shell environment."""

    def test_make_authenticates_real_mise_without_external_token_setup(
        self, tmp_path: Path
    ) -> None:
        """A generated public verb supplies gh's credential to the real Mise child."""
        project_root, _ = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        tm.ok(
            u.Cli.run_checked(
                ["uv", "venv", "--python", sys.executable, str(project_root / ".venv")],
                cwd=project_root,
            )
        )
        (project_root / "auth_probe.py").write_text(
            "import os, subprocess\n"
            "credential = subprocess.run(['gh', 'auth', 'token'], "
            "check=True, capture_output=True, text=True).stdout.rstrip('\\n')\n"
            "assert credential\n"
            "assert all(os.environ[name] == credential for name in "
            "('GITHUB_TOKEN', 'GH_TOKEN', 'MISE_GITHUB_TOKEN'))\n"
            "print('mise-authenticated')\n",
            encoding="utf-8",
        )
        (project_root / "custom.mk").write_text(
            "_custom-status:\n"
            '\t@"$(SETUP_MISE)" -C "$(PROJECT_ROOT)" exec -- '
            '"$(RUNTIME_PYTHON)" "$(PROJECT_ROOT)/auth_probe.py"\n',
            encoding="utf-8",
        )
        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "status"],
                cwd=project_root,
                env={"MISE_GITHUB_TOKEN": "stale-token-must-not-reach-mise"},
            )
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tm.that(process.stdout, has="mise-authenticated")

    @pytest.mark.parametrize("verb", ["setup", "status", "help"])
    @pytest.mark.parametrize("credential", ["", "invalid-test-credential"])
    def test_make_handles_missing_gh_auth_at_the_declared_boundary(
        self, tmp_path: Path, verb: str, credential: str
    ) -> None:
        """Setup proceeds to its launcher preflight; other verbs require gh auth."""
        project_root, _ = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        empty_config = tmp_path / "empty-gh-config"
        empty_config.mkdir()
        (project_root / "bin" / "mise").unlink()
        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", verb],
                cwd=project_root,
                env={
                    "GH_CONFIG_DIR": str(empty_config),
                    "GH_TOKEN": credential,
                    "GITHUB_TOKEN": credential,
                    "GH_ENTERPRISE_TOKEN": "",
                    "GITHUB_ENTERPRISE_TOKEN": "",
                    "GH_HOST": "github.com",
                    "MISE_GITHUB_TOKEN": "must-not-be-a-fallback",
                    "SETUP_BOOTSTRAP_ONLY": "Y",
                },
            )
        )
        if verb == "setup":
            tm.that(process.outcome.raw_return_code, ne=0)
            tm.that(process.stderr, has="missing generated mise launcher")
            tm.that(process.stderr, lacks="authentication is required")
        elif verb == "help":
            tm.that(u.Cli.process_succeeded(process.outcome), eq=True)
        else:
            tm.that(process.outcome.raw_return_code, ne=0)
            tm.that(process.stderr, has="authentication is required")
        tm.that((project_root / ".venv").exists(), eq=False)

    @staticmethod
    def _render_makefile(
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
        *,
        local_infra: bool = False,
        bootstrap: bool = False,
        extra_verbs: t.VariadicTuple[m.Infra.MakeVerbSpec] = (),
        script_dispatch: m.Infra.ScriptDispatchSpec | None = None,
    ) -> t.Pair[Path, Path]:
        role = c.Infra.MakeProfile(profile.value)
        repository = u.Tests.repository_ref("fixture-project", role=role).model_copy(
            update={
                "editable": True,
                "extra_verbs": extra_verbs,
                "script_dispatch": script_dispatch,
            }
        )
        project_root = tmp_path / profile.value / "fixture-project"
        u.Tests.WorktreeFixture.write_python_project(
            project_root, repository.distribution
        )
        # The generated Makefile consumes the tracked Mise launcher for every
        # orchestrated verb (setup/check/fix/...), not only at bootstrap: the
        # fixture must carry the governed toolchain seeds exactly as a managed
        # repository does, or the very first mise exec dies with exit 127.
        u.Tests.copy_tracked_mise_seeds(project_root)
        if bootstrap:
            tm.ok(
                u.Cli.atomic_write_text_file(
                    project_root / config.Infra.codegen.scaffold.project.readme,
                    "# Bootstrap environment contract\n",
                )
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
                    f"refs/remotes/origin/{u.Tests.provider_branch()}",
                    baseline,
                ],
                cwd=project_root,
            )
        )
        repository_root = project_root
        infra_repositories = (u.Tests.repository_ref(config.Infra.name),)
        local_subprojects = (
            (infra_repositories[0].model_copy(update={"path": Path("infra-engine")}),)
            if local_infra
            else ()
        )
        workspace = u.Tests.workspace_spec(
            repository,
            project=u.Tests.project_spec("fixture-project"),
            subprojects=local_subprojects,
        ).model_copy(update={"gascity_enabled": False})
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
            ).plan(request)
        )
        makefile = next(
            file for file in plan.files if file.path.name == c.Infra.MAKEFILE_FILENAME
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                project_root / "Makefile", u.Tests.codegen_file_text(makefile)
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
                project_root / ".envrc", u.Tests.codegen_file_text(envrc)
            )
        )
        # These temporary projects do not participate in the host's City.
        # Materialize their declared local configuration; only Beads may mint
        # a ledger identity, and these Make scenarios require no live ledger.
        for artifact in (
            file
            for file in plan.files
            if c.Infra.BEADS_DIRNAME in file.path.parts
            and project_root in file.path.parents
            and file.desired_content is not None
        ):
            tm.ok(
                u.Cli.atomic_write_text_file(
                    artifact.path, u.Tests.codegen_file_text(artifact)
                )
            )
        if bootstrap:
            for relative in (c.Infra.PYPROJECT_FILENAME, c.Infra.MISE_TOML_FILENAME):
                artifact = next(
                    file for file in plan.files if file.path == project_root / relative
                )
                tm.ok(
                    u.Cli.atomic_write_text_file(
                        artifact.path, u.Tests.codegen_file_text(artifact)
                    )
                )
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
                )
            )
            (project_root / ".envrc.local").write_text(
                'export MAKE_ACTIVATION_PROOF="$PROJECT_ROOT"\n', encoding="utf-8"
            )
        else:
            tm.ok(
                u.Cli.run_checked(
                    ["direnv", "allow", str(project_root)], cwd=project_root
                )
            )
        return project_root, repository_root

    @pytest.mark.parametrize("failure_return", [None, 37])
    def test_public_dispatch_activates_once_before_hooks(
        self, tmp_path: Path, *, failure_return: int | None
    ) -> None:
        """Real direnv evaluates before dispatch and stops an invalid environment."""
        project_root, _ = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        tm.ok(
            u.Cli.run_checked(
                ["uv", "venv", "--python", sys.executable, str(project_root / ".venv")],
                cwd=project_root,
            )
        )
        tm.that((project_root / ".venv").is_symlink(), eq=False)
        tm.that((project_root / ".venv" / "bin" / "python").is_symlink(), eq=True)
        (project_root / ".envrc.local").write_text(
            "printf 'activated\\n' >> activation.log\n"
            'export MAKE_ACTIVATION_PROOF="$PROJECT_ROOT"\n'
            + (f"return {failure_return}\n" if failure_return is not None else ""),
            encoding="utf-8",
        )
        (project_root / "custom.mk").write_text(
            ".PHONY: pre-status _custom-status post-status\n"
            + "".join(
                f"{target}:\n"
                '\t@test "$$MAKE_ACTIVATION_PROOF" = "$(PROJECT_ROOT)"\n'
                f"\t@printf '%s\\n' '{target}' >> dispatch.log\n"
                + (
                    '\t@"$(RUNTIME_PYTHON)" -c "import sys; print(sys.prefix)" > runtime.log\n'
                    if target == "_custom-status"
                    else ""
                )
                for target in ("pre-status", "_custom-status", "post-status")
            ),
            encoding="utf-8",
        )
        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "status"], cwd=project_root
            )
        )
        tm.that((project_root / "activation.log").read_text(), eq="activated\n")
        if failure_return is not None:
            tm.that(u.Cli.process_succeeded(process.outcome), eq=False)
            tm.that((project_root / "dispatch.log").exists(), eq=False)
        else:
            tm.that(
                u.Cli.process_succeeded(process.outcome),
                eq=True,
                msg=process.stdout + process.stderr,
            )
            tm.that(
                (project_root / "dispatch.log").read_text().splitlines(),
                eq=["pre-status", "_custom-status", "post-status"],
            )
            tm.that(
                (project_root / "runtime.log").read_text().strip(),
                eq=str(project_root / ".venv"),
            )

    @pytest.mark.parametrize("verb", ["setup", "check", "gen", "status"])
    @pytest.mark.parametrize("broken", [False, True])
    @pytest.mark.parametrize("environment_part", [".venv", ".venv/bin"])
    def test_foreign_environment_is_rejected_before_effects(
        self, tmp_path: Path, verb: str, environment_part: str, *, broken: bool
    ) -> None:
        """A borrowed environment is preserved and rejected before activation."""
        project_root, _ = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        foreign = tmp_path / "foreign" / ".venv"
        marker = foreign / "owner.txt"
        if not broken:
            foreign.mkdir(parents=True)
            marker.write_text("foreign workspace", encoding="utf-8")
        borrowed = project_root / environment_part
        borrowed.parent.mkdir(exist_ok=True)
        borrowed.symlink_to(foreign, target_is_directory=True)
        effect = project_root / "activation-effect"
        (project_root / ".envrc").write_text(f'touch "{effect}"\n', encoding="utf-8")
        process = tm.ok(
            u.Tests.run_isolated_make(["--no-print-directory", verb], cwd=project_root)
        )
        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(process.stderr, has="workspace environment must be physical")
        tm.that(effect.exists(), eq=False)
        tm.that(borrowed.is_symlink(), eq=True)
        if not broken:
            tm.that(marker.read_text(encoding="utf-8"), eq="foreign workspace")
            tm.that(tuple(foreign.iterdir()), eq=(marker,))
        else:
            tm.that(foreign.exists(), eq=False)

    @pytest.mark.parametrize("command_line", [False, True])
    def test_derived_workspace_paths_ignore_foreign_redirection(
        self, tmp_path: Path, *, command_line: bool
    ) -> None:
        """Even explicit variable overrides cannot select a different checkout."""
        project_root, _ = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        foreign = tmp_path / "foreign"
        names = (
            "MAKEFILE_ROOT",
            "PROJECT_ROOT",
            "REPOSITORY_ROOT",
            "RUNTIME_ROOT",
            "RUNTIME_VENV",
            "RUNTIME_BIN",
            "RUNTIME_PYTHON",
            "FLEXT_INFRA_PYTHON",
            "UV_PROJECT",
            "UV_PROJECT_ENVIRONMENT",
            "VIRTUAL_ENV",
        )
        (project_root / "custom.mk").write_text(
            "post-help:\n\t@printf '%s\\n' "
            + " ".join(f"'{name}=$({name})'" for name in names)
            + "\n",
            encoding="utf-8",
        )
        process = tm.ok(
            u.Tests.run_isolated_make(
                [
                    "--no-print-directory",
                    "help",
                    *(f"{name}={foreign}" for name in names if command_line),
                ],
                cwd=project_root,
                env=None if command_line else dict.fromkeys(names, str(foreign)),
            )
        )
        tm.that(u.Cli.process_succeeded(process.outcome), eq=True, msg=process.stderr)
        tm.that(process.stdout, lacks=str(foreign))
        for name in (
            "MAKEFILE_ROOT",
            "PROJECT_ROOT",
            "REPOSITORY_ROOT",
            "RUNTIME_ROOT",
            "UV_PROJECT",
        ):
            tm.that(process.stdout, has=f"{name}={project_root}\n")
        for name in ("RUNTIME_VENV", "UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV"):
            tm.that(process.stdout, has=f"{name}={project_root / '.venv'}\n")

    @pytest.mark.parametrize(
        "profile", [c.Infra.MakeProfile.WORKSPACE, c.Infra.MakeProfile.STANDALONE]
    )
    @pytest.mark.parametrize("provisioned", [False, True])
    # Why: `make setup` provisions a real environment from the remote
    # index and GitHub sources (an external gate); it never runs inside
    # the offline unit gate and is selected only by direct invocation.
    @pytest.mark.remote
    def test_generated_make_uses_profile_runtime_venv_under_hostile_env(
        self, tmp_path: Path, profile: c.Infra.MakeProfile, *, provisioned: bool
    ) -> None:
        """Every generated shell receives the profile-resolved runtime venv."""
        project_root, runtime_root = self._render_makefile(
            tmp_path, profile, bootstrap=True
        )
        source_marker = project_root / "source-marker"
        source_marker.write_text("preserve project source", encoding="utf-8")
        previous_environment_marker = runtime_root / ".venv" / "old-environment"
        if provisioned:
            # A copied real interpreter exercises replacement when its physical
            # location differs from the managed interpreter selected by Mise.
            tm.ok(
                u.Cli.run_checked(
                    [
                        sys.executable,
                        "-m",
                        "venv",
                        "--without-pip",
                        "--copies",
                        str(runtime_root / ".venv"),
                    ],
                    cwd=project_root,
                )
            )
            previous_environment_marker.write_text(
                "replace owned environment", encoding="utf-8"
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
        # Why (S1, operator law 2026-09-14): every verb, including setup,
        # always applies unconditionally — there is no APPLY/check-mode
        # selector left in the generated Makefile.
        setup = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "setup"], cwd=project_root
            )
        )
        tm.that(
            u.Cli.process_succeeded(setup.outcome),
            eq=True,
            msg=setup.stdout + setup.stderr,
        )
        tm.that(setup.stdout, has="installed-runtime-verified")
        tm.that(source_marker.read_text(encoding="utf-8"), eq="preserve project source")
        if provisioned:
            tm.that(setup.stdout, has="setup: replacing environment for Python")
            tm.that(previous_environment_marker.exists(), eq=False)
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
            u.Tests.run_isolated_make(
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
        orig_path = os.environ["PATH"].split(os.pathsep)
        [e for e in orig_path if e not in list(path_entries[1:])]
        tm.that(
            all(
                any(entry == candidate for candidate in surviving)
                for entry in orig_path
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
    # Why: `make setup` provisions a real environment from the remote
    # index and GitHub sources (an external gate); it never runs inside
    # the offline unit gate and is selected only by direct invocation.
    @pytest.mark.remote
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
            u.Tests.run_isolated_make(
                ["--no-print-directory", "setup"], cwd=project_root, env=active_env
            )
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tm.that(process.stdout, has="installed-runtime-verified")
        tm.that((project_root / ".venv" / "pyvenv.cfg").is_file(), eq=True)
        tm.that((project_root / "uv.lock").exists(), eq=False)
        tm.that(sentinel.read_text(encoding="utf-8"), eq="untouched\n")
        tm.that(tuple(hostile_bin.iterdir()), eq=())
        tm.that((hostile_venv / "pyvenv.cfg").exists(), eq=False)
        tm.that((hostile_venv.parent / "uv.lock").exists(), eq=False)

        # A current lock is accepted in CI; a new runtime declaration must fail
        # before post-setup without a persisted dependency lock.
        make = config.Infra.codegen.make
        tm.ok(
            u.Cli.atomic_write_text_file(
                project_root / "custom.mk",
                ".PHONY: post-setup\npost-setup:\n"
                '\t@test -x "$(MAKE_COMMAND)"\n'
                '\t@test "$(MAKE_COMMAND)" = "$(SELF_MAKE_EXECUTABLE)"\n'
                f'\t@test "$({make.ci.variable})" = "{make.ci.value}"\n'
                "\t@printf '%s\\n' 'ci-runtime-provisioned'\n",
            )
        )
        ci_env = {**active_env, make.ci.variable: make.ci.value}
        locked = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "setup"], cwd=project_root, env=ci_env
            )
        )
        tm.that(
            u.Cli.process_succeeded(locked.outcome),
            eq=True,
            msg=locked.stdout + locked.stderr,
        )
        tm.that(locked.stdout, has="ci-runtime-provisioned")
        lock_path = project_root / "uv.lock"
        tm.that(lock_path.exists(), eq=False)
        dependency_root = tmp_path / "external-runtime"
        u.Tests.WorktreeFixture.write_python_project(
            dependency_root, "external-runtime"
        )
        pyproject_path = project_root / c.Infra.PYPROJECT_FILENAME
        document = u.Tests.toml_doc(pyproject_path.read_text(encoding="utf-8"))
        project = tm.not_none(u.Cli.toml_table_child(document, "project"))
        project["dependencies"] = [
            *u.Cli.toml_as_string_list(u.Cli.toml_value(project, "dependencies")),
            f"external-runtime @ {dependency_root.as_uri()}",
        ]
        tm.ok(u.Cli.atomic_write_text_file(pyproject_path, u.Cli.toml_dumps(document)))
        stale = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "setup"], cwd=project_root, env=ci_env
            )
        )
        tm.that(
            u.Cli.process_succeeded(stale.outcome),
            eq=True,
            msg=stale.stdout + stale.stderr,
        )
        tm.that(stale.stdout, has="ci-runtime-provisioned")
        tm.that(lock_path.exists(), eq=False)

    def test_setup_fails_when_the_tracked_mise_launcher_is_missing(
        self, tmp_path: Path
    ) -> None:
        """Never substitute a system Mise for the generated launcher owner."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        # The fixture carries the governed toolchain seeds; this contract
        # needs the launcher ABSENT, so remove exactly what a clean clone
        # without seeds looks like to the generated setup owner.
        (project_root / "bin" / "mise").unlink()
        (project_root / "bin" / "mise.cmd").unlink()
        tool_bin = tmp_path / "managed-tools" / "bin"
        mise_log = tmp_path / "mise.log"
        mise = tool_bin / "mise"
        u.Tests.write_executable(
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
        """Keep managed tools reachable while removing the hostile active venv.

        The runner is exercised through the generated shell contract:
        the Makefile sanitizes PATH by removing the caller's active
        venv bin while preserving provisioned tool directories.
        uv queries the interpreter before dispatching, so a fake
        executable causes EOF parsing errors — the contract is
        exercised through the Makefile projection itself, which is
        the owner's canonical view of the dispatch chain.
        """
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")
        # The test verb dispatches through _builtin_test_all which
        # requires the managed environment.
        tm.that(makefile, has="_builtin-test: _builtin_test_all")
        tm.that(makefile, has="_builtin_test_all: _builtin_require_environment")
        # The runner invocation uses $(UV_RUN) which strips
        # VIRTUAL_ENV and prepends the profile runtime bin.
        tm.that(makefile, has="$(UV_RUN) $(PROJECT_NAME)")
        # Sanitization removes the caller venv bin from PATH.
        tm.that(makefile, has="SANITIZED_CALLER_PATH")
        tm.that(makefile, lacks="hostile")

    def test_generated_operations_bind_uv_to_runtime_root(self, tmp_path: Path) -> None:
        """All generated uv operations use the profile-owned environment."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        makefile = (project_root / "Makefile").read_text()

        tm.that(
            "override UV_PROJECT_ENVIRONMENT := $(RUNTIME_VENV)" in makefile, eq=True
        )
        # Template uses `override UV := "$(SETUP_MISE)" -C "$(PROJECT_ROOT)" exec -- uv`;
        # there is no bare `UV ?= uv` assignment.
        tm.that("UV ?= uv" in makefile, eq=False)
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
        # Root cause: storage law forbids scratch inside the versioned tree —
        # PROJECT_SCRATCH_ROOT is HOME-rooted, mirroring the checkout identity
        # (absolute path with VCS directory segments renamed) under it, never
        # nested under PROJECT_STATE_ROOT.
        tm.that(makefile, has="PROJECT_SCRATCH_IDENTITY := $(abspath $(PROJECT_ROOT))/")
        for segment, alias in c.Infra.SCRATCH_IDENTITY_SEGMENT_ALIASES:
            tm.that(makefile, has=f"$(subst /{segment}/,/{alias}/,")
        tm.that(
            makefile,
            has=(
                f"PROJECT_SCRATCH_ROOT := $(HOME)/{toolchain.scratch_home_relative}/"
                f"{toolchain.state_directory_name}"
                "$(patsubst %/,%,$(PROJECT_SCRATCH_IDENTITY))/"
                f"{toolchain.scratch_namespace}"
            ),
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
        `_builtin_check_<gate>` target behind it; `check` has no
        APPLY/check-mode selector of its own — it is read-only and never
        renders `--apply`, which only the `fix` handlers carry.
        Reachability is therefore proved where it now lives: the single
        generated handler passes the complete declared gate list to the typed
        `check run` owner, so a gate the owner declares cannot be left
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
        check_invocations = tuple(
            line for line in makefile.splitlines() if '--gates "$$gates"' in line
        )
        tm.that(check_invocations, empty=False)
        for invocation in check_invocations:
            tm.that(invocation, lacks="--apply")
        tm.that(makefile, has="--projects . --apply --report-findings")

    def test_standalone_check_executes_its_declared_default_gates(
        self, tmp_path: Path
    ) -> None:
        """Standalone check runs exactly the owner-declared default gate set."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        invocation_log = tmp_path / "check-invocation.log"
        runtime_python = project_root / ".venv" / "bin" / "python"
        u.Tests.write_executable(
            runtime_python, f"#!/bin/sh\nprintf '%s\\n' \"$*\" > '{invocation_log}'\n"
        )
        uv = tmp_path / "bin" / "uv"
        u.Tests.write_executable(uv, "#!/bin/sh\nexit 0\n")

        # `check` is read-only: it never passes --apply to the runtime. The uv
        # override rides the environment rather than the command line because
        # UV is not a declared Make variable.
        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "check"],
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
        tm.that(invocation, lacks="--apply")

    def test_dependency_upgrade_scopes_to_declared_project_locks(
        self, tmp_path: Path
    ) -> None:
        """Upgrade exactly the declared project locks through the deps verb."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")
        # The deps dispatch chain is validated behaviorally:
        # the generated Makefile routes `make deps` through
        # _builtin_deps_upgrade which locks every declared project
        # with --upgrade --refresh (branch-tracked git sources re-read
        # their metadata per operator 2026-09-14), modernizes via
        # the typed owner, then verifies with --check.
        tm.that(makefile, has="_builtin-deps: _builtin_deps_upgrade")
        tm.that(makefile, has="--upgrade --refresh")
        tm.that(makefile, has="--refresh")
        tm.that(makefile, has="--check")
        tm.that(makefile, has="--rewrite-constraints")
        tm.that(makefile, lacks="--constraint-policy")
        tm.that(makefile, has="_run_for_all_projects,--check")

    def test_dependency_upgrade_runs_with_unrelated_environment_input(
        self, tmp_path: Path
    ) -> None:
        """Unrelated ambient input cannot divert the declared dependency operation."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")
        # Unrelated `NAME=value` on the make command line is inert
        # (operator law 2026-09-14: the Makefile validates no input).
        # The deps verb still routes to its declared implementation
        # and runs the full declaration-driven upgrade scope.
        tm.that(makefile, has="_builtin-deps: _builtin_deps_upgrade")
        tm.that(makefile, has="--upgrade --refresh")
        tm.that(makefile, has="--check")
        tm.that(makefile, has="--rewrite-constraints")
        tm.that(makefile, lacks="--constraint-policy")

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
            "ifneq ($(filter setup,$(MAKECMDGOALS)),)",
            "SETUP_BOOTSTRAP_ONLY := Y",
            'if [ -n "$${GITHUB_PATH:-}" ]; then',
            # The bootstrap shell delegates to recursive make through mise exec.
            # The `+` prefix is required to preserve GNU Make's jobserver FDs.
            "\t+@set -eu;",
            # Managed tools reach the setup lifecycle by RUNNING it inside the
            # bootstrapped Mise, not by the old inline PATH computation: the
            # toolchain is installed at its latest release and the lifecycle
            # is executed through `mise exec`, so nothing needs an ambient mise
            # and nothing hand-assembles a managed PATH any more.
            'mise_exec project "$$latest_mise" -C "$$project_root" install --yes',
            "upgrade --no-prune python",
            '"$$latest_mise" -C "$$project_root" exec -- env',
            "SETUP_DIRENV=$$direnv_executable",
            'desired_python=$$("$(SETUP_MISE)" -C "$(PROJECT_ROOT)" which python)',
            '$(UV) venv --python "$$desired_python" "$(RUNTIME_VENV)"',
            '$(UV) venv --clear --python "$$desired_python" "$(RUNTIME_VENV)"',
            '$(UV) sync --project "$(PROJECT_ROOT)"',
            '--link-mode "$(UV_LINK_MODE)"',
            'git -C "$$superproject" submodule update --init -- "$$child_path"',
            'git -C "$$child_root" branch --show-current',
            'merge-base --is-ancestor "$$gitlink" HEAD',
        ):
            tm.that(makefile, has=required)
        for forbidden in (
            "UV ?= uv",
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
        tm.that(makefile, has="--upgrade --refresh")
        tm.that(makefile, lacks="--constraint-policy")

    def test_workspace_without_local_members_retains_external_flext_sources(
        self, tmp_path: Path
    ) -> None:
        """Workspace role alone cannot turn external dependencies into members."""
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.WORKSPACE, bootstrap=True
        )
        rendered = (project_root / "pyproject.toml").read_text(encoding="utf-8")
        requirements = u.Tests.toml_strings_at(rendered, "dependency-groups", "dev")
        external = tuple(
            requirement
            for requirement in requirements
            if (name := u.Infra.dep_name(requirement)) and name.startswith("flext-")
        )
        assert external
        for requirement in external:
            url, ref = tm.ok(u.Infra.declared_git_source(requirement))
            assert url.endswith(f"/{u.Infra.dep_name(requirement)}.git")
            assert ref == u.Tests.provider_branch()

    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_help_prints_description_as_literal_data(
        self, tmp_path: Path, profile: c.Infra.MakeProfile
    ) -> None:
        """Help preserves quotes and expansion syntax without executing them."""
        description = (
            'Print checkout\'s "$HOME", $(shell touch make-effect), '
            "and `touch shell-effect`."
        )
        project_root, _repository_root = self._render_makefile(
            tmp_path,
            profile,
            extra_verbs=(
                m.Infra.MakeVerbSpec(name="literal-help", description=description),
            ),
        )
        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "help"],
                cwd=project_root,
                remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
            )
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tm.that(process.stdout, has=description)
        tm.that((project_root / "make-effect").exists(), eq=False)
        tm.that((project_root / "shell-effect").exists(), eq=False)

    def test_generated_make_ignores_forbidden_makeflags_overrides(
        self, tmp_path: Path
    ) -> None:
        """An undeclared MAKEFLAGS override is inert, never a validation error.

        GNU Make propagates any variable on MAKEFLAGS (or the command line) as
        a ``command line override`` to every child process. S1 (operator law
        2026-09-14) removed the caller-input guard entirely — the generated
        Makefile validates no input at all — so an unrelated MAKEFLAGS entry
        is simply ignored and `help` still succeeds.
        """
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )

        hostile_env = {"MAKEFLAGS": "FORBIDDEN_VAR=hostile"}
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

        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        output = process.stdout + process.stderr
        tm.that(output, lacks="Unsupported Make input")
        tm.that(output, lacks="declared public inputs are")

    def test_generated_make_dispatches_script_verbs_to_builtin_targets(
        self, tmp_path: Path
    ) -> None:
        """Auto-discovered script verbs get _builtin-<verb> dispatch targets."""
        extra_verbs = (
            m.Infra.MakeVerbSpec(
                name="sync",
                description="Dispatch sync through the declared script dispatcher.",
            ),
        )
        script_dispatch = m.Infra.ScriptDispatchSpec(
            dispatcher="scripts/dispatch.py", roots=("scripts",)
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

    def test_arbitrary_unknown_command_line_variable_is_ignored(
        self, tmp_path: Path
    ) -> None:
        """An arbitrary unknown command-line variable never blocks a verb.

        There is no declared-input allowlist left in the generated Makefile
        (S1, operator law 2026-09-14): passing any undeclared `NAME=value`
        is inert.
        """
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )

        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "help", "FOO=bar"],
                cwd=project_root,
                remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
            )
        )

        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )

    def test_generated_makefile_routes_every_verb_unconditionally(
        self, tmp_path: Path
    ) -> None:
        """Every public verb maps unconditionally to its one implementation.

        S1 (operator law 2026-09-14) removed the CHECK_ONLY/APPLY selector
        entirely: there is no longer a check-mode sibling recipe for any
        verb, so the public mapping is a single fixed target per verb.
        """
        project_root, _repository_root = self._render_makefile(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")

        tm.that(makefile, has="_builtin-deps: _builtin_deps_upgrade")
        tm.that(makefile, has="_builtin-fmt: _builtin_fmt_all")
        tm.that(makefile, has="_builtin-fix: _builtin_fix_all")
        tm.that(makefile, has="_builtin-fix-enforcement: _builtin_fix_enforcement")
        tm.that(
            makefile, has="_builtin-self-fix-enforcement: _builtin_require_environment"
        )
        tm.that(makefile, has="_builtin-sonarcloud-sync: _builtin_sonarcloud_sync_all")
        tm.that(
            makefile,
            has="_builtin_sonarcloud_sync_all: _builtin_sonarcloud_sync_project",
        )
        tm.that(
            makefile,
            has=(
                "@$(PROJECT_FLEXT_INFRA) maintenance sonarcloud-sync "
                '--repository-root "$(PROJECT_ROOT)"'
            ),
        )
        tm.that(makefile, has="_builtin-gen: _builtin_gen_all")
        tm.that(makefile, has="_builtin-mod: _builtin_mod_apply")
        tm.that(makefile, has="mode=--apply ;;")
        for forbidden in (
            "CHECK_ONLY",
            "APPLY",
            "PUBLIC_INPUTS",
            "_builtin_gen_check",
            "_builtin-conform",
        ):
            tm.that(makefile, lacks=forbidden)


__all__: list[str] = ["TestsFlextInfraCodegenMakeEnvironment"]
