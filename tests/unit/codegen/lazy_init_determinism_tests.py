"""Deterministic-order contract for the lazy-init render.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c
from tests import u


class TestsFlextInfraLazyInitDeterminism:
    """The rendered lazy map is byte-identical on every host.

    The rope index enumerates modules in filesystem directory-entry order,
    which differs between machines; the planner must therefore impose a
    canonical order, or two hosts rendering the same sources produce two
    different committed inits and every consumer's gen fixed point drifts.
    """

    def test_rendered_lazy_map_keys_are_canonically_ordered(
        self, tmp_path: Path
    ) -> None:
        """Every rendered mapping key row follows lexicographic order."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        for name in (
            "zulu",
            "alpha",
            "mike",
            "bravo",
            "yankee",
            "delta",
            "whiskey",
            "echo",
            "tango",
            "kilo",
            "sierra",
            "november",
        ):
            u.Tests.write_lazy_init_namespace_module(
                package_root / f"{name}.py",
                class_name=f"FlextTests{name.capitalize()}",
                alias=name,
                docstring=f"{name.capitalize()} module.",
            )
        exit_code = u.Tests.run_lazy_init(repository_root)
        tm.that(exit_code, eq=0)
        init_text = (package_root / c.Infra.INIT_PY).read_text(
            encoding=c.Cli.ENCODING_DEFAULT
        )
        entries, _refs = u.Infra.module_mapping_assignment_source(
            init_text, u.Infra.lazy_imports_name_source(init_text)
        )
        keys = [key for key, _names in entries]
        tm.that(keys, empty=False)
        tm.that(keys, eq=sorted(keys))
