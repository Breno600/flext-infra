"""Execution tests for the generated project Make verb contract."""

from __future__ import annotations

import os
import stat
import tempfile
from pathlib import Path

from flext_infra import c, config, m as infra_m
from flext_infra.basemk.generator import FlextInfraBaseMkGenerator
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_tests import tm
from tests import m, p, u, u as test_u

_MAKE_ISOLATION_ENV_KEYS = (
    "FLEXT_ROOT",
    "FLEXT_STANDALONE",
    "FLEXT_WORKSPACE_ROOT",
    "PROJECT",
    "PROJECTS",
    "WORKSPACE_ROOT",
)
_MAKE_TEST_ENV_KEYS = (
    "BASH_ENV",
    "DEPENDENCY",
    "FILE",
    "FILES",
    "CHANGED_ONLY",
    "CHECK_GATES",
    "VALIDATE_GATES",
    "PYTEST_ARGS",
    "MATCH",
    "FAIL_FAST",
    "RUFF_ARGS",
    "PYRIGHT_ARGS",
    "CHECK_ONLY",
    "CI",
    "MAKEFLAGS",
    "MAKEOVERRIDES",
    "MFLAGS",
    "MAKELEVEL",
    "GNUMAKEFLAGS",
    "FLEXT_INFRA_PYTHON",
    "FLEXT_PYTEST_ARGS_RAW",
    "FLEXT_PYTEST_DIAG_RAW",
    "FLEXT_PYTEST_FAIL_FAST_RAW",
    "FLEXT_PYTEST_FILE_RAW",
    "FLEXT_PYTEST_FILES_RAW",
    "FLEXT_PYTEST_MATCH_RAW",
    "FLEXT_PYTEST_REPORTS_RAW",
    "FLEXT_PYTEST_TARGET_RAW",
    "FLEXT_PYTEST_VERBOSE_RAW",
    "FLEXT_PYTEST_WHAT_RAW",
    "UV",
    "WHAT",
    *_MAKE_ISOLATION_ENV_KEYS,
)


def _render_base_mk() -> str:
    result = FlextInfraBaseMkGenerator().generate_basemk()
    rendered: str = tm.ok(result)
    return rendered


def _render_project_makefile() -> str:
    """Render the standalone project Makefile from its single conform owner.

    R12 moved every public verb out of ``base.mk`` and into the project
    ``Makefile`` template. The verb contract therefore lives in the conform
    projection, so these tests exercise the artifact a real checkout runs.
    """
    repository = test_u.Tests.repository_ref(
        "demo-project", role=c.Infra.RepositoryRole.STANDALONE
    )
    workspace = infra_m.Infra.WorkspaceSpec(
        version=c.Infra.WORKSPACE_MANIFEST_VERSION,
        name=repository.name,
        repository=repository,
        project=infra_m.Infra.ProjectSpec(
            package_name="demo_project",
            class_stem="DemoProject",
            namespace="DemoProject",
            constant_name=repository.name,
            namespace_attribute="demo_project",
            alias="demo_project",
            environment_prefix="DEMO_PROJECT_",
            description="Demo project",
            version="0.12.0.dev0",
            license="MIT",
            author_name="FLEXT Team",
            author_email="team@flext.dev",
            upstream="flext_cli",
            homepage=repository.url.removesuffix(".git"),
            documentation=repository.url.removesuffix(".git"),
            workspace_root_rel=".",
            year=2026,
        ),
    )
    with tempfile.TemporaryDirectory() as staging:
        root = Path(staging) / "demo-project"
        request = infra_m.Infra.CodegenConformRequest(
            root=root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        plan = tm.ok(
            FlextInfraCodegenConform(
                workspace_root=root, request=request, initial_workspace=workspace
            ).plan(request)
        )
    makefile_plans = tuple(
        file for file in plan.files if Path(file.path).name == c.Infra.MAKEFILE_FILENAME
    )
    tm.that(makefile_plans, len=1)
    rendered: str = makefile_plans[0].rendered
    return rendered


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_stubs(bin_dir: Path, log_path: Path) -> None:
    bin_dir.mkdir(parents=True, exist_ok=True)
    _write_executable(
        bin_dir / "python",
        '#!/usr/bin/env bash\nprintf \'python %s\\n\' "$*" >> "'
        + str(log_path)
        + '"\nexit 0\n',
    )
    _write_executable(
        bin_dir / "uv",
        '#!/usr/bin/env bash\nprintf \'uv %s\\n\' "$*" >> "'
        + str(log_path)
        + '"\nif [ "$1" = "sync" ]; then\n'
        + '  mkdir -p "${UV_PROJECT_ENVIRONMENT}/bin"\n'
        + '  cp "$(dirname "$0")/python" "${UV_PROJECT_ENVIRONMENT}/bin/python"\n'
        + "fi\nexit 0\n",
    )


def _write_venv_python_stub(
    project_root: Path, log_path: Path, *, include_env: bool = False
) -> None:
    venv_bin = project_root / ".venv" / "bin"
    venv_bin.mkdir(parents=True, exist_ok=True)
    body = (
        "#!/usr/bin/env bash\nprintf "
        "'PYTHONPATH=%s MYPYPATH=%s python %s\\n' "
        '"${PYTHONPATH-unset}" "${MYPYPATH-unset}" "$*" >> "'
        + str(log_path)
        + '"\nexit 0\n'
        if include_env
        else '#!/usr/bin/env bash\nprintf \'python %s\\n\' "$*" >> "'
        + str(log_path)
        + '"\nexit 0\n'
    )
    _write_executable(venv_bin / "python", body)


def _write_managed_python_stub(path: Path, log_path: Path) -> None:
    _write_executable(
        path,
        "#!/usr/bin/env bash\nprintf "
        "'PYTHONPATH=%s MYPYPATH=%s VIRTUAL_ENV=%s UV_PROJECT=%s "
        "UV_PROJECT_ENVIRONMENT=%s python %s\\n' "
        '"${PYTHONPATH-unset}" "${MYPYPATH-unset}" "${VIRTUAL_ENV-unset}" '
        '"${UV_PROJECT-unset}" "${UV_PROJECT_ENVIRONMENT-unset}" "$*" >> "'
        + str(log_path)
        + '"\nexit 0\n',
    )


def _write_pytest_diag_python_stub(
    project_root: Path, *, payload: str, exit_code: int
) -> None:
    del payload, exit_code
    venv_bin = project_root / ".venv" / "bin"
    venv_bin.mkdir(parents=True, exist_ok=True)
    body = (
        "#!/usr/bin/env bash\n"
        'if [[ "$*" == *"-m flext_infra._pytest_entry"* ]]; then\n'
        "  exit 0\n"
        "fi\n"
        "exit 97\n"
    )
    _write_executable(venv_bin / "python", body)


def _write_project(project_root: Path, *, include_parent: bool = False) -> None:
    """Materialize a project whose Makefile is the real conform projection.

    ``include_parent`` keeps the legacy shape where the shared infrastructure
    file lives one directory up, so worktree/workspace detection still has a
    parent ``base.mk`` to find.
    """
    (project_root / "tests").mkdir(parents=True, exist_ok=True)
    if include_parent:
        (project_root.parent / "base.mk").write_text(
            _render_base_mk(), encoding="utf-8"
        )
    else:
        (project_root / "base.mk").write_text(_render_base_mk(), encoding="utf-8")
    (project_root / "Makefile").write_text(_render_project_makefile(), encoding="utf-8")
    # Every generated verb depends on _builtin_require_environment, which
    # provisions a venv when the interpreter is absent. Without a pyproject the
    # provisioning fails before the verb body runs, so the fixture never reaches
    # the contract under test. Materialize the minimum a real checkout has: a
    # project manifest and an interpreter the guard accepts.
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "demo-project"\nversion = "0.12.0.dev0"\n'
        'requires-python = ">=3.13"\n',
        encoding="utf-8",
    )


def _run_make(
    project_root: Path, *args: str, env: dict[str, str] | None = None
) -> p.Cli.CommandOutput:
    active_env = os.environ.copy()
    for key in _MAKE_TEST_ENV_KEYS:
        active_env.pop(key, None)
    if env is not None:
        active_env.update(env)
    result = u.Cli.run_raw(
        ["make", *args],
        cwd=project_root,
        env=active_env,
        remove_env_keys=_MAKE_TEST_ENV_KEYS,
    )
    if result.success:
        return result.value
    return m.Cli.CommandOutput(
        stdout="", stderr=result.error or "make execution failed", exit_code=1
    )


class TestsFlextInfraBasemkMakeContract:
    """Behavior contract for test_make_contract."""

    def test_make_verb_runs_pre_and_post_hooks_from_custom_mk(
        self, tmp_path: Path
    ) -> None:
        """A member verb runs custom.mk pre-<verb> and post-<verb> around its body."""
        log_path = tmp_path / "tool.log"
        bin_dir = tmp_path / "bin"
        _write_stubs(bin_dir, log_path)
        _write_project(tmp_path)
        _write_venv_python_stub(tmp_path, log_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "demo.py").write_text("x = 1\n", encoding="utf-8")
        # Real member Makefiles -include custom.mk (see flext-core/Makefile);
        # replicate that so the verb hook seam can see the custom hooks.
        (tmp_path / "custom.mk").write_text(
            ".PHONY: pre-check post-check\n"
            "pre-check:\n\t@echo HOOK_PRE_CHECK\n"
            "post-check:\n\t@echo HOOK_POST_CHECK\n",
            encoding="utf-8",
        )
        result = _run_make(
            tmp_path,
            "check",
            "FILE=src/demo.py",
            "CHECK_GATES=mypy",
            f"UV={bin_dir / 'uv'}",
            env={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )
        output = result.stdout + result.stderr
        tm.that(result.exit_code, eq=0)
        pre_at = output.find("HOOK_PRE_CHECK")
        post_at = output.find("HOOK_POST_CHECK")
        tm.that(pre_at >= 0 and post_at >= 0, eq=True)
        tm.that(pre_at < post_at, eq=True)

    def test_make_verb_runs_what_scoped_and_verb_wide_hooks_in_order(
        self, tmp_path: Path
    ) -> None:
        """pre/post hooks run verb-wide and WHAT-scoped, ordered around the body."""
        _write_project(tmp_path)
        _write_pytest_diag_python_stub(
            tmp_path,
            payload=("failed_count=0\nerror_count=0\nwarning_count=0\nskipped_count=0"),
            exit_code=0,
        )
        (tmp_path / "custom.mk").write_text(
            ".PHONY: pre-test post-test pre-test-contract post-test-contract "
            "_custom_test_contract\n"
            "pre-test:\n\t@echo H_PRE_TEST\n"
            "pre-test-contract:\n\t@echo H_PRE_TEST_CONTRACT\n"
            "_custom_test_contract:\n\t@echo BODY_CONTRACT\n"
            "post-test-contract:\n\t@echo H_POST_TEST_CONTRACT\n"
            "post-test:\n\t@echo H_POST_TEST\n",
            encoding="utf-8",
        )
        result = _run_make(
            tmp_path, "test", "DIAG=1", "MATCH=contract", "WHAT=contract"
        )
        tm.that(result.exit_code, eq=0)
        # The pytest body reports DIAG on stderr; the four hooks print on stdout.
        # Assert the hook ordering on stdout (verb-wide before WHAT-scoped for pre,
        # WHAT-scoped before verb-wide for post) and that the body actually ran.
        stdout = result.stdout
        order = [
            stdout.find("H_PRE_TEST"),
            stdout.find("H_PRE_TEST_CONTRACT"),
            stdout.find("H_POST_TEST_CONTRACT"),
            stdout.find("H_POST_TEST"),
        ]
        tm.that(stdout, has="BODY_CONTRACT")
        tm.that(all(position >= 0 for position in order), eq=True)
        tm.that(order == sorted(order), eq=True)

    def test_make_verbs_dispatch_custom_what_handlers(self, tmp_path: Path) -> None:
        """Every verb runs _custom_<verb>_<what> from custom.mk for a custom WHAT."""
        _write_project(tmp_path)
        (tmp_path / "custom.mk").write_text(
            ".PHONY: _custom_build_proto _custom_test_dbt _custom_run_x\n"
            "_custom_build_proto:\n\t@echo CUSTOM_BUILD_PROTO\n"
            "_custom_test_dbt:\n\t@echo CUSTOM_TEST_DBT\n"
            "_custom_run_x:\n\t@echo CUSTOM_RUN_X\n",
            encoding="utf-8",
        )
        # `docs` is no longer a public verb (mro-x0rau.3), so dispatching it
        # would assert a target the generator does not ship.
        for verb, what, marker in (
            ("build", "proto", "CUSTOM_BUILD_PROTO"),
            ("test", "dbt", "CUSTOM_TEST_DBT"),
            ("run", "x", "CUSTOM_RUN_X"),
        ):
            result = _run_make(tmp_path, verb, f"WHAT={what}")
            output = result.stdout + result.stderr
            tm.that(result.exit_code, eq=0)
            tm.that(output, has=marker)

    def test_make_run_verb_validates_its_what_selector(self, tmp_path: Path) -> None:
        """An unsupported WHAT is rejected against the declared selectors.

        `run` declares a default WHAT (`default`), so a bare `make run` resolves
        to it and executes the project entry point rather than demanding WHAT.
        The contract still worth guarding is that an undeclared WHAT is refused
        loudly, naming the allowed set, instead of silently doing nothing.
        """
        _write_project(tmp_path)
        _write_venv_python_stub(tmp_path, tmp_path / "venv.log")
        (tmp_path / "custom.mk").write_text("# no handlers\n", encoding="utf-8")

        missing = _run_make(tmp_path, "run", "WHAT=nope")

        tm.that(missing.exit_code, ne=0)
        tm.that(missing.stdout + missing.stderr, has="unsupported run WHAT=nope")
        tm.that(missing.stdout + missing.stderr, has="default")

    def test_make_build_uses_uv_and_propagates_failure(self, tmp_path: Path) -> None:
        """Fail the target when the uv builder fails."""
        log_path = tmp_path / "tool.log"
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir()
        _write_executable(
            bin_dir / "uv",
            '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "' + str(log_path) + '"\nexit 23\n',
        )
        _write_project(tmp_path)
        # Every verb depends on _builtin_require_environment, which provisions
        # the venv when the interpreter is absent. Without the stub interpreter
        # the uv stub answers that provisioning call instead of the build, so
        # the log records the wrong command and the failure never propagates.
        _write_venv_python_stub(tmp_path, tmp_path / "venv.log")

        result = _run_make(
            tmp_path,
            "build",
            f"UV={bin_dir / 'uv'}",
            env={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )

        tm.that(result.exit_code, ne=0)
        tm.that(
            log_path.read_text(encoding="utf-8").splitlines(),
            eq=[f"build --project {tmp_path}"],
        )
        tm.that(result.stdout, lacks="Build complete")

    def test_make_help_lists_supported_options(self, tmp_path: Path) -> None:
        """Advertise every declared verb with its WHAT selectors."""
        _write_project(tmp_path)
        result = _run_make(tmp_path, "help")
        tm.that(result.exit_code, eq=0)
        declared = tuple(config.Infra.codegen.make.verbs)
        tm.that(bool(declared), eq=True)
        for verb in declared:
            tm.that(result.stdout, has=verb.name)
        # R12: `docs` became a WHAT selector on the standard verbs, so it must
        # never be advertised as a verb of its own.
        tm.that(result.stdout, lacks="  docs ")
        tm.that(result.stdout, lacks="check-fast")

    def test_make_help_documents_and_lists_custom_hooks(self, tmp_path: Path) -> None:
        """Help documents the hook contract and lists custom.mk-defined hooks."""
        _write_project(tmp_path)
        (tmp_path / "custom.mk").write_text(
            ".PHONY: pre-check post-test-all _custom_check_myscan\n"
            "pre-check:\n\t@true\n"
            "post-test-all:\n\t@true\n"
            "_custom_check_myscan:\n\t@true\n",
            encoding="utf-8",
        )
        result = _run_make(tmp_path, "help")
        tm.that(result.exit_code, eq=0)
        # The hook contract is documented.
        tm.that(result.stdout, has=["Custom hooks", "pre-<verb>", "post-<verb>"])
        # The actual custom.mk hooks and custom WHATs are discovered and listed.
        tm.that(
            result.stdout, has=["pre-check", "post-test-all", "_custom_check_myscan"]
        )

    def test_rendered_base_mk_declares_cli_group_roots(self) -> None:
        """Verify generated command roots use canonical CLI groups."""
        # The infra command roots are bootstrap wiring base.mk owns: R12 moved
        # the public VERBS to the project Makefile, not the roots they call.
        rendered = _render_base_mk()
        tm.that(
            rendered,
            has=[
                "FLEXT_INFRA_PYTHON ?= $(VENV_PYTHON)",
                "PROJECT_INFRA_HOME := $(WORKSPACE_ROOT)/flext-infra",
                "PROJECT_INFRA_SRC := $(PROJECT_INFRA_HOME)/src",
                "PROJECT_INFRA_PYTHONPATH ?= $(PROJECT_INFRA_SRC)",
                'PROJECT_INFRA_ROOT := test -x "$(FLEXT_INFRA_PYTHON)"',
                'PYTHONPATH="$(PROJECT_INFRA_PYTHONPATH)" $(FLEXT_INFRA_PYTHON) -m flext_infra',
                'PROJECT_INFRA_CHECK := FLEXT_WORKSPACE_ROOT="$(WORKSPACE_ROOT)" $(PROJECT_INFRA_ROOT) check',
                'PROJECT_INFRA_CODEGEN := FLEXT_WORKSPACE_ROOT="$(WORKSPACE_ROOT)" $(PROJECT_INFRA_ROOT) codegen',
                'PROJECT_INFRA_DEPS := FLEXT_WORKSPACE_ROOT="$(WORKSPACE_ROOT)" $(PROJECT_INFRA_ROOT) deps',
                'PROJECT_INFRA_DOCS := FLEXT_WORKSPACE_ROOT="$(WORKSPACE_ROOT)" $(PROJECT_INFRA_ROOT) docs',
                'PROJECT_INFRA_GITHUB := FLEXT_WORKSPACE_ROOT="$(WORKSPACE_ROOT)" $(PROJECT_INFRA_ROOT) github',
                'PROJECT_INFRA_VALIDATE := FLEXT_WORKSPACE_ROOT="$(WORKSPACE_ROOT)" $(PROJECT_INFRA_ROOT) validate',
            ],
        )

    def test_make_managed_infra_python_isolated_from_consumer_environment(
        self, tmp_path: Path
    ) -> None:
        """Run flext-infra only through the managed interpreter, never the caller's.

        The recipe pins the interpreter with `override FLEXT_INFRA_PYTHON :=
        $(FLEXT_INFRA_RUNTIME_PYTHON)`, so an ambient FLEXT_INFRA_PYTHON is
        deliberately IGNORED -- a stronger contract than honouring it -- and the
        hostile PYTHONPATH/MYPYPATH/VIRTUAL_ENV/UV_* values are stripped by the
        `env -u ...` prefix before the managed interpreter runs.
        """
        log_path = tmp_path / "tool.log"
        hostile_python = tmp_path / "hostile" / "bin" / "python"
        hostile_python.parent.mkdir(parents=True)
        _write_managed_python_stub(hostile_python, tmp_path / "hostile.log")
        _write_project(tmp_path)
        _write_venv_python_stub(tmp_path, log_path, include_env=True)

        result = _run_make(
            tmp_path,
            "check",
            "CHECK_GATES=mypy",
            env={
                "FLEXT_INFRA_PYTHON": str(hostile_python),
                "PYTHONPATH": str(tmp_path / "hostile-pythonpath"),
                "MYPYPATH": str(tmp_path / "hostile-mypypath"),
                "VIRTUAL_ENV": str(tmp_path / "hostile-venv"),
                "UV_PROJECT": str(tmp_path / "hostile-project"),
                "UV_PROJECT_ENVIRONMENT": str(tmp_path / "hostile-uv-venv"),
            },
        )

        tm.that(result.exit_code, eq=0)
        # The caller-supplied interpreter never ran.
        tm.that((tmp_path / "hostile.log").exists(), eq=False)
        # The managed one did, with every hostile variable stripped.
        tm.that(
            log_path.read_text(encoding="utf-8"),
            has=(
                f"PYTHONPATH={tmp_path / 'src'} MYPYPATH=unset "
                f"python -m flext_infra check run --workspace {tmp_path}"
            ),
        )

    def test_make_pins_the_infra_interpreter_to_the_managed_runtime(
        self, tmp_path: Path
    ) -> None:
        """A caller-supplied interpreter can never redirect the infra command.

        The recipe pins `override FLEXT_INFRA_PYTHON :=
        $(FLEXT_INFRA_RUNTIME_PYTHON)`, itself derived from the runtime venv
        path. That is why a hostile or missing FLEXT_INFRA_PYTHON in the
        environment cannot redirect execution: it is ignored outright rather
        than validated, which is the stronger guarantee.
        """
        log_path = tmp_path / "tool.log"
        _write_project(tmp_path)
        _write_venv_python_stub(tmp_path, log_path)

        result = _run_make(
            tmp_path,
            "check",
            "CHECK_GATES=mypy",
            env={"FLEXT_INFRA_PYTHON": str(tmp_path / "missing-python")},
        )

        # The bogus interpreter is ignored, so the run still succeeds through
        # the managed one -- and that is what executed.
        tm.that(result.exit_code, eq=0)
        tm.that(log_path.read_text(encoding="utf-8"), has="flext_infra check run")

    def test_rendered_base_mk_sanitizes_validation_env(self) -> None:
        """Verify base validation clears inherited Python import paths."""
        rendered = _render_base_mk()
        tm.that(
            rendered,
            has="BASE_INFRA_VALIDATE = $(PROJECT_INFRA_ROOT) validate",
            lacks='PYTHONPATH="$(WORKSPACE_ROOT)/flext-infra/src"',
        )

    def test_rendered_base_mk_validates_canonical_root_in_workspace_preflight(
        self,
    ) -> None:
        """Verify project preflight validates the canonical workspace root."""
        rendered = _render_base_mk()
        tm.that(
            rendered, has='basemk-validate --workspace "$(WORKSPACE_ROOT)/flext-infra"'
        )
        tm.that(rendered, lacks="AUTO_SYNC_BASE_AND_SCRIPTS")

    def test_rendered_base_mk_delegates_pytest_to_one_typed_runner(self) -> None:
        """Keep process policy and report ownership out of generated shell."""
        rendered = _render_project_makefile()
        tm.that(
            rendered,
            has=[
                "python -m flext_infra._pytest_entry",
                "FLEXT_PYTEST_FILE_RAW",
                "FLEXT_PYTEST_MATCH_RAW",
                "FLEXT_PYTEST_WHAT_RAW",
            ],
            lacks=["_all_pytest_args", "pytest-diag", "PYTEST_TARGETS"],
        )

    def test_rendered_base_mk_does_not_reimplement_pytest_reports_in_shell(
        self,
    ) -> None:
        """The typed Python owner validates reports without shell parsing."""
        rendered = _render_project_makefile()
        tm.that(
            rendered,
            lacks=[
                "_coverage_args=",
                "coverage report was not generated",
                "pytest diagnostic extraction failed",
                "invalid pytest diagnostic counts contract",
                'source "$$',
                '. "$$',
            ],
        )

    def test_rendered_base_mk_exports_config_owned_pytest_deadlines(self) -> None:
        """Expose immutable typed policy while rejecting command-line overrides."""
        rendered = _render_project_makefile()
        policy = config.Infra.tooling.tools.pytest
        tm.that(
            rendered,
            has=[
                (
                    "override PYTEST_CASE_TIMEOUT_SECONDS := "
                    f"{policy.case_timeout_seconds}"
                ),
                (
                    "override PYTEST_RUN_TIMEOUT_SECONDS := "
                    f"{policy.run_timeout_seconds}"
                ),
                (
                    "override PYTEST_TERMINATION_GRACE_SECONDS := "
                    f"{policy.termination_grace_seconds}"
                ),
                "override PYTEST_TIMEOUT_EXIT_CODE :=",
            ],
        )

    def test_make_test_watchdog_terminates_running_pytest(self, tmp_path: Path) -> None:
        """A pytest run exceeding the wall clock is terminated with exit 124."""
        _write_project(tmp_path)
        # The recipe is `$(PYTEST_BOUNDED) $(UV_RUN) python -m ..._pytest_entry`,
        # so the process the watchdog must kill is spawned by `uv run`, not by
        # .venv/bin/python directly. Stub uv, or the run dies resolving the
        # interpreter before the timeout can fire.
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        _write_executable(
            bin_dir / "uv",
            "#!/usr/bin/env bash\n"
            'if [[ "$*" == *"_pytest_entry"* ]]; then sleep 5; fi\n'
            "exit 0\n",
        )
        _write_venv_python_stub(tmp_path, tmp_path / "tool.log")

        result = _run_make(
            tmp_path,
            "test",
            "PYTEST_PROCESS_TIMEOUT_SECONDS=1",
            f"UV={bin_dir / 'uv'}",
            env={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )

        tm.that(result.exit_code, ne=0)
        tm.that(result.stdout + result.stderr, has="Error 124")

    # R12 removed CHANGED_ONLY discovery with the rest of the pre-R12 verb
    # surface: it has no owner in src/ and appears nowhere in the generated
    # Makefile, only in the orphan base.mk (mro-x0rau.2). The test that guarded
    # it is deleted with the feature rather than kept asserting dead content.

    def test_make_check_file_scope_runs_mypy(self, tmp_path: Path) -> None:
        """Verify file-scoped checks invoke Mypy for the selected file."""
        log_path = tmp_path / "tool.log"
        bin_dir = tmp_path / "bin"
        _write_stubs(bin_dir, log_path)
        _write_project(tmp_path)
        _write_venv_python_stub(tmp_path, log_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "demo.py").write_text("x = 1\n", encoding="utf-8")

        result = _run_make(
            tmp_path,
            "check",
            "FILE=src/demo.py",
            "CHECK_GATES=mypy",
            f"UV={bin_dir / 'uv'}",
            env={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )

        tm.that(result.exit_code, eq=0)
        # R12: the Makefile no longer shells out to each tool. It delegates the
        # whole gate run to the typed check service, which owns tool selection,
        # file scoping and env isolation. Assert the delegation contract.
        logged = log_path.read_text(encoding="utf-8")
        tm.that(logged, has="flext_infra check run")
        tm.that(logged, has="--gates mypy")

    def test_mypy_execution_is_bounded_by_the_runtime_owner(self) -> None:
        """Every Mypy command carries the validated memory and time caps.

        mro-x0rau.3: base.mk defined MYPY_BOUNDED / VALIDATE_MYPY_LIMITS /
        REPORT_MYPY_FAILURE but invoked none of them once the daemon recipes
        were deleted, so grepping the rendered Make output proved nothing. The
        cap is applied in Python at the gate boundary; assert that owner.
        """
        bounded = u.Infra.mypy_limited_command(("python", "-m", "mypy", "src"))
        joined = " ".join(bounded)

        tm.that(joined, has="prlimit")
        tm.that(joined, has="timeout")
        tm.that(joined, has="--as=6442450944:6442450944")
        tm.that(joined, has="600s")
        tm.that(tuple(bounded[-4:]), eq=("python", "-m", "mypy", "src"))

    def test_mypy_resource_failure_is_distinguished_from_a_type_error(self) -> None:
        """Only a timeout or memory exhaustion yields a resource diagnostic.

        mro-x0rau.3: this classification lived in base.mk's REPORT_MYPY_FAILURE,
        which nothing invoked. The live owner is mypy_failure_diagnostic(), used
        by gates/mypy.py -- an ordinary type error must NOT be reported as a
        resource failure, and a 124 timeout must be.
        """
        type_error = m.Cli.CommandOutput(
            stdout="", stderr="demo.py:1: error: incompatible type", exit_code=1
        )
        timeout = m.Cli.CommandOutput(stdout="", stderr="", exit_code=124)

        tm.that(u.Infra.mypy_failure_diagnostic(type_error), eq=None)
        resource = u.Infra.mypy_failure_diagnostic(timeout)
        tm.that(resource, ne=None)
        tm.that(str(resource), has="bounded Mypy execution failed")
        tm.that(str(resource), has="exit=124")

    # mro-x0rau.3 deleted the daemon-* recipes (base_daemons.mk.j2): they were
    # unreachable in every real checkout because no generated Makefile includes
    # base.mk. The dmypy-timeout test is removed with the feature it guarded.

    def test_make_check_file_scope_unsets_python_path_env(self, tmp_path: Path) -> None:
        """Verify file-scoped checks clear inherited Python path variables.

        R12 routes every gate run through PROJECT_FLEXT_INFRA (the managed venv
        interpreter), not through `uv`, so the sanitized env must be observed on
        the interpreter the recipe actually launches.
        """
        log_path = tmp_path / "tool.log"
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        _write_executable(
            bin_dir / "python",
            '#!/usr/bin/env bash\nprintf \'python %s\\n\' "$*" >> "'
            + str(log_path)
            + '"\nexit 0\n',
        )
        _write_project(tmp_path)
        _write_venv_python_stub(tmp_path, log_path, include_env=True)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "demo.py").write_text("x = 1\n", encoding="utf-8")

        result = _run_make(
            tmp_path,
            "check",
            "FILE=src/demo.py",
            "CHECK_GATES=mypy",
            env={
                "PYTHONPATH": str(tmp_path / "poison-pythonpath"),
                "MYPYPATH": str(tmp_path / "poison-mypypath"),
            },
        )

        tm.that(result.exit_code, eq=0)
        expected_src = tmp_path / "src"
        tm.that(
            log_path.read_text(encoding="utf-8"),
            has=(
                f"PYTHONPATH={expected_src} MYPYPATH=unset "
                f"python -m flext_infra check run --workspace {tmp_path} --gates mypy"
            ),
        )

    def test_make_check_full_run_unsets_python_path_env(self, tmp_path: Path) -> None:
        """Verify full checks clear inherited Python path variables."""
        log_path = tmp_path / "tool.log"
        bin_dir = tmp_path / "bin"
        bin_dir.mkdir(parents=True, exist_ok=True)
        _write_executable(
            bin_dir / "python",
            '#!/usr/bin/env bash\nprintf \'python %s\\n\' "$*" >> "'
            + str(log_path)
            + '"\nexit 0\n',
        )
        _write_project(tmp_path)
        _write_venv_python_stub(tmp_path, log_path, include_env=True)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "demo.py").write_text("x = 1\n", encoding="utf-8")

        result = _run_make(
            tmp_path,
            "check",
            "CHECK_GATES=mypy",
            env={
                "PYTHONPATH": str(tmp_path / "poison-pythonpath"),
                "MYPYPATH": str(tmp_path / "poison-mypypath"),
            },
        )

        tm.that(result.exit_code, eq=0)
        expected_src = tmp_path / "src"
        tm.that(
            log_path.read_text(encoding="utf-8"),
            has=(
                f"PYTHONPATH={expected_src} MYPYPATH=unset "
                f"python -m flext_infra check run --workspace {tmp_path} --gates mypy"
            ),
        )

    def test_make_check_full_run_forwards_fix_and_tool_args(
        self, tmp_path: Path
    ) -> None:
        """Verify full checks forward fix and analyzer arguments."""
        log_path = tmp_path / "tool.log"
        _write_project(tmp_path)
        _write_venv_python_stub(tmp_path, log_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "demo.py").write_text("x = 1\n", encoding="utf-8")

        result = _run_make(
            tmp_path,
            "check",
            "CHECK_GATES=lint,pyright",
            "FIX=1",
            "RUFF_ARGS=--select E501",
            "PYRIGHT_ARGS=--level basic",
        )

        tm.that(result.exit_code, eq=0)
        tm.that(
            log_path.read_text(encoding="utf-8"),
            has=f"flext_infra check run --workspace {tmp_path} --gates lint,pyright",
        )
        tm.that(log_path.read_text(encoding="utf-8"), has="--projects .")

    def test_make_check_fast_path_check_only_suppresses_fix_writes(
        self, tmp_path: Path
    ) -> None:
        """Verify check-only fast paths never forward write-enabled fixes."""
        log_path = tmp_path / "tool.log"
        bin_dir = tmp_path / "bin"
        _write_stubs(bin_dir, log_path)
        _write_project(tmp_path)
        _write_venv_python_stub(tmp_path, log_path)
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "demo.py").write_text("x = 1\n", encoding="utf-8")

        result = _run_make(
            tmp_path,
            "check",
            "FILE=src/demo.py",
            "CHECK_GATES=lint",
            "FIX=1",
            "CHECK_ONLY=1",
            f"UV={bin_dir / 'uv'}",
            env={"PATH": f"{bin_dir}:{os.environ['PATH']}"},
        )

        tm.that(result.exit_code, eq=0, msg=result.stdout + result.stderr)
        # R12: the gate run is delegated; CHECK_ONLY must still suppress --fix.
        logged = log_path.read_text(encoding="utf-8")
        tm.that(logged, has="flext_infra check run")
        tm.that(logged, has="--gates lint")
        tm.that("--fix" not in logged, eq=True)

    # mro-x0rau.3: commit 2a4a8ea7a deleted the FILE/FILES/CHANGED_ONLY
    # fast-path gate restriction along with base_verbs.mk.j2. A file-scoped run
    # now goes through the same typed gate pipeline as a full run, so every
    # allowed gate is file-scopable -- proven by `make check FILE=<py>
    # CHECK_GATES=security` exiting 0 with the gate actually executed. The test
    # that asserted the removed restriction is deleted with it.

    # mro-x0rau.3 deleted the `boot` verb: it was unreachable in every real
    # checkout (no generated Makefile includes base.mk) and its behaviour is
    # owned by `setup WHAT=environment`. The test is removed with the verb.

    def test_make_custom_mk_redefining_reserved_verb_fails_loud(
        self, tmp_path: Path
    ) -> None:
        """A custom.mk redefining a reserved verb fails every make invocation."""
        _write_project(tmp_path)
        (tmp_path / "custom.mk").write_text(
            "check:\n\t@echo EVIL_CHECK\n", encoding="utf-8"
        )

        result = _run_make(tmp_path, "help")

        output = result.stdout + result.stderr
        tm.that(result.exit_code, ne=0)
        tm.that(output, has=["custom.mk", "reserved flext-infra", "check"])
        tm.that(output, lacks="EVIL_CHECK")

    def test_make_custom_mk_redefining_reserved_builtin_what_fails_loud(
        self, tmp_path: Path
    ) -> None:
        """A custom.mk shadowing a builtin _custom_<verb>_<what> pair fails."""
        _write_project(tmp_path)
        # `docs` is no longer a public verb, so `_custom_docs_all` is NOT
        # reserved and the guard rightly permits it. Assert the guard with a
        # pair the SSOT actually reserves today.
        (tmp_path / "custom.mk").write_text(
            "_custom_check_all:\n\t@echo EVIL_CHECK\n", encoding="utf-8"
        )

        result = _run_make(tmp_path, "help")

        output = result.stdout + result.stderr
        tm.that(result.exit_code, ne=0)
        tm.that(output, has=["custom.mk", "reserved flext-infra", "_custom_check_all"])
        tm.that(output, lacks="EVIL_CHECK")

    def test_make_custom_mk_arbitrary_custom_verb_and_hooks_pass(
        self, tmp_path: Path
    ) -> None:
        """Any non-reserved custom verb/WHAT handler and hook is permitted."""
        _write_project(tmp_path)
        (tmp_path / "custom.mk").write_text(
            ".PHONY: _custom_ship_fast _custom_docs_mydoc pre-ship\n"
            "_custom_ship_fast:\n\t@echo CUSTOM_SHIP_FAST\n"
            "_custom_docs_mydoc:\n\t@echo CUSTOM_DOCS_MYDOC\n"
            "pre-ship:\n\t@true\n",
            encoding="utf-8",
        )

        custom = _run_make(tmp_path, "_custom_ship_fast")
        tm.that(custom.exit_code, eq=0)
        tm.that(custom.stdout, has="CUSTOM_SHIP_FAST")
        docs = _run_make(tmp_path, "_custom_docs_mydoc")
        tm.that(docs.exit_code, eq=0)
        tm.that(docs.stdout, has="CUSTOM_DOCS_MYDOC")
        help_result = _run_make(tmp_path, "help")
        tm.that(help_result.exit_code, eq=0)
        tm.that(help_result.stdout, has="_custom_ship_fast")

    def test_make_guarantees_bytecode_caching_without_direnv(
        self, tmp_path: Path
    ) -> None:
        """Make neutralizes an inherited PYTHONDONTWRITEBYTECODE and sets a cache prefix.

        `make` does not source `.envrc` (that needs direnv), so a bytecode policy
        expressed only there is inert for every Make-driven run. An ambient
        PYTHONDONTWRITEBYTECODE=1 then disables the import cache and every verb
        pays full source recompilation. The generated Makefile must therefore own
        the guarantee itself, so the policy holds for any caller environment.
        """
        _write_project(tmp_path)
        probe = tmp_path / "custom.mk"
        probe.write_text(
            ".PHONY: _custom_probe_bytecode\n"
            "_custom_probe_bytecode:\n"
            '\t@printf "DONTWRITE=[%s]\\n" "$${PYTHONDONTWRITEBYTECODE:-}"\n'
            '\t@printf "PYCACHEPREFIX=[%s]\\n" "$${PYTHONPYCACHEPREFIX:-}"\n',
            encoding="utf-8",
        )

        result = _run_make(
            tmp_path, "_custom_probe_bytecode", env={"PYTHONDONTWRITEBYTECODE": "1"}
        )

        tm.that(result.exit_code, eq=0)
        # Bytecode writing must be ENABLED despite the hostile inherited value.
        tm.that(result.stdout, has="DONTWRITE=[]")
        # And the cache must be redirected out of the working tree, not disabled.
        tm.that(result.stdout, lacks="PYCACHEPREFIX=[]")

    def test_fix_apply_reaches_every_fixable_gate(self) -> None:
        """`make fix APPLY=Y` routes through the gate pipeline, not ruff alone.

        mro-38p39: four gates declare can_fix=True (ruff-format, smells,
        canonical-alias, markdown), and `flext_infra check run` already exposes
        `--fix` to drive them. The generated member recipe ran only
        `ruff check --fix`, so every other fixable gate was unreachable: a
        markdown finding that the linter itself marks auto-fixable blocked
        `make check` while `make fix APPLY=Y` exited 0 without repairing it.
        The canonical sequence could then never reach green, and the only
        remaining move was hand-editing a file the gate owns.

        `check` already routes through the pipeline; `fix` is its mutating dual
        and must reach the same gates.
        """
        rendered = _render_project_makefile()
        body = rendered.split("_builtin_fix_all:", 1)[1].split("\n\n", 1)[0]

        tm.that(body, has=["check run", "--fix"])
