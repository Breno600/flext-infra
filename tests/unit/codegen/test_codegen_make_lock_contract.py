"""Conform publication preserves the committed dependency lock graph.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, r
from tests import c, m, u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeLockContract:
    """A conform publication never rewrites the committed lock inputs."""

    @staticmethod
    def test_conform_publication_preserves_committed_lock_graph(
        tmp_path: Path,
    ) -> None:
        """Test conform publication preserves committed lock graph."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        lock = root / c.Infra.UV_LOCK_FILENAME
        lock.write_bytes((Path(__file__).resolve().parents[3] / lock.name).read_bytes())
        paths = (
            lock,
            # Unlocked fleet mode commits no mise.lock; the SSOT decides.
            *(
                (root / c.Infra.MISE_LOCK_FILENAME,)
                if config.Infra.codegen.toolchain.mise_lockfile
                else ()
            ),
        )
        before = {path: path.read_bytes() for path in paths}
        repository = u.Tests.repository_ref(
            root.name,
            role=c.Infra.MakeProfile.STANDALONE,
        )
        workspace = u.Tests.workspace_spec(
            repository,
            project=u.Tests.project_spec(repository.name),
        )
        plan = u.Tests.conform_plan(root, workspace)
        tm.ok(
            u.Tests.materialize_codegen_plans(
                r[tuple[m.Infra.CodegenFilePlan, ...]].ok(tuple(plan.files)),
            ),
        )

        tm.that({path: path.read_bytes() for path in paths}, eq=before)
        tm.that(
            (root / c.Infra.MISE_LOCK_FILENAME).exists(),
            eq=config.Infra.codegen.toolchain.mise_lockfile,
        )
