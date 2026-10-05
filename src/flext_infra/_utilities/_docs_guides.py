"""Root-owned project-guide generation for documentation utilities.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from collections.abc import MutableMapping
from pathlib import Path
from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, config, m, t
from flext_infra._utilities._docs_generate_plan import (
    FlextInfraUtilitiesDocsGeneratePlanMixin,
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
    def docs_project_guides_artifacts(
        scope: m.Infra.DocScope,
        *,
        repository_root: Path,
        source_states: t.SequenceOf[m.Cli.AtomicFileState],
    ) -> p.Result[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]]:
        """Plan root-owned guide projections from authenticated snapshot bytes.

        Returns:
            The resulting
                ``p.Result[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]]``.

        Raises:
            ValueError: If ``issues``.

        """
        from flext_infra import u

        source_root = repository_root / c.Infra.DIR_DOCS / "guides"
        destination_root = scope.path / c.Infra.DIR_DOCS / "guides"
        if source_root == destination_root:
            # Same-root inputs are authoritative, never their own projections.
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].ok(())
        if not scope.path.is_relative_to(repository_root):
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].fail(
                f"docs guide scope escapes repository {repository_root}: {scope.path}",
            )
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
                return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].fail(
                    f"docs guide source is absent: {path}",
                )
            content = state.content.decode(c.Cli.ENCODING_DEFAULT)
            if path.parent == source_root:
                sources[path] = content
            else:
                destinations[path] = content
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
        artifacts: list[t.Infra.DocsRenderedArtifactTuple] = []
        expected_paths = {destination_root / path.name for path in sources}
        loaded = u.Infra.load_workspace_manifest(repository_root)
        if loaded.failure:
            return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].from_failure(
                loaded,
            )
        effective_verbs = (
            *config.Infra.codegen.make.verbs,
            *(
                verb
                for manifest in loaded.value
                for verb in manifest.repository.extra_verbs
            ),
        )
        for source_path, source in sorted(sources.items()):
            destination = destination_root / source_path.name
            if destination in destinations and destination not in owned:
                return r[t.VariadicTuple[t.Infra.DocsRenderedArtifactTuple]].fail(
                    f"canonical guide collides with protected custom guide: "
                    f"{destination}",
                )
            relative_path = source_path.relative_to(repository_root).as_posix()
            issues = u.Infra.docs_command_contract_content_issues(
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
        artifacts.extend(
            (scope.path, path, None) for path in sorted(owned - expected_paths)
        )
        return FlextInfraUtilitiesDocsGeneratePlanMixin.docs_normalize_artifacts(
            artifacts,
        )


__all__: list[str] = ["FlextInfraUtilitiesDocsGuidesMixin"]
