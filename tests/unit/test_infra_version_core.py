"""Public package version behavior tests.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

import flext_infra as infra_pkg
from flext_infra import u


class TestsFlextInfraInfraVersionCore:
    """Validate public package metadata against canonical public utilities."""

    def test_package_version_matches_project_metadata(self) -> None:
        metadata = tm.ok(
            u.Infra.read_project_metadata_result(Path(__file__).resolve().parents[2])
        )

        tm.that(infra_pkg.__version__, eq=metadata.project.version)

    def test_package_version_info_matches_current_workspace_semver_prefix(self) -> None:
        version_result = u.Infra.current_workspace_version(
            Path(__file__).resolve().parents[2]
        )

        tm.ok(version_result)
        parse_result = u.Infra.parse_semver(version_result.value)
        tm.ok(parse_result)
        tm.that(infra_pkg.__version_info__[:3], eq=parse_result.value)

    def test_package_version_fields_have_public_runtime_types(self) -> None:
        tm.that(infra_pkg.__version__, is_=str)
        tm.that(infra_pkg.__version_info__, is_=tuple)
