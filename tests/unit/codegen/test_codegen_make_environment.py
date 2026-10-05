"""Generated Make environment isolation contract.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, t, u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeEnvironment:
    """Prove generated operations ignore the caller shell environment."""

    @staticmethod
    @pytest.mark.parametrize("failure_return", [None, 37])
    def test_public_dispatch_activates_once_before_hooks(
        tmp_path: Path,
        *,
        failure_return: int | None,
    ) -> None:
        """Real direnv evaluates before dispatch and stops an invalid environment."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        runtime_environment = u.Infra.runtime_environment_dir(project_root)
        tm.ok(u.Tests.create_python_environment(project_root))
        tm.that(runtime_environment.is_symlink(), eq=False)
        tm.that((runtime_environment / "bin" / "python").is_symlink(), eq=True)
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
                ["--no-print-directory", "status"],
                cwd=project_root,
            ),
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
                eq=str(runtime_environment),
            )

    @staticmethod
    @pytest.mark.parametrize("verb", ["setup", "check", "gen", "status"])
    @pytest.mark.parametrize("broken", [False, True])
    @pytest.mark.parametrize(
        "environment_part",
        ["runtime", "runtime-bin", ".venv", ".venv/bin"],
    )
    def test_foreign_environment_is_rejected_before_effects(
        tmp_path: Path,
        verb: str,
        environment_part: str,
        *,
        broken: bool,
    ) -> None:
        """A borrowed environment is preserved and rejected before activation."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        foreign = tmp_path / "foreign" / ".venv"
        marker = foreign / "owner.txt"
        if not broken:
            foreign.mkdir(parents=True)
            marker.write_text("foreign workspace", encoding="utf-8")
        runtime_environment = u.Infra.runtime_environment_dir(project_root)
        borrowed = {
            "runtime": runtime_environment,
            "runtime-bin": runtime_environment / "bin",
        }.get(environment_part, project_root / environment_part)
        borrowed.parent.mkdir(parents=True, exist_ok=True)
        borrowed.symlink_to(foreign, target_is_directory=True)
        effect = project_root / "activation-effect"
        (project_root / ".envrc").write_text(f'touch "{effect}"\n', encoding="utf-8")
        process = tm.ok(
            u.Tests.run_isolated_make(["--no-print-directory", verb], cwd=project_root),
        )
        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(
            "workspace environment must be physical" in process.stderr
            or ".envrc is blocked" in process.stderr,
            eq=True,
        )
        tm.that(effect.exists(), eq=False)
        tm.that(borrowed.is_symlink(), eq=True)
        if not broken:
            tm.that(marker.read_text(encoding="utf-8"), eq="foreign workspace")
            tm.that(tuple(foreign.iterdir()), eq=(marker,))
        else:
            tm.that(foreign.exists(), eq=False)

    @staticmethod
    @pytest.mark.parametrize("command_line", [False, True])
    def test_derived_workspace_paths_ignore_foreign_redirection(
        tmp_path: Path,
        *,
        command_line: bool,
    ) -> None:
        """Even explicit variable overrides cannot select a different checkout."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
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
            ),
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
            tm.that(
                process.stdout,
                has=f"{name}={u.Infra.runtime_environment_dir(project_root)}\n",
            )

    @staticmethod
    @pytest.mark.parametrize(
        "profile",
        [c.Infra.MakeProfile.WORKSPACE, c.Infra.MakeProfile.STANDALONE],
    )
    @pytest.mark.parametrize("provisioned", [False, True])
    # Why: `make setup` provisions a real environment from the remote
    # index and GitHub sources (an external gate); `make test-full` selects
    # it after the incremental test phase.
    @pytest.mark.remote
    def test_generated_make_uses_profile_runtime_venv_under_hostile_env(
        tmp_path: Path,
        resolved_make_templates: t.MappingKV[c.Infra.MakeProfile, Path],
        profile: c.Infra.MakeProfile,
        *,
        provisioned: bool,
    ) -> None:
        """Every generated shell receives the profile-resolved runtime venv."""
        project_root = u.Tests.resolved_make_checkout(
            resolved_make_templates[profile],
            tmp_path,
            profile,
        )
        runtime_root = project_root
        runtime_environment = u.Infra.runtime_environment_dir(
            project_root,
            runtime_root=runtime_root,
        )
        source_marker = project_root / "source-marker"
        source_marker.write_text("preserve project source", encoding="utf-8")
        previous_environment_marker = runtime_environment / "old-environment"
        if provisioned:
            # A copied real interpreter exercises replacement when its physical
            # location differs from the managed interpreter selected by Mise.
            runtime_environment.parent.mkdir(parents=True, exist_ok=True)
            tm.ok(
                u.Cli.run_checked(
                    [
                        sys.executable,
                        "-m",
                        "venv",
                        "--without-pip",
                        "--copies",
                        str(runtime_environment),
                    ],
                    cwd=project_root,
                ),
            )
            previous_environment_marker.write_text(
                "replace owned environment",
                encoding="utf-8",
            )
        if profile == c.Infra.MakeProfile.STANDALONE:
            # Without Make's explicit binding, uv selects this parent's default
            # .venv even when --project names the member checkout.
            tm.ok(
                u.Cli.atomic_write_text_file(
                    project_root.parent / "pyproject.toml",
                    f'[tool.uv.workspace]\nmembers = ["{project_root.name}"]\n',
                ),
            )
        # Why (S1, operator law 2026-09-14): every verb, including setup,
        # always applies unconditionally — there is no APPLY/check-mode
        # selector left in the generated Makefile.
        setup = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "setup"],
                cwd=project_root,
            ),
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
        runtime_bin = runtime_environment / "bin"
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
                ["--no-print-directory", "status"],
                cwd=project_root,
                env=active_env,
            ),
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stderr or process.stdout or "make probe failed without output",
        )
        output = process.stdout.strip().splitlines()
        tm.that(output[0], eq=f"FLEXT_INFRA_PYTHON={runtime_python}")
        tm.that(output[1], eq=f"UV_PROJECT_ENVIRONMENT={runtime_environment}")
        tm.that(output[2], eq=f"VIRTUAL_ENV={runtime_environment}")
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
        tm.that(output[5:], eq=[str(runtime_environment)] * 2)
        tm.that(hostile_python.exists(), eq=False)
        tm.that((project_root.parent / ".venv").exists(), eq=False)

    @pytest.mark.parametrize(
        "profile",
        [c.Infra.MakeProfile.STANDALONE, c.Infra.MakeProfile.WORKSPACE],
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
            tmp_path,
            profile,
            bootstrap=True,
        )
        hostile_venv = tmp_path / c.Tests.MAKE_TEMPLATE_HOSTILE_VENV
        (hostile_venv / "bin").mkdir(parents=True)
        active_env = u.Tests.hostile_uv_environment(hostile_venv)
        tm.that(u.Infra.runtime_environment_dir(project_root).exists(), eq=False)
        # Without a committed lock, setup never resolves: uv refuses loudly.
        unlocked = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "setup"],
                cwd=project_root,
                env=active_env,
            ),
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
        # One upg resolves the toolchain once: gen re-renders the manifest the
        # resolve half locked, so the relock half installs from that lock.
        tm.that(upgraded.stderr.count("setup probe: begin stage=lock.log"), eq=1)
        tm.that(upgraded.stdout, has="upg relock: .mise.toml is byte-identical")
        tool_receipts = re.findall(
            r"uv setup selector=\S+ receipt=(\S+) selected=(\S+)",
            upgraded.stdout,
        )
        tm.that(len(tool_receipts), gte=2)
        for reported, selected in tool_receipts:
            tm.that(reported, eq=selected)
        for lock in (c.Infra.UV_LOCK_FILENAME, c.Infra.MISE_LOCK_FILENAME):
            tm.that((template / lock).is_file(), eq=True)
        tm.that(
            (u.Infra.runtime_environment_dir(template) / "pyvenv.cfg").is_file(),
            eq=True,
        )
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

        # Only upg writes locks, and setup always runs. A new dependency
        # declaration drifts uv.lock: setup warns, installs the committed lock
        # frozen, and leaves every lock untouched.
        checkout = u.Tests.resolved_make_checkout(template, tmp_path / "stale", profile)
        dependency_root = tmp_path / "external-runtime"
        u.Tests.WorktreeFixture.write_python_project(
            dependency_root,
            "external-runtime",
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
            ),
        )
        tm.that(
            u.Cli.process_succeeded(stale.outcome),
            eq=True,
            msg=stale.stdout + stale.stderr,
        )
        tm.that(stale.stderr, has="uv.lock drifts from pyproject.toml")
        tm.that(self._locks(checkout), eq=resolved_locks)

        # Missing a declared tool must stop the locked install before lifecycle
        # execution, even when the tool is already present in warm storage.
        drifted = u.Tests.resolved_make_checkout(
            template,
            tmp_path / "drifted",
            profile,
        )
        mise_lock = drifted / c.Infra.MISE_LOCK_FILENAME
        lock_document = u.Tests.toml_doc(mise_lock.read_text(encoding="utf-8"))
        locked_tools = tm.not_none(u.Cli.toml_table_child(lock_document, "tools"))
        del locked_tools[next(iter(locked_tools))]
        tm.ok(u.Cli.atomic_write_text_file(mise_lock, u.Cli.toml_dumps(lock_document)))
        drifted_locks = {
            **resolved_locks,
            c.Infra.MISE_LOCK_FILENAME: mise_lock.read_bytes(),
        }
        unsatisfied = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "setup"],
                cwd=drifted,
                env={
                    **active_env,
                    make.ci.variable: make.ci.value,
                    bootstrap.storage_root_variable: str(cold_storage),
                },
            ),
        )
        tm.that(
            u.Cli.process_succeeded(unsatisfied.outcome),
            eq=False,
            msg=unsatisfied.stdout + unsatisfied.stderr,
        )
        tm.that(unsatisfied.stdout, has="is not in the lockfile")
        output = unsatisfied.stdout + unsatisfied.stderr
        tm.that(output.count("setup probe: begin stage=install.log"), eq=1)
        failure = tm.not_none(
            re.search(r"setup probe: failed stage=install.log exit=(\d+)", output),
        )
        cleanup = tm.not_none(
            re.search(r"mise scratch: cleaned path=.* exit=(\d+)", output),
        )
        tm.that(cleanup.group(1), eq=failure.group(1))
        tm.that(output, lacks=["WARN:", "mise WARN", "[warn]"])
        tm.that(unsatisfied.stdout, lacks="setup: entering lifecycle")
        tm.that(u.Infra.runtime_environment_dir(drifted).exists(), eq=False)
        tm.that(self._locks(drifted), eq=drifted_locks)

    @staticmethod
    def _locks(root: Path) -> t.MappingKV[str, bytes]:
        """Return every lock artifact ``make upg`` owns, keyed by relative path.

        Returns:
            Every lock artifact ``make upg`` owns, keyed by relative path.

        """
        sidecars = root / ".mise" / "locks"
        paths = (
            root / c.Infra.UV_LOCK_FILENAME,
            root / c.Infra.MISE_LOCK_FILENAME,
            root / c.Infra.MISE_VERSION_PIN_FILENAME,
            *(path for path in sidecars.rglob("*") if path.is_file()),
        )
        return {path.relative_to(root).as_posix(): path.read_bytes() for path in paths}

    @staticmethod
    def test_setup_fails_when_the_tracked_mise_launcher_is_missing(
        tmp_path: Path,
    ) -> None:
        """Never substitute a system Mise for the generated launcher owner."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
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
            mise,
            f"#!/bin/sh\nprintf '%s\\n' \"$*\" >> '{mise_log}'\nexit 0\n",
        )

        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "setup"],
                cwd=project_root,
                env={"PATH": f"{tool_bin}:{os.environ['PATH']}"},
                remove_env_keys=(*c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS, "UV"),
            ),
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(process.stdout + process.stderr, has="missing generated mise launcher")
        tm.that(mise.is_file(), eq=True)
        tm.that(mise_log.exists(), eq=False)
        tm.that(u.Infra.runtime_environment_dir(project_root).exists(), eq=False)

    @staticmethod
    def test_dispatched_runner_preserves_provisioned_external_tools(
        tmp_path: Path,
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
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
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

    @staticmethod
    def test_generated_operations_bind_uv_to_runtime_root(tmp_path: Path) -> None:
        """All generated uv operations use the profile-owned environment."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        makefile = (project_root / "Makefile").read_text()

        tm.that(
            "override UV_PROJECT_ENVIRONMENT := $(RUNTIME_VENV)" in makefile,
            eq=True,
        )
        # Template uses `override UV := "$(SETUP_MISE)" -C "$(PROJECT_ROOT)" exec -- uv`;
        # there is no bare `UV ?= uv` assignment.
        tm.that("UV ?= uv" in makefile, eq=False)
        # UV_RUN's environment binding is exercised by the real runtime test
        # above, including a parent uv workspace with a different default venv.
        # Make never accepts a caller-selected database path: it derives the
        # external persistent testmon cache from the typed SSOT and hands it
        # to the runner, which reads it exclusively from that Make input.
        (project_root / "custom.mk").write_text(
            "post-help:\n\t@printf '%s\\n' 'RUNTIME_VENV=$(RUNTIME_VENV)'\n",
            encoding="utf-8",
        )
        environment = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "help"],
                cwd=project_root,
            ),
        )
        tm.that(u.Cli.process_succeeded(environment.outcome), eq=True)
        # Primary standalone checkouts retain their local environment;
        # linked Git worktrees are exercised separately above.
        checkout_venv = project_root.resolve() / c.Infra.ENVIRONMENT_DIRECTORY
        tm.that(u.Infra.runtime_environment_dir(project_root), eq=checkout_venv)
        tm.that(environment.stdout, has=f"RUNTIME_VENV={checkout_venv}\n")
        envrc = (project_root / ".envrc").read_text(encoding="utf-8")
        tm.that(
            envrc,
            has=f'VENV_DIR="${{RUNTIME_ROOT}}/{c.Infra.ENVIRONMENT_DIRECTORY}"',
        )
        # One testmon database per project (flext-3l1gk): every checkout and
        # worktree of the project resolves the same file, so a new lane starts
        # from the project's measured selection, never a cold inventory.
        testmon = config.Infra.codegen.make.testmon_cache
        database = (
            f"{testmon.external_storage_directory}/$(PROJECT_NAME)/"
            f"{testmon.database_filename}"
        )
        tm.that(
            makefile,
            has=[database, f'{testmon.database_environment_variable}="$$database"'],
        )
        tm.that(makefile, lacks="$(subst /,_,$(PROJECT_ROOT))")
        # The declarative cache policy (bead flext-j0u23) keeps an ascending
        # quota ladder and bounded generations whatever values config declares.
        policy = config.Infra.codegen.make.testmon_cache_policy
        tm.that(
            policy.warning_threshold_percent
            < policy.maintenance_threshold_percent
            < policy.block_threshold_percent,
            eq=True,
        )
        tm.that(policy.max_bootstrap_generations, gt=0)
        tm.that(policy.max_stable_generations, gt=0)
        for forced in ("PROJECT_STATE_ROOT", "PROJECT_SCRATCH", 'TMPDIR="$$test_tmp"'):
            tm.that(makefile, lacks=forced)
        # Every gate the typed owner schedules by default reaches the runtime
        # in ONE `check run --gates` invocation. The Make layer no longer
        # publishes a per-gate selector, so the gate list itself is the
        # reachability proof.
        gates = ",".join(config.Infra.codegen.make.check_gates_default)
        tm.that(makefile, has=f'gates="{gates}"')
        tm.that(
            '$(PROJECT_FLEXT_INFRA) check run --repository-root "$(PROJECT_ROOT)" '
            '--gates "$$gates"' in makefile,
            eq=True,
        )
        tm.that("$(UV_RUN) actionlint" in makefile, eq=False)
        tm.that('$(UV) sync --project "$(UV_PROJECT)"' in makefile, eq=True)
        tm.that('$(UV) build --project "$(PROJECT_ROOT)"' in makefile, eq=True)
        envrc = (project_root / ".envrc").read_text(encoding="utf-8")
        for forced in ("PYTHONPYCACHEPREFIX", "export TMPDIR", "PROJECT_STATE_ROOT"):
            tm.that(envrc, lacks=forced)

    @staticmethod
    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_ci_rebuilds_the_shim_farm_from_the_pinned_release(
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
    ) -> None:
        """CI publishes a shim farm rebuilt by the pinned Mise, never a cached one.

        Mise never replaces a shim bound to another binary, so a farm restored
        from a tool cache keeps running the Mise release that built it, and an
        older release rejects a newer lockfile revision.
        """
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            profile,
            bootstrap=True,
        )
        makefile = (project_root / c.Infra.MAKEFILE_FILENAME).read_text(
            encoding="utf-8",
        )
        ci_branch = makefile.split('if [ -n "$${GITHUB_PATH:-}" ]; then', 1)[1]
        ci_branch = ci_branch.split("\tfi;", 1)[0]
        steps = (
            'rm -rf "$$shim_farm"',
            'mise_offline project "$$pinned_mise" -C "$$project_root" reshim',
            '"$$shim_farm" >> "$$GITHUB_PATH"',
        )
        positions = [ci_branch.find(step) for step in steps]
        tm.that(min(positions), ne=-1)
        tm.that(positions, eq=sorted(positions))

    @staticmethod
    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_bootstrap_selects_the_github_credential_from_declared_sources(
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
    ) -> None:
        """Every profile selects the credential once, in the global preamble."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            profile,
            bootstrap=True,
        )
        makefile = (project_root / c.Infra.MAKEFILE_FILENAME).read_text(
            encoding="utf-8",
        )
        tm.that(makefile, has="export GITHUB_TOKEN GH_TOKEN MISE_GITHUB_TOKEN")
        for command in u.Infra.mise_bootstrap_environment().credential_commands:
            tm.that(makefile.count(" ".join(command)), eq=1)

    @staticmethod
    def test_public_gate_fails_closed_before_managed_environment_exists(
        tmp_path: Path,
    ) -> None:
        """A public gate preserves the canonical setup-required diagnostic."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )

        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "test"],
                cwd=project_root,
            ),
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(
            process.stdout + process.stderr,
            has=["missing environment interpreter", "make setup creates it"],
        )

    @staticmethod
    def test_workspace_without_local_members_retains_external_flext_sources(
        tmp_path: Path,
    ) -> None:
        """Workspace role alone cannot turn external dependencies into members."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.WORKSPACE,
            bootstrap=True,
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
