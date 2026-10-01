"""FLEXT ruff_lint quality gate."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, ClassVar, override

from flext_infra import c, config, m, u
from flext_infra.gates.base_gate import FlextInfraGate

if TYPE_CHECKING:
    from pathlib import Path

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
        self, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.StrSequence:
        """Ruff always runs — never skip."""
        _ = ctx
        return self._existing_check_dirs(project_dir) or ["."]

    @override
    def _build_check_command(
        self, project_dir: Path, ctx: m.Infra.GateContext, check_dirs: t.StrSequence
    ) -> t.StrSequence:
        """Build check command."""
        _ = project_dir
        return self._lint_command(
            ctx, check_dirs, config.Infra.codegen.make.ruff.lint_check
        )

    @override
    def _build_fix_command(
        self, project_dir: Path, ctx: m.Infra.GateContext, targets: t.StrSequence
    ) -> t.StrSequence:
        """Build the explicit Ruff fix command."""
        _ = project_dir
        return self._lint_command(ctx, targets, config.Infra.codegen.make.ruff.lint_fix)

    def _lint_command(
        self, ctx: m.Infra.GateContext, targets: t.StrSequence, mode_args: t.StrSequence
    ) -> t.StrSequence:
        """Keep check and fix on the same Ruff lint invocation contract."""
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
        self, result: p.Cli.CommandOutput, project_dir: Path, ctx: m.Infra.GateContext
    ) -> t.Pair[bool, t.SequenceOf[m.Infra.Issue]]:
        """Parse check output."""
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
                                    entry, "location", "column"
                                ),
                                code=u.Cli.json_pick_str(entry, "code"),
                                message=u.Cli.json_pick_str(entry, "message"),
                            )
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
                )
            )
            return False, issues
        return self._finalize_parse_result(result, project_dir, issues, c.Infra.RUFF)


__all__: list[str] = ["FlextInfraRuffLintGate"]
