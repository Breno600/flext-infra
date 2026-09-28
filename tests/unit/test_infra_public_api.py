"""Public API contract tests for flext_infra facades."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

import flext_infra


class TestsFlextInfraPublicApi:
    """Exercise the root public package metadata against its pyproject."""

    def test_public_runtime_metadata_matches_public_constants(self) -> None:
        metadata = tm.ok(
            flext_infra.u.Infra.read_project_metadata_result(
                Path(__file__).resolve().parents[2]
            )
        )

        tm.that(flext_infra.__title__, eq=metadata.project.name)
        tm.that(flext_infra.__version__, eq=metadata.project.version)
        tm.that(flext_infra.__description__, eq=metadata.project.description)
        tm.that(flext_infra.__url__, eq=metadata.project.urls.homepage)
        tm.that(metadata.project.authors, empty=False)
        tm.that(flext_infra.__author__, eq=metadata.project.authors[0].name)
