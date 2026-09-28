"""Real public semantic publication, identity and rollback contracts."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_core import r
from flext_infra import c, m, p, u

if TYPE_CHECKING:
    from tests import t
from flext_infra.codemod import FlextInfraCodemodSemanticApply
from flext_infra.transformers import publish_semantic_file_plans


class TestsSemanticPublication:
    """All files remain recoverable until the semantic consumer accepts them."""

    @staticmethod
    def _plans(root: Path) -> t.VariadicTuple[m.Infra.SemanticFilePlan]:
        plans: list[m.Infra.SemanticFilePlan] = []
        for name in ("first.py", "second.py"):
            path = root / name
            u.Cli.atomic_write_text_file(path, 'value = "before"\n').unwrap()
            before = u.Cli.atomic_read_binary_file_state(path, required=True).unwrap()
            plans.append(
                m.Infra.SemanticFilePlan(
                    project=root,
                    path=path,
                    before=before,
                    desired_content=b'value = "after"\n',
                    desired_mode=before.mode,
                    changes=("publication contract",),
                )
            )
        return tuple(plans)

    @pytest.mark.parametrize("raises", [False, True])
    def test_rejected_semantic_acceptance_rolls_back_every_file(
        self, mod_workspace: Path, *, raises: bool
    ) -> None:
        plans = self._plans(mod_workspace)
        failure = RuntimeError("semantic acceptance rejected")

        def reject() -> p.Result[bool]:
            for plan in plans:
                tm.that(plan.path.read_bytes(), eq=plan.desired_content)
            if raises:
                raise failure
            return r[bool].fail(str(failure))

        if raises:
            with pytest.raises(RuntimeError) as raised:
                publish_semantic_file_plans(
                    plans, repository_root=mod_workspace, validator=reject
                )
            tm.that(raised.value is failure, eq=True)
        else:
            tm.fail(
                publish_semantic_file_plans(
                    plans, repository_root=mod_workspace, validator=reject
                ),
                has=str(failure),
            )
        for plan in plans:
            tm.that(plan.path.read_bytes(), eq=plan.before.content)
        # Recovery leaves the same public operation available, not a poisoned journal.
        fresh = tuple(
            plan.model_copy(
                update={
                    "before": u.Cli.atomic_read_binary_file_state(
                        plan.path, required=True
                    ).unwrap()
                }
            )
            for plan in plans
        )
        tm.ok(publish_semantic_file_plans(fresh, repository_root=mod_workspace))

    @pytest.mark.parametrize("linked", [False, True])
    def test_changed_later_identity_prevents_earlier_publication(
        self, mod_workspace: Path, *, linked: bool
    ) -> None:
        first, second = self._plans(mod_workspace)
        if linked:
            actual = second.path.with_suffix(".actual")
            second.path.rename(actual)
            second.path.symlink_to(actual)
        else:
            u.Cli.atomic_write_text_file(second.path, 'value = "concurrent"\n').unwrap()
        observed = second.path.read_bytes()
        tm.fail(
            publish_semantic_file_plans((first, second), repository_root=mod_workspace)
        )
        tm.that(first.path.read_bytes(), eq=first.before.content)
        tm.that(second.path.read_bytes(), eq=observed)

    def test_generated_later_plan_rejects_authored_earlier_plan(
        self, mod_workspace: Path
    ) -> None:
        first, second = self._plans(mod_workspace)
        u.Cli.atomic_write_text_file(
            second.path, f'{c.Infra.AUTOGEN_HEADERS[0]}\nvalue = "before"\n'
        ).unwrap()
        generated = second.model_copy(
            update={
                "before": u.Cli.atomic_read_binary_file_state(
                    second.path, required=True
                ).unwrap()
            }
        )
        tm.fail(
            publish_semantic_file_plans(
                (first, generated), repository_root=mod_workspace
            ),
            has="canonical generator repair",
        )
        tm.that(first.path.read_bytes(), eq=first.before.content)

    def test_none_content_preserves_the_file(self, mod_workspace: Path) -> None:
        first, _ = self._plans(mod_workspace)
        noop = first.model_copy(update={"desired_content": None, "desired_mode": None})
        tm.that(
            tm.ok(publish_semantic_file_plans((noop,), repository_root=mod_workspace)),
            eq=(),
        )
        tm.that(first.path.read_bytes(), eq=first.before.content)

    def test_real_formatter_rejects_later_source_before_any_publication(
        self, mod_workspace: Path
    ) -> None:
        plans = self._plans(mod_workspace)
        edits = tuple(
            m.Infra.SemanticMigrationEdit(
                file_path=plan.path,
                original_source=plan.path.read_text(),
                updated_source='value="after"\n' if index == 0 else "value = (\n",
                changes=("formatter preflight",),
            )
            for index, plan in enumerate(plans)
        )
        with pytest.raises(RuntimeError, match="failed"):
            FlextInfraCodemodSemanticApply.apply_transaction_paths(mod_workspace, edits)
        for plan in plans:
            tm.that(plan.path.read_bytes(), eq=plan.before.content)

    def test_real_semantic_caller_commits_normalized_source_idempotently(
        self, mod_workspace: Path
    ) -> None:
        first, _ = self._plans(mod_workspace)
        edit = m.Infra.SemanticMigrationEdit(
            file_path=first.path,
            original_source=first.path.read_text(),
            updated_source='value="after"\n',
            changes=("semantic normalization",),
        )
        FlextInfraCodemodSemanticApply.apply_transaction_paths(mod_workspace, (edit,))
        published = first.path.read_text()
        tm.that(published, has="after")
        tm.that(published, lacks="before")
        repeated = edit.model_copy(
            update={"original_source": published, "updated_source": published}
        )
        FlextInfraCodemodSemanticApply.apply_transaction_paths(
            mod_workspace, (repeated,)
        )
        tm.that(first.path.read_text(), eq=published)
