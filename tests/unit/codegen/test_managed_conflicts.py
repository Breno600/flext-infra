"""Owner-declared managed document conflict recovery tests."""

from __future__ import annotations

from flext_tests import tm

from flext_infra import c, u


class TestsFlextInfraManagedConflictRecovery:
    """Prove conflict recovery remains bounded by the document SSOT."""

    def test_every_table_the_conform_pipeline_writes_is_recoverable(self) -> None:
        """Whatever the owner writes, the owner must be able to recover.

        The table is named by the same constant the conform pipeline writes
        through, so the writer and this declaration cannot drift. They did
        drift once: the pipeline gained a table while the declaration did not,
        and absorbing the integration base then dead-ended the superproject
        merge on the owner's own output.
        """
        pyproject = tm.ok(u.Infra.pyproject_managed_file())

        tm.that(
            u.Infra.toml_section_is_owned(
                u.Cli.toml_dot_path(*c.Infra.CONFORM_NAMESPACE_TABLE),
                pyproject.conflict_sections,
            ),
            eq=True,
        )

    def test_every_generated_pyproject_section_declares_recovery(self) -> None:
        """A section the owner renders must be recoverable, or a merge dead-ends.

        `per-file-ignores` is rendered from `tooling.yaml` exactly like the
        pytest and uv sections. Without the declaration, absorbing an
        integration base that still carries the previous lint projection left
        the superproject merge unresolvable through the canonical surface.
        """
        pyproject = tm.ok(u.Infra.pyproject_managed_file())
        tm.that("tool.uv" in pyproject.conflict_sections, eq=True)
        tm.that("build-system" in pyproject.conflict_sections, eq=True)
        tm.that(pyproject.preserve_project_keys, empty=False)
        tm.that(pyproject.overwrite_project_keys, empty=False)
        tm.that(
            set(pyproject.overwrite_project_keys).isdisjoint(
                pyproject.preserve_project_keys
            ),
            eq=True,
        )

    def test_recovers_the_lint_policy_section(self) -> None:
        """Keep the owner's current lint projection over an absorbed base."""
        content = (
            "[tool.ruff.lint.per-file-ignores]\n"
            "<<<<<<< HEAD\n"
            '"**/__init__.py" = ["unused-import"]\n'
            "=======\n"
            '"**/.vulture_whitelist.py" = ["ALL"]\n'
            ">>>>>>> origin/0.12.0-dev\n"
        )

        recovered = tm.ok(
            u.Infra.recover_managed_toml(
                content, conflict_sections=("tool.ruff.lint.per-file-ignores",)
            )
        )

        tm.that(
            recovered,
            eq=(
                "[tool.ruff.lint.per-file-ignores]\n"
                '"**/__init__.py" = ["unused-import"]\n'
            ),
        )

    def test_recovers_only_configured_toml_section(self) -> None:
        """Keep the current projection for a configured owner section."""
        content = (
            "[project]\n"
            'name = "fixture"\n'
            "\n"
            "[tool.uv]\n"
            "<<<<<<< HEAD\n"
            'link-mode = "copy"\n'
            "=======\n"
            'link-mode = "clone"\n'
            'required-version = "==0.11.32"\n'
            ">>>>>>> origin/0.12.0-dev\n"
            "\n"
            "[tool.ruff]\n"
            "line-length = 100\n"
        )

        recovered: str = tm.ok(
            u.Infra.recover_managed_toml(content, conflict_sections=("tool.uv",))
        )

        tm.that(
            recovered,
            eq=(
                "[project]\n"
                'name = "fixture"\n'
                "\n"
                "[tool.uv]\n"
                'link-mode = "copy"\n'
                "\n"
                "[tool.ruff]\n"
                "line-length = 100\n"
            ),
        )

    def test_rejects_conflict_outside_configured_toml_section(self) -> None:
        """Fail closed when the canonical owner did not declare the section."""
        content = (
            "[project]\n"
            "<<<<<<< HEAD\n"
            'name = "current"\n'
            "=======\n"
            'name = "incoming"\n'
            ">>>>>>> origin/0.12.0-dev\n"
        )

        result = u.Infra.recover_managed_toml(content, conflict_sections=("tool.uv",))

        tm.fail(result, has="outside owner-declared TOML sections: project")

    def test_preserves_clean_document_bytes(self) -> None:
        """Leave documents without conflict markers byte-identical."""
        content = '[tool.uv]\nlink-mode = "copy"\n'

        recovered: str = tm.ok(
            u.Infra.recover_managed_toml(content, conflict_sections=("tool.uv",))
        )

        tm.that(recovered, eq=content)
