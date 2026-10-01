"""Public package metadata export tests.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

import flext_infra as infra_pkg
from flext_infra import u


class TestsFlextInfraInfraVersionExtra:
    """Validate public package metadata exports against project SSOT."""

    def test_public_package_metadata_matches_project_metadata(self) -> None:
        metadata = tm.ok(
            u.Infra.read_project_metadata_result(Path(__file__).resolve().parents[2])
        )

        tm.that(infra_pkg.__title__, eq=metadata.project.name)
        tm.that(infra_pkg.__version__, eq=metadata.project.version)
        tm.that(infra_pkg.__description__, eq=metadata.project.description)
        tm.that(infra_pkg.__url__, eq=metadata.project.urls.homepage)

    def test_public_package_author_matches_project_authors(self) -> None:
        metadata = tm.ok(
            u.Infra.read_project_metadata_result(Path(__file__).resolve().parents[2])
        )

        tm.that(metadata.project.authors, empty=False)
        author = metadata.project.authors[0]
        tm.that(infra_pkg.__author__, eq=author.name)
        tm.that(infra_pkg.__author_email__, eq=author.email)

    def test_public_package_exports_have_expected_runtime_types(self) -> None:
        tm.that(infra_pkg.__version__, is_=str)
        tm.that(infra_pkg.__version_info__, is_=tuple)
        tm.that(infra_pkg.__title__, is_=str)
        tm.that(infra_pkg.__description__, is_=str)
        tm.that(infra_pkg.__author__, is_=str)
        tm.that(infra_pkg.__author_email__, is_=str)
        tm.that(infra_pkg.__license__, is_=str)
        tm.that(infra_pkg.__url__, is_=str)

    def test_public_package_version_info_is_tuple(self) -> None:
        """Test that module-level __version_info__ is a tuple."""
        tm.that(infra_pkg.__version_info__, is_=tuple)
