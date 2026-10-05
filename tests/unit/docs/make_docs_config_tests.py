"""Contract tests for the make.docs actions configuration.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, m

if TYPE_CHECKING:
    from tests import t


def _spec_payload(**overrides: t.JsonValue) -> t.MutableJsonMapping:
    """Build one valid synthetic spec payload; overrides mutate one field.

    Returns:
        The resulting ``t.MutableJsonMapping``.

    """
    payload: t.MutableJsonMapping = {
        "actions": ["generate", "fix", "validate"],
        "mutable_actions": ["fix"],
        "reports_dir": ".reports/docs",
        "cross_project_relative_link_pattern": "^(?:../)+flext-[a-z0-9-]+(?:/|$)",
        "stale_github_organizations": ["placeholder-org"],
        "overview_preview_limits": {
            "aliases": 3,
            "public_symbols": 3,
            "facades": 3,
            "module_exports": 3,
            "keywords": 3,
        },
    }
    payload.update(overrides)
    return payload


class TestsFlextInfraMakeDocsActionsConfig:
    """Validation contract for make.docs lifecycle actions."""

    @staticmethod
    def test_live_config_actions_stay_on_the_registered_cli_surface() -> None:
        """The declared workspace lifecycle dispatches only existing verbs."""
        docs = config.Infra.codegen.make.docs
        tm.that(set(docs.actions) <= c.Infra.DOCS_ACTION_IDS, eq=True)
        tm.that(set(docs.mutable_actions) <= set(docs.actions), eq=True)

    @staticmethod
    def test_synthetic_lifecycle_validates() -> None:
        """Test synthetic lifecycle validates."""
        spec = m.Infra.MakeDocsSpec.model_validate(_spec_payload())
        tm.that(spec.actions, eq=("generate", "fix", "validate"))

    @staticmethod
    def test_unknown_action_is_rejected() -> None:
        """Test unknown action is rejected."""
        with pytest.raises(c.ValidationError, match="not a registered CLI action"):
            m.Infra.MakeDocsSpec.model_validate(
                _spec_payload(actions=["generate", "deploy"]),
            )

    @staticmethod
    def test_duplicate_action_is_rejected() -> None:
        """Test duplicate action is rejected."""
        with pytest.raises(c.ValidationError, match="must be unique"):
            m.Infra.MakeDocsSpec.model_validate(
                _spec_payload(actions=["generate", "generate"]),
            )

    @staticmethod
    def test_mutable_action_outside_lifecycle_is_rejected() -> None:
        """Test mutable action outside lifecycle is rejected."""
        with pytest.raises(c.ValidationError, match="not part of the docs lifecycle"):
            m.Infra.MakeDocsSpec.model_validate(_spec_payload(mutable_actions=["fmt"]))

    @staticmethod
    def test_warning_posture_is_not_a_docs_option() -> None:
        """Test warning posture is not a docs option."""
        with pytest.raises(c.ValidationError):
            m.Infra.MakeDocsSpec.model_validate(
                _spec_payload(warning_actions=["audit"]),
            )
