"""Owner-declared managed document conflict recovery utilities."""

from __future__ import annotations

from typing import TYPE_CHECKING

from flext_core import r
from flext_infra import c, m, t

from .._config import FlextInfraConfig
from .base import FlextInfraUtilitiesBase

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraUtilitiesManagedConflicts:
    """Recover only merge blocks authorized by the document owner."""

    @staticmethod
    def toml_section_is_owned(section: str, owned: t.StrSequence) -> bool:
        """True when ``section`` is an owned table or a child of one."""
        return any(section == item or section.startswith(f"{item}.") for item in owned)

    @staticmethod
    def pyproject_managed_file() -> p.Result[m.Infra.ManagedFileSpec]:
        """Return the pyproject ManagedFileSpec. Missing declaration is a bug."""
        for item in FlextInfraConfig.fetch_global().Infra.codegen.managed_files:
            if item.path.as_posix() == c.PYPROJECT_FILENAME:
                return r[m.Infra.ManagedFileSpec].ok(item)
        return r[m.Infra.ManagedFileSpec].fail(
            f"codegen.yaml templates.managed_files must declare {c.PYPROJECT_FILENAME}"
        )

    @classmethod
    def pyproject_section_markers(cls, section_header: str) -> p.Result[t.StrSequence]:
        """Render CUSTOM/MANAGED comments from the pyproject ManagedFileSpec."""
        spec_result = cls.pyproject_managed_file()
        if spec_result.failure:
            return r[t.StrSequence].from_failure(spec_result)
        spec = spec_result.value
        if not (section_header.startswith("[") and section_header.endswith("]")):
            return r[t.StrSequence].ok(())
        inner = section_header[1:-1]
        if inner == c.Infra.PROJECT:
            custom = ", ".join(spec.preserve_project_keys)
            managed = ", ".join(spec.overwrite_project_keys)
            markers = (
                *((f"# [CUSTOM] {custom}",) if custom else ()),
                *((f"# [MANAGED] {managed}",) if managed else ()),
            )
            return r[t.StrSequence].ok(markers)
        owned = next(
            (
                item
                for item in spec.conflict_sections
                if cls.toml_section_is_owned(inner, (item,))
            ),
            None,
        )
        if owned is not None:
            return r[t.StrSequence].ok((f"# [MANAGED] {owned}",))
        if inner.startswith("tool.") and not cls.toml_section_is_owned(
            inner, spec.conflict_sections
        ):
            tool_table = ".".join(inner.split(".")[:2])
            return r[t.StrSequence].ok((f"# [CUSTOM] {tool_table}",))
        return r[t.StrSequence].ok(())

    @staticmethod
    def recover_managed_toml(
        content: str, *, conflict_sections: t.StrSequence
    ) -> p.Result[str]:
        """Choose current TOML bytes only inside explicitly owned sections."""
        if FlextInfraUtilitiesBase.first_merge_conflict_marker(content) is None:
            return r[str].ok(content)
        lines = content.splitlines(keepends=True)
        recovered: list[str] = []
        section = ""
        index = 0
        while index < len(lines):
            line = lines[index]
            control = FlextInfraUtilitiesBase.merge_conflict_control(line)
            if control is None:
                section_match = c.Infra.TOML_SECTION_HEADER_RE.fullmatch(
                    line.rstrip("\r\n")
                )
                if section_match is not None:
                    section = section_match.group(1)
                recovered.append(line)
                index += 1
                continue
            if control != "current":
                return r[str].fail("orphan TOML merge-control marker")
            if not FlextInfraUtilitiesManagedConflicts.toml_section_is_owned(
                section, conflict_sections
            ):
                return r[str].fail(
                    "merge conflict is outside owner-declared TOML sections: "
                    f"{section or '<document-root>'}"
                )
            index += 1
            current: list[str] = []
            while index < len(lines):
                control = FlextInfraUtilitiesBase.merge_conflict_control(lines[index])
                if control in {"ancestor", "separator"}:
                    break
                if control is not None:
                    return r[str].fail("nested or malformed TOML merge conflict")
                current.append(lines[index])
                index += 1
            if index >= len(lines):
                return r[str].fail("TOML merge conflict has no separator")
            if control == "ancestor":
                index += 1
                while index < len(lines):
                    control = FlextInfraUtilitiesBase.merge_conflict_control(
                        lines[index]
                    )
                    if control == "separator":
                        break
                    if control is not None:
                        return r[str].fail("nested or malformed TOML merge conflict")
                    index += 1
                if index >= len(lines):
                    return r[str].fail("TOML merge conflict has no separator")
            index += 1
            while index < len(lines):
                control = FlextInfraUtilitiesBase.merge_conflict_control(lines[index])
                if control == "incoming":
                    break
                if control is not None:
                    return r[str].fail("nested or malformed TOML merge conflict")
                index += 1
            if index >= len(lines):
                return r[str].fail("TOML merge conflict has no closing marker")
            for current_line in current:
                section_match = c.Infra.TOML_SECTION_HEADER_RE.fullmatch(
                    current_line.rstrip("\r\n")
                )
                if section_match is not None:
                    section = section_match.group(1)
            recovered.extend(current)
            index += 1
        return r[str].ok("".join(recovered))


__all__: t.VariadicTuple[str] = ("FlextInfraUtilitiesManagedConflicts",)
