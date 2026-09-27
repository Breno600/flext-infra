"""Public behavior tests for census removal previews."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

import flext_infra
from flext_infra import c, m, u as infra_u
from tests import u as test_u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraRefactorCensusPreview:
    """Validate removal planning only through public FLEXT facades."""

    def test_build_simple_removal_sources_collapse_excess_blank_lines(
        self, tmp_path: Path
    ) -> None:
        """Plan one class removal without leaving excess blank lines."""
        repository_root, package_root = test_u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "service.py"
        module_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "def before() -> int:\n"
                "    return 1\n\n\n"
                "class Helper:\n"
                "    pass\n\n\n"
                "def after() -> int:\n"
                "    return before()\n"
            ),
            encoding="utf-8",
        )
        candidate = m.Infra.RemovalCandidate(
            project="flext-demo",
            file_path=str(module_path.resolve()),
            line=6,
            object_name="Helper",
            object_kind="class",
            scope_path="Helper",
            reason="unused",
            suggested_action="remove",
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            updates = infra_u.Infra.build_simple_removal_sources(rope, candidate)

        tm.that(updates, none=False)
        if updates is None:
            pytest.fail("simple-removal planning returned no source mapping")
        updated_source = updates[module_path.resolve()]
        tm.that(updated_source, lacks="class Helper")
        tm.that(updated_source, has="def after")
        tm.that(updated_source, lacks="\n\n\n\n")

    def test_build_simple_removal_sources_updates_multiline_consumers(
        self, tmp_path: Path
    ) -> None:
        """Plan removal of a base used by a multiline test facade."""
        repository_root, package_root = test_u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        base_path = package_root / "base.py"
        base_path.write_text(
            "from __future__ import annotations\n\nclass Shared:\n    pass\n",
            encoding="utf-8",
        )
        scripts_dir = repository_root / c.Infra.DIR_SCRIPTS
        scripts_dir.mkdir(parents=True, exist_ok=True)
        consumer_path = scripts_dir / "constants.py"
        consumer_path.write_text(
            (
                "from __future__ import annotations\n\n"
                "from flext_demo.base import Shared\n\n"
                "class Other:\n"
                "    pass\n\n"
                "class TestsFacade:\n"
                "    class Tests(\n"
                "        Other,\n"
                "        Shared,\n"
                "    ):\n"
                "        pass\n"
            ),
            encoding="utf-8",
        )
        candidate = m.Infra.RemovalCandidate(
            project="flext-demo",
            file_path=str(base_path.resolve()),
            line=3,
            object_name="Shared",
            object_kind="class",
            scope_path="Shared",
            reason="script_only",
            suggested_action="remove",
            script_reference_sites=(
                m.Infra.ReferenceSite(
                    file_path=str(consumer_path.resolve()),
                    line=3,
                    surface=c.Infra.DIR_SCRIPTS,
                ),
                m.Infra.ReferenceSite(
                    file_path=str(consumer_path.resolve()),
                    line=11,
                    surface=c.Infra.DIR_SCRIPTS,
                ),
            ),
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            updates = infra_u.Infra.build_simple_removal_sources(rope, candidate)

        tm.that(updates, none=False)
        if updates is None:
            pytest.fail("multiline-removal planning returned no source mapping")
        updated_consumer = updates[consumer_path.resolve()]
        tm.that(updated_consumer, lacks="from flext_demo.base import Shared")
        tm.that(updated_consumer, lacks="Shared,")
        tm.that(updated_consumer, has="Other,")

    def test_preview_simple_removal_candidate_does_not_write_source(
        self, tmp_path: Path
    ) -> None:
        """Validate a public preview while preserving the source artifact."""
        repository_root, package_root = test_u.Tests.create_lazy_init_workspace(
            tmp_path, project_name="flext-demo", package_name="flext_demo"
        )
        module_path = package_root / "dispatcher.py"
        original_source = (
            "from __future__ import annotations\n\n"
            "def run() -> int:\n"
            "    return 1\n\n\n"
            "class ExampleDispatchDsl:\n"
            "    @staticmethod\n"
            "    def run() -> int:\n"
            "        return run()\n"
        )
        module_path.write_text(original_source, encoding="utf-8")
        candidate = m.Infra.RemovalCandidate(
            project="flext-demo",
            file_path=str(module_path.resolve()),
            line=6,
            object_name="ExampleDispatchDsl",
            object_kind="class",
            scope_path="ExampleDispatchDsl",
            reason="unused",
            suggested_action="remove",
        )

        with flext_infra.infra.rope_workspace(repository_root) as rope:
            preview = infra_u.Infra.preview_simple_removal_candidate(
                rope, repository_root, candidate, gates=("lint",)
            )

        tm.ok(preview)
        tm.that(module_path.read_text(encoding="utf-8"), eq=original_source)
