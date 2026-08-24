"""Every generated ``uv`` invocation resolves the project's own runtime.

``uv`` honours ``VIRTUAL_ENV``, ``UV_PROJECT`` and ``UV_PROJECT_ENVIRONMENT``
from the ambient environment. A developer or CI job with another project's
virtualenv active therefore hijacks the runtime: the generated Makefile asks
for ``--project <this repo>`` but ``uv`` resolves interpreter and packages from
the *caller's* environment instead.

The template already knows this. ``FLEXT_INFRA_BOOTSTRAP`` and
``PROJECT_FLEXT_INFRA`` both strip all three variables before calling ``uv``.
``UV_RUN`` -- the definition that actually runs pytest, ruff, pyright and mypy
-- stripped only ``PYTHONPATH`` and ``MYPYPATH``, so the gates were the one
surface left exposed.

That gap produced false evidence, not just a slow path: with another project's
venv exported, ``make test`` imported ``flext_infra`` from that venv's
site-packages and validated this repository's tree against a stale installed
copy. Gate results then describe code that is not under test.

This pins the invariant at the template: no ``uv`` invocation may be built
without environment sanitation -- either the definition strips the hijacking
variables itself, or the template overrides and exports them so Make replaces
any inherited value before a recipe runs.
"""

from __future__ import annotations

import re
from pathlib import Path

_TEMPLATE = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "flext_infra"
    / "templates"
    / "project"
    / "base"
    / "Makefile.j2"
)

# uv reads these to locate the interpreter and the package set. Any one of them
# left in the environment lets the caller redirect a `--project`-pinned run.
_HIJACKING_VARIABLES = ("VIRTUAL_ENV", "UV_PROJECT", "UV_PROJECT_ENVIRONMENT")


def _template_text() -> str:
    """Return the generated-Makefile template source."""
    return _TEMPLATE.read_text(encoding="utf-8")


def _uv_invocation_definitions() -> dict[str, str]:
    """Return every ``NAME := ...`` definition whose value invokes ``uv``.

    Matches the recursive (``=``) and simple (``:=``) assignment forms the
    template uses, keyed by variable name so a failure names the offender.
    """
    return {
        name: value
        for name, value in re.findall(
            r"^([A-Z_]+)\s*:?=\s*(.*(?:\$\(UV\)|\$\(UV_RUN\)).*)$",
            _template_text(),
            re.MULTILINE,
        )
        if "$(UV)" in value
    }


def _unstripped_variables(definition: str) -> list[str]:
    """Return the hijacking variables a definition fails to strip."""
    return [
        variable
        for variable in _HIJACKING_VARIABLES
        if f"-u {variable}" not in definition
    ]


def _template_level_guarded_variables() -> frozenset[str]:
    """Return hijacking variables the template overrides and exports globally.

    ``override NAME := ...`` plus ``export`` makes Make replace any inherited
    value before a recipe runs, which is hermeticity by construction: no uv
    invocation built after that point can observe the caller's environment.
    """
    text = _template_text()
    return frozenset(
        variable
        for variable in _HIJACKING_VARIABLES
        if f"override {variable} :=" in text
        and re.search(rf"^export .*\b{variable}\b", text, re.MULTILINE)
    )


def test_every_uv_invocation_strips_environment_hijacking_variables() -> None:
    """No generated ``uv`` call may inherit another project's environment.

    ``uv run --project X`` is not sufficient on its own: ``VIRTUAL_ENV`` and
    friends win over ``--project``, so the command silently executes against a
    foreign runtime and reports gate results for code it never loaded.
    """
    guarded = _template_level_guarded_variables()
    offenders = {
        name: [variable for variable in unstripped if variable not in guarded]
        for name, definition in _uv_invocation_definitions().items()
        if (unstripped := _unstripped_variables(definition))
    }
    offenders = {name: missing for name, missing in offenders.items() if missing}

    assert not offenders, (
        "generated uv invocations inherit environment that overrides "
        f"--project: {offenders}"
    )


def test_uv_invocations_are_actually_present_in_the_template() -> None:
    """Guard the matcher itself against silently matching nothing.

    If the template's assignment style changes, the invariant above would pass
    vacuously. This keeps the contract honest.
    """
    assert _uv_invocation_definitions(), (
        f"no uv invocation definitions found in {_TEMPLATE}"
    )


__all__: tuple[str, ...] = ()
