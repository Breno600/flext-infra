"""Execute migrated public model-validation boundaries with real Pydantic types.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import infra
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsModelFieldsCutover:
    """Migration preserves rejection semantics and reaches a stable source."""

    @staticmethod
    @pytest.mark.parametrize(
        "access",
        [
            'getattr(candidate, "model_fields", None)',
            'getattr(candidate, "model_fields", {})',
            'getattr(candidate, "model_fields")',
            "candidate.model_fields",
        ],
    )
    def test_public_boundary_rejects_non_models_without_attribute_access(
        tmp_path: Path,
        access: str,
    ) -> None:
        """Test public boundary rejects non models without attribute access."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / "validation.py"
        source = (
            "from flext_core import m\n"
            "def inspect_definition(candidate: object, *, label: str) -> None:\n"
            f"    fields = {access}\n"
            "    if not isinstance(fields, dict) or not fields:\n"
            "        raise ValueError(label)\n"
            "class Populated(m.BaseModel):\n"
            "    value: str\n"
            "class Empty(m.BaseModel):\n"
            "    pass\n"
            "class Pretender:\n"
            "    model_fields = {'value': None}\n"
            "class Poison:\n"
            "    def __getattr__(self, name: str) -> None:\n"
            "        raise RuntimeError('unexpected attribute access')\n"
            "inspect_definition(Populated, label='valid')\n"
            "for invalid in (None, object(), 1, str, Empty, Pretender, Poison(), Populated(value='x')):\n"
            "    try:\n"
            "        inspect_definition(invalid, label='original boundary error')\n"
            "    except ValueError as error:\n"
            "        assert str(error) == 'original boundary error'\n"
            "    else:\n"
            "        raise AssertionError('invalid model was accepted')\n"
        )
        with infra.rope_workspace(root) as rope:
            edits = tm.ok(
                u.Infra.plan_semantic_cutover(
                    c.Infra.SemanticCutoverPhase.MODEL_FIELDS,
                    rope_workspace=rope,
                    sources={path: source},
                ),
            )
            tm.that(len(edits), eq=1)
            remaining = tm.ok(
                u.Infra.plan_semantic_cutover(
                    c.Infra.SemanticCutoverPhase.MODEL_FIELDS,
                    rope_workspace=rope,
                    sources={path: edits[0].updated_source},
                ),
            )
        tm.that(remaining, empty=True)
        path.write_text(edits[0].updated_source, encoding="utf-8")
        outcome = tm.ok(u.Cli.run_raw((sys.executable, "-I", str(path))))
        tm.that(outcome.exit_code, eq=0)
        tm.that(outcome.stderr, eq="")

    @staticmethod
    def test_ambiguous_rejection_keeps_the_source_untouched(
        tmp_path: Path,
    ) -> None:
        """Test ambiguous rejection keeps the source untouched."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / "validation.py"
        source = (
            "def validate(candidate: object) -> None:\n"
            "    fields = candidate.model_fields\n"
            "    print(fields)\n"
        )
        path.write_text(source, encoding="utf-8")
        with infra.rope_workspace(root) as rope:
            result = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.MODEL_FIELDS,
                rope_workspace=rope,
                sources={path: source},
            )
        tm.fail(result, has="lacks a rejecting guard")
        tm.that(path.read_text(encoding="utf-8"), eq=source)

    @staticmethod
    def test_conflicting_guard_binding_is_not_overwritten(tmp_path: Path) -> None:
        """Test conflicting guard binding is not overwritten."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / "validation.py"
        source = (
            "u = 1\n"
            "def validate(candidate: object) -> None:\n"
            "    fields = candidate.model_fields\n"
            "    if not isinstance(fields, dict) or not fields:\n"
            "        raise ValueError('invalid')\n"
        )
        with infra.rope_workspace(root) as rope:
            result = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.MODEL_FIELDS,
                rope_workspace=rope,
                sources={path: source},
            )
        tm.fail(result, has="conflicts with a local binding")

    @staticmethod
    @pytest.mark.parametrize(
        "declaration",
        [
            "from another import type\n",
            "def isinstance(*args):\n    return True\n",
            "class object:\n    pass\n",
            "getattr = lambda *args: {}\n",
            "try:\n    pass\nexcept Exception as dict:\n    pass\n",
            "match None:\n    case type:\n        pass\n",
        ],
    )
    def test_shadowed_contract_is_rejected(
        tmp_path: Path,
        declaration: str,
    ) -> None:
        """Test shadowed contract is rejected."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / "validation.py"
        source = declaration + (
            "def validate(candidate: object) -> None:\n"
            "    fields = candidate.model_fields\n"
            "    if not isinstance(fields, dict) or not fields:\n"
            "        raise ValueError('invalid')\n"
        )
        with infra.rope_workspace(root) as rope:
            result = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.MODEL_FIELDS,
                rope_workspace=rope,
                sources={path: source},
            )
        tm.fail(result)

    @staticmethod
    @pytest.mark.parametrize(
        "body",
        [
            (
                "    candidate = object()\n"
                "    fields = candidate.model_fields\n"
                "    if not isinstance(fields, dict) or not fields:\n"
                "        raise ValueError('invalid')\n"
            ),
            (
                "    fields = candidate.model_fields\n"
                "    if not isinstance(fields, dict) or not fields: raise ValueError('invalid')\n"
            ),
        ],
    )
    def test_unsafe_statement_layout_or_receiver_rebinding_fails(
        tmp_path: Path,
        body: str,
    ) -> None:
        """Test unsafe statement layout or receiver rebinding fails."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / "validation.py"
        source = "def validate(candidate: object) -> None:\n" + body
        with infra.rope_workspace(root) as rope:
            result = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.MODEL_FIELDS,
                rope_workspace=rope,
                sources={path: source},
            )
        tm.fail(result)
