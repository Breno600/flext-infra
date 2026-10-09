"""Generation uses one root and one owner for the complete declared composition.

The conform owner receives ``PROJECT_ROOT`` with explicit ``ALL`` scope so root
generation includes every declared member. Other writers must not independently
escalate to ``REPOSITORY_ROOT`` or duplicate the conform transaction.

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
    """`gen` delegates the complete composition through exactly one root."""

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

        Conform owns member discovery; a second writer must not independently
        escalate from ``PROJECT_ROOT`` to ``REPOSITORY_ROOT``.
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

        # The gen recipe is PROJECT_ROOT-anchored, so the invariant below is
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
        tm.that(
            conform_lines[0],
            has=f"--scope {c.Infra.CodegenConformScope.ALL.value}",
        )
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
        rendered_lines = rendered_makefile.splitlines()
        for verb in config.Infra.codegen.make.verbs:
            if verb.name in {"setup", "upg", "help", "clean"} or (
                verb.profiles and c.Infra.MakeProfile.WORKSPACE not in verb.profiles
            ):
                continue
            activation_target = f"_activated-{verb.name}"
            expected_route = f"{activation_target}: _builtin_require_environment"
            activation_routes = tuple(
                line
                for line in rendered_lines
                if line.startswith(f"{activation_target}:")
            )
            tm.that(
                any(expected_route in line for line in activation_routes),
                eq=True,
                msg=(
                    f"verb={verb.name!r}: expected route {expected_route!r}; "
                    f"observed routes={activation_routes!r}"
                ),
            )
            if not verb.produces_activation:
                expected_invocation = (
                    f'direnv exec "$(PROJECT_ROOT)" $(SELF_MAKE) {activation_target}'
                )
                activation_commands = tuple(
                    line.strip()
                    for line in rendered_lines
                    if line.startswith("\t") and activation_target in line
                )
                tm.that(
                    any(expected_invocation in line for line in activation_commands),
                    eq=True,
                    msg=(
                        f"verb={verb.name!r}: expected invocation "
                        f"{expected_invocation!r}; "
                        f"observed commands={activation_commands!r}"
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
