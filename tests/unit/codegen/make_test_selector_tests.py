"""Behavior contract for focused pytest selection through generated Make."""

from __future__ import annotations

from pathlib import Path

import flext_infra
from flext_infra import c, config, u
from flext_tests import tm
from tests import u as test_u


def _makefile_template() -> Path:
    """Locate the generated-Makefile template for the checkout in use."""
    marker = Path("src/flext_infra/templates/project/base/Makefile.j2")
    for candidate in Path(__file__).resolve().parents:
        if (candidate / marker).is_file():
            return candidate / marker
    msg = f"no ancestor of {Path(__file__).resolve()} provides {marker}"
    raise FileNotFoundError(msg)


class TestsMakeTestSelector:
    """The generated `test` recipe honours the documented argument knob."""

    def test_test_verb_is_canonical(self) -> None:
        """`test` is part of the canonical verb surface every project exposes."""
        matches = tuple(
            verb for verb in config.Infra.codegen.make.verbs if verb.name == "test"
        )
        tm.that(matches, len=1)

    def test_fmt_is_the_only_public_formatting_verb(self, tmp_path: Path) -> None:
        """The generated Makefile runs canonical fmt and rejects its retired name."""
        public_verbs = {verb.name for verb in config.Infra.codegen.make.verbs}
        tm.that("fmt" in public_verbs, where=bool)
        tm.that("format" not in public_verbs, where=bool)

        makefile = tm.ok(u.Cli.files_read_text(Path("Makefile")))
        (tmp_path / "Makefile").write_text(makefile, encoding="utf-8")
        # Public verbs dispatch straight into their builtin, so the managed
        # interpreter only has to exist for the environment guard.
        test_u.Tests.write_executable(
            tmp_path / ".venv" / "bin" / "python", "#!/bin/sh\nexit 0\n"
        )
        invocation_log = tmp_path / "uv-args.log"
        uv = tmp_path / "bin" / "uv"
        test_u.Tests.write_executable(
            uv, f'#!/bin/sh\nprintf "%s\\n" "$*" >> "{invocation_log}"\n'
        )

        canonical = tm.ok(
            test_u.Tests.run_isolated_make(
                ["--no-print-directory", "fmt", "WHAT=check", f"UV={uv}"], cwd=tmp_path
            )
        )
        tm.that(canonical.exit_code, eq=0, msg=canonical.stdout + canonical.stderr)
        invocations = invocation_log.read_text(encoding="utf-8")
        tm.that(invocations, has="ruff format --check")
        calls_before_retired = invocations.splitlines()

        retired = tm.ok(
            test_u.Tests.run_isolated_make(
                ["--no-print-directory", "format", f"UV={uv}"], cwd=tmp_path
            )
        )
        tm.that(retired.exit_code, ne=0)
        tm.that(
            invocation_log.read_text(encoding="utf-8").splitlines(),
            eq=calls_before_retired,
        )

    def test_recursive_dispatch_preserves_explicit_makefile(
        self, tmp_path: Path
    ) -> None:
        """An external -f invocation keeps the selected Make owner and runtime."""
        caller_root = tmp_path / "consumer"
        caller_root.mkdir()
        target_root = tmp_path / "target"
        target_root.mkdir()
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        selected_makefile = engine_root / "canonical.mk"
        selected_makefile.write_text(
            tm.ok(u.Cli.files_read_text(Path("Makefile"))), encoding="utf-8"
        )
        (caller_root / "Makefile").write_text("all:\n\t@exit 99\n", encoding="utf-8")
        invocation_log = engine_root / "python-args.log"
        test_u.Tests.write_executable(
            engine_root / ".venv" / "bin" / "python",
            (f'#!/bin/sh\nprintf "%s\\n" "$PYTHONPATH" "$*" > "{invocation_log}"\n'),
        )
        uv = caller_root / "bin" / "uv"
        test_u.Tests.write_executable(uv, "#!/bin/sh\nexit 0\n")

        executed = tm.ok(
            test_u.Tests.run_isolated_make(
                [
                    "--no-print-directory",
                    "-f",
                    str(selected_makefile),
                    "work",
                    "WHAT=status",
                    f"WORKSPACE={target_root}",
                    f"UV={uv}",
                ],
                cwd=caller_root,
            )
        )

        tm.that(executed.exit_code, eq=0, msg=executed.stdout + executed.stderr)
        tm.that(
            invocation_log.read_text(encoding="utf-8"),
            has=[str(engine_root / "src"), "workspace work", "--operation status"],
        )

    def test_external_makefile_owns_the_runtime_engine(self, tmp_path: Path) -> None:
        """A selected Make owner, not its caller, owns runtime and lock routing."""
        caller_root = tmp_path / "consumer"
        caller_root.mkdir()
        engine_root = tmp_path / "engine"
        engine_root.mkdir()
        selected_makefile = engine_root / "canonical.mk"
        selected_makefile.write_text(
            tm.ok(u.Cli.files_read_text(Path("Makefile"))), encoding="utf-8"
        )
        invocation_log = engine_root / "python-args.log"
        test_u.Tests.write_executable(
            engine_root / ".venv" / "bin" / "python",
            f'#!/bin/sh\nprintf "%s\\n" "$*" > "{invocation_log}"\n',
        )
        test_u.Tests.write_executable(
            caller_root / ".venv" / "bin" / "python", "#!/bin/sh\nexit 91\n"
        )
        uv = caller_root / "bin" / "uv"
        test_u.Tests.write_executable(uv, "#!/bin/sh\nexit 0\n")

        executed = tm.ok(
            test_u.Tests.run_isolated_make(
                [
                    "--no-print-directory",
                    "-f",
                    str(selected_makefile),
                    "gen",
                    "WHAT=all",
                    "APPLY=Y",
                    f"UV={uv}",
                ],
                cwd=caller_root,
            )
        )

        tm.that(executed.exit_code, eq=0, msg=executed.stdout + executed.stderr)
        tm.that(
            invocation_log.read_text(encoding="utf-8"),
            has=[
                "-m flext_infra codegen conform",
                f"--root {engine_root}",
                "--scope self",
                "--mode apply",
            ],
        )

    def test_explicit_target_replaces_the_default_suite(self, tmp_path: Path) -> None:
        """A focused target is the pytest target, not an appendix to tests/."""
        makefile = tm.ok(u.Cli.files_read_text(Path("Makefile")))
        (tmp_path / "Makefile").write_text(makefile, encoding="utf-8")
        test_u.Tests.write_executable(
            tmp_path / ".venv" / "bin" / "python",
            (
                "#!/bin/sh\n"
                "mode=''\n"
                'for argument in "$@"; do\n'
                '  if [ "$argument" = "validate" ]; then mode="validate"; fi\n'
                "done\n"
                'if [ "$mode" = "validate" ]; then\n'
                "  printf '%s\\n' failed_count=0 error_count=0 "
                "warning_count=0 skipped_count=0\n"
                "  exit 0\n"
                "fi\n"
                "exit 2\n"
            ),
        )
        invocation_log = tmp_path / "uv-args.log"
        uv = tmp_path / "bin" / "uv"
        test_u.Tests.write_executable(
            uv,
            (
                "#!/bin/sh\n"
                f'printf "file=%s\\nargs=%s\\n" "$FLEXT_PYTEST_FILE_RAW" "$*" '
                f'> "{invocation_log}"\n'
            ),
        )
        selected = "tests/unit/selected_test.py"
        selected_path = tmp_path / selected
        selected_path.parent.mkdir(parents=True)
        selected_path.write_text(
            "from flext_tests import tm\n\n"
            "def test_selected() -> None:\n"
            "    tm.that(True, eq=True)\n",
            encoding="utf-8",
        )

        executed = tm.ok(
            test_u.Tests.run_isolated_make(
                ["--no-print-directory", "test", f"FILE={selected}", f"UV={uv}"],
                cwd=tmp_path,
            )
        )

        tm.that(
            executed.exit_code,
            eq=0,
            msg=f"stdout:\n{executed.stdout}\nstderr:\n{executed.stderr}",
        )
        arguments = invocation_log.read_text(encoding="utf-8")
        tm.that(arguments, has=f"file={selected}")
        # The contract is that the explicit FILE reaches the typed runner
        # through uv. Which uv flags the generated Makefile uses is template
        # policy (it moved from --offline to --project/--no-sync), so freezing
        # them here breaks the test on a legitimate template change.
        tm.that(arguments, has="python -m flext_infra._pytest_entry")

    def test_generated_test_recipe_uses_one_typed_runner_boundary(self) -> None:
        """Forward supported selectors without reconstructing pytest in shell.

        Without this, a targeted run is impossible through `make`, and the only
        way to filter is to call pytest directly -- exactly the loose command the
        canonical-command law forbids.
        """
        template_path = _makefile_template()
        template = template_path.read_text(encoding="utf-8")
        reporter = (template_path.parent / "base_test_report_recipe.j2").read_text(
            encoding="utf-8"
        )

        tm.that(template, has="test_report_recipe(")
        tm.that(template, has="python -m flext_infra._pytest_entry")
        tm.that(
            template,
            has=[
                "FLEXT_PYTEST_FILE_RAW",
                "FLEXT_PYTEST_MATCH_RAW",
                "FLEXT_PYTEST_WHAT_RAW",
                "FLEXT_PYTEST_FAIL_FAST_RAW",
            ],
            lacks=["PYTEST_TARGETS", "_all_pytest_args", "pytest-diag"],
        )
        tm.that(reporter, has="{{ command_prefix }}{{ runner }}")
        tm.that(reporter, lacks=["grep ", "awk ", "source ", '. "$'])

    def test_generated_owners_use_distinct_canonical_verbs(self) -> None:
        """Gen (conform) stays on the Makefile; custom.mk is hooks-only.

        The generated Makefile owns ``gen``. custom.mk must not declare a
        private basemk-generate WHAT — base.mk generation is not a custom
        handler on this surface.
        """
        template = _makefile_template().read_text(encoding="utf-8")
        custom = (
            Path(flext_infra.__file__).resolve().parents[2]
            / c.Infra.CUSTOM_MAKE_FILENAME
        ).read_text(encoding="utf-8")

        tm.that(template, has="_builtin_gen_apply")
        tm.that(template, lacks="_builtin_build_gen")
        tm.that(custom, lacks="_custom_basemk_generate:")
        tm.that(custom, lacks="basemk generate")
