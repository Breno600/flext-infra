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
        one, since a new summary exposes the sections its function needs; the
        static-method recipe edits only signatures and decorators, so it runs
        in that first phase.
        Ruff re-reads the tree after each phase; a recipe-owned finding that
        survives both phases is a recipe defect and raises.

        Returns:
            The gate execution of Ruff's final pass.

        """
        execution = super().fix(project_dir, ctx)
        recipes = config.Infra.tooling.tools.ruff.lint.fix_recipes
        overridden = self._project_overrides(project_dir, execution.issues, recipes)
        for phase in (
            frozenset({
                c.Infra.LintFixRecipe.SUMMARY_DOCSTRING,
                c.Infra.LintFixRecipe.COPYRIGHT_NOTICE,
                c.Infra.LintFixRecipe.STATIC_METHOD,
            }),
            frozenset({
                c.Infra.LintFixRecipe.RETURNS_SECTION,
                c.Infra.LintFixRecipe.YIELDS_SECTION,
                c.Infra.LintFixRecipe.RAISES_SECTION,
            }),
            # The staticmethod rewrite rewrites the def itself: it runs last,
            # alone, so its findings never share a phase with docstring edits
            # computed against the pre-rewrite positions.
            frozenset({c.Infra.LintFixRecipe.NO_SELF_USE}),
        ):
<<<<<<< HEAD
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
                    repaired, left_issues = u.Infra.apply_lint_recipes(
=======
            hooks = self._overridden_hooks(execution.issues, recipes, overridden)
            by_file = self._phase_findings(execution.issues, recipes, phase, hooks)
            if by_file:
                self._apply_phase(project_dir, by_file, recipes)
                execution = super().fix(project_dir, ctx)
        self._reject_recipe_residue(
            execution.issues,
            recipes,
            self._overridden_hooks(execution.issues, recipes, overridden),
        )
        return execution

    def _project_overrides(
        self,
        project_dir: Path,
        issues: t.SequenceOf[m.Infra.Issue],
        recipes: t.MappingKV[str, c.Infra.LintFixRecipe],
    ) -> frozenset[t.Pair[str, str]]:
        """Index the methods a subclass of this project redefines.

        The index exists only for the static-method recipe, so a run without
        its findings builds none. A module Ruff reports as ``invalid-syntax``
        declares no class Ruff could judge and stays out of the index; its
        finding remains for its owner.

        Returns:
            The overridden ``(class name, method name)`` pairs.

        """
        if not any(
            recipes.get(issue.code) is c.Infra.LintFixRecipe.STATIC_METHOD
            for issue in issues
        ):
            return frozenset()
        unparsable = {
            Path(issue.file).resolve()
            for issue in issues
            if issue.code == c.Infra.RUFF_INVALID_SYNTAX
        }
        return u.Infra.overridden_methods(
            tuple(
                path.read_text(encoding=c.Cli.ENCODING_DEFAULT)
                for directory in self._existing_check_dirs(project_dir)
                for path in u.Infra.iter_directory_python_files(
                    project_dir / directory,
                )
                if path.resolve() not in unparsable
            ),
        )

    @staticmethod
    def _phase_findings(
        issues: t.SequenceOf[m.Infra.Issue],
        recipes: t.MappingKV[str, c.Infra.LintFixRecipe],
        phase: frozenset[c.Infra.LintFixRecipe],
        hooks: t.StrSequence,
    ) -> t.MappingKV[Path, t.SequenceOf[m.Infra.Issue]]:
        """Group by file the findings one recipe phase repairs.

        Returns:
            The phase's findings per module, overridden hooks excluded.

        """
        by_file: MutableMapping[Path, list[m.Infra.Issue]] = {}
        for issue in issues:
            if (
                recipes.get(issue.code) in phase
                and f"{issue.file}:{issue.line}:{issue.code}" not in hooks
            ):
                by_file.setdefault(Path(issue.file), []).append(issue)
        return by_file

    def _apply_phase(
        self,
        project_dir: Path,
        by_file: t.MappingKV[Path, t.SequenceOf[m.Infra.Issue]],
        recipes: t.MappingKV[str, c.Infra.LintFixRecipe],
    ) -> None:
        """Repair every module of one phase, computing all before any write."""
        with self._mutation_lease(project_dir):
            # A module the recipes cannot place stops the phase with nothing
            # written.
            planned: t.MutableSequenceOf[t.Pair[m.Cli.AtomicFileState, str]] = []
            for path, issues in sorted(by_file.items()):
                before = u.Cli.atomic_read_binary_file_state(
                    path,
                    required=True,
                ).unwrap()
                planned.append((
                    before,
                    u.Infra.apply_lint_recipes(
>>>>>>> origin/0.12.0-dev
                        (before.content or b"").decode(c.Cli.ENCODING_DEFAULT),
                        issues,
                        path=path,
                        recipes=recipes,
                        notice=u.Infra.copyright_notice(path.parent),
<<<<<<< HEAD
                    )
                    planned.append((before, repaired, left_issues))
                for before, repaired, _ in planned:
                    u.Cli.atomic_write_text_file_guarded(before, repaired).unwrap()
            execution = super().fix(project_dir, ctx)
=======
                    ),
                ))
            for before, repaired in planned:
                u.Cli.atomic_write_text_file_guarded(before, repaired).unwrap()

    @staticmethod
    def _reject_recipe_residue(
        issues: t.SequenceOf[m.Infra.Issue],
        recipes: t.MappingKV[str, c.Infra.LintFixRecipe],
        hooks: t.StrSequence,
    ) -> None:
        """Report overridden hooks and raise on any other recipe-owned finding.

        Raises:
            ValueError: If a recipe-owned finding survives every recipe phase.

        """
        if hooks:
            u.Cli.info(
                f"lint: {len(hooks)} no-self-use finding(s) are hooks a subclass "
                f"overrides, left to their owner: {', '.join(hooks)}",
            )
>>>>>>> origin/0.12.0-dev
        left = sorted(
            located
            for issue in issues
            if issue.code in recipes
            and (located := f"{issue.file}:{issue.line}:{issue.code}") not in hooks
        )
        if left:
<<<<<<< HEAD
            # Owner-visible, never silent: the unplaceable findings (e.g. a
            # no-self-use method the staticmethod rewrite cannot hold) are
            # the L2 campaign's manual repair queue, reported per finding.
            u.Cli.info(
                "lint recipes left their own findings (manual repair): "
                + ", ".join(left),
            )
        return execution
=======
            msg = f"lint recipes left their own findings: {', '.join(left)}"
            raise ValueError(msg)

    @staticmethod
    def _overridden_hooks(
        issues: t.SequenceOf[m.Infra.Issue],
        recipes: t.MappingKV[str, c.Infra.LintFixRecipe],
        overridden: frozenset[t.Pair[str, str]],
    ) -> t.StrSequence:
        """Locate the static-method findings the recipe leaves to their owner.

        Returns:
            ``file:line:code`` of each finding on a method a subclass overrides.

        """
        by_file: MutableMapping[Path, list[m.Infra.Issue]] = {}
        for issue in issues:
            if recipes.get(issue.code) is c.Infra.LintFixRecipe.STATIC_METHOD:
                by_file.setdefault(Path(issue.file), []).append(issue)
        return sorted(
            f"{issue.file}:{issue.line}:{issue.code}"
            for path, found in by_file.items()
            for issue in u.Infra.overridden_findings(
                path.read_text(encoding=c.Cli.ENCODING_DEFAULT),
                found,
                path=path,
                recipes=recipes,
                overridden=overridden,
            )
        )
>>>>>>> origin/0.12.0-dev

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
        """Parse Ruff's JSON report into findings named by their Ruff rule.

        Ruff names every finding by rule name (a syntax error included, as
        ``invalid-syntax``); a report that is not the declared JSON list is a
        tool error and raises with its cause.

        Returns:
            The run's verdict and the findings it reported.

        Raises:
            TypeError: If the report is not a list of finding objects.

        """
        _ = ctx
        report = u.Cli.json_parse(result.stdout or "[]").unwrap()
        if not isinstance(report, list):
            msg = f"Ruff JSON report is not a list: {type(report).__name__}"
            raise TypeError(msg)
        issues: t.MutableSequenceOf[m.Infra.Issue] = []
        for entry in report:
            if not isinstance(entry, Mapping):
                msg = f"Ruff JSON finding is not an object: {type(entry).__name__}"
                raise TypeError(msg)
            issues.append(
                m.Infra.Issue(
                    file=u.Cli.json_pick_str(entry, "filename", "?"),
                    line=u.Cli.json_nested_int(entry, "location", "row"),
                    column=u.Cli.json_nested_int(entry, "location", "column"),
                    code=u.Cli.json_pick_str(entry, "name"),
                    message=u.Cli.json_pick_str(entry, "message"),
                ),
            )
        return self._finalize_parse_result(result, project_dir, issues, c.Infra.RUFF)

    @staticmethod
    @override
    def _findings_exit_codes() -> t.VariadicTuple[int]:
        """Exit statuses with which Ruff reports its findings.

        Returns:
            The findings statuses declared for Ruff in the tooling config.

        """
        return config.Infra.tooling.tools.ruff.findings_exit_codes


__all__: list[str] = ["FlextInfraRuffLintGate"]
