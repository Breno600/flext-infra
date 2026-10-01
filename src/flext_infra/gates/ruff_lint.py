"""FLEXT ruff_lint quality gate.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, config, m, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraRuffLintGate(FlextInfraGate):
    """Ruff Lint quality gate."""

    gate_id: ClassVar[str] = c.Infra.LINT
    gate_name: ClassVar[str] = "Ruff Lint"
    # Why: the gate implements _build_fix_command (ruff check --fix); declaring
    # can_fix=False made workspace_check_gates skip it, so `make fix`
    # never applied a single lint fix and the command below was dead code.
    can_fix: ClassVar[bool] = True

    @override
    def _get_check_dirs(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.StrSequence:
        """Ruff always runs — never skip.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = ctx
        return self._existing_check_dirs(project_dir) or ["."]

    @override
    def _build_check_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        check_dirs: t.StrSequence,
    ) -> t.StrSequence:
        """Build check command.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = project_dir
        return self._lint_command(
            ctx,
            check_dirs,
            config.Infra.codegen.make.ruff.lint_check,
        )

    @override
    def _build_fix_command(
        self,
        project_dir: Path,
        ctx: m.Infra.GateContext,
        targets: t.StrSequence,
    ) -> t.StrSequence:
        """Build the explicit Ruff fix command.

        Returns:
            The resulting ``t.StrSequence``.

        """
        _ = project_dir
        return self._lint_command(ctx, targets, config.Infra.codegen.make.ruff.lint_fix)

    @override
    def fix(self, project_dir: Path, ctx: m.Infra.GateContext) -> m.Infra.GateExecution:
        """Apply Ruff's own fixes, then the declared recipe of each finding left.

        A recipe that creates a docstring runs before the recipes that extend
        one, since a new summary exposes the sections its function needs.
        Ruff re-reads the tree after each phase; a recipe-owned finding that
        survives both phases is a recipe defect and raises.

        Returns:
            The gate execution of Ruff's final pass.

        Raises:
            ValueError: If a recipe-owned finding survives every recipe phase.

        """
        execution = super().fix(project_dir, ctx)
        recipes = config.Infra.tooling.tools.ruff.lint.fix_recipes
        for phase in (
            frozenset({
                c.Infra.LintFixRecipe.SUMMARY_DOCSTRING,
                c.Infra.LintFixRecipe.COPYRIGHT_NOTICE,
            }),
            frozenset({
                c.Infra.LintFixRecipe.RETURNS_SECTION,
                c.Infra.LintFixRecipe.YIELDS_SECTION,
                c.Infra.LintFixRecipe.RAISES_SECTION,
            }),
        ):
            by_file: MutableMapping[Path, list[m.Infra.Issue]] = {}
            for issue in execution.issues:
                if recipes.get(issue.code) in phase:
                    by_file.setdefault(Path(issue.file), []).append(issue)
            if not by_file:
                continue
            with self._mutation_lease(project_dir):
                # Every repair is computed before the first write: a module
                # the recipes cannot place stops the phase with nothing written.
                planned: t.MutableSequenceOf[t.Pair[m.Cli.AtomicFileState, str]] = []
                for path, issues in sorted(by_file.items()):
                    before = u.Cli.atomic_read_binary_file_state(
                        path,
                        required=True,
                    ).unwrap()
                    planned.append((
                        before,
                        u.Infra.apply_lint_recipes(
                            (before.content or b"").decode(c.Cli.ENCODING_DEFAULT),
                            issues,
                            path=path,
                            recipes=recipes,
                            notice=u.Infra.copyright_notice(path.parent),
                        ),
                    ))
                for before, repaired in planned:
                    u.Cli.atomic_write_text_file_guarded(before, repaired).unwrap()
            execution = super().fix(project_dir, ctx)
        left = sorted(
            f"{issue.file}:{issue.line}:{issue.code}"
            for issue in execution.issues
            if issue.code in recipes
        )
        if left:
            msg = f"lint recipes left their own findings: {', '.join(left)}"
            raise ValueError(msg)
        return execution

    def _lint_command(
        self,
        ctx: m.Infra.GateContext,
        targets: t.StrSequence,
        mode_args: t.StrSequence,
    ) -> t.StrSequence:
        """Keep check and fix on the same Ruff lint invocation contract.

        Returns:
            The resulting ``t.StrSequence``.

        """
        return self._python_module_command(
            c.Infra.RUFF,
            c.Infra.VERB_CHECK,
            *targets,
            *ctx.ruff_args,
            *mode_args,
            "--output-format",
            c.Infra.OUTPUT_JSON,
            "--quiet",
        )

    @override
    def _parse_check_output(
        self,
        result: p.Cli.CommandOutput,
        project_dir: Path,
        ctx: m.Infra.GateContext,
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse check output.

        Returns:
            The resulting ``t.Pair[bool, t.SequenceOf[m.Infra.Issue]]``.

        """
        _ = project_dir, ctx
        issues: t.MutableSequenceOf[m.Infra.Issue] = []
        parsed_result = u.Cli.json_parse(result.stdout or "[]")
        empty_items: t.JsonValueList = []
        ruff_data = parsed_result.unwrap() if parsed_result.success else empty_items
        try:
            if isinstance(ruff_data, list):
                for entry in ruff_data:
                    if isinstance(entry, Mapping):
                        issues.append(
                            m.Infra.Issue(
                                file=u.Cli.json_pick_str(entry, "filename", "?"),
                                line=u.Cli.json_nested_int(entry, "location", "row"),
                                column=u.Cli.json_nested_int(
                                    entry,
                                    "location",
                                    "column",
                                ),
                                code=u.Cli.json_pick_str(entry, "code"),
                                message=u.Cli.json_pick_str(entry, "message"),
                            ),
                        )
        except c.EXC_VALIDATION_TYPE as err:
            issues.append(
                m.Infra.Issue(
                    file="<ruff-output>",
                    line=0,
                    column=0,
                    code="PARSE_ERROR",
                    message=f"Tool output parsing failed: {type(err).__name__}",
                    severity="ERROR",
                ),
            )
            return False, issues
        return self._finalize_parse_result(result, project_dir, issues, c.Infra.RUFF)


__all__: list[str] = ["FlextInfraRuffLintGate"]
