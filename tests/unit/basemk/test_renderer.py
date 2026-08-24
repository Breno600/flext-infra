"""Public rendering tests for the base.mk template renderer."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import m, main as infra_main
from flext_infra.basemk.generator import FlextInfraBaseMkGenerator
from flext_infra.basemk.renderer import FlextInfraBaseMkTemplateRenderer
from flext_tests import tm

if TYPE_CHECKING:
    from _pytest.capture import CaptureFixture

_MIN_RENDERED_LINES = 200
_STANDARD_VERBS_ASSIGNMENT = "STANDARD_VERBS :="


def _declared_standard_verbs(rendered: str) -> tuple[str, ...]:
    """Return the verbs base.mk declares through STANDARD_VERBS."""
    for line in rendered.splitlines():
        if line.startswith(_STANDARD_VERBS_ASSIGNMENT):
            declared = line.removeprefix(_STANDARD_VERBS_ASSIGNMENT)
            return tuple(declared.split())
    return ()


def _target_has_recipe(rendered: str, target: str) -> bool:
    """Report whether ``target`` owns at least one recipe line in the render.

    A Make target carries a recipe when a tab-indented line follows its rule.
    Prerequisite-only rules (``$(STANDARD_VERBS): _preflight``) never do, which
    is exactly the silent no-op this predicate detects.
    """
    lines = rendered.splitlines()
    prefix = f"{target}:"
    for index, line in enumerate(lines):
        if not line.startswith(prefix):
            continue
        for candidate in lines[index + 1 :]:
            if candidate.startswith("\t"):
                return True
            if candidate.strip() and not candidate.startswith("#"):
                break
    return False


class TestsFlextInfraBasemkRenderer:
    """Behavior contract for test_renderer."""

    def test_render_all_generates_large_makefile(self) -> None:
        """Render the complete base Makefile surface."""
        result = FlextInfraBaseMkTemplateRenderer().render_all()

        tm.ok(result)
        tm.that(len(result.value.splitlines()), gt=_MIN_RENDERED_LINES)

    def test_bootstrap_setup_is_self_contained_and_branch_aware(self) -> None:
        rendered = tm.ok(FlextInfraBaseMkTemplateRenderer.render_bootstrap_include())

        for required in (
            "SETUP_ROOT := $(shell git rev-parse --show-toplevel)",
            "SETUP_BRANCH := $(shell git rev-parse --abbrev-ref HEAD)",
            'UV_PROJECT_ENVIRONMENT="$(SETUP_VENV)"',
            "SETUP_BIN := $(SETUP_ROOT)/.bin",
            "MISE_DATA_DIR := $(SETUP_ROOT)/.tools",
            "SETUP_MISE ?= $(SETUP_BIN)/mise",
            "SETUP_UV := $(MISE_DATA_DIR)/shims/uv",
            "github.com/jdx/mise/releases/download",
            "$(SETUP_MISE) install --yes",
            "$(SETUP_UV_ENV) uv sync --project",
            "git submodule update --init --recursive",
            'test -z "$$(git status --porcelain)"',
            'test "$$(git rev-parse HEAD)" = "$$sha1"',
            "refs/heads/$(SETUP_BRANCH)",
            'git checkout --quiet -b "$(SETUP_BRANCH)"',
            "$(SETUP_PYTHON) -m flext_infra",
        ):
            tm.that(rendered, has=required)
        for forbidden in (
            "SETUP_UV ?= uv",
            "python -m venv",
            "BOOTSTRAP_PIP",
            "pip install",
            "poetry",
            "mise exec",
            "$(PYTHON_CMD) -c 'import flext_infra'",
        ):
            tm.that(rendered, lacks=forbidden)

    def test_render_all_has_no_scripts_path_references(self) -> None:
        """Exclude legacy script paths from the rendered contract."""
        result = FlextInfraBaseMkTemplateRenderer().render_all()

        tm.ok(result)
        tm.that(result.value, lacks="scripts/")

    def test_render_all_preflight_is_read_only_and_fail_closed(self) -> None:
        """Reject stale state without deleting environments or syncing source."""
        rendered = tm.ok(FlextInfraBaseMkTemplateRenderer().render_all())

        tm.that(rendered, has="define VALIDATE_CANONICAL_BASE_MK")
        tm.that(rendered, has="basemk-validate")
        tm.that(rendered, has="Project-local .venv violates")
        tm.that(rendered, lacks="AUTO_SYNC_BASE_AND_SCRIPTS")
        tm.that(rendered, lacks="rm -rf .venv")

    def test_render_all_builds_with_canonical_uv_command(self) -> None:
        """Build distributions without unrelated codegen or Poetry commands."""
        rendered = tm.ok(FlextInfraBaseMkTemplateRenderer().render_all())

        tm.that(rendered, has="UV ?= uv")
        tm.that(rendered, lacks="$(PROJECT_INFRA_CODEGEN) grpc")
        tm.that(rendered, lacks="$(POETRY) build")

    def test_render_all_with_config_override(self) -> None:
        """Render validated project-specific settings."""
        settings = m.Infra.BaseMkConfig(
            project_name="sample-project",
            python_version="3.13",
            source_dir="src",
            tests_dir="tests",
            lint_gates=["lint", "mypy"],
        )

        result = FlextInfraBaseMkGenerator().generate_basemk(settings)

        tm.ok(result)
        tm.that(result.value, has="PROJECT_NAME ?= sample-project")

    def test_render_single_missing_template_fails(self) -> None:
        """Reject a template name outside the canonical inventory."""
        result = FlextInfraBaseMkTemplateRenderer().render_single(
            "missing-template.mk.j2"
        )

        tm.fail(result)
        tm.that((result.error or ""), has="template render failed")

    def test_basemk_cli_generate_to_stdout(self, capsys: CaptureFixture[str]) -> None:
        """Generate the public base Makefile through the CLI."""
        exit_code = infra_main(["basemk", "generate", "--project-name", "cli-project"])
        captured = capsys.readouterr()

        tm.that(exit_code, eq=0)
        tm.that(captured.out, has="PROJECT_NAME ?= cli-project")

    def test_renderer_execute_returns_string(self) -> None:
        """Return rendered text from the service execution contract."""
        result = FlextInfraBaseMkTemplateRenderer().execute()

        tm.ok(result)
        tm.that(result.value, is_=str)
        tm.that(result.value, empty=False)

    def test_render_all_declares_only_verbs_it_ships_a_recipe_for(self) -> None:
        """Every verb base.mk declares must own a recipe in base.mk.

        R12 moved the public verb recipes into the project Makefile. A verb left
        in STANDARD_VERBS without a recipe is not a cosmetic leftover: Make
        treats it as a satisfied target and the verb becomes a silent no-op,
        so a gate like `check` exits 0 having validated nothing.

        The expected set is therefore derived from the rendered text itself -
        never from a hardcoded verb list - by intersecting what is declared with
        what actually carries a recipe.
        """
        text = tm.ok(FlextInfraBaseMkTemplateRenderer().render_all())

        declared = _declared_standard_verbs(text)
        tm.that(declared, empty=False)

        recipeless = tuple(
            verb for verb in declared if not _target_has_recipe(text, verb)
        )
        tm.that(recipeless, eq=())
        tm.that(text, lacks="setup build check security format docs")
        tm.that(text, lacks="docs-base")
        tm.that(text, lacks="docs-sync-scripts")

    def test_render_all_declares_and_documents_runtime_options(self) -> None:
        """Document the runtime options accepted by generated targets."""
        result = FlextInfraBaseMkTemplateRenderer().render_all()

        tm.ok(result)
        text = result.value
        for part in ("FIX ?=", "PYTEST_BOUNDED", "PYTEST_REPORT_ARGS"):
            tm.that(text, has=part)
        tm.that(text, lacks="check-fast")
