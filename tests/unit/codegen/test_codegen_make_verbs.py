"""Generated Make verb rendering and dispatch contract.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, m, u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeVerbs:
    """Prove every declared verb renders one reachable, inert-input target."""

    @staticmethod
    @pytest.mark.parametrize(
        "profile",
        [c.Infra.MakeProfile.WORKSPACE, c.Infra.MakeProfile.STANDALONE],
    )
    def test_build_verb_renders_uv_build_for_packaged_repositories(
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
    ) -> None:
        """A repository that publishes a package keeps the real build recipe.

        The `package` flag is an input of the fixture, not a frozen constant:
        both branches of the flag are exercised (the false branch lives in the
        twin test) so the contract holds for any valid manifest value.
        """
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            profile,
            shape=u.Tests.MakeEnvironmentShape(package=True),
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")
        tm.that('$(UV) build --project "$(PROJECT_ROOT)"' in makefile, eq=True)
        tm.that(makefile, lacks="package=false (content-only root)")

    @staticmethod
    @pytest.mark.parametrize(
        "profile",
        [c.Infra.MakeProfile.WORKSPACE, c.Infra.MakeProfile.STANDALONE],
    )
    def test_build_verb_renders_typed_noop_for_package_false_roots(
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
    ) -> None:
        """A content-only root (package=false) builds nothing and says so.

        `uv build` on a package:false root cannot produce a wheel (no content
        to ship) and fails the wheel step after wasting an sdist — the invest
        root proof (92MB sdist, wheel failure, exit 2). The generated verb
        must instead emit a typed receipt and exit zero. The `package` flag is
        the fixture input; both branches are exercised across the twins.
        """
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            profile,
            shape=u.Tests.MakeEnvironmentShape(package=False),
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")
        tm.that('$(UV) build --project "$(PROJECT_ROOT)"' in makefile, eq=False)
        tm.that(makefile, has="package=false (content-only root)")
        # The noop verb itself exists with one body in both profiles.
        tm.that(makefile, has="_builtin-build: _builtin_build_artifacts")
        tm.that(makefile, has="_builtin_build_artifacts:")

    @staticmethod
    @pytest.mark.parametrize(
        "profile",
        [c.Infra.MakeProfile.WORKSPACE, c.Infra.MakeProfile.STANDALONE],
    )
    def test_every_declared_check_gate_reaches_the_runtime(
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
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
            tmp_path,
            profile,
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
        # Every profile, the workspace root included, schedules the declared
        # gates on its own project through one local `check run` body.
        scheduled = ",".join(config.Infra.codegen.make.check_gates_default)
        tm.that(makefile, has=f'gates="{scheduled}"')
        for gate in config.Infra.codegen.make.check_gates_default:
            tm.that(scheduled.split(","), has=gate)
        tm.that(makefile, has='--gates "$$gates"')
        check_invocations = tuple(
            line for line in makefile.splitlines() if '--gates "$$gates"' in line
        )
        tm.that(check_invocations, empty=False)
        for invocation in check_invocations:
            tm.that(invocation, lacks="--apply")
        tm.that(makefile, has="--apply")
        tm.that(makefile, lacks="--report-findings")

    @staticmethod
    def test_standalone_check_executes_its_declared_default_gates(
        tmp_path: Path,
    ) -> None:
        """Standalone check runs exactly the owner-declared default gate set."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        invocation_log = tmp_path / "check-invocation.log"
        runtime_python = u.Infra.runtime_python(project_root)
        u.Tests.write_executable(
            runtime_python,
            f"#!/bin/sh\nprintf '%s\\n' \"$*\" > '{invocation_log}'\n",
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
            ),
        )

        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        gates = ",".join(config.Infra.codegen.make.check_gates_default)
        invocation = invocation_log.read_text(encoding="utf-8")
        tm.that(invocation, has="-m flext_infra check run")
        tm.that(invocation, has=f"--gates {gates}")
        tm.that(invocation, lacks="--apply")

    @staticmethod
    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_help_prints_description_as_literal_data(
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
    ) -> None:
        """Help preserves quotes and expansion syntax without executing them."""
        description = (
            'Print checkout\'s "${HOME}", $(shell touch make-effect), '
            "and `touch shell-effect`."
        )
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            profile,
            shape=u.Tests.MakeEnvironmentShape(
                extra_verbs=(
                    m.Infra.MakeVerbSpec(name="literal-help", description=description),
                ),
            ),
        )
        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "help"],
                cwd=project_root,
                options=m.Cli.ProcessOptions(
                    remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
                ),
            ),
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tm.that(process.stdout, has=description)
        tm.that((project_root / "make-effect").exists(), eq=False)
        tm.that((project_root / "shell-effect").exists(), eq=False)

    @staticmethod
    def test_generated_make_ignores_forbidden_makeflags_overrides(
        tmp_path: Path,
    ) -> None:
        """An undeclared MAKEFLAGS override is inert, never a validation error.

        GNU Make propagates any variable on MAKEFLAGS (or the command line) as
        a ``command line override`` to every child process. S1 (operator law
        2026-09-14) removed the caller-input guard entirely — the generated
        Makefile validates no input at all — so an unrelated MAKEFLAGS entry
        is simply ignored and `help` still succeeds.
        """
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )

        hostile_env = {"MAKEFLAGS": "FORBIDDEN_VAR=hostile"}
        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "help"],
                cwd=project_root,
                options=m.Cli.ProcessOptions(
                    env=hostile_env,
                    remove_env_keys=tuple(
                        key
                        for key in c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS
                        if key not in hostile_env
                    ),
                ),
            ),
        )

        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        output = process.stdout + process.stderr
        tm.that(output, lacks="Unsupported Make input")
        tm.that(output, lacks="declared public inputs are")

    @staticmethod
    def test_generated_make_dispatches_script_verbs_to_builtin_targets(
        tmp_path: Path,
    ) -> None:
        """Auto-discovered script verbs get _builtin-<verb> dispatch targets."""
        extra_verbs = (
            m.Infra.MakeVerbSpec(
                name="sync",
                description="Dispatch sync through the declared script dispatcher.",
            ),
        )
        script_dispatch = m.Infra.ScriptDispatchSpec(
            dispatcher="scripts/dispatch.py",
            roots=("scripts",),
        )
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
            shape=u.Tests.MakeEnvironmentShape(
                extra_verbs=extra_verbs,
                script_dispatch=script_dispatch,
            ),
        )
        (project_root / "scripts" / "sync").mkdir(parents=True)
        (project_root / "scripts" / "sync" / "all.sh").write_text(
            "#!/bin/sh\necho sync\n",
            encoding="utf-8",
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")
        tm.that("_builtin-sync:" in makefile, eq=True)
        tm.that("scripts/dispatch.py" in makefile, eq=True)
        tm.that("sync" in makefile, eq=True)

    @staticmethod
    def test_arbitrary_unknown_command_line_variable_is_ignored(
        tmp_path: Path,
    ) -> None:
        """An arbitrary unknown command-line variable never blocks a verb.

        There is no declared-input allowlist left in the generated Makefile
        (S1, operator law 2026-09-14): passing any undeclared `NAME=value`
        is inert.
        """
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )

        process = tm.ok(
            u.Cli.run_raw(
                [c.Infra.MAKE, "--no-print-directory", "help", "FOO=bar"],
                cwd=project_root,
                options=m.Cli.ProcessOptions(
                    remove_env_keys=c.Infra.ORCHESTRATOR_REMOVE_ENV_KEYS,
                ),
            ),
        )

        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )

    @staticmethod
    def test_generated_makefile_routes_every_verb_unconditionally(
        tmp_path: Path,
    ) -> None:
        """Every public verb maps unconditionally to its one implementation.

        S1 (operator law 2026-09-14) removed the CHECK_ONLY/APPLY selector
        entirely: there is no longer a check-mode sibling recipe for any
        verb, so the public mapping is a single fixed target per verb.
        """
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")

        tm.that(
            makefile,
            has="upg: _builtin_require_runtime_root _bootstrap_setup_tools",
        )
        tm.that(makefile, has="_builtin-fmt: _builtin_fmt_all")
        tm.that(makefile, has="_builtin-fix: _builtin_fix_all")
        tm.that(makefile, lacks="fix-enforcement")
        tm.that(makefile, has="_builtin-fix-namespace: _builtin_fix_namespace")
        tm.that(makefile, has="_builtin-fix-accessors: _builtin_fix_accessors")
        # Each repository evaluates only itself: no _builtin-self-* fan-out.
        tm.that(makefile, lacks="_builtin-self-")
        tm.that(makefile, has="_builtin-sonarcloud-sync: _builtin_sonarcloud_sync_all")
        tm.that(
            makefile,
            has="_builtin_sonarcloud_sync_all: _builtin_require_environment",
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
        profile = c.Infra.MakeProfile.STANDALONE
        for verb in config.Infra.codegen.make.verbs:
            if profile not in verb.profiles:
                continue
            rendered = re.search(
                rf"^_builtin-{re.escape(verb.name)}:(\s|$)"
                rf"|^{re.escape(verb.name)}:(\s|$)",
                makefile,
                re.MULTILINE,
            )
            tm.that(
                rendered is not None,
                eq=True,
                msg=f"declared verb {verb.name!r} renders no Make target",
            )
        for forbidden in (
            "CHECK_ONLY",
            "APPLY",
            "PUBLIC_INPUTS",
            "_builtin_gen_check",
            "_builtin-conform",
        ):
            tm.that(makefile, lacks=forbidden)

    @staticmethod
    def test_every_declared_verb_renders_implementation_target(
        tmp_path: Path,
    ) -> None:
        """Every codegen.yaml-declared verb renders a reachable implementation.

        Derived from the typed SSOT (``config.Infra.codegen.make.verbs``), never
        a hand list: a verb declared in config without a rendered body in the
        template — the silent ``Nothing to be done`` exit-0 class reported on
        ``fix-accessors`` — fails here for the profile it declares.
        """
        declared = tuple(config.Infra.codegen.make.verbs)
        # Template-declared shapes without a _builtin twin: setup/upg carry
        # their own bootstrap recipes; help/clean render short bodies.
        body_free = frozenset({"setup", "upg", "help", "clean"})
        for profile in c.Infra.MakeProfile:
            project_root, _repository_root = u.Tests.render_make_environment(
                tmp_path / profile.value,
                profile,
            )
            makefile = (project_root / "Makefile").read_text(encoding="utf-8")
            lines = makefile.splitlines()
            public_tokens = next(
                line[len("PUBLIC_VERBS :=") :].split()
                for line in lines
                if line.startswith("PUBLIC_VERBS :=")
            )
            builtin_tokens = next(
                line[len("BUILTIN_VERBS :=") :].split()
                for line in lines
                if line.startswith("BUILTIN_VERBS :=")
            )
            public_padded = f" {' '.join(public_tokens)} "
            builtin_padded = f" {' '.join(builtin_tokens)} "
            for verb in declared:
                if profile not in verb.profiles:
                    continue
                tm.that(public_padded, has=f" {verb.name} ")
                tm.that(builtin_padded, has=f" {verb.name} ")
                if verb.name not in body_free:
                    tm.that(makefile, has=f"_builtin-{verb.name}:")
