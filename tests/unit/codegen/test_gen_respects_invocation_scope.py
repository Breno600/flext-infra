"""Every command in one verb recipe writes to the same root.

Scope is the invocation point's own repository: every repository, the
workspace root included, works on itself alone (operator ruling 2026-09-29).

The ``gen`` recipe broke that by mixing two criteria in the same body:
``codegen conform`` received ``PROJECT_ROOT`` while dependency stages received
``REPOSITORY_ROOT``. A ``gen`` invoked inside one
member therefore rewrote the ``pyproject.toml`` of every sibling -- measured as
"INFO: Updated <sibling>/pyproject.toml" for ~30 repositories, leaving each one
dirty without the caller ever touching it.

The damage compounds: ``gen`` runs inside ``check``, and ``check`` runs in the
pre-commit hook, so a single commit in any lane dirties every sibling.

At the workspace root ``PROJECT_ROOT`` is the root repository itself, so one
rule keeps every verb on its own repository everywhere. No flag is needed --
one rule, applied consistently.

Every contract is asserted on the Makefile the public conform owner renders
for a workspace fixture composing one member.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config
from tests import t, u

pytestmark = pytest.mark.slow

_MEMBER = "fixture-member"


class TestsFlextInfraGenRespectsInvocationScope:
    """`gen` recipes write to exactly one root per invocation."""

    @staticmethod
    @pytest.fixture
    def rendered_makefile(tmp_path: Path) -> str:
        """Render the workspace Makefile through the conform owner.

        Returns:
            The resulting ``str``.

        """
        return u.Tests.scaffold_text(
            tmp_path / "fixture-project",
            c.Infra.MAKEFILE_FILENAME,
            members=(_MEMBER,),
        )

    @staticmethod
    def _recipe_bodies(text: str) -> t.MutableMappingKV[str, list[str]]:
        """Return each rendered ``_builtin_*`` target mapped to its recipe lines.

        Returns:
            Each rendered ``_builtin_*`` target mapped to its recipe lines.

        """
        bodies: t.MutableMappingKV[str, list[str]] = {}
        current: str | None = None
        for line in text.splitlines():
            target = re.match(r"^(_builtin_[a-z_]+):", line)
            if target:
                current = target.group(1)
                bodies[current] = []
                continue
            if current is None:
                continue
            if line.startswith("\t"):
                bodies[current].append(line.strip())
                continue
            current = None
        return bodies

    def test_no_recipe_mixes_project_and_repository_roots(
        self,
        rendered_makefile: str,
    ) -> None:
        """One rendered recipe never writes to two different roots.

        A command that escalates to ``REPOSITORY_ROOT`` beside one scoped to
        ``PROJECT_ROOT`` mutates siblings the caller never asked for.
        """
        bodies = self._recipe_bodies(rendered_makefile)
        project_scoped = {
            target
            for target, lines in bodies.items()
            if any("$(PROJECT_ROOT)" in line for line in lines)
        }
        mixed = {
            target: bodies[target]
            for target in project_scoped
            if any("$(REPOSITORY_ROOT)" in line for line in bodies[target])
        }

        # The rendered gen recipe is project-scoped, so the invariant below is
        # never satisfied vacuously by an unparsed Makefile.
        tm.that(project_scoped, has="_builtin_gen_all")
        tm.that(mixed, eq={})

    def test_gen_has_one_codegen_owner(self, rendered_makefile: str) -> None:
        """The gen recipe delegates once to the conform owner.

        Apply verifies its own fixed point inside the conform transaction, so a
        second external check invocation would duplicate ownership.
        """
        tm.that(rendered_makefile, lacks="CODEGEN_PROJECT_ARGS")
        body = self._recipe_bodies(rendered_makefile)["_builtin_gen_all"]
        conform_lines = [line for line in body if "codegen conform" in line]

        tm.that(len(conform_lines), eq=1)
        tm.that(conform_lines[0], has="--mode apply")
        tm.that(conform_lines[0], has='--root "$(PROJECT_ROOT)"')
        tm.that(conform_lines[0], lacks="--scope")
        tm.that(any("deps modernize" in line for line in body), eq=False)
        tm.that(any("deps extra-paths" in line for line in body), eq=False)

    def test_gen_init_uses_the_provisioned_owner_route(
        self,
        rendered_makefile: str,
    ) -> None:
        """Initialize uses its declared interpreter and one initializer owner."""
        init_lines = self._recipe_bodies(rendered_makefile)["_builtin_gen_init"]
        init_commands = [line for line in init_lines if "codegen init" in line]

        tm.that(len(init_commands), eq=2)
        tm.that(
            all(
                '--repository-root "$(PROJECT_ROOT)"' in line for line in init_commands
            ),
            eq=True,
        )
        tm.that(any("codegen conform" in line for line in init_lines), eq=False)
        for verb in config.Infra.codegen.make.verbs:
            if verb.name in {"setup", "upg", "help", "clean"} or (
                verb.profiles and c.Infra.MakeProfile.WORKSPACE not in verb.profiles
            ):
                continue
            tm.that(
                rendered_makefile,
                has=f"_activated-{verb.name}: _builtin_require_environment",
            )
            if not verb.produces_activation:
                tm.that(
                    rendered_makefile,
                    has=(
                        'direnv exec "$(PROJECT_ROOT)" $(SELF_MAKE) '
                        f"_activated-{verb.name}"
                    ),
                )
        tm.that(rendered_makefile, has="_builtin-initialize: _builtin_gen_init")
        tm.that(rendered_makefile, has="ifneq ($(filter initialize,$(MAKECMDGOALS)),)")
        tm.that(rendered_makefile, has="GEN_INIT_ONLY := Y")
        tm.that(rendered_makefile, has="REPOSITORY_ROOT := $(MAKEFILE_ROOT)")
        tm.that(rendered_makefile, lacks="INIT_FLEXT_INFRA")

    @staticmethod
    def test_project_selector_resolves_members_from_repository_root(
        rendered_makefile: str,
    ) -> None:
        """Workspace members are projected as declared gitlinks, not a WORKSPACE var.

        Root cause: the `override WORKSPACE := .../$(PROJECT)` selector was
        retired in favor of `WORKSPACE_SUBPROJECTS`/`MANAGED_GITLINKS`, which the
        generator renders from the declared workspace members, never re-derived
        from a shell probe at `REPOSITORY_ROOT` or `PROJECT_ROOT`.
        """
        tm.that(rendered_makefile, lacks="override WORKSPACE :=")
        tm.that(rendered_makefile, has=f"WORKSPACE_SUBPROJECTS := {_MEMBER}")
        tm.that(rendered_makefile, has="MANAGED_GITLINKS :=$(WORKSPACE_SUBPROJECTS)")
