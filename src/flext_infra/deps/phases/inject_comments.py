"""Phase: Inject managed/custom markers into pyproject.toml."""

from __future__ import annotations

from flext_infra import c, config, t, u


class FlextInfraInjectCommentsPhase:
    """Inject managed/custom markers into pyproject.toml."""

    _STRIP_PREFIXES: t.StrSequence = (
        "# [MANAGED]",
        "# [CUSTOM]",
        "# [AUTO]",
        "# Sections with [",
        "# FLEXT mypy[",
        "# FLEXT ruff[",
        "# FLEXT pyright[",
    )

    @staticmethod
    def _rationale_blocks() -> t.MappingKV[str, t.Pair[str, t.StrSequence]]:
        """Render each managed section's evidence-backed suppression comments."""
        tools = config.Infra.tooling.tools
        return {
            f"[tool.{section}]": (
                label,
                (
                    f"# FLEXT {label} suppression rationale (validated {boundary}):",
                    *(
                        f"# FLEXT {tag}[{code}]: {rationale}"
                        for code, rationale in sorted(items.items())
                    ),
                ),
            )
            for section, tag, label, boundary, items in (
                (
                    "mypy",
                    "mypy",
                    "mypy",
                    "at the facade-FLEXT boundary",
                    tools.mypy.disabled_error_codes,
                ),
                (
                    "ruff.lint",
                    "ruff",
                    "Ruff",
                    "against semantic facet order",
                    tools.ruff.lint.ignored_rule_rationales,
                ),
                (
                    "pyright",
                    "pyright",
                    "Pyright",
                    "at the facade-FLEXT boundary",
                    tools.pyright.global_suppression_rationales,
                ),
            )
        }

    @staticmethod
    def _is_section_header(line: str) -> bool:
        """Is section header."""
        stripped = line.strip()
        return stripped.startswith("[") and stripped.endswith("]")

    @classmethod
    def _managed_marker_lines(cls) -> t.Infra.StrSet:
        """Return banner and rationale lines to strip."""
        markers = {c.Infra.LEGACY_AUTO_BANNER_LINE}
        markers.update(c.Infra.BANNER.splitlines())
        for _, block in cls._rationale_blocks().values():
            markers.update(block)
        return markers

    @classmethod
    def _strip_managed_lines(
        cls, lines: t.StrSequence
    ) -> t.Pair[t.StrSequence, t.StrSequence]:
        """Strip managed lines."""
        changes: t.MutableSequenceOf[str] = []
        managed_lines = cls._managed_marker_lines()
        cleaned: t.MutableSequenceOf[str] = []
        skip_broken_group_section = False
        broken_removed = False
        for line in lines:
            stripped = line.strip()
            if skip_broken_group_section:
                if cls._is_section_header(line):
                    skip_broken_group_section = False
                else:
                    continue
            if stripped.startswith(tuple(cls._STRIP_PREFIXES)):
                continue
            if stripped == "[group.dev.dependencies]":
                skip_broken_group_section = True
                broken_removed = True
                continue
            if stripped in managed_lines:
                continue
            cleaned.append(line)
        if broken_removed:
            changes.append("broken [group.dev.dependencies] section removed")
        return cleaned, changes

    @staticmethod
    def _collapse_blank_lines(lines: t.StrSequence) -> t.StrSequence:
        """Collapse repeated blank lines into a single canonical separator."""
        normalized: t.MutableSequenceOf[str] = []
        previous_blank = False
        for line in lines:
            is_blank = not line.strip()
            if is_blank and previous_blank:
                continue
            normalized.append(line)
            previous_blank = is_blank
        return normalized

    def apply(self, rendered: str) -> t.Pair[str, t.StrSequence]:
        """Inject managed banner/markers and return updated TOML plus change messages."""
        changes: t.MutableSequenceOf[str] = []
        lines = rendered.splitlines()
        cleaned_lines, cleanup_changes = self._strip_managed_lines(lines)
        changes.extend(cleanup_changes)
        banner_lines = c.Infra.BANNER.splitlines()
        first_content = next(
            (index for index, line in enumerate(cleaned_lines) if line.strip()),
            len(cleaned_lines),
        )
        content_lines = cleaned_lines[first_content:]
        out: t.MutableSequenceOf[str] = [*banner_lines, ""]
        if lines[: len(banner_lines)] != banner_lines:
            changes.append("managed banner injected")
        emitted_markers: set[str] = set()
        rationale_blocks = self._rationale_blocks()
        for line in content_lines:
            stripped = line.strip()
            markers_result = u.Infra.pyproject_section_markers(stripped)
            if markers_result.failure:
                raise RuntimeError(
                    markers_result.error or "pyproject section markers failed"
                )
            for marker in markers_result.value:
                if marker not in emitted_markers:
                    out.append(marker)
                    changes.append(f"marker injected for {stripped}")
                    emitted_markers.add(marker)
            out.append(line)
            if stripped in rationale_blocks:
                label, rationale = rationale_blocks[stripped]
                out.extend(rationale)
                changes.append(f"{label.capitalize()} suppression rationales injected")
        updated = "\n".join(self._collapse_blank_lines(out)).rstrip() + "\n"
        original = rendered.rstrip() + "\n"
        if updated == original:
            return (updated, [])
        return (updated, changes)


__all__: list[str] = ["FlextInfraInjectCommentsPhase"]
