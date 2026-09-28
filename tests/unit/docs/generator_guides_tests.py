"""Root-owned guide projections through the public immutable docs planner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_tests import tm

from flext_core import r
from flext_infra import c
from flext_infra.docs.generator import FlextInfraDocGenerator
from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraDocsGeneratorGuides:
    """Root-owned guide projections through the public immutable docs planner."""

    def test_root_guide_change_reaches_member_and_one_pass_fixed_point(
        self, tmp_path: Path
    ) -> None:
        """Render current root bytes and the desired index without a second pass."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path, project_names=("flext-a",), selected_projects=["flext-a"]
        )
        source = workspace / "docs/guides/operator.md"
        source.write_text("# Operator\n\nFirst body.\n", encoding="utf-8")
        destination = workspace / "flext-a/docs/guides/operator.md"
        plans = u.Tests.plan_docs_bundle(generator)
        guide_plan = next(plan for plan in plans if plan.path == destination)
        tm.that(guide_plan.desired_content or b"", has=b"First body.")
        tm.that(guide_plan.owner, eq="docs")
        snapshot = next(
            state for state in guide_plan.source_states if state.path == source
        )
        tm.that(snapshot.content, eq=source.read_bytes())
        tm.that(snapshot.parent_device is not None, eq=True)
        tm.that(snapshot.parent_inode is not None, eq=True)
        tm.that(destination.exists(), eq=False)
        tm.ok(
            u.Tests.materialize_codegen_plans(
                r[tuple[m.Infra.CodegenFilePlan, ...]].ok(plans)
            )
        )
        index = destination.parent / "README.md"
        tm.that(index.read_text(encoding="utf-8"), has="(operator.md)")
        tm.that(
            any(
                u.Infra.codegen_file_requires_effect(plan)
                for plan in u.Tests.plan_docs_bundle(generator)
            ),
            eq=False,
        )

        source.write_text("# Operator\n\nChanged root body.\n", encoding="utf-8")
        changed = u.Tests.publish_docs_bundle(generator)
        tm.that(
            any(
                plan.path == destination and u.Infra.codegen_file_requires_effect(plan)
                for plan in changed
            ),
            eq=True,
        )
        tm.that(destination.read_text(encoding="utf-8"), has="Changed root body.")
        tm.that(destination.read_text(encoding="utf-8"), lacks="First body.")
        tm.that(index.read_text(encoding="utf-8"), has="(operator.md)")
        fixed_point = u.Tests.plan_docs_bundle(generator)
        tm.that(
            any(u.Infra.codegen_file_requires_effect(plan) for plan in fixed_point),
            eq=False,
        )
        tm.that(
            source.read_text(encoding="utf-8"), eq="# Operator\n\nChanged root body.\n"
        )

    def test_removed_root_guide_plans_only_exact_owned_member_deletion(
        self, tmp_path: Path
    ) -> None:
        """Retain custom and differently owned guides; journal only our stale target."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path, project_names=("flext-a",), selected_projects=["flext-a"]
        )
        source = workspace / "docs/guides/operator.md"
        source.write_text("# Operator\n\nBody.\n", encoding="utf-8")
        _ = u.Tests.publish_docs_bundle(generator)
        guides = workspace / "flext-a/docs/guides"
        custom = guides / "custom.md"
        custom.write_text("# Custom\n\nKeep.\n", encoding="utf-8")
        foreign = guides / "foreign.md"
        foreign.write_text(
            "<!-- AUTO-GENERATED FILE by another owner -->\n", encoding="utf-8"
        )
        mismatched = guides / "mismatched.md"
        mismatched.write_bytes((guides / "operator.md").read_bytes())
        retained = {path: path.read_bytes() for path in (custom, foreign, mismatched)}
        source.unlink()

        plans = u.Tests.plan_docs_bundle(generator)
        deleted = next(plan for plan in plans if plan.path == guides / "operator.md")
        tm.that(deleted.desired_content, eq=None)
        tm.that(deleted.desired_mode, eq=None)
        tm.that(
            any(state.path == deleted.path for state in deleted.source_states), eq=True
        )
        tm.that(any(plan.path in retained for plan in plans), eq=False)
        tm.that(deleted.path.exists(), eq=True)
        tm.ok(
            u.Tests.materialize_codegen_plans(
                r[tuple[m.Infra.CodegenFilePlan, ...]].ok(plans)
            )
        )
        tm.that(deleted.path.exists(), eq=False)
        tm.that({path: path.read_bytes() for path in retained}, eq=retained)
        index = (guides / "README.md").read_text(encoding="utf-8")
        tm.that(index, lacks="(operator.md)")
        tm.that(index, has="(custom.md)")
        tm.that(
            any(
                u.Infra.codegen_file_requires_effect(plan)
                for plan in u.Tests.plan_docs_bundle(generator)
            ),
            eq=False,
        )

    def test_root_guide_cannot_overwrite_protected_custom_collision(
        self, tmp_path: Path
    ) -> None:
        """Reject a filename collision without adopting or overwriting custom content."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path, project_names=("flext-a",), selected_projects=["flext-a"]
        )
        source = workspace / "docs/guides/operator.md"
        source.write_text("# Canonical\n", encoding="utf-8")
        destination = workspace / "flext-a/docs/guides/operator.md"
        destination.parent.mkdir(parents=True)
        destination.write_text("# Custom\n", encoding="utf-8")

        prepared = generator.prepare_bundle()

        tm.fail(prepared)
        tm.that(prepared.error or "", has="protected custom guide")
        tm.that(destination.read_text(encoding="utf-8"), eq="# Custom\n")

    def test_previous_generated_guide_header_is_adopted_by_current_owner(
        self, tmp_path: Path
    ) -> None:
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path, project_names=("flext-a",), selected_projects=["flext-a"]
        )
        source = workspace / "docs/guides/operator.md"
        source.write_text("# Operator\n\nCurrent.\n", encoding="utf-8")
        destination = workspace / "flext-a/docs/guides/operator.md"
        destination.parent.mkdir(parents=True)
        destination.write_text(
            "<!-- AUTO-GENERATED FILE — regenerate through `make gen` from the workspace root. -->\n"
            "<!-- Source of truth: `docs/guides/operator.md`; adjust that source, never this projection. -->\n\n"
            "# flext-a - Operator\n\n> Project profile: `flext-a`\n\nPrevious.\n",
            encoding="utf-8",
        )

        plan = next(
            item
            for item in u.Tests.plan_docs_bundle(generator)
            if item.path == destination
        )

        tm.that(
            plan.desired_content or b"",
            has=b"`<workspace-root>/docs/guides/operator.md`",
        )

    def test_legacy_generated_guide_header_is_adopted_by_current_owner(
        self, tmp_path: Path
    ) -> None:
        """Adopt only the historical generator marker, never unmarked custom text."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path, project_names=("flext-a",), selected_projects=["flext-a"]
        )
        source = workspace / "docs/guides/operator.md"
        source.write_text("# Operator\n\nCurrent.\n", encoding="utf-8")
        destination = workspace / "flext-a/docs/guides/operator.md"
        destination.parent.mkdir(parents=True)
        destination.write_text(
            "<!-- AUTO-GENERATED FILE — regenerate through `make gen` from the workspace root. -->\n"
            "<!-- Source of truth: `docs/guides/operator.md`; adjust that source, never this projection. -->\n\n"
            "# flext-a - Operator\n\n> Project profile: `flext-a`\n\nPrevious.\n",
            encoding="utf-8",
        )

        plan = next(
            item
            for item in u.Tests.plan_docs_bundle(generator)
            if item.path == destination
        )

        tm.that(plan.desired_content or b"", has=b"Current.")

    def test_root_guide_snapshot_change_rejects_prepared_bundle(
        self, tmp_path: Path
    ) -> None:
        """Keep root inputs behind the same source barrier as destination ownership."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path, project_names=("flext-a",), selected_projects=["flext-a"]
        )
        source = workspace / "docs/guides/operator.md"
        source.write_text("# Operator\n", encoding="utf-8")
        bundle = u.Tests.prepare_docs_bundle(generator)
        source.write_text("# Changed\n", encoding="utf-8")

        planned = generator.plan_files(bundle)

        tm.fail(planned)
        tm.that(planned.error or "", has=c.Infra.DOCS_SOURCE_STATE_RACE_MARKER)
        tm.that((workspace / "flext-a/docs/guides/operator.md").exists(), eq=False)

    def test_guide_parent_identity_change_rejects_prepared_bundle(
        self, tmp_path: Path
    ) -> None:
        """Replacing the root guide parent must not preserve authority via same bytes."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path, project_names=("flext-a",), selected_projects=["flext-a"]
        )
        source = workspace / "docs/guides/operator.md"
        source.write_text("# Operator\n", encoding="utf-8")
        bundle = u.Tests.prepare_docs_bundle(generator)
        moved = workspace / "docs/displaced-guides"
        source.parent.rename(moved)
        source.parent.mkdir()
        (moved / source.name).rename(source)

        planned = generator.plan_files(bundle)

        tm.fail(planned)
        tm.that(planned.error or "", has=c.Infra.DOCS_SOURCE_STATE_RACE_MARKER)

    def test_stale_guide_ownership_change_rejects_prepared_delete(
        self, tmp_path: Path
    ) -> None:
        """Do not delete a member guide converted to custom content after preparation."""
        workspace, generator = u.Tests.docs_workspace_generator(
            tmp_path, project_names=("flext-a",), selected_projects=["flext-a"]
        )
        source = workspace / "docs/guides/operator.md"
        source.write_text("# Operator\n", encoding="utf-8")
        _ = u.Tests.publish_docs_bundle(generator)
        source.unlink()
        bundle = u.Tests.prepare_docs_bundle(generator)
        destination = workspace / "flext-a/docs/guides/operator.md"
        destination.write_text("# Now custom\n", encoding="utf-8")

        planned = generator.plan_files(bundle)

        tm.fail(planned)
        tm.that(planned.error or "", has=c.Infra.DOCS_SOURCE_STATE_RACE_MARKER)
        tm.that(destination.read_text(encoding="utf-8"), eq="# Now custom\n")

    def test_standalone_guides_never_read_parent_or_project_their_own_heading(
        self, tmp_path: Path
    ) -> None:
        """Standalone has no implicit umbrella context, even beside root guides."""
        workspace = u.Tests.create_docs_workspace(tmp_path, project_names=("flext-a",))
        (workspace / "docs/guides/operator.md").write_text(
            "# Parent\n", encoding="utf-8"
        )
        project = workspace / "flext-a"
        guide = project / "docs/guides/operator.md"
        guide.parent.mkdir(parents=True)
        guide.write_text("# Local\n\nKeep local content.\n", encoding="utf-8")
        generator = FlextInfraDocGenerator(repository_root=project)

        first = u.Tests.plan_docs_bundle(generator)
        second = u.Tests.plan_docs_bundle(generator)

        tm.that(any(plan.path == guide for plan in (*first, *second)), eq=False)
        tm.that(
            guide.read_text(encoding="utf-8"), eq="# Local\n\nKeep local content.\n"
        )
        tm.that(
            any(
                state.path == workspace / "docs/guides/operator.md"
                for plan in second
                for state in plan.source_states
            ),
            eq=False,
        )
