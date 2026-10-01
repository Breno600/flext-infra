"""Tests that a custom Make surface never redefines a public verb.

The generated ``Makefile`` owns every verb in the typed Make configuration and
dispatches it through ``$(PUBLIC_VERBS)``. ``custom.mk`` is ``-include``d after
that block, so a recipe there for the same target silently *replaces* the
generated one — GNU Make reports ``overriding recipe for target`` and keeps the
last definition. The canonical verb then stops doing what the engine generated.

``config/codegen.yaml`` already declares this policy for the custom surface
(``allow_public_targets: false``); this test enforces it against the real files
on disk, which is where the shadowing actually happens.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from pathlib import Path

from flext_tests import tm

from flext_infra import c, config
from tests import t


class TestsFlextInfraCustomSurfaceNeverShadowsPublicVerbs:
    _TARGET_LINE = re.compile(r"^(?P<names>[a-z][a-z0-9 _-]*):(?!=)")

    def _repository_root(self) -> Path:
        """Return the repository root that owns this checkout."""
        return Path(__file__).resolve().parents[2]

    def _custom_surfaces(self) -> t.VariadicTuple[Path]:
        """Return every custom Make surface present in the workspace."""
        root = self._repository_root()
        name = c.Infra.CUSTOM_MAKE_FILENAME
        return tuple(
            sorted(
                path
                for path in (root / name, *root.glob(f"*/{name}"))
                if path.is_file()
            )
        )

    def _shadowed_verbs(self, surface: Path) -> t.VariadicTuple[str]:
        """Return public verbs this custom surface declares as targets."""
        public = frozenset(verb.name for verb in config.Infra.codegen.make.verbs)
        found: list[str] = []
        for line in surface.read_text(encoding="utf-8").splitlines():
            match = self._TARGET_LINE.match(line)
            if match is None:
                continue
            found.extend(
                name for name in match.group("names").split() if name in public
            )
        return tuple(sorted(set(found)))

    def test_policy_forbids_public_targets_on_the_custom_surface(self) -> None:
        """The codegen catalog declares the custom surface private-only."""
        policy = config.Infra.codegen.make.custom_handler_policy

        tm.that(policy.allow_public_targets, eq=False)

    def test_no_custom_surface_redefines_a_public_verb(self) -> None:
        """No custom.mk on disk overrides a generated public verb recipe."""
        root = self._repository_root()
        offenders = {
            str(surface.relative_to(root)): shadowed
            for surface in self._custom_surfaces()
            if (shadowed := self._shadowed_verbs(surface))
        }

        tm.that(offenders, eq={})
