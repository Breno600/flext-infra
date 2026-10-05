"""Exercise elected import deferral through the real public utility facade.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import infra
from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraSelfFacadeCutover:
    """Keep method behavior, docstrings, and local shadowing after migration."""

    def test_resolved_body_import_preserves_real_consumer(self, tmp_path: Path) -> None:
        """Test resolved body import preserves real consumer."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / "consumer.py"
        source = (
            "from flext_infra import u\n"
            "class Consumer:\n"
            "    @staticmethod\n"
            "    def digest() -> str:\n"
            "        '''Documented public operation.'''\n"
            "        return u.Cli.sha256_bytes(b'payload')\n"
            "def unrelated(u: str) -> str:\n"
            "    return u\n"
            "assert Consumer.digest() == "
            "__import__('hashlib').sha256(b'payload').hexdigest()\n"
            "assert Consumer.digest.__doc__ == 'Documented public operation.'\n"
            "assert unrelated('local') == 'local'\n"
        )
        finding = self._finding(path.relative_to(root))
        with infra.rope_workspace(root) as rope:
            edits = tm.ok(
                u.Infra.plan_semantic_cutover(
                    c.Infra.SemanticCutoverPhase.SELF_FACADE_IMPORT,
                    rope_workspace=rope,
                    sources={path: source},
                    findings=(finding,),
                ),
            )
            tm.that(len(edits), eq=1)
            remaining = tm.ok(
                u.Infra.plan_semantic_cutover(
                    c.Infra.SemanticCutoverPhase.SELF_FACADE_IMPORT,
                    rope_workspace=rope,
                    sources={path: edits[0].updated_source},
                    findings=(finding,),
                ),
            )
        tm.that(remaining, empty=True)
        path.write_text(edits[0].updated_source, encoding="utf-8")
        output = tm.ok(u.Cli.run_raw((sys.executable, "-I", str(path))))
        tm.that(u.Cli.process_succeeded(output.outcome), eq=True, msg=output.stderr)

    @pytest.mark.parametrize(
        "consumer",
        [
            "value = u.Cli.sha256_bytes(b'payload')\n",
            "class Consumer:\n    value = u.Cli.sha256_bytes(b'payload')\n",
            "def consumer(value=u.Cli.sha256_bytes(b'payload')):\n    return value\n",
            (
                "def consumer():\n    global u\n"
                "    return u.Cli.sha256_bytes(b'payload')\n"
            ),
            (
                "def outer():\n    u = None\n"
                "    def consumer():\n        nonlocal u\n        return u\n"
            ),
        ],
    )
    def test_eager_reference_is_rejected_before_publication(
        self,
        tmp_path: Path,
        consumer: str,
    ) -> None:
        """Test eager reference is rejected before publication."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / "consumer.py"
        source = "from flext_infra import u\n" + consumer
        path.write_text(source, encoding="utf-8")
        with infra.rope_workspace(root) as rope:
            result = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.SELF_FACADE_IMPORT,
                rope_workspace=rope,
                sources={path: source},
                findings=(self._finding(path.relative_to(root)),),
            )
        tm.fail(result, has="cannot be deferred")
        tm.that(path.read_text(encoding="utf-8"), eq=source)

    @pytest.mark.parametrize(
        "declaration",
        [
            "from flext_infra import u as first, u as second\n",
            (
                "from flext_infra import u as first\n"
                "from flext_infra import u as second\n"
                "from flext_infra import u as first\n"
            ),
        ],
    )
    def test_multiple_aliases_and_duplicate_imports_preserve_each_use(
        self,
        tmp_path: Path,
        declaration: str,
    ) -> None:
        """Test multiple aliases and duplicate imports preserve each use."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / "consumer.py"
        source = declaration + (
            "def first_digest():\n    return first.Cli.sha256_bytes(b'payload')\n"
            "def second_digest():\n    return second.Cli.sha256_bytes(b'payload')\n"
            "assert first_digest() == second_digest()\n"
        )
        finding = self._finding(path.relative_to(root))
        with infra.rope_workspace(root) as rope:
            edits = tm.ok(
                u.Infra.plan_semantic_cutover(
                    c.Infra.SemanticCutoverPhase.SELF_FACADE_IMPORT,
                    rope_workspace=rope,
                    sources={path: source},
                    findings=(finding,),
                ),
            )
            tm.that(len(edits), eq=1)
            remaining = tm.ok(
                u.Infra.plan_semantic_cutover(
                    c.Infra.SemanticCutoverPhase.SELF_FACADE_IMPORT,
                    rope_workspace=rope,
                    sources={path: edits[0].updated_source},
                    findings=(finding,),
                ),
            )
        tm.that(remaining, empty=True)
        path.write_text(edits[0].updated_source, encoding="utf-8")
        output = tm.ok(u.Cli.run_raw((sys.executable, "-I", str(path))))
        tm.that(u.Cli.process_succeeded(output.outcome), eq=True, msg=output.stderr)

    @staticmethod
    def _finding(path: Path) -> m.Infra.ModScanFinding:
        rule = c.Infra.SEMANTIC_CUTOVER_RULE_IDS[
            c.Infra.SemanticCutoverPhase.SELF_FACADE_IMPORT
        ]
        return m.Infra.ModScanFinding(
            rule_file=f"{rule}.yml",
            rule_id=rule,
            repository="fixture",
            file=path,
            range={},
            text="from flext_infra import u",
            actionable=False,
            classification=c.Infra.ModScanFindingClass.DETECTION_ONLY,
            payload={},
        )
