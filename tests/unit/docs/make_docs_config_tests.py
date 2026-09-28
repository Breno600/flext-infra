"""Contract tests for the make.docs actions configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, m

if TYPE_CHECKING:
    from tests import t


def _spec_payload(**overrides: t.JsonValue) -> dict[str, object]:
    """Build one valid synthetic spec payload; overrides mutate one field."""
    payload: dict[str, object] = {
        "actions": ["generate", "fix", "validate"],
        "api_modules": {"flext-demo": ("api", "base")},
        "mutable_actions": ["fix"],
        "reports_dir": ".reports/docs",
        "cross_project_relative_link_pattern": "^(?:../)+flext-[a-z0-9-]+(?:/|$)",
    }
    payload.update(overrides)
    return payload


class TestsFlextInfraMakeDocsActionsConfig:
    """Validation contract for make.docs lifecycle actions."""

    def test_live_config_actions_stay_on_the_registered_cli_surface(self) -> None:
        """The declared workspace lifecycle dispatches only existing verbs."""
        docs = config.Infra.codegen.make.docs
        tm.that(set(docs.actions) <= c.Infra.DOCS_ACTION_IDS, eq=True)
        tm.that(set(docs.mutable_actions) <= set(docs.actions), eq=True)
        tm.that(set(docs.warning_actions) <= set(docs.actions), eq=True)

    def test_synthetic_lifecycle_validates(self) -> None:
        spec = m.Infra.MakeDocsSpec.model_validate(
            _spec_payload(warning_actions=["validate"])
        )
        tm.that(spec.actions, eq=("generate", "fix", "validate"))
        tm.that(spec.warning_actions, eq=("validate",))

    def test_unknown_action_is_rejected(self) -> None:
        with pytest.raises(c.ValidationError, match="not a registered CLI action"):
            m.Infra.MakeDocsSpec.model_validate(
                _spec_payload(actions=["generate", "deploy"])
            )

    def test_duplicate_action_is_rejected(self) -> None:
        with pytest.raises(c.ValidationError, match="must be unique"):
            m.Infra.MakeDocsSpec.model_validate(
                _spec_payload(actions=["generate", "generate"])
            )

    def test_mutable_action_outside_lifecycle_is_rejected(self) -> None:
        with pytest.raises(c.ValidationError, match="not part of the docs lifecycle"):
            m.Infra.MakeDocsSpec.model_validate(_spec_payload(mutable_actions=["fmt"]))

    def test_warning_action_outside_lifecycle_is_rejected(self) -> None:
        with pytest.raises(c.ValidationError, match="not part of the docs lifecycle"):
            m.Infra.MakeDocsSpec.model_validate(
                _spec_payload(warning_actions=["audit"])
            )
