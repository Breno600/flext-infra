"""Fresh-import probe scope contract for the conform verifier.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra.codegen import FlextInfraCodegenConformExecute
from tests import c, u


class TestFreshImportRepositoryScope:
    """Only declared Python packages enter the fresh-import probe scope."""

    def test_package_false_roots_are_excluded_from_probe_scope(self) -> None:
        """A workspace umbrella root that publishes no package is not probed.

        The manifest of a ``package: false`` repository is the authority for
        that declaration (the detector honors the declared repository record),
        so the probe scope derived from the conform plan must not include it.
        Requiring an importable layout there made ``make gen`` fail on every
        such checkout regardless of what conform actually published.
        """
        workspace_root = u.Tests.repository_ref(
            "demo-workspace", role=c.Infra.MakeProfile.WORKSPACE
        )
        member = u.Tests.repository_ref("demo-member", path=Path("demo-member"))
        umbrella_without_package = workspace_root.model_copy(update={"package": False})

        resolved = FlextInfraCodegenConformExecute.fresh_import_repository_roots(
            Path("/checkouts"), (umbrella_without_package, member)
        )

        tm.that(resolved, eq=(Path("/checkouts/demo-member"),))

    def test_package_true_roots_resolve_under_the_workspace_root(self) -> None:
        """Every declared package repository resolves under the workspace root."""
        first = u.Tests.repository_ref("demo-first", path=Path("demo-first"))
        second = u.Tests.repository_ref("demo-second", path=Path("demo-second"))

        resolved = FlextInfraCodegenConformExecute.fresh_import_repository_roots(
            Path("/checkouts"), (first, second)
        )

        tm.that(
            resolved, eq=(Path("/checkouts/demo-first"), Path("/checkouts/demo-second"))
        )
