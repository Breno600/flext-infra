"""Root-owned project-guide generation for documentation utilities.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, config, m, r, t
from flext_infra._utilities import (
    FlextInfraUtilitiesDocsCommandContractMixin,
    FlextInfraUtilitiesDocsGeneratePlanMixin,
    FlextInfraUtilitiesWorkspaceManifest,
)

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesDocsGuidesMixin:
    """Project guide projections derived from root ``docs/guides`` sources."""

    @staticmethod
    def docs_project_guide_content(
        content: str,
        project_name: str,
        guide_name: str,
    ) -> str:
        """Render a member guide with explicit source and regeneration ownership.

        Returns:
            The resulting ``str``.

        """
        lines = content.splitlines()
        title = Path(guide_name).stem.replace("_", " ").replace("-", " ").strip()
        body_lines = lines
        for index, line in enumerate(lines):
            match = c.Infra.HEADING_RE.match(line)
            if match is None:
                continue
            title = match.group(1).strip() or title
            body_lines = lines[index + 1 :]
            break
        body = "\n".join(body_lines).lstrip()
        header = (
            "<!-- AUTO-GENERATED FILE — regenerate through `make gen` "
            "from the workspace root. -->\n"
            f"<!-- Source of truth: `<workspace-root>/docs/guides/{guide_name}`; "
            "adjust that workspace source, never this member projection. -->\n\n"
            f"# {project_name} - {title}\n\n"
            f"> Project profile: `{project_name}`"
        )
        return f"{header}\n\n{body}".rstrip() + "\n"

    @staticmethod
    def docs_sanitize_internal_anchor_links(content: str) -> str:
        """Replace local Markdown links with text while retaining external links.

        Returns:
            The resulting ``str``.

        """
        preserved = (
            *(f"{scheme}:" for scheme in sorted(c.Infra.DOCS_EXTERNAL_SCHEMES)),
            c.Infra.DOCS_FRAGMENT_PREFIX,
        )

        def sanitize_link(match: re.Match[str]) -> str:
            # The declared scheme catalog is the only authority for what
            # survives: a second list here drifted into preserving `http://`
            # while the insecure scheme is rejected elsewhere.
            target = match.group(2)
            return match.group(0) if target.startswith(preserved) else match.group(1)

        return re.sub(c.Infra.MARKDOWN_LINK_RE, sanitize_link, content)

    @staticmethod
    def _classified_guide_sources(
        source_states: t.SequenceOf[m.Cli.AtomicFileState],
        source_root: Path,
        destination_root: Path,
    ) -> p.Result[
        t.Pair[
            t.MutableMappingKV[Path, str],
            t.MutableMappingKV[Path, str],
        ]
    ]:
        """Split authenticated guide states into source and destination bytes.

        Returns:
            The resulting ``(sources, destinations)`` mapping pair.

        """
        sources: MutableMapping[Path, str] = {}
        destinations: MutableMapping[Path, str] = {}
        for state in source_states:
            path = state.path
            if (
                path.parent not in {source_root, destination_root}
                or path.suffix != ".md"
                or path.name == "README.md"
            ):
                continue
            if state.content is None:
                return r[
                    t.Pair[
                        t.MutableMappingKV[Path, str],
                        t.MutableMappingKV[Path, str],
                    ]
                ].fail(f"docs guide source is absent: {path}")
            content = state.content.decode(c.Cli.ENCODING_DEFAULT)
            if path.parent == source_root:
                sources[path] = content
            else:
                destinations[path] = content
        return r[
            t.Pair[
                t.MutableMappingKV[Path, str],
                t.MutableMappingKV[Path, str],
            ]
        ].ok((sources, destinations))

    @staticmethod
    def _owned_destinations(
        scope: m.Infra.DocScope,
        destinations: t.MappingKV[Path, str],
    ) -> set[Path]:
        """Collect destination guides still carrying a canonical ownership header.

        Returns:
            The resulting ``set[Path]``.

        """
        owned: set[Path] = set()
        for path, content in destinations.items():
            lines = content.splitlines()
            generated = (
                "<!-- AUTO-GENERATED FILE — regenerate through `make gen` "
                "from the workspace root. -->"
            )
            source_headers = {
                (
                    f"<!-- Source of truth: `docs/guides/{path.name}`; "
                    "adjust that source, never this projection. -->"
                ),
                (
                    f"<!-- Source of truth: `<workspace-root>/docs/guides/{path.name}`"
                    "; adjust that workspace source, never this member projection. -->"
                ),
            }
            if (
                len(lines) >= c.Infra.DOCS_OWNED_HEADER_LINES
                and lines[0] == generated
                and lines[1] in source_headers
            ):
                owned.add(path)
                continue
            ownership = FlextInfraUtilitiesDocsGuidesMixin.docs_project_guide_content(
                "",
                scope.name,
                path.name,
            ).partition("\n\n")[0]
            previous_ownership = ownership.replace("`<workspace-root>/", "`")
            legacy_ownership = (
                "<!-- AUTO-GENERATED FILE — regenerate through `make gen` "
                "from the workspace root. -->\n"
                f"<!-- Source of truth: `docs/guides/{path.name}`; "
                "adjust that workspace source, never this member projection. -->"
            )
            if content.startswith((
                ownership + "\n\n",
                previous_ownership + "\n\n",
                legacy_ownership + "\n\n",
            )):
                owned.add(path)
        return owned

    @classmethod
    def _rendered_guide_artifacts(
        cls,
        scope: m.Infra.DocScope,
        repository_root: Path,
        sources: t.MappingKV[Path, str],
        destinations: t.MappingKV[Path, str],
        owned: set[Path],
    ) -> p.Result[list[t.Infra.DocsRenderedArtifactTuple]]:
        """Render every canonical guide and drop retired owned projections.

        Returns:
            The resulting ``p.Result[list[t.Infra.DocsRenderedArtifactTuple]]``.

        Raises:
            ValueError: If issues.

        """
        loaded = FlextInfraUtilitiesWorkspaceManifest.load_workspace_manifest(
            repository_root,
        )
        if loaded.failure:
            return r[list[t.Infra.DocsRenderedArtifactTuple]].from_failure(loaded)
        effective_verbs = (
            *config.Infra.codegen.make.verbs,
            *(
                verb
                for manifest in loaded.value
                for verb in manifest.repository.extra_verbs
            ),
        )
        destination_root = scope.path / c.Infra.DIR_DOCS / "guides"
        artifacts: list[t.Infra.DocsRenderedArtifactTuple] = []
        for source_path, source in sorted(sources.items()):
            destination = destination_root / source_path.name
            if destination in destinations and destination not in owned:
                return r[list[t.Infra.DocsRenderedArtifactTuple]].fail(
                    f"canonical guide collides with protected custom guide: "
                    f"{destination}",
                )
            relative_path = source_path.relative_to(repository_root).as_posix()
            contract_mixin = FlextInfraUtilitiesDocsCommandContractMixin
            issues = contract_mixin.docs_command_contract_content_issues(
                source,
                relative_path=relative_path,
                effective_verbs=effective_verbs,
            )
            if issues:
                first = issues[0]
                msg = f"{first.file}: {first.message}"
                raise ValueError(msg)
            rendered = FlextInfraUtilitiesDocsGuidesMixin.docs_project_guide_content(
                source,
                scope.name,
                source_path.name,
            )
            artifacts.append((
                scope.path,
                destination,
                FlextInfraUtilitiesDocsGuidesMixin.docs_sanitize_internal_anchor_links(
                    rendered,
                ),
            ))
        expected_paths = {destination_root / path.name for path in sources}
        artifacts.extend(
            (scope.path, path, None) for path in sorted(owned - expected_paths)
        )
        return r[list[t.Infra.DocsRenderedArtifactTuple]].ok(artifacts)

    @classmethod
    def docs_project_guides_artifacts(
        cls,
        scope: m.Infra.DocScope,
        *,
        repository_root: Path,
        source_states: t.SequenceOf[m.Cli.AtomicFileState],
    ) -> p.Result[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]]:
        """Plan root-owned guide projections from authenticated snapshot bytes.

        Returns:
            The resulting
                ``p.Result[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]]``.

        """
        source_root = repository_root / c.Infra.DIR_DOCS / "guides"
        destination_root = scope.path / c.Infra.DIR_DOCS / "guides"
        if source_root == destination_root:
            # Same-root inputs are authoritative, never their own projections.
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].ok(())
        if not scope.path.is_relative_to(repository_root):
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].fail(
                f"docs guide scope escapes repository {repository_root}: {scope.path}",
            )
        classified = cls._classified_guide_sources(
            source_states,
            source_root,
            destination_root,
        )
        if classified.failure:
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].from_failure(
                classified,
            )
        sources, destinations = classified.value
        owned = cls._owned_destinations(scope, destinations)
        artifacts = cls._rendered_guide_artifacts(
            scope,
            repository_root,
            sources,
            destinations,
            owned,
        )
        if artifacts.failure:
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].from_failure(
                artifacts,
            )
        return FlextInfraUtilitiesDocsGeneratePlanMixin.docs_normalize_artifacts(
            artifacts.value,
        )


__all__: list[str] = ["FlextInfraUtilitiesDocsGuidesMixin"]
