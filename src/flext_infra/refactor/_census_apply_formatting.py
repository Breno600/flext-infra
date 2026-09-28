"""Post-apply formatting helpers for refactor census fixes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_infra import c, config, p, u

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path


class FlextInfraRefactorCensusApplyFormattingMixin:
    """Mixin for normalizing files touched by census apply operations."""

    @staticmethod
    def normalize_source(
        repository_root: Path, path: Path, source: str
    ) -> p.Result[str]:
        """Normalize staged source with the destination's real Ruff configuration."""
        checked = u.Cli.run(
            [
                "ruff",
                "check",
                *config.Infra.codegen.make.ruff.lint_fix,
                "--select",
                "I,W",
                "--stdin-filename",
                str(path),
                "-",
            ],
            cwd=repository_root,
            input_data=source,
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        return checked.flat_map(
            lambda output: u.Cli.run(
                [
                    "ruff",
                    "format",
                    *config.Infra.codegen.make.ruff.format_apply,
                    "--stdin-filename",
                    str(path),
                    "-",
                ],
                cwd=repository_root,
                input_data=output.stdout,
                timeout=c.Infra.TIMEOUT_SHORT,
            ).map(lambda formatted: formatted.stdout)
        )

    @staticmethod
    def normalize_touched_files(paths: Iterable[Path]) -> None:
        """Normalize import order and whitespace on files an apply touched.

        Two apply paths need this and there is one owner: the census apply
        cascade and the semantic cutover publication. It is public because
        it is consumed across surfaces, not because it is a helper.
        """
        existing = sorted({str(path) for path in paths if path.is_file()})
        if not existing:
            return
        check_result = u.Cli.run_checked(
            [
                "ruff",
                "check",
                *config.Infra.codegen.make.ruff.lint_fix,
                "--select",
                "I,W",
                *existing,
            ],
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        if check_result.failure:
            msg = (
                "ruff check --fix failed after refactor apply: "
                f"{check_result.error or 'unknown error'}; files={existing!r}"
            )
            raise RuntimeError(msg)
        format_result = u.Cli.run_checked(
            ["ruff", "format", *config.Infra.codegen.make.ruff.format_apply, *existing],
            timeout=c.Infra.TIMEOUT_SHORT,
        )
        if format_result.failure:
            msg = (
                "ruff format failed after refactor apply: "
                f"{format_result.error or 'unknown error'}; files={existing!r}"
            )
            raise RuntimeError(msg)


__all__: list[str] = ["FlextInfraRefactorCensusApplyFormattingMixin"]
