"""Real-source regression evidence for staged semantic cutovers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_infra import infra
from flext_infra.codemod import FlextInfraCodemodSemanticApply
from tests import c, m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraSemanticPhaseContract:
    """Require planned and published sources to reach the same fixed point."""

    def test_annotations_and_nesting_complete_in_one_atomic_cutover(
        self, tmp_path: Path
    ) -> None:
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        # Publication runs through the codegen transaction, which coordinates
        # only inside an exact Git worktree root, exactly as in production.
        u.Tests.initialize_git_repo(root)
        owner = f"{u.derive_class_stem(root.name)}{c.Infra.FAMILY_SUFFIXES['c']}"
        path = package / "constants.py"
        u.Tests.write_lazy_init_namespace_module(
            path, class_name=owner, alias="c", extra_class_names=(f"{owner}Member",)
        )
        source = path.read_text(encoding="utf-8").replace(
            "from __future__ import annotations\n", ""
        )
        path.write_text(source, encoding="utf-8")
        # Semantic publication runs inside a codegen transaction, which only
        # coordinates through a real repository rooted at the project.
        u.Tests.initialize_git_repo(root)
        finding = m.Infra.ModScanFinding(
            rule_file="require-future-annotations.yml",
            rule_id="require-future-annotations",
            repository=root.name,
            file=path.relative_to(root),
            range={},
            text=source,
            actionable=False,
            classification=c.Infra.ModScanFindingClass.DETECTION_ONLY,
            payload={},
        )
        report = m.Infra.ModScanReport(
            findings=1,
            actionable=0,
            detection_only=1,
            non_actionable_with_fix=0,
            files=frozenset({path}),
            entries=(finding,),
        )
        tm.ok(FlextInfraCodemodSemanticApply.apply(root, report))
        published = path.read_text(encoding="utf-8")
        tm.that(published, has="from __future__ import annotations")
        tm.that(published, has=f"    class {owner}Member")
        tm.ok(FlextInfraCodemodSemanticApply.apply(root, report))
        tm.that(path.read_text(encoding="utf-8"), eq=published)

    def test_nesting_replans_proposed_sources_without_publishing(
        self, tmp_path: Path
    ) -> None:
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        owner = f"{u.derive_class_stem(root.name)}{c.Infra.FAMILY_SUFFIXES['c']}"
        path = package / "constants.py"
        u.Tests.write_lazy_init_namespace_module(
            path, class_name=owner, alias="c", extra_class_names=(f"{owner}Member",)
        )
        original = path.read_text(encoding="utf-8")
        nesting = c.Infra.SemanticCutoverPhase.CLASS_NESTING
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                nesting, rope_workspace=rope, sources={path: original}
            )
            tm.ok(planned)
            tm.that(len(planned.value), eq=1)
            tm.that(
                planned.value[0].changes, eq=(f"nested {owner}Member under {owner}",)
            )
            remaining = u.Infra.plan_semantic_cutover(
                nesting,
                rope_workspace=rope,
                sources={path: planned.value[0].updated_source},
            )
        tm.ok(remaining)
        tm.that(remaining.value, empty=True)
        tm.that(path.read_text(encoding="utf-8"), eq=original)

    def test_nesting_reports_every_module_without_an_owner_as_a_failure(
        self, tmp_path: Path
    ) -> None:
        """A module without its declared owner fails the plan instead of raising."""
        root, package = u.Tests.create_lazy_init_workspace(tmp_path)
        path = package / "models.py"
        source = "class FirstCandidate:\n    pass\n\nclass SecondCandidate:\n    pass\n"
        path.write_text(source, encoding="utf-8")
        with infra.rope_workspace(root) as rope:
            planned = u.Infra.plan_semantic_cutover(
                c.Infra.SemanticCutoverPhase.CLASS_NESTING,
                rope_workspace=rope,
                sources={path: source},
            )
        tm.fail(planned, has="requires exactly one declared module owner")
