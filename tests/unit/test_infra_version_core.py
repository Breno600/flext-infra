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

    @staticmethod
    def test_package_version_matches_project_metadata() -> None:
        """Test package version matches project metadata."""
        metadata = tm.ok(
            u.Infra.read_project_metadata_result(Path(__file__).resolve().parents[2]),
        )

        tm.that(infra_pkg.__version__, eq=metadata.project.version)

    @staticmethod
    def test_package_version_info_matches_current_workspace_semver_prefix() -> None:
        """Test package version info matches current workspace semver prefix."""
        version_result = u.Infra.current_workspace_version(
            Path(__file__).resolve().parents[2],
        )

        tm.ok(version_result)
        parse_result = u.Infra.parse_semver(version_result.value)
        tm.ok(parse_result)
        tm.that(infra_pkg.__version_info__[:3], eq=parse_result.value)

    @staticmethod
    def test_package_version_fields_have_public_runtime_types() -> None:
        """Test package version fields have public runtime types."""
        tm.that(infra_pkg.__version__, is_=str)
        tm.that(infra_pkg.__version_info__, is_=tuple)

    @staticmethod
    def test_latest_release_tag_ranks_versions_and_ignores_foreign_namespaces() -> None:
        """Test latest release tag ranks versions and ignores foreign namespaces.

        Cycle-control markers (``val*``) and other foreign tag namespaces share
        the ``v`` prefix collision but are not release candidates: they are
        skipped, never ranked and never a failure. A tag that looks like a
        version (digit-leading after the prefix) but does not parse still
        fails loud — typo protection stays.
        """
        ranked = tm.ok(
            u.Infra.latest_release_tag(
                ("v0.4.7", "val20261003t1808", "v0.4.8", "v0.4.10"),
            ),
        )
        tm.that(ranked, eq="v0.4.10")

        only_foreign = tm.ok(u.Infra.latest_release_tag(("val20261002t2254",)))
        tm.that(only_foreign, eq="")

        nothing = tm.ok(u.Infra.latest_release_tag(()))
        tm.that(nothing, eq="")

        malformed = u.Infra.latest_release_tag(("v0.4.not.a.version",))
        tm.fail(malformed, has="invalid release tag")
