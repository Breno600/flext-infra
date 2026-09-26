"""Generated Make environment isolation contract."""

from __future__ import annotations

import os
import re
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, m, t, u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeEnvironment:
    """Prove generated operations ignore the caller shell environment."""

    @pytest.mark.parametrize("failure_return", [None, 37])
    def test_public_dispatch_activates_once_before_hooks(
        self, tmp_path: Path, *, failure_return: int | None
    ) -> None:
        """Real direnv evaluates before dispatch and stops an invalid environment."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        tm.ok(u.Tests.create_python_environment(project_root))
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
        project_root, _ = u.Tests.render_make_environment(
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
        project_root, _ = u.Tests.render_make_environment(
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
    # index and GitHub sources (an external gate); `make test-full` selects
    # it after the incremental test phase.
    @pytest.mark.remote
    def test_generated_make_uses_profile_runtime_venv_under_hostile_env(
        self,
        tmp_path: Path,
        resolved_make_templates: t.MappingKV[c.Infra.MakeProfile, Path],
        profile: c.Infra.MakeProfile,
        *,
        provisioned: bool,
    ) -> None:
        """Every generated shell receives the profile-resolved runtime venv."""
        project_root = u.Tests.resolved_make_checkout(
            resolved_make_templates[profile], tmp_path, profile
        )
        runtime_root = project_root
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
    # the offline unit gate; make test-full includes this remote boundary.
    @pytest.mark.remote
    def test_setup_provisions_environment_before_project_runtime(
        self,
        tmp_path: Path,
        resolved_make_templates: t.MappingKV[c.Infra.MakeProfile, Path],
        profile: c.Infra.MakeProfile,
    ) -> None:
        """Setup creates the venv and syncs dependencies before any runtime use."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path, profile, bootstrap=True
        )
        hostile_venv = tmp_path / c.Tests.MAKE_TEMPLATE_HOSTILE_VENV
        (hostile_venv / "bin").mkdir(parents=True)
        active_env = u.Tests.hostile_uv_environment(hostile_venv)
        tm.that((project_root / ".venv").exists(), eq=False)
        # Without a committed lock, setup never resolves: uv refuses loudly.
        unlocked = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "setup"], cwd=project_root, env=active_env
            )
        )
        tm.that(u.Cli.process_succeeded(unlocked.outcome), eq=False)
        tm.that((project_root / c.Infra.UV_LOCK_FILENAME).exists(), eq=False)

        # `upg` is the only resolver: the run's template was upgraded under the
        # same foreign environment with a declared post-upg hook. It wrote both
        # locks, provisioned the environment frozen from them, and ran the
        # hook inside the activated environment, exactly as setup runs post-setup.
        template = resolved_make_templates[profile]
        receipts = template.parent.parent
        upgraded = u.Tests.command_receipt(receipts / c.Tests.MAKE_TEMPLATE_UPG_RECEIPT)
        tm.that(upgraded.stdout, has="upg-hook-ran")
        for lock in (c.Infra.UV_LOCK_FILENAME, c.Infra.MISE_LOCK_FILENAME):
            tm.that((template / lock).is_file(), eq=True)
        tm.that((template / ".venv" / "pyvenv.cfg").is_file(), eq=True)
        template_hostile = receipts / c.Tests.MAKE_TEMPLATE_HOSTILE_VENV
        tm.that(
            (template_hostile / "sentinel").read_text(encoding="utf-8"),
            eq="untouched\n",
        )
        tm.that(tuple((template_hostile / "bin").iterdir()), eq=())
        tm.that((template_hostile / "pyvenv.cfg").exists(), eq=False)
        tm.that((template_hostile.parent / c.Infra.UV_LOCK_FILENAME).exists(), eq=False)

        # A cold CI storage must install every tool without auto-locking. A warm
        # storage would skip installation and conceal an absent locked-mode guard.
        bootstrap = u.Infra.mise_bootstrap_environment()
        cold_storage = receipts / c.Tests.COLD_MISE_STORAGE
        locked = u.Tests.command_receipt(receipts / c.Tests.MAKE_TEMPLATE_CI_RECEIPT)
        tm.that(
            u.Cli.process_succeeded(locked.outcome),
            eq=True,
            msg=locked.stdout + locked.stderr,
        )
        tm.that(locked.stdout, has="ci-runtime-provisioned")
        tm.that(locked.stdout, has=f"storage={cold_storage}")
        install_root = cold_storage / next(
            relative
            for name, relative in bootstrap.persistent_environment
            if name == "MISE_INSTALLS_DIR"
        )
        tm.that(any(install_root.iterdir()), eq=True)
        resolved_locks = self._locks(template)
        ci_checkout = (
            receipts / c.Tests.MAKE_TEMPLATE_CI_CHECKOUT / profile.value / template.name
        )
        tm.that(self._locks(ci_checkout), eq=resolved_locks)

        # A new dependency declaration makes the committed lock stale: setup
        # fails instead of re-resolving, and the lock stays untouched.
        checkout = u.Tests.resolved_make_checkout(template, tmp_path / "stale", profile)
        dependency_root = tmp_path / "external-runtime"
        u.Tests.WorktreeFixture.write_python_project(
            dependency_root, "external-runtime"
        )
        pyproject_path = checkout / c.PYPROJECT_FILENAME
        document = u.Tests.toml_doc(pyproject_path.read_text(encoding="utf-8"))
        project = tm.not_none(u.Cli.toml_table_child(document, "project"))
        project["dependencies"] = [
            *u.Cli.toml_as_string_list(u.Cli.toml_value(project, "dependencies")),
            f"external-runtime @ {dependency_root.as_uri()}",
        ]
        tm.ok(u.Cli.atomic_write_text_file(pyproject_path, u.Cli.toml_dumps(document)))
        make = config.Infra.codegen.make
        stale = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "setup"],
                cwd=checkout,
                env={
                    **active_env,
                    make.ci.variable: make.ci.value,
                    bootstrap.storage_root_variable: str(cold_storage),
                },
            )
        )
        tm.that(u.Cli.process_succeeded(stale.outcome), eq=False)
        tm.that(self._locks(checkout), eq=resolved_locks)

    @staticmethod
    def _locks(root: Path) -> t.MappingKV[str, bytes]:
        """Return every lock artifact ``make upg`` owns, keyed by relative path."""
        sidecars = root / ".mise" / "locks"
        paths = (
            root / c.Infra.UV_LOCK_FILENAME,
            root / c.Infra.MISE_LOCK_FILENAME,
            root / c.Infra.MISE_VERSION_PIN_FILENAME,
            *(path for path in sidecars.rglob("*") if path.is_file()),
        )
        return {path.relative_to(root).as_posix(): path.read_bytes() for path in paths}

    def test_setup_fails_when_the_tracked_mise_launcher_is_missing(
        self, tmp_path: Path
    ) -> None:
        """Never substitute a system Mise for the generated launcher owner."""
        project_root, _repository_root = u.Tests.render_make_environment(
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
        project_root, _repository_root = u.Tests.render_make_environment(
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
        project_root, _repository_root = u.Tests.render_make_environment(
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
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path, profile
        )
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
        project_root, _repository_root = u.Tests.render_make_environment(
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
            u.Tests.run_isolated_make(
                ["--no-print-directory", "check"],
                cwd=project_root,
                env={"UV": str(uv), "PATH": f"{uv.parent}:{os.environ['PATH']}"},
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

    @staticmethod
    def _recipe_targets_containing(makefile: str, needle: str) -> set[str]:
        """Return every rule target whose recipe (not comments) carries *needle*."""
        targets: set[str] = set()
        current: str | None = None
        continued = False
        for line in makefile.splitlines():
            if line.startswith("\t") or continued:
                if (
                    current is not None
                    and not line.lstrip().startswith("#")
                    and needle in line
                ):
                    targets.add(current)
                continued = line.endswith("\\")
                continue
            continued = False
            header = re.match(r"^([A-Za-z0-9_.$()%-]+)\s*:(?![=:])", line)
            current = header.group(1) if header else None
        return targets

    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_upg_is_the_only_resolver_and_setup_installs_frozen(
        self, tmp_path: Path, profile: c.Infra.MakeProfile
    ) -> None:
        """Operator law 2026-09-24: only `upg` resolves and writes the locks.

        The generated Makefile confines every uv upgrade to the `upg`
        lifecycle and every `mise lock --bump` to the shared bootstrap gated by
        a switch that only `upg` sets; `setup` syncs `--locked`, and the
        generated `.mise.toml` makes mise install exactly what the lock pins.
        """
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path, profile, bootstrap=True
        )
        makefile = (project_root / c.Infra.MAKEFILE_FILENAME).read_text(
            encoding="utf-8"
        )

        tm.that(
            self._recipe_targets_containing(makefile, "--upgrade"),
            eq={"_upg_lifecycle"},
        )
        tm.that(
            self._recipe_targets_containing(makefile, "lock --bump"),
            eq={"_bootstrap_setup_tools"},
        )
        toolchain = config.Infra.codegen.toolchain
        artifact_selectors = (
            "python",
            "uv",
            "kubectl",
            "helm",
            "kind",
            "direnv",
            "taplo",
            "ast-grep",
            "gitleaks",
            toolchain.scc_selector,
            "kubeconform",
            "node",
            "go",
            "make",
            toolchain.qlty_selector,
            toolchain.jscpd_selector,
            toolchain.waza_selector,
        )
        lock_invocations = re.findall(r"lock --bump ([^;]+);", makefile)
        tm.that(
            tuple(tuple(shlex.split(arguments)) for arguments in lock_invocations),
            eq=(artifact_selectors, (toolchain.prettier_selector,)),
        )
        for selector in (
            toolchain.qlty_selector,
            toolchain.jscpd_selector,
            toolchain.prettier_selector,
            toolchain.scc_selector,
            toolchain.waza_selector,
        ):
            tm.that(makefile, has=f'"{selector}"')
        platform_matrix = ",".join(toolchain.mise_lockfile_platforms)
        tm.that(
            makefile,
            has=[
                f'mise_lockfile_platforms="{platform_matrix}";',
                '$${mise_lockfile_platforms:+"MISE_LOCKFILE_PLATFORMS=$$mise_lockfile_platforms"}',
                'mise_lockfile_platforms=; \\\n\t\tmise_checked "$$scratch/lock-npm-prettier.log"',
                'mise_checked "$$scratch/lock-npm-prettier.log"',
                f'mise_lockfile_platforms="{platform_matrix}"; \\\n\tfi;',
            ],
        )
        tm.that(makefile, has='if [ "$(TOOL_BOOTSTRAP_RESOLVE)" = "1" ]; then')
        resolve_assignments = re.findall(
            r"^(?:([\w-]+): )?TOOL_BOOTSTRAP_RESOLVE :=[ ]?(.*)$",
            makefile,
            flags=re.MULTILINE,
        )
        tm.that(sorted(resolve_assignments), eq=[("", ""), ("upg", "1")])
        tm.that(makefile, has="upg: TOOL_BOOTSTRAP_LIFECYCLE := _upg_lifecycle")
        sync_flags = re.search(r"^UV_SYNC_FLAGS := (.*)$", makefile, re.MULTILINE)
        assert sync_flags is not None
        tm.that(sync_flags.group(1), has="--locked")
        tm.that(sync_flags.group(1), lacks="--upgrade")

        mise_toml = u.Cli.toml_mapping_from_text(
            (project_root / c.Infra.MISE_TOML_FILENAME).read_text(encoding="utf-8")
        )
        assert mise_toml is not None
        settings = mise_toml.get("settings")
        tool_config = mise_toml.get("tool_config")
        assert isinstance(settings, Mapping)
        assert isinstance(tool_config, Mapping)
        tm.that(settings.get("lockfile"), eq=toolchain.mise_lockfile)
        tm.that(settings.get("locked"), eq=toolchain.mise_locked)
        tm.that(tool_config.get("locked"), eq=toolchain.mise_locked)
        tm.that(
            settings.get("lockfile_platforms"),
            eq=list(toolchain.mise_lockfile_platforms),
        )
        tools = mise_toml.get("tools")
        assert isinstance(tools, Mapping)
        jscpd = tools.get(toolchain.jscpd_selector)
        waza = tools.get(toolchain.waza_selector)
        assert isinstance(jscpd, Mapping)
        assert isinstance(waza, Mapping)
        tm.that(jscpd.get("version"), eq=toolchain.jscpd_version)
        tm.that(
            jscpd.get("platforms"),
            eq={
                platform: {"asset_pattern": pattern}
                for platform, pattern in toolchain.jscpd_asset_patterns.items()
            },
        )
        tm.that(waza.get("version"), eq=toolchain.waza_version)
        tm.that(waza.get("version_prefix"), eq=toolchain.waza_version_prefix)

    def test_public_gate_fails_closed_before_managed_environment_exists(
        self, tmp_path: Path
    ) -> None:
        """A public gate preserves the canonical setup-required diagnostic."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )

        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "test"], cwd=project_root
            )
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(
            process.stdout + process.stderr,
            has=["missing environment interpreter", "make setup creates it"],
        )

    def test_generated_setup_is_self_contained(self, tmp_path: Path) -> None:
        project_root, _repository_root = u.Tests.render_make_environment(
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
            # Runtime tool identity is exercised through the public status
            # regression, including an invalid ambient Mise configuration.
            'mise_exec project "$$latest_mise" -C "$$project_root" install --yes',
            "SETUP_DIRENV=$$direnv_executable",
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
        """`upg` owns lock upgrade, open-floor projection, and final resolution."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")

        for needle in (
            "deps modernize",
            "--rewrite-constraints",
            "--upgrade --refresh",
        ):
            tm.that(
                self._recipe_targets_containing(makefile, needle), eq={"_upg_lifecycle"}
            )
        tm.that(makefile, has="_run_for_all_projects,--check")
        tm.that(makefile, lacks="--constraint-policy")

    def test_workspace_without_local_members_retains_external_flext_sources(
        self, tmp_path: Path
    ) -> None:
        """Workspace role alone cannot turn external dependencies into members."""
        project_root, _repository_root = u.Tests.render_make_environment(
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
        project_root, _repository_root = u.Tests.render_make_environment(
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
        project_root, _repository_root = u.Tests.render_make_environment(
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
        project_root, _repository_root = u.Tests.render_make_environment(
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
        project_root, _repository_root = u.Tests.render_make_environment(
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
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")

        tm.that(makefile, has="upg: _bootstrap_setup_tools")
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
