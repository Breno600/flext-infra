"""Fail-closed recovery for owner-declared managed document conflicts."""

from __future__ import annotations

import re

from flext_infra import p, r, t


class FlextInfraCodegenManagedConflicts:
    """Recover only merge blocks explicitly owned by document configuration."""

    _TOML_SECTION_RE = re.compile(r"^\s*\[([^\[\]]+)\]\s*(?:#.*)?$")

    @classmethod
    def recover_toml(
        cls, content: str, *, conflict_sections: t.StrSequence
    ) -> p.Result[str]:
        """Choose the current projection inside configured TOML sections only."""
        if "<<<<<<< " not in content:
            return r[str].ok(content)
        allowed = frozenset(conflict_sections)
        lines = content.splitlines(keepends=True)
        recovered: list[str] = []
        section = ""
        index = 0
        while index < len(lines):
            line = lines[index]
            section_match = cls._TOML_SECTION_RE.match(line.rstrip("\r\n"))
            if section_match is not None:
                section = section_match.group(1)
            if not line.startswith("<<<<<<< "):
                recovered.append(line)
                index += 1
                continue
            if section not in allowed:
                return r[str].fail(
                    "merge conflict is outside owner-declared TOML sections: "
                    f"{section or '<document-root>'}"
                )
            index += 1
            current: list[str] = []
            while index < len(lines) and not lines[index].startswith("======="):
                if lines[index].startswith(("<<<<<<< ", ">>>>>>> ")):
                    return r[str].fail("nested or malformed TOML merge conflict")
                current.append(lines[index])
                index += 1
            if index >= len(lines):
                return r[str].fail("TOML merge conflict has no separator")
            index += 1
            while index < len(lines) and not lines[index].startswith(">>>>>>> "):
                if lines[index].startswith(("<<<<<<< ", "=======")):
                    return r[str].fail("nested or malformed TOML merge conflict")
                index += 1
            if index >= len(lines):
                return r[str].fail("TOML merge conflict has no closing marker")
            recovered.extend(current)
            index += 1
        return r[str].ok("".join(recovered))


__all__: tuple[str, ...] = ("FlextInfraCodegenManagedConflicts",)
