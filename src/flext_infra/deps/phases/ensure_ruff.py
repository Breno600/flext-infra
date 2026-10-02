"""Phase: Ensure standard Ruff configuration inline with known-first-party overlay.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_infra import c, m, t, u
from flext_infra.deps.extra_paths import FlextInfraExtraPathsManager
from flext_infra.deps.phases.tool_tables import FlextInfraToolTablesPhase
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector


class FlextInfraEnsureRuffConfigPhase:
    """Ensure standard Ruff configuration inline with known-first-party overlay."""

    def __init__(self, tool_config: m.Infra.ToolConfigDocument) -> None:
        """Store tool configuration used to build canonical Ruff settings."""
        self._tool_config = tool_config

    @staticmethod
    def _workspace_exclusion_globs(project_dir: Path) -> t.StrSequence:
        """Return immutable repository and explicit exclusion path globs.

        Content-only repositories are foreign, read-only trees and therefore
        never enter Ruff. Explicit ``exclusions`` extend that same typed scope
        for non-repository paths without duplicating repository declarations.

        Returns:
            Immutable repository and explicit exclusion path globs.

        Raises:
            ValueError: If ``paths.failure``.

        """
        if not (project_dir / c.PYPROJECT_FILENAME).is_file():
            return ()
        paths = FlextInfraWorkspaceDetector.analysis_exclusion_paths(project_dir)
        if paths.failure:
            raise ValueError(paths.error or "workspace analysis scope is unavailable")
        return sorted(path.as_posix() for path in paths.value)

    @staticmethod
    def _analysis_exclusion_root_set(project_dir: Path) -> frozenset[str]:
        """First segments of the detector's declared analysis exclusions.

        Deliberately a DIFFERENT authority from
        ``FlextInfraToolTablesPhase.excluded_roots`` (the manifest
        non-participant set used by the per-file-ignores projection): this
        set drives the namespace-packages projection and follows the
        workspace detector's analysis-exclusion paths (gitmodules-driven).
        Like the manifest authority it is order-independent: a repository
        declares a retired tree once and every root-scoped projection
        converges.

        Returns:
            The resulting ``frozenset[str]``.

        Raises:
            ValueError: If ``paths.failure``.

        """
        if not (project_dir / c.PYPROJECT_FILENAME).is_file():
            return frozenset()
        paths = FlextInfraWorkspaceDetector.analysis_exclusion_paths(project_dir)
        if paths.failure:
            raise ValueError(
                paths.error or "workspace analysis exclusions are unavailable",
            )
        return frozenset(p.parts[0] for p in paths.value if Path(p).parts)

    def _phase(
        self,
        *,
        path: Path,
        facts: m.Infra.RuffProjectFacts,
    ) -> m.Infra.DepsToml.PhaseConfig:
        """Build the canonical Ruff phase for one project path.

        Returns:
            The resulting ``m.Infra.DepsToml.PhaseConfig``.

        """
        ruff_cfg = self._tool_config.tools.ruff
        workspace_exclusions = (
            self._workspace_exclusion_globs(path.parent)
            if facts.analysis_exclusions is None
            else facts.analysis_exclusions
        )
        isort_values: t.MutableSequenceOf[t.Pair[str, t.JsonValue]] = [
            ("combine-as-imports", ruff_cfg.lint.isort.combine_as_imports),
            ("force-single-line", ruff_cfg.lint.isort.force_single_line),
            ("split-on-trailing-comma", ruff_cfg.lint.isort.split_on_trailing_comma),
        ]
        detected_packages = sorted(facts.first_party)
        if detected_packages:
            isort_values.append((
                c.Infra.KNOWN_FIRST_PARTY_HYPHEN,
                u.normalize_to_json_value(detected_packages),
            ))
        # Dev/tooling source roots are config-declared, but a repository that
        # retired a tree (e.g. scripts/) must not keep analyzer entries naming
        # it: ruff fails hard on src roots whose directories do not exist, and
        # the namespace-packages contract only holds for roots on disk. The
        # declared lists stay the SSOT; existence filters the projection, with
        # roots the active plan is materializing accepted as present (the
        # extra-paths manager owns that declared set).
        generated_roots = FlextInfraExtraPathsManager(
            repository_root=path.parent,
            generated_python_roots=facts.generated_python_roots,
        ).generated_python_roots

        def _present(directory: str) -> bool:
            return (path.parent / directory).is_dir() or (directory in generated_roots)

        existing_root = tuple(d for d in ruff_cfg.src if _present(d))
        excluded_roots = self._analysis_exclusion_root_set(path.parent)
        existing_namespace_packages = tuple(
            d for d in ruff_cfg.namespace_packages if d not in excluded_roots
        )
        toml = m.Infra.DepsToml
        return toml.PhaseConfig(
            name="ruff",
            table_path=(c.Infra.RUFF,),
            operations=(
                toml.RemoveOp(key=c.Infra.EXTEND),
                toml.ListOp(
                    key="extend-exclude",
                    values=sorted(workspace_exclusions),
                ),
                toml.ListOp(
                    key="namespace-packages",
                    values=sorted(existing_namespace_packages),
                ),
                toml.SetOp(key="fix", value=ruff_cfg.fix),
                toml.SetOp(key="line-length", value=ruff_cfg.line_length),
                toml.SetOp(key="preview", value=ruff_cfg.preview),
                toml.SetOp(key="respect-gitignore", value=ruff_cfg.respect_gitignore),
                toml.SetOp(key="show-fixes", value=ruff_cfg.show_fixes),
                toml.SetOp(key="target-version", value=ruff_cfg.target_version),
                toml.ListOp(key="src", values=sorted(existing_root)),
            ),
            nested_tables=(
                toml.PhaseConfig(
                    name="ruff",
                    root_path=(),
                    table_path=("format",),
                    operations=tuple(
                        toml.SetOp(key=key, value=value)
                        for key, value in (
                            (
                                "docstring-code-format",
                                ruff_cfg.format.docstring_code_format,
                            ),
                            ("indent-style", ruff_cfg.format.indent_style),
                            ("line-ending", ruff_cfg.format.line_ending),
                            ("quote-style", ruff_cfg.format.quote_style),
                            (
                                "skip-magic-trailing-comma",
                                ruff_cfg.format.skip_magic_trailing_comma,
                            ),
                        )
                    ),
                ),
                toml.PhaseConfig(
                    name="ruff",
                    root_path=(),
                    table_path=(c.Infra.LINT_SECTION,),
                    operations=(
                        toml.SetOp(
                            key="select",
                            value=u.normalize_to_json_value(
                                sorted(ruff_cfg.lint.select),
                            ),
                        ),
                        # make fix never deletes information: the fix-safety
                        # policy comes from the same SSOT the template renders.
                        toml.SetOp(
                            key="unfixable",
                            value=u.normalize_to_json_value(
                                sorted(ruff_cfg.lint.unfixable),
                            ),
                        ),
                        toml.SetOp(
                            key="extend-safe-fixes",
                            value=u.normalize_to_json_value(
                                sorted(ruff_cfg.lint.extend_safe_fixes),
                            ),
                        ),
                        # Only the unscoped operator-authorized exceptions of
                        # the tooling owner, the same SSOT the template renders.
                        toml.SetOp(
                            key="ignore",
                            value=u.normalize_to_json_value(list(ruff_cfg.lint.ignore)),
                        ),
                    ),
                ),
                toml.PhaseConfig(
                    name="ruff",
                    root_path=(),
                    table_path=(c.Infra.LINT_SECTION, "flake8-copyright"),
                    operations=(
                        toml.SetOp(
                            key="notice-rgx",
                            value=ruff_cfg.lint.copyright_notice_rgx,
                        ),
                    ),
                ),
                toml.PhaseConfig(
                    name="ruff",
                    root_path=(),
                    table_path=(c.Infra.LINT_SECTION, "pydocstyle"),
                    operations=(
                        toml.SetOp(
                            key="convention",
                            value=ruff_cfg.lint.pydocstyle.convention,
                        ),
                    ),
                ),
                toml.PhaseConfig(
                    name="ruff",
                    root_path=(),
                    table_path=(c.Infra.LINT_SECTION, "flake8-tidy-imports"),
                    operations=(
                        toml.SetOp(
                            key="ban-relative-imports",
                            value=ruff_cfg.lint.ban_relative_imports,
                        ),
                    ),
                ),
                toml.PhaseConfig(
                    name="ruff",
                    root_path=(),
                    table_path=(
                        c.Infra.LINT_SECTION,
                        "flake8-tidy-imports",
                        "banned-api",
                    ),
                    operations=tuple(
                        toml.SetOp(
                            key=name,
                            value=u.normalize_to_json_value({"msg": message}),
                        )
                        for name, message in ruff_cfg.lint.banned_api.items()
                    ),
                ),
                toml.PhaseConfig(
                    name="ruff",
                    root_path=(),
                    table_path=(c.Infra.LINT_SECTION, c.Infra.ISORT),
                    operations=tuple(
                        toml.SetOp(key=key, value=value) for key, value in isort_values
                    ),
                ),
                toml.PhaseConfig(
                    name="ruff",
                    root_path=(),
                    table_path=(c.Infra.LINT_SECTION, "per-file-ignores"),
                    operations=(
                        *(
                            toml.SetOp(
                                key=pattern,
                                value=u.normalize_to_json_value(sorted(rules)),
                            )
                            for pattern, rules in facts.per_file_ignores.items()
                        ),
                        *(
                            toml.RemoveOp(key=pattern)
                            for pattern in facts.stale_patterns
                        ),
                    ),
                ),
            ),
        )

    def apply_payload(
        self,
        payload: t.MutableJsonMapping,
        *,
        path: Path,
        analysis_exclusions: t.StrSequence | None = None,
        generated_python_roots: t.StrSequence = (),
    ) -> t.StrSequence:
        """Apply canonical Ruff settings directly to one normalized payload.

        ``analysis_exclusions`` is the caller's declared topology; ``None``
        derives the workspace exclusion globs on disk.

        Returns:
            The resulting ``t.StrSequence``.

        """
        # One fleet exemption map, declared with its authority at the tooling
        # owner, reaches every project unchanged.
        effective_ignores = self._tool_config.tools.ruff.lint.per_file_ignores
        current_ignores = u.Cli.toml_mapping_path(
            payload,
            (c.Infra.TOOL, c.Infra.RUFF, c.Infra.LINT_SECTION, "per-file-ignores"),
        )
        changes = list(
            u.Infra.apply_toml_phases(
                payload,
                self._phase(
                    path=path,
                    facts=m.Infra.RuffProjectFacts(
                        first_party=FlextInfraToolTablesPhase.first_party_namespaces(
                            path.parent,
                        ),
                        stale_patterns=[
                            pattern
                            for pattern in current_ignores or ()
                            if pattern not in effective_ignores
                        ],
                        per_file_ignores=effective_ignores,
                        analysis_exclusions=analysis_exclusions,
                        generated_python_roots=generated_python_roots,
                    ),
                ),
            ),
        )
        if u.Cli.toml_mapping_remove_key_if_present(payload, c.Infra.LINT_SECTION):
            changes.append("removed stale top-level [lint] section")
        return changes


__all__: list[str] = ["FlextInfraEnsureRuffConfigPhase"]
