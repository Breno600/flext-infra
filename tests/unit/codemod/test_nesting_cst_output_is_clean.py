"""The class-nesting cutover emits source the canonical gates accept."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

import flext_infra
from tests import c, u


class TestsFlextInfraNestingCutoverOutput:
    """A cutover whose output fails ruff is not a repair.

    Every module the mover touched came back with findings a human then fixed
    by hand, which is the sweep this engine exists to eliminate. The defects
    pinned here were reproduced verbatim in a committed module on a member
    branch: a blank line carrying the block indent (W293), an export
    declaration rebuilt without its separation (E305), and a docstring left at
    the depth the class no longer has (D207).
    """

    @staticmethod
    def _planned_source(tmp_path: Path) -> str:
        """Plan one class-nesting cutover through the public cutover owner."""
        repository_root, package_root = u.Tests.create_lazy_init_workspace(tmp_path)
        alias, module_name = next(iter(c.Infra.FAMILY_PUBLIC_MODULES.items()))
        owner_name = (
            f"{u.derive_class_stem(repository_root.name)}"
            f"{c.Infra.FAMILY_SUFFIXES[alias]}"
        )
        module_path = package_root / f"{module_name}.py"
        u.Tests.write_lazy_init_namespace_module(
            module_path,
            class_name=owner_name,
            alias=alias,
            extra_class_names=(f"{owner_name}Member",),
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources={module_path: module_path.read_text(encoding="utf-8")},
            )

        return tm.ok(planned)[0].updated_source

    def test_emitted_source_carries_no_blank_line_with_indentation(
        self, tmp_path: Path
    ) -> None:
        """A separator line inside the owner block is empty, never indented."""
        emitted = self._planned_source(tmp_path)

        indented_blanks = [
            line for line in emitted.splitlines() if line.strip() == "" and line != ""
        ]

        tm.that(indented_blanks, empty=True)

    def test_emitted_source_keeps_docstrings_at_their_new_depth(
        self, tmp_path: Path
    ) -> None:
        """A moved class carries its docstring to the depth it now sits at."""
        emitted = self._planned_source(tmp_path)
        lines = emitted.splitlines()
        nested = next(
            index
            for index, line in enumerate(lines)
            if line.lstrip().startswith("class ") and line.startswith("    ")
        )
        depth = len(lines[nested]) - len(lines[nested].lstrip())

        for line in lines[nested + 1 :]:
            if not line.strip():
                continue
            if line.startswith(" " * (depth + 1)):
                continue
            tm.that(line.startswith(" " * depth) or not line.startswith(" "), eq=True)
            break

    def test_emitted_source_passes_the_whitespace_and_docstring_gates(
        self, tmp_path: Path
    ) -> None:
        """Ruff finds none of the three defects the mover used to write.

        Formatting proper belongs to the publication stage, which runs the
        canonical formatter; what the planner emits must already be free of
        the defects no formatter should have to repair.
        """
        module = tmp_path / "emitted" / "nested_module.py"
        tm.ok(u.Cli.ensure_dir(module.parent))
        tm.ok(u.Cli.atomic_write_text_file(module, self._planned_source(tmp_path)))

        linted = u.Cli.run([
            "ruff",
            "check",
            "--isolated",
            "--select",
            "W291,W293,E301,E303,E305,D207",
            str(module),
        ])

        tm.ok(linted)
