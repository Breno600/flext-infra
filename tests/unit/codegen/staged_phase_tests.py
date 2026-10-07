"""Journal phase contract for the codegen staged publication models.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from flext_tests import tm
from pydantic import ValidationError

from flext_infra import c, m


def _staged_file_payload(phase: str, root: Path) -> dict[str, Any]:
    """Build one staged-publication payload with the given wire phase.

    Returns:
        The resulting ``dict[str, Any]``.
    """
    project = root / "codegen-staged-phase-contract"
    path = project / "generated" / "artifact.txt"
    return {
        "phase": phase,
        "project": project,
        "before": {
            "path": path,
            "content": b"payload",
            "mode": 0o644,
            "device": 1,
            "inode": 1,
            "link_count": 1,
            "parent_device": 1,
            "parent_inode": 1,
        },
    }


class TestsFlextInfraCodegenStagedFilePhase:
    """The journal phase vocabulary is closed and code-owned."""

    @staticmethod
    def test_vocabulary_is_the_canonical_publication_set() -> None:
        """The enum members are exactly the phases the pipeline publishes."""
        tm.that(
            {phase.value for phase in c.Infra.CodegenStagedFilePhase},
            eq={
                "candidate-bootstrap",
                "conform",
                "conform-bootstrap",
                "docs",
                "lazy-init",
                "layout",
                "mise",
                "mod-text",
                "recovery",
                "scaffold",
                "semantic",
                "transaction",
                "version-file",
            },
        )

    @staticmethod
    def test_journal_coerces_every_declared_phase(tmp_path: Path) -> None:
        """Each wire phase value validates into the closed enum contract."""
        accepted = [
            m.Infra.CodegenStagedFile.model_validate(
                _staged_file_payload(phase.value, tmp_path),
            ).phase
            for phase in c.Infra.CodegenStagedFilePhase
        ]
        tm.that(frozenset(accepted), eq=frozenset(c.Infra.CodegenStagedFilePhase))

    @staticmethod
    def test_journal_rejects_phase_outside_the_contract(tmp_path: Path) -> None:
        """A literal outside the enum fails loud instead of freezing a string."""
        with pytest.raises(ValidationError, match="input_value='bogus-phase'"):
            _ = m.Infra.CodegenStagedFile.model_validate(
                _staged_file_payload("bogus-phase", tmp_path),
            )
