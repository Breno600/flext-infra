"""Immutable source-bundle preparation for the documentation generator.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import TYPE_CHECKING

from flext_infra import c, m, r, t, u

if TYPE_CHECKING:
    from flext_infra import p

type _DocsScopeArtifacts = t.Pair[
    m.Infra.DocScope,
    t.VariadicTuple[t.Triple[Path, Path, str | None]],
]


class FlextInfraDocGeneratorBundleMixin:
    """Freeze one render and every authenticated input before planning."""

    @staticmethod
    def _is_collocated_workspace_project(
        scope: m.Infra.DocScope,
        *,
        root_scope: m.Infra.DocScope | None,
    ) -> bool:
        """Return whether a project scope shares the aggregate root path.

        ``root_scope`` is ``None`` whenever the root does not participate as
        a docs output scope (e.g. conform's DECLARED scope); no scope can be
        collocated with an absent root.

        Returns:
            Whether a project scope shares the aggregate root path.

        """
        return (
            root_scope is not None
            and scope.name != c.Infra.RK_ROOT
            and scope.path == root_scope.path
        )

    @staticmethod
    def _validate_scope_targets(
        scopes: t.SequenceOf[m.Infra.DocScope],
        output_dir: Path,
    ) -> p.Result[bool]:
        """Require builders to preserve each lexical scope and report target.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        for scope in scopes:
            expected = scope.path / output_dir
            if scope.report_dir != expected:
                return r[bool].fail(
                    "docs report directory is aliased or escaped: "
                    f"expected {expected}, observed {scope.report_dir}",
                )
        return r[bool].ok(value=True)

    @classmethod
    def _prepare_request(
        cls,
        request: m.Infra.DocsGenerateRequest,
    ) -> p.Result[m.Infra.DocsGenerationBundle]:
        """Render one canonical docs artifact inventory from the frozen snapshot.

        Source-state race verification is owned by ``docs_file_plans``, the
        single pre-publication barrier of the docs cycle.

        Returns:
            The resulting ``p.Result[m.Infra.DocsGenerationBundle]``.

        """
        started_at = perf_counter()
        sources = cls._discovered_sources(request, started_at)
        if sources.failure:
            return r[m.Infra.DocsGenerationBundle].from_failure(sources)
        repository_root, _selected_roots, source_states = sources.value
        output_dir = u.Cli.resolve_optional_path(
            request.output_dir,
            default=Path(c.Infra.DEFAULT_DOCS_OUTPUT_DIR),
        )
        scopes = cls._validated_scopes(repository_root, request, output_dir)
        if scopes.failure:
            return r[m.Infra.DocsGenerationBundle].from_failure(scopes)
        rendered = cls._rendered_scopes(
            repository_root,
            scopes.value,
            source_states,
        )
        if rendered.failure:
            return r[m.Infra.DocsGenerationBundle].from_failure(rendered)
        return cls._validated_bundle(
            repository_root,
            rendered.value,
            source_states,
        )

    @classmethod
    def _discovered_sources(
        cls,
        request: m.Infra.DocsGenerateRequest,
        started_at: float,
    ) -> p.Result[t.Triple[Path, list[Path], t.VariadicTuple[m.Cli.AtomicFileState]]]:
        """Discover, select, and authenticate the docs source inventory.

        Returns:
            The resulting ``(repository_root, selected_roots, source_states)``
            triple.

        """
        result_type = r[
            t.Triple[Path, list[Path], t.VariadicTuple[m.Cli.AtomicFileState]]
        ]
        roots = u.Infra.docs_repository_roots(request.repository_root)
        if roots.failure:
            return result_type.from_failure(roots)
        repository_root = roots.value[0]
        selected_names = u.Infra.normalize_sequence_values(request.projects) or ()
        selected_roots: list[Path] = []
        for name in selected_names:
            selector = Path(name)
            if selector.is_absolute() or ".." in selector.parts:
                return result_type.fail(
                    f"docs project selector escapes workspace: {name}",
                )
            selected_roots.append(repository_root / selector)
        source_paths = u.Infra.docs_source_paths(repository_root, tuple(selected_roots))
        if source_paths.failure:
            return result_type.from_failure(source_paths)
        u.Cli.info(
            f"docs: discovered {len(source_paths.value)} source paths in "
            f"{perf_counter() - started_at:.2f}s",
        )
        sources = u.Infra.required_file_states(source_paths.value)
        if sources.failure:
            return result_type.from_failure(sources)
        u.Cli.info(
            f"docs: authenticated {len(sources.value)} source paths in "
            f"{perf_counter() - started_at:.2f}s",
        )
        return result_type.ok((repository_root, selected_roots, sources.value))

    @classmethod
    def _validated_scopes(
        cls,
        repository_root: Path,
        request: m.Infra.DocsGenerateRequest,
        output_dir: Path,
    ) -> p.Result[
        t.Pair[
            t.VariadicTuple[m.Infra.DocScope],
            t.VariadicTuple[m.Infra.DocScope],
        ]
    ]:
        """Build and target-validate the selected and aggregate doc scopes.

        Returns:
            The resulting ``(selected_scopes, aggregate_scopes)`` pair.

        """
        result_type = r[
            t.Pair[
                t.VariadicTuple[m.Infra.DocScope],
                t.VariadicTuple[m.Infra.DocScope],
            ]
        ]
        selected = u.Infra.build_scopes(
            repository_root,
            request.projects,
            output_dir,
            include_root=request.include_root,
        )
        if selected.failure:
            return result_type.from_failure(selected)
        selected_targets = cls._validate_scope_targets(selected.value, output_dir)
        if selected_targets.failure:
            return result_type.from_failure(selected_targets)
        # Why (X-47): the aggregate inventory always includes root (independent
        # of `request.include_root`) because `docs_root_artifacts` needs the
        # complete project catalog whenever the root scope IS rendered; it is
        # simply unused when `selected` excludes root.
        aggregate = u.Infra.build_scopes(
            repository_root,
            None,
            output_dir,
            include_root=True,
        )
        if aggregate.failure:
            return result_type.from_failure(aggregate)
        aggregate_targets = cls._validate_scope_targets(aggregate.value, output_dir)
        if aggregate_targets.failure:
            return result_type.from_failure(aggregate_targets)
        return result_type.ok((tuple(selected.value), tuple(aggregate.value)))

    @classmethod
    def _rendered_scopes(
        cls,
        repository_root: Path,
        scopes: t.Pair[
            t.VariadicTuple[m.Infra.DocScope],
            t.VariadicTuple[m.Infra.DocScope],
        ],
        source_states: t.VariadicTuple[m.Cli.AtomicFileState],
    ) -> p.Result[list[_DocsScopeArtifacts]]:
        """Render one docs artifact set per selected scope.

        Returns:
            The resulting per-scope rendered artifacts.

        """
        selected, aggregate = scopes
        root_scope: m.Infra.DocScope | None = (
            selected[0] if selected and selected[0].name == c.Infra.RK_ROOT else None
        )
        rendered: list[_DocsScopeArtifacts] = []
        for scope in selected:
            scope_started_at = perf_counter()
            if cls._is_collocated_workspace_project(scope, root_scope=root_scope):
                rendered.append((scope, ()))
                continue
            artifacts = u.Infra.docs_scope_artifacts(
                scope,
                repository_root=repository_root,
                aggregate_scopes=aggregate,
                source_states=source_states,
            )
            if artifacts.failure:
                return r[list[_DocsScopeArtifacts]].from_failure(artifacts)
            rendered.append((scope, artifacts.value))
            u.Cli.info(
                f"docs: rendered {scope.name} artifacts={len(artifacts.value)} "
                f"elapsed={perf_counter() - scope_started_at:.2f}s",
            )
        return r[list[_DocsScopeArtifacts]].ok(rendered)

    @classmethod
    def _normalized_scope_artifacts(
        cls,
        rendered: list[_DocsScopeArtifacts],
    ) -> p.Result[list[m.Infra.DocsScopeArtifacts]]:
        """Normalize rendered artifacts and bind each to its owning scope.

        Returns:
            The resulting normalized per-scope artifact sets.

        """
        normalized = u.Infra.docs_normalize_artifacts(
            tuple(artifact for _scope, artifacts in rendered for artifact in artifacts),
        )
        if normalized.failure:
            return r[list[m.Infra.DocsScopeArtifacts]].from_failure(normalized)
        normalized_scopes: list[m.Infra.DocsScopeArtifacts] = []
        offset = 0
        for scope, scope_artifacts in rendered:
            size = len(scope_artifacts)
            normalized_artifacts: list[m.Infra.DocsRenderedArtifact] = []
            for project, target, content in normalized.value[offset : offset + size]:
                if project != scope.path:
                    return r[list[m.Infra.DocsScopeArtifacts]].fail(
                        f"docs artifact owner differs from scope: {target}",
                    )
                normalized_content = content
                if normalized_content is not None and target.suffix == ".md":
                    normalized_content = c.Infra.FENCE_NOTEST_RE.sub(
                        r"```\1",
                        normalized_content,
                    )
                    normalized_content = u.Infra.docs_contract_update_toc(
                        normalized_content,
                    )[0]
                normalized_artifacts.append(
                    m.Infra.DocsRenderedArtifact(
                        relative_path=target.relative_to(project),
                        desired_content=(
                            None
                            if normalized_content is None
                            else normalized_content.encode(c.Cli.ENCODING_DEFAULT)
                        ),
                        desired_mode=(
                            c.Infra.DOCS_ARTIFACT_MODE
                            if normalized_content is not None
                            else None
                        ),
                    ),
                )
            normalized_scopes.append(
                m.Infra.DocsScopeArtifacts(
                    scope=scope,
                    artifacts=tuple(normalized_artifacts),
                ),
            )
            offset += size
        return r[list[m.Infra.DocsScopeArtifacts]].ok(normalized_scopes)

    @classmethod
    def _validated_bundle(
        cls,
        repository_root: Path,
        rendered: list[_DocsScopeArtifacts],
        source_states: t.VariadicTuple[m.Cli.AtomicFileState],
    ) -> p.Result[m.Infra.DocsGenerationBundle]:
        """Validate the rendered docs generation bundle.

        Returns:
            The resulting ``p.Result[m.Infra.DocsGenerationBundle]``.

        """
        normalized = cls._normalized_scope_artifacts(rendered)
        if normalized.failure:
            return r[m.Infra.DocsGenerationBundle].from_failure(normalized)
        validated_bundle: p.Result[m.Infra.DocsGenerationBundle] = u.validate_value(
            m.Infra.DocsGenerationBundle,
            {
                "scopes": tuple(normalized.value),
                "source_states": source_states,
                "repository_root": repository_root,
            },
        )
        if validated_bundle.failure:
            return r[m.Infra.DocsGenerationBundle].fail_op(
                "docs generation bundle validation",
                validated_bundle.error,
            )
        return r[m.Infra.DocsGenerationBundle].ok(validated_bundle.value)


__all__: list[str] = ["FlextInfraDocGeneratorBundleMixin"]
