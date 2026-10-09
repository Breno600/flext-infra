"""Projection-manifest derivation contract for the lazy-init phase.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from flext_tests import tm

from flext_infra import m
from flext_infra.codegen import FlextInfraCodegenLazyInitProjectionManifest
from tests import u


def _plan(
    project: Path,
    relative: str,
    content: bytes | None,
) -> m.Infra.CodegenFilePlan:
    path = project / relative
    if content is None:
        before = m.Cli.AtomicFileState(path=path)
    else:
        before = m.Cli.AtomicFileState(
            path=path,
            content=content,
            mode=0o644,
            device=1,
            inode=1,
            link_count=1,
            parent_device=1,
            parent_inode=1,
        )
    return m.Infra.CodegenFilePlan(
        project=project,
        path=path,
        before=before,
        desired_content=content,
        desired_mode=0o644 if content is not None else None,
    )


class TestsFlextInfraLazyInitProjectionManifest:
    """The manifest is a pure, deterministic function of the phase plans."""

    @staticmethod
    def test_manifest_is_deterministic_and_digest_bound(tmp_path: Path) -> None:
        """Identical plans render identical bytes bound to content digests."""
        first = _plan(tmp_path, ".agents/aihub-hooks/__init__.py", b"alpha")
        second = _plan(tmp_path, ".codex/rules/rule.mdc", b"beta")
        composed = (first, second)
        one = FlextInfraCodegenLazyInitProjectionManifest.projection_manifest_plans(
            files=composed,
        )
        two = FlextInfraCodegenLazyInitProjectionManifest.projection_manifest_plans(
            files=composed,
        )
        tm.that(one.failure, eq=False)
        tm.that(one.value, eq=two.value)
        manifest = one.value[0]
        tm.that(manifest.path, eq=tmp_path / ".agents" / "projections.lock.json")
        assert manifest.desired_content is not None
        parsed = u.Tests.json_payload(manifest.desired_content.decode("utf-8"))
        tm.that(parsed["apiVersion"], eq="flext-infra/projections-lock/v1")
        entries = parsed["entries"]
        assert isinstance(entries, list)
        tm.that(len(entries), eq=2)
        first_entry = entries[0]
        assert isinstance(first_entry, dict)
        second_entry = entries[1]
        assert isinstance(second_entry, dict)
        tm.that(first_entry.get("path"), eq=".agents/aihub-hooks/__init__.py")
        tm.that(second_entry.get("path"), eq=".codex/rules/rule.mdc")
        tm.that(first_entry.get("sha256"), eq=hashlib.sha256(b"alpha").hexdigest())
        tm.that(first_entry.get("bytes"), eq=5)
        assert manifest.desired_content is not None
        tm.that(manifest.desired_content.endswith(b"\n"), eq=True)

    @staticmethod
    def test_manifest_excludes_itself_and_non_projected_plans(
        tmp_path: Path,
    ) -> None:
        """Only .agents/.codex projections feed entries; no manifest self-reference."""
        projected = _plan(tmp_path, ".agents/aihub-hooks/x.py", b"kept")
        engine = _plan(tmp_path, "src/engine.py", b"ignored")
        existing = _plan(
            tmp_path,
            ".agents/projections.lock.json",
            b'{"apiVersion": "stale"}',
        )
        result = FlextInfraCodegenLazyInitProjectionManifest.projection_manifest_plans(
            files=(projected, engine, existing),
        )
        tm.that(result.failure, eq=False)
        tm.that(len(result.value), eq=1)
        assert result.value[0].desired_content is not None
        parsed = u.Tests.json_payload(
            result.value[0].desired_content.decode("utf-8"),
        )
        entries = parsed["entries"]
        assert isinstance(entries, list)
        only_entry = entries[0]
        assert isinstance(only_entry, dict)
        tm.that(only_entry.get("path"), eq=".agents/aihub-hooks/x.py")

    @staticmethod
    def test_project_without_projections_gets_no_manifest(tmp_path: Path) -> None:
        """A project owning no projected files emits no manifest plan."""
        engine = _plan(tmp_path, "src/engine.py", b"only")
        result = FlextInfraCodegenLazyInitProjectionManifest.projection_manifest_plans(
            files=(engine,),
        )
        tm.that(result.failure, eq=False)
        tm.that(result.value, eq=())

    @staticmethod
    def test_manifest_groups_one_plan_per_project(tmp_path: Path) -> None:
        """Two projects each receive their own manifest at their own root."""
        other = tmp_path / "member"
        other.mkdir()
        composed = (
            _plan(tmp_path, ".agents/a.py", b"root"),
            _plan(other, ".codex/b.mdc", b"member"),
        )
        result = FlextInfraCodegenLazyInitProjectionManifest.projection_manifest_plans(
            files=composed,
        )
        tm.that(result.failure, eq=False)
        tm.that(len(result.value), eq=2)
        roots = sorted(plan.project for plan in result.value)
        tm.that(roots, eq=sorted([tmp_path, other]))
