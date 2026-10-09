"""Gitignore rendering utilities for ``u.Infra``.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import itertools
import operator
from pathlib import Path

from flext_infra import c, m, p, r, t


class FlextInfraUtilitiesGitignore:
    """Gitignore rendering utilities."""

    @staticmethod
    def codegen_templates_root(codegen: m.Infra.CodegenConfigSpec) -> Path:
        """Return the resolved template root of the installed flext-infra package.

        Returns:
            The resolved template root of the installed flext-infra package.

        """
        package_root = Path(__file__).resolve().parent.parent
        return (package_root / "templates" / codegen.templates.root).resolve()

    @staticmethod
    def codegen_template_sources(codegen: m.Infra.CodegenConfigSpec) -> frozenset[Path]:
        """Resolve only manifest-declared template inputs, never output suffixes.

        Returns:
            The resulting ``frozenset[Path]``.

        Raises:
            ValueError: If declared template source escapes its owner root.

        """
        root = FlextInfraUtilitiesGitignore.codegen_templates_root(codegen)
        sources: set[Path] = set()
        for entry in codegen.templates.entries:
            if entry.source is None:
                continue
            path = (root / entry.source).resolve()
            if not path.is_relative_to(root):
                msg = f"declared template source escapes its owner root: {entry.source}"
                raise ValueError(msg)
            sources.add(path)
        return frozenset(sources)

    @staticmethod
    def render_project_gitignore(
        codegen: m.Infra.CodegenConfigSpec,
        *,
        profile: c.Infra.MakeProfile,
        project_name: str,
        workspace: m.Infra.WorkspaceSpec | None = None,
        project_dir: Path | None = None,
    ) -> p.Result[str]:
        """Render the canonical ``.gitignore`` for one named project.

        Render the declared fleet sections, then retain any external blocks
        delegated by the project's typed config from its live ignore file.

        Returns:
            The resulting ``p.Result[str]``.

        """
        from flext_infra import u

        entry = next(
            (
                item
                for item in codegen.templates.entries
                if item.destination == c.Infra.GITIGNORE
            ),
            None,
        )
        if entry is None:
            return r[str].fail(
                "gitignore template is missing from codegen configuration",
            )
        if entry.source is None:
            return r[str].fail(
                "gitignore codegen entry must declare a render template source",
            )
        templates_root = FlextInfraUtilitiesGitignore.codegen_templates_root(codegen)
        project_patterns: t.StrSequence = ()
        preserved_blocks: t.VariadicTuple[m.Infra.ProjectGitignorePreservedBlock] = ()
        if project_dir is not None:
            resolved = u.Infra.load_project_managed_artifacts(project_dir)
            if resolved.failure:
                return r[str].from_failure(resolved)
            project_patterns = resolved.value.artifacts.Gitignore.patterns
            preserved_blocks = resolved.value.artifacts.Gitignore.preserved_blocks
        context = m.Infra.GitignoreRenderSpec(
            gitignore_sections=FlextInfraUtilitiesGitignore.gitignore_sections(
                codegen,
                profile=profile,
                project_name=project_name,
                workspace=workspace,
                project_patterns=project_patterns,
            ),
        )
        rendered = u.Cli.template_render(templates_root / entry.source, context)
        if rendered.failure or project_dir is None:
            return rendered
        return FlextInfraUtilitiesGitignore.preserve_project_gitignore_blocks(
            rendered.value,
            project_dir,
            preserved_blocks,
        )

    @staticmethod
    def preserve_project_gitignore_blocks(
        rendered: str,
        project_dir: Path,
        blocks: t.VariadicTuple[m.Infra.ProjectGitignorePreservedBlock],
    ) -> p.Result[str]:
        """Compose declared external blocks without taking ownership of their lines.

        Returns:
            The resulting ``p.Result[str]``.

        """
        if not blocks:
            return r[str].ok(rendered)
        from flext_infra import u

        destination = project_dir / c.Infra.GITIGNORE
        markers = frozenset(
            marker for block in blocks for marker in (block.begin, block.end)
        )
        if any(line in markers for line in rendered.splitlines()):
            return r[str].fail(
                f"generated gitignore claims a declared external block: {destination}",
            )
        snapshot = u.Cli.atomic_read_binary_file_state(destination, required=False)
        if snapshot.failure:
            return r[str].from_failure(snapshot)
        content = snapshot.value.content
        if content is None:
            return r[str].ok(rendered)
        current = content.decode(c.Cli.ENCODING_DEFAULT)
        lines = current.splitlines(keepends=True)
        found: dict[str, list[int]] = {marker: [] for marker in markers}
        for index, line in enumerate(lines):
            text = line.rstrip("\r\n")
            if text in found:
                found[text].append(index)
            elif any(text.startswith(marker) for marker in markers):
                return r[str].fail(
                    f"malformed gitignore preserved marker: {destination}: {text!r}",
                )
        sections: list[tuple[int, int, str]] = []
        for block in blocks:
            begins = found[block.begin]
            ends = found[block.end]
            if not begins and not ends:
                continue
            if len(begins) != 1 or len(ends) != 1 or begins[0] >= ends[0]:
                return r[str].fail(
                    f"ambiguous gitignore preserved block {block.begin!r}: "
                    f"{destination}",
                )
            sections.append((
                begins[0],
                ends[0],
                "".join(lines[begins[0] : ends[0] + 1]),
            ))
        sections.sort(key=operator.itemgetter(0))
        if any(
            previous[1] >= current[0]
            for previous, current in itertools.pairwise(sections)
        ):
            return r[str].fail(f"overlapping gitignore preserved blocks: {destination}")
        composed = rendered
        for _, _, external in sections:
            if composed and not composed.endswith("\n"):
                composed += "\n"
            if composed and not composed.endswith("\n\n"):
                composed += "\n"
            composed += external
        return r[str].ok(composed)

    @staticmethod
    def gitignore_sections(
        codegen: m.Infra.CodegenConfigSpec,
        *,
        profile: c.Infra.MakeProfile,
        project_name: str | None = None,
        workspace: m.Infra.WorkspaceSpec | None = None,
        project_patterns: t.StrSequence = (),
    ) -> t.VariadicTuple[m.Infra.ScaffoldGitignoreSectionSpec]:
        """Derive the ordered ``.gitignore`` sections for one project.

        Single owner of the section list: the profile-filtered SSOT sections,
        the workspace-root subproject whitelist derived from the live topology,
        the layout override additions and the repository-owned patterns. Every
        renderer of ``base/gitignore.j2`` (conform planning, the layout engine,
        ``codegen new``) consumes this projection, so the layout gate can never
        demand a pattern that ``make gen`` does not materialize.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.ScaffoldGitignoreSectionSpec]``.

        """
        sections = [
            section
            for section in codegen.gitignore_sections
            if not section.profiles or profile in section.profiles
        ]
        # The deny-all root policy (`/*` + `/*/`) would swallow every governed
        # subproject directory, so their whitelist is DERIVED from the live workspace
        # topology instead of a hardcoded name glob: declaring a subproject in
        # local .gitmodules is the single source that makes it trackable.
        # Nested paths need every ancestor unignored, otherwise git never
        # descends far enough to reach the subproject itself. Only the
        # workspace root carries that policy; a subproject never does.
        member_patterns: list[str] = []
        if workspace is not None and profile is c.Infra.MakeProfile.WORKSPACE:
            for declared_repository in workspace.subprojects:
                parts = declared_repository.path.as_posix().strip("/").split("/")
                # Every ancestor is unignored so git can descend into the
                # subproject, then its contents are unignored with the `/**` form.
                prefixes = [
                    "/".join(parts[:depth]) for depth in range(1, len(parts) + 1)
                ]
                candidates = [f"!/{prefix}/" for prefix in prefixes]
                candidates.append(f"!/{prefixes[-1]}/**")
                for pattern in candidates:
                    if pattern not in member_patterns:
                        member_patterns.append(pattern)
        if member_patterns:
            sections.append(
                m.Infra.ScaffoldGitignoreSectionSpec(
                    name="WHITELIST: governed workspace subprojects (derived)",
                    patterns=tuple(member_patterns),
                ),
            )
        if project_name is not None:
            override = codegen.layout.project_overrides.get(project_name)
            if override is not None and override.gitignore_additions:
                sections.append(
                    m.Infra.ScaffoldGitignoreSectionSpec(
                        name=c.Infra.GITIGNORE_LAYOUT_SECTION_NAME,
                        patterns=override.gitignore_additions,
                    ),
                )
        if project_patterns:
            # The repository owns the ignore patterns the fleet scaffold cannot
            # know (local caches, generated runtime state); they are declared in
            # its own config/*.yaml and appended as one derived section.
            sections.append(
                m.Infra.ScaffoldGitignoreSectionSpec(
                    name=c.Infra.GITIGNORE_PROJECT_SECTION_NAME,
                    patterns=tuple(project_patterns),
                ),
            )
        return tuple(sections)


__all__: list[str] = ["FlextInfraUtilitiesGitignore"]
