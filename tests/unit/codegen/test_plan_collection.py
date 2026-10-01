"""Public file-collection contracts with real source and destination states."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import m, u


class TestsFlextInfraPlanCollection:
    """Collection plans are reproducible and preserve curated documentation."""

    @staticmethod
    def _write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tm.ok(u.Cli.atomic_write_text_file(path, text))
        path.chmod(0o644)

    @staticmethod
    def _config() -> m.Infra.PlanCollectionConfig:
        return m.Infra.PlanCollectionConfig(
            enabled=True,
            canonical_dir=Path("docs/plans"),
            sources=(
                m.Infra.PlanCollectionSource(
                    id="fixture",
                    provider="files",
                    root=Path("input"),
                    adapter="files",
                    driver="fixture",
                    driver_version="1",
                    plan_globs=("*.md",),
                    publication="plan-artifacts",
                ),
            ),
        )

    def test_yaml_shaped_configuration_parses_at_the_typed_boundary(self) -> None:
        config = m.Infra.PlanCollectionConfig.model_validate({
            "enabled": True,
            "canonical_dir": "docs/plans",
            "sources": [
                {
                    "id": "kilo-local-plans",
                    "provider": "kilo",
                    "root": ".kilo/plans",
                    "adapter": "files",
                    "driver": "flext-infra-files",
                    "driver_version": "1",
                    "plan_globs": ["**/*.md"],
                    "exclude_globs": [],
                    "publication": "plan-artifacts",
                }
            ],
        })

        tm.that(config.canonical_dir, eq=Path("docs/plans"))
        tm.that(config.sources[0].root, eq=Path(".kilo/plans"))
        tm.that(config.sources[0].plan_globs, eq=("**/*.md",))
        tm.that(config.sources[0].exclude_globs, eq=())

    def test_disabled_configuration_has_no_publication_sources(self) -> None:
        config = m.Infra.PlanCollectionConfig(
            enabled=False, canonical_dir=Path("docs/plans")
        )

        tm.that(config.sources, eq=())
        disabled = {**self._config().model_dump(), "enabled": False}
        with pytest.raises(ValueError, match="disabled plan collection"):
            m.Infra.PlanCollectionConfig.model_validate(disabled)
        with pytest.raises(ValueError, match="requires at least one source"):
            m.Infra.PlanCollectionConfig(enabled=True, canonical_dir=Path("docs/plans"))

    def test_yaml_sequence_fields_reject_scalar_strings(self) -> None:
        with pytest.raises(ValueError, match="valid tuple"):
            m.Infra.PlanCollectionConfig.model_validate({
                "enabled": True,
                "canonical_dir": "docs/plans",
                "sources": "kilo-local-plans",
            })

    def test_plan_and_companion_are_snapshotted_without_writing(
        self, tmp_path: Path
    ) -> None:
        self._write(tmp_path / "input" / "design.md", "# Design\n")
        self._write(tmp_path / "input" / "design" / "research.md", "# Research\n")
        config = self._config()

        bundle = u.Infra.docs_collect_plan_files(tmp_path, config)

        tm.that(len(bundle.revisions), eq=1)
        tm.that(bundle.revisions[0].attachments, eq=("research.md",))
        captured = {state.path for state in bundle.source_states}
        tm.that(tmp_path / "input" / "design.md" in captured, eq=True)
        tm.that(tmp_path / "input" / "design" / "research.md" in captured, eq=True)
        tm.that((tmp_path / config.canonical_dir).exists(), eq=False)
        repeated = u.Infra.docs_collect_plan_files(tmp_path, config)
        tm.that(repeated.revisions[0].digest, eq=bundle.revisions[0].digest)

    def test_changed_attachment_creates_revision_without_overwriting_curated_plan(
        self, tmp_path: Path
    ) -> None:
        self._write(tmp_path / "input" / "design.md", "# Source\n")
        attachment = tmp_path / "input" / "design" / "research.md"
        self._write(attachment, "# Initial research\n")
        config = self._config()
        first = u.Infra.docs_collect_plan_files(tmp_path, config)
        canonical = tmp_path / config.canonical_dir / first.revisions[0].canonical_path
        curated = "# Reconciled with implementation evidence\n"
        self._write(canonical, curated)
        self._write(attachment, "# Additional research\n")

        second = u.Infra.docs_collect_plan_files(tmp_path, config)

        tm.that(second.revisions[0].identity, eq=first.revisions[0].identity)
        tm.that(second.revisions[0].digest != first.revisions[0].digest, eq=True)
        plan = next(item for item in second.files if item.path == canonical)
        tm.that(plan.desired_content, eq=curated.encode())
        tm.that(canonical.read_text(), eq=curated)

    def test_modified_generated_revision_is_repaired_from_unchanged_source(
        self, tmp_path: Path
    ) -> None:
        source = tmp_path / "input" / "design.md"
        self._write(source, "# Source\n")
        config = self._config()
        first = u.Infra.docs_collect_plan_files(tmp_path, config)
        for plan in first.files:
            assert plan.desired_content is not None
            self._write(plan.path, plan.desired_content.decode())
        revision = first.revisions[0]
        generated = (
            tmp_path
            / config.canonical_dir
            / revision.canonical_path.with_suffix("")
            / "incoming"
            / revision.digest
            / "plan.md"
        )
        self._write(generated, "# Hand-edited generated output\n")

        repaired = u.Infra.docs_collect_plan_files(tmp_path, config)

        plan = next(item for item in repaired.files if item.path == generated)
        tm.that(plan.desired_content, eq=source.read_bytes())
        tm.that(u.Infra.codegen_file_requires_effect(plan), eq=True)

    def test_disabled_collection_plans_manifest_owned_pruning(
        self, tmp_path: Path
    ) -> None:
        self._write(tmp_path / "input" / "design.md", "# Private source\n")
        published = u.Infra.docs_collect_plan_files(tmp_path, self._config())
        for plan in published.files:
            assert plan.desired_content is not None
            self._write(plan.path, plan.desired_content.decode())
        disabled = m.Infra.PlanCollectionConfig(
            enabled=False, canonical_dir=Path("docs/plans")
        )

        pruning = u.Infra.docs_collect_plan_files(tmp_path, disabled)

        tm.that(bool(pruning.files), eq=True)
        tm.that(pruning.revisions, eq=())
        tm.that(pruning.coverage, eq=())
        tm.that(pruning.inventories, eq=())
        tm.that(bool(pruning.prunable_directories), eq=True)
        for plan in pruning.files:
            tm.that(plan.desired_content, eq=None)
            tm.that(plan.path.is_relative_to(tmp_path / "docs" / "plans"), eq=True)

    def test_private_inventory_never_publishes_session_contents(
        self, tmp_path: Path
    ) -> None:
        private_session_text = "Private session text must stay at its source."
        session = tmp_path / "sessions" / "session.jsonl"
        self._write(session, private_session_text)
        config = m.Infra.PlanCollectionConfig(
            enabled=True,
            canonical_dir=Path("docs/plans"),
            sources=(
                m.Infra.PlanCollectionSource(
                    id="private",
                    provider="fixture",
                    root=Path("sessions"),
                    adapter="private-inventory",
                    driver="fixture",
                    driver_version="1",
                    plan_globs=("*.jsonl",),
                    publication="private",
                ),
            ),
        )

        bundle = u.Infra.docs_collect_plan_files(tmp_path, config)

        tm.that(bundle.coverage[0].status, eq="private-inventory")
        tm.that(bundle.coverage[0].private_paths, eq=(session,))
        tm.that(bundle.revisions, eq=())
        tm.that(any(state.path == session for state in bundle.source_states), eq=False)
        for plan in bundle.files:
            tm.that(
                private_session_text.encode() not in (plan.desired_content or b""),
                eq=True,
            )

    def test_missing_source_is_not_empty_coverage(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="input"):
            u.Infra.docs_collect_plan_files(tmp_path, self._config())

    def test_projection_is_explicit_and_carries_its_own_owner(
        self, tmp_path: Path
    ) -> None:
        self._write(tmp_path / "input" / "design.md", "# Design\n")
        projection = tmp_path / "home-docs" / "plans"
        config = self._config().model_copy(update={"projection_root": projection})

        bundle = u.Infra.docs_collect_plan_files(tmp_path, config)

        projected = tuple(item for item in bundle.files if item.project == projection)
        tm.that(bool(projected), eq=True)
        for item in projected:
            tm.that(item.path.is_relative_to(projection), eq=True)
        tm.that(projection.exists(), eq=False)

    def test_second_collection_ignores_unchanged_projection_but_detects_home_edit(
        self, tmp_path: Path
    ) -> None:
        projection = tmp_path / "home" / "plans"
        self._write(projection / "design.md", "# Original home plan\n")
        config = m.Infra.PlanCollectionConfig(
            enabled=True,
            canonical_dir=Path("docs/plans"),
            projection_root=projection,
            sources=(
                m.Infra.PlanCollectionSource(
                    id="home",
                    provider="files",
                    root=projection,
                    adapter="files",
                    driver="fixture",
                    driver_version="1",
                    plan_globs=("*.md",),
                    publication="plan-artifacts",
                ),
            ),
        )
        first = u.Infra.docs_collect_plan_files(tmp_path, config)
        for plan in first.files:
            assert plan.desired_content is not None
            self._write(plan.path, plan.desired_content.decode())
        u.Infra.verify_plan_collection_publication(tmp_path, config, first)

        second = u.Infra.docs_collect_plan_files(tmp_path, config)

        tm.that(second.revisions, eq=first.revisions)
        for plan in second.files:
            tm.that(u.Infra.codegen_file_requires_effect(plan), eq=False)
        imported = first.revisions[0]
        home_copy = projection / imported.canonical_path.name
        edited = "# Home amendment requiring semantic review\n"
        self._write(home_copy, edited)

        third = u.Infra.docs_collect_plan_files(tmp_path, config)

        tm.that(len(third.revisions), eq=1)
        tm.that(third.revisions[0].identity, eq=imported.identity)
        tm.that(third.revisions[0].digest != imported.digest, eq=True)
        tm.that(
            any(item.desired_content == edited.encode() for item in third.files),
            eq=True,
        )
        tm.that(
            (tmp_path / config.canonical_dir / imported.canonical_path).read_text(),
            eq="# Original home plan\n",
        )
        for plan in third.files:
            assert plan.desired_content is not None
            self._write(plan.path, plan.desired_content.decode())
        fourth = u.Infra.docs_collect_plan_files(tmp_path, config)
        tm.that(fourth.revisions, eq=third.revisions)
        for plan in fourth.files:
            tm.that(u.Infra.codegen_file_requires_effect(plan), eq=False)

    def test_source_topology_change_fails_publication_preflight(
        self, tmp_path: Path
    ) -> None:
        self._write(tmp_path / "input" / "design.md", "# Design\n")
        config = self._config()
        bundle = u.Infra.docs_collect_plan_files(tmp_path, config)
        self._write(tmp_path / "input" / "additional.md", "# Additional\n")

        with pytest.raises(ValueError, match="topology changed"):
            u.Infra.verify_plan_collection_sources(tmp_path, config, bundle)

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("2026-09-14T17:20:28Z", "2026-09-14T17:20:28Z"),
            ("2026-09-14T14:20:28-03:00", "2026-09-14T17:20:28Z"),
            ("2026-09-14", "2026-09-14"),
            ("2026-09-14T14:20:28", "2026-09-14T14:20:28"),
        ],
    )
    @pytest.mark.parametrize("newline", ["\n", "\r\n"])
    @pytest.mark.parametrize("prefix", ["", "\ufeff"])
    def test_native_yaml_timestamp_preserves_precision(
        self, tmp_path: Path, value: str, expected: str, newline: str, prefix: str
    ) -> None:
        self._write(
            tmp_path / "input" / "design.md",
            prefix
            + newline.join((
                "---",
                f"source_updated_at: {value}",
                "---",
                "# Design",
                "",
            )),
        )

        bundle = u.Infra.docs_collect_plan_files(tmp_path, self._config())

        tm.that(bundle.revisions[0].source_updated_at, eq=expected)
        tm.that(bundle.revisions[0].source_updated_at_original is not None, eq=True)
        if value in {"2026-09-14", "2026-09-14T14:20:28"}:
            tm.that(bundle.revisions[0].source_updated_at_utc, eq=None)

    def test_new_companion_file_changes_source_topology(self, tmp_path: Path) -> None:
        self._write(tmp_path / "input" / "design.md", "# Design\n")
        config = self._config()
        bundle = u.Infra.docs_collect_plan_files(tmp_path, config)
        self._write(tmp_path / "input" / "design" / "new.md", "# Research\n")

        with pytest.raises(ValueError, match="topology changed"):
            u.Infra.verify_plan_collection_sources(tmp_path, config, bundle)

    def test_projected_attachment_edit_is_collected_when_plan_is_unchanged(
        self, tmp_path: Path
    ) -> None:
        projection = tmp_path / "home" / "plans"
        self._write(projection / "design.md", "# Original\n")
        self._write(projection / "design" / "research.md", "# Research\n")
        config = m.Infra.PlanCollectionConfig(
            enabled=True,
            canonical_dir=Path("docs/plans"),
            projection_root=projection,
            sources=(
                m.Infra.PlanCollectionSource(
                    id="home",
                    provider="files",
                    root=projection,
                    adapter="files",
                    driver="fixture",
                    driver_version="1",
                    plan_globs=("*.md",),
                    publication="plan-artifacts",
                ),
            ),
        )
        initial = u.Infra.docs_collect_plan_files(tmp_path, config)
        for plan in initial.files:
            assert plan.desired_content is not None
            self._write(plan.path, plan.desired_content.decode())
        revision = initial.revisions[0]
        attachment = (
            projection
            / revision.canonical_path.stem
            / "incoming"
            / revision.digest
            / "attachments"
            / "research.md"
        )
        amendment = "# Updated projected research\n"
        self._write(attachment, amendment)

        changed = u.Infra.docs_collect_plan_files(tmp_path, config)

        tm.that(changed.revisions[0].identity, eq=revision.identity)
        tm.that(changed.revisions[0].digest != revision.digest, eq=True)
        tm.that(
            any(plan.desired_content == amendment.encode() for plan in changed.files),
            eq=True,
        )
        u.Infra.verify_plan_collection_sources(tmp_path, config, changed)
        for plan in changed.files:
            assert plan.desired_content is not None
            self._write(plan.path, plan.desired_content.decode())
        u.Infra.verify_plan_collection_publication(tmp_path, config, changed)
        stable = u.Infra.docs_collect_plan_files(tmp_path, config)
        tm.that(stable.revisions, eq=changed.revisions)
        for plan in stable.files:
            tm.that(u.Infra.codegen_file_requires_effect(plan), eq=False)

    def test_concurrent_canonical_edit_rejects_stale_plan(self, tmp_path: Path) -> None:
        self._write(tmp_path / "input" / "design.md", "# Source\n")
        config = self._config()
        first = u.Infra.docs_collect_plan_files(tmp_path, config)
        canonical = tmp_path / config.canonical_dir / first.revisions[0].canonical_path
        self._write(canonical, "# Curated\n")
        pending = u.Infra.docs_collect_plan_files(tmp_path, config)
        self._write(canonical, "# Concurrent curated amendment\n")

        with pytest.raises(ValueError, match="source changed"):
            u.Infra.verify_plan_collection_sources(tmp_path, config, pending)

    def test_corpus_relocation_preserves_identity_and_exact_receipts(
        self, tmp_path: Path
    ) -> None:
        first_root, next_root = tmp_path / "first", tmp_path / "next"
        config = self._config()
        for root in (first_root, next_root):
            self._write(root / "input" / "design.md", "# Portable source\n")
        first = u.Infra.docs_collect_plan_files(first_root, config)
        for plan in first.files:
            assert plan.desired_content is not None
            self._write(
                next_root / plan.path.relative_to(first_root),
                plan.desired_content.decode(),
            )

        relocated = u.Infra.docs_collect_plan_files(next_root, config)

        tm.that(relocated.revisions, eq=first.revisions)
        for revision in relocated.revisions:
            tm.that(revision.canonical_path.is_absolute(), eq=False)
            tm.that(revision.source_path.is_absolute(), eq=False)
        for plan in relocated.files:
            tm.that(u.Infra.codegen_file_requires_effect(plan), eq=False)
            tm.that(
                str(first_root).encode() not in (plan.desired_content or b""), eq=True
            )
