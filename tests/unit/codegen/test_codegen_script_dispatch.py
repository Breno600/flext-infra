"""Public functional contract for new and existing project conformance.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from flext_infra.codegen import FlextInfraCodegenConform
from tests import c, m, t, u

pytestmark = [pytest.mark.slow]


class TestsFlextInfraScriptDispatchMakefile:
    """Prove per-repo extra verbs and script-dispatch WHAT normalization."""

    @staticmethod
    def _render_root_makefile(
        tmp_path: Path,
        *,
        extra_verbs: t.VariadicTuple[m.Infra.MakeVerbSpec],
        script_dispatch: m.Infra.ScriptDispatchSpec | None,
    ) -> str:
        # The engine is consumer-agnostic, so this fixture models a
        # neutral downstream root and takes its provider from the engine's own
        # configured provider catalog instead of naming a real consumer.
        provider = u.Tests.provider()
        root_repository = m.Infra.RepositoryRef(
            name="demo-root",
            distribution="demo-root",
            url=f"{provider.base_url}/demo-root.git",
            path=Path(),
            # Script dispatch is a generic capability: exercise it on standalone.
            role=c.Infra.MakeProfile.STANDALONE,
            provider=provider.name,
            kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
            codegen=c.Infra.CodegenKind.CONFORM,
            package=False,
            editable=False,
            read_only=False,
            extra_verbs=extra_verbs,
            script_dispatch=script_dispatch,
        )
        workspace = u.Tests.workspace_spec(
            root_repository, project=u.Tests.project_spec("demo-root")
        )
        root = tmp_path / "demo-root"
        request = u.Tests.conform_request(
            root,
            what=c.Infra.CodegenConformSurface.MAKEFILE,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned = FlextInfraCodegenConform(
            repository_root=root, request=request, initial_workspace=workspace
        ).plan(request)
        plan = tm.ok(planned)
        makefile = next(
            file for file in plan.files if file.path.name == c.Infra.MAKEFILE_FILENAME
        )
        rendered: str = u.Tests.codegen_file_text(makefile)
        return rendered

    def test_script_dispatch_repo_routes_extra_verbs_and_normalizes_what(
        self, tmp_path: Path
    ) -> None:
        """Extra verbs join PUBLIC_VERBS and dispatch through the declared dispatcher."""
        rendered = self._render_root_makefile(
            tmp_path,
            extra_verbs=(
                m.Infra.MakeVerbSpec(
                    name="incidente",
                    description="Dispatch incidente through the declared script dispatcher.",
                ),
                m.Infra.MakeVerbSpec(
                    name="charts",
                    description="Dispatch charts through the declared script dispatcher.",
                ),
            ),
            script_dispatch=m.Infra.ScriptDispatchSpec(
                dispatcher="scripts/dispatch.py",
                roots=("scripts", "apps/demo-app/scripts"),
            ),
        )
        # Extra verbs are public targets the dispatcher can reach.
        tm.that("incidente" in rendered, eq=True)
        tm.that("charts" in rendered, eq=True)
        # Each extra verb gets a _builtin-<verb> target that dispatches through
        # the repo's declared dispatcher.
        tm.that("_builtin-incidente:" in rendered, eq=True)
        tm.that("_builtin-charts:" in rendered, eq=True)
        # It forwards to the declared dispatcher through uv, not a raw builtin.
        tm.that("scripts/dispatch.py" in rendered, eq=True)
        # Script dispatch roots are recorded for operator visibility.
        tm.that("apps/demo-app/scripts" in rendered, eq=True)

    def test_extra_verb_dispatch_target_is_emitted_exactly_once(
        self, tmp_path: Path
    ) -> None:
        """Every extra verb owns one public recipe; a second one is a Make warning.

        Two integrations of the same dispatch block once rendered every extra
        verb twice, and GNU Make reported ``overriding recipe for target`` on
        each parse of the consumer's Makefile.
        """
        rendered = self._render_root_makefile(
            tmp_path,
            extra_verbs=(
                m.Infra.MakeVerbSpec(name="deploy", description="Publish the runtime."),
            ),
            script_dispatch=None,
        )
        root = tmp_path / "public-help"
        root.mkdir()
        (root / c.Infra.MAKEFILE_FILENAME).write_text(rendered, encoding="utf-8")
        output = tm.ok(
            u.Tests.run_isolated_make(["--no-print-directory", "help"], cwd=root)
        )
        tm.that(u.Cli.process_succeeded(output.outcome), eq=True)
        tm.that(output.stderr, lacks="overriding recipe")
        verbs = [line.split()[0] for line in output.stdout.splitlines() if line.strip()]
        tm.that(verbs.count("deploy"), eq=1)

    def test_dispatch_routes_custom_what_before_allowlist(self, tmp_path: Path) -> None:
        """Custom ``_custom_<verb>`` handlers bypass the builtin allowlist.

        ai-hub and other projects extend ``run`` / ``check`` via custom.mk. The
        continuous Makefile RUN_PUBLIC macro discovers those handlers and
        dispatches them instead of falling through to _builtin-<verb>.
        """
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        # RUN_PUBLIC checks CUSTOM_DECLARED_TARGETS first and calls _custom-$(1)
        # when it exists, falling back to _builtin-$(1).
        tm.that("define RUN_PUBLIC" in rendered, eq=True)
        tm.that("_custom-$(1)" in rendered, eq=True)
        tm.that("_builtin-$(1)" in rendered, eq=True)

    def test_repo_without_script_dispatch_omits_script_routing(
        self, tmp_path: Path
    ) -> None:
        """A repo with no script dispatch omits every script-routing projection."""
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        # No script routing leaks into non-opted-in repositories.
        tm.that("tr '-' '_'" in rendered, eq=False)
        tm.that("scripts/dispatch.py" in rendered, eq=False)

    def test_gen_replaces_codegen_as_the_single_conform_verb(
        self, tmp_path: Path
    ) -> None:
        """The public help advertises gen and Make rejects the retired verb."""
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        root = tmp_path / "public-verbs"
        root.mkdir()
        (root / c.Infra.MAKEFILE_FILENAME).write_text(rendered, encoding="utf-8")
        output = tm.ok(
            u.Tests.run_isolated_make(["--no-print-directory", "help"], cwd=root)
        )
        tm.that(u.Cli.process_succeeded(output.outcome), eq=True)
        verbs = {line.split()[0] for line in output.stdout.splitlines() if line.strip()}
        tm.that("gen" in verbs, eq=True)
        tm.that("initialize" in verbs, eq=True)
        tm.that("codegen" in verbs, eq=False)
        retired = tm.ok(
            u.Tests.run_isolated_make(["--no-print-directory", "codegen"], cwd=root)
        )
        tm.that(u.Cli.process_succeeded(retired.outcome), eq=False)
        tm.that(retired.stdout + retired.stderr, has="codegen")

    def test_make_initialize_requires_its_provisioned_interpreter(
        self, tmp_path: Path
    ) -> None:
        """The public initializer fails before effects when its runtime is absent."""
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        root = tmp_path / "declared-target"
        package = root / "src" / "demo_root"
        package.mkdir(parents=True)
        makefile = root / c.Infra.MAKEFILE_FILENAME
        makefile.write_text(rendered, encoding="utf-8")
        invoked = u.Tests.run_isolated_make(
            ["--no-print-directory", "-f", str(makefile), "initialize"], cwd=root
        )

        tm.ok(invoked)
        tm.that(u.Cli.process_succeeded(invoked.value.outcome), eq=False)
        tm.that(invoked.value.stderr, has="missing environment interpreter")
        tm.that((package / c.Infra.INIT_PY).exists(), eq=False)

    def test_work_lifecycle_is_not_projected(self, tmp_path: Path) -> None:
        """Gas City owns lanes; generated repositories expose no second lifecycle."""
        make_config = config.Infra.codegen.make
        verb_names = {verb.name for verb in make_config.verbs}
        tm.that("work" in verb_names, eq=False)
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        public_line = next(
            line for line in rendered.splitlines() if line.startswith("PUBLIC_VERBS :=")
        )
        tm.that(" work" in public_line, eq=False)
        tm.that(rendered, lacks="_builtin_work_")
        tm.that(rendered, lacks="workspace work")

    # A test asserting a downstream consumer's verbs from this
    # engine's catalog was removed. The engine is consumer-agnostic: a consumer
    # declares extra_verbs/script_dispatch in its own typed repository input. The
    # generic capability stays covered by the fixture-driven cases below.
    def test_script_dispatch_adds_scripts_to_lint_and_type_paths(
        self, tmp_path: Path
    ) -> None:
        """Opted-in repos scan scripts alongside src and tests."""
        rendered = self._render_root_makefile(
            tmp_path,
            extra_verbs=(
                m.Infra.MakeVerbSpec(
                    name="charts",
                    description="Dispatch charts through the declared script dispatcher.",
                ),
                m.Infra.MakeVerbSpec(
                    name="chart-release",
                    description="Dispatch chart-release through the declared script dispatcher.",
                ),
                m.Infra.MakeVerbSpec(
                    name="bead",
                    description="Dispatch bead through the declared script dispatcher.",
                ),
            ),
            script_dispatch=m.Infra.ScriptDispatchSpec(
                dispatcher="scripts/dispatch.py", roots=("scripts",)
            ),
        )
        tm.that(
            "RUFF_PATHS := $(strip $(foreach d,src tests examples scripts,"
            "$(if $(wildcard $(PROJECT_ROOT)/$(d)/.),$(PROJECT_ROOT)/$(d),)))"
            in rendered,
            eq=True,
        )
        tm.that(
            "MYPY_PATHS := $(strip $(foreach d,src tests examples scripts,"
            "$(if $(wildcard $(PROJECT_ROOT)/$(d)/.),$(PROJECT_ROOT)/$(d),)))"
            in rendered,
            eq=True,
        )

    def test_repo_without_script_dispatch_retains_canonical_lint_and_type_paths(
        self, tmp_path: Path
    ) -> None:
        """A repo without script dispatch keeps src/tests/scripts paths and excludes scripts."""
        rendered = self._render_root_makefile(
            tmp_path, extra_verbs=(), script_dispatch=None
        )
        tm.that(
            "RUFF_PATHS := $(strip $(foreach d,src tests examples,"
            "$(if $(wildcard $(PROJECT_ROOT)/$(d)/.),$(PROJECT_ROOT)/$(d),)))"
            in rendered,
            eq=True,
        )
        tm.that(
            "MYPY_PATHS := $(strip $(foreach d,src tests examples,"
            "$(if $(wildcard $(PROJECT_ROOT)/$(d)/.),$(PROJECT_ROOT)/$(d),)))"
            in rendered,
            eq=True,
        )
        tm.that("$(PROJECT_ROOT)/scripts" in rendered, eq=False)
