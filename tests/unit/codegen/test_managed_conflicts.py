"""Owner-declared managed document conflict recovery tests."""

from __future__ import annotations

from flext_infra import config
from flext_infra.codegen.managed_conflicts import FlextInfraCodegenManagedConflicts
from flext_tests import tm


class TestsFlextInfraCodegenManagedConflicts:
    """Prove conflict recovery remains bounded by the document SSOT."""

    def test_every_generated_pyproject_section_declares_recovery(self) -> None:
        """A section the owner renders must be recoverable, or a merge dead-ends.

        `per-file-ignores` is rendered from `tooling.yaml` exactly like the
        pytest and uv sections. Without the declaration, absorbing an
        integration base that still carries the previous lint projection left
        the superproject merge unresolvable through the canonical surface.
        """
        managed = config.Infra.codegen.managed_files
        pyproject = next(
            spec for spec in managed if spec.path.as_posix() == "pyproject.toml"
        )

        tm.that(
            set(pyproject.conflict_sections),
            eq={
                "tool.pytest.ini_options",
                "tool.uv",
                "tool.ruff.lint.per-file-ignores",
            },
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
            FlextInfraCodegenManagedConflicts.recover_toml(
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

        recovered = tm.ok(
            FlextInfraCodegenManagedConflicts.recover_toml(
                content, conflict_sections=("tool.uv",)
            )
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

        result = FlextInfraCodegenManagedConflicts.recover_toml(
            content, conflict_sections=("tool.uv",)
        )

        tm.fail(result, has="outside owner-declared TOML sections: project")

    def test_preserves_clean_document_bytes(self) -> None:
        """Leave documents without conflict markers byte-identical."""
        content = '[tool.uv]\nlink-mode = "copy"\n'

        recovered = tm.ok(
            FlextInfraCodegenManagedConflicts.recover_toml(
                content, conflict_sections=("tool.uv",)
            )
        )

        tm.that(recovered, eq=content)
