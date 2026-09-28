"""Centralized constants for the deps subpackage."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_cli import t


class FlextInfraConstantsDeps:
    """Deps infrastructure constants."""

    # NOTE: Hardcoded base path constants removed.
    # All tool settings phases now use dynamic discovery via
    # u.Infra.discover_python_dirs() (SSOT in FlextInfraUtilitiesDiscovery).
    SKIP_DIRS: ClassVar[frozenset[str]] = frozenset({
        ".archive",
        ".claude.disabled",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "htmlcov",
        "node_modules",
        "site",
        "vendor",
    })
    DEP_NAME_RE: ClassVar[t.RegexPattern] = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
    PYPROJECT_DOCUMENT_MAPPING_ERROR: ClassVar[str] = (
        "pyproject document is not a TOML mapping"
    )
    PEP621_NAME_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^\s*(?P<name>[A-Za-z0-9_.-]+)"
    )
    PEP621_REQUIREMENT_HEAD_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^\s*(?P<head>[A-Za-z0-9_.-]+(?:\[[^\]]+\])?)"
    )
    BANNER: ClassVar[str] = (
        "# @flext-generated: continuous\n"
        "# @flext-owner: flext-infra/config/codegen.yaml"
        " + flext-infra/src/flext_infra/templates/project/base/pyproject.toml.j2\n"
        "# @flext-adjust: MANAGED=conflict_sections + overwrite_project_keys."
        " CUSTOM=preserve_project_keys and [tool.*] outside conflict_sections."
        " Never edit this projection.\n"
        "# @flext-regenerate: make gen\n"
    )
    DEV_OPTIONAL_DEPS_MARKER: ClassVar[str] = (
        "# [MANAGED] consolidated development dependencies"
    )
    LEGACY_AUTO_MARKER: ClassVar[str] = (
        "# [AUTO] merged from dev/docs/security/test/typings"
    )
    LEGACY_AUTO_BANNER_LINE: ClassVar[str] = (
        "# Sections with [AUTO] are derived from workspace layout and dependencies."
    )
    DEPENDENCY_LIMITS_FILENAME: ClassVar[str] = "limits.toml"
    """Packaged dependency-limit configuration resource."""
    DEPTRY_UNUSED_DEPENDENCY_CODE: ClassVar[str] = "DEP002"
    """Deptry rule code for a declared dependency the code never imports."""
    MYPY_FOLLOW_UNTYPED_IMPORTS: ClassVar[str] = "follow_untyped_imports"
    """Mypy option that analyzes installed packages lacking stubs or py.typed."""
    MYPY_FOLLOW_UNTYPED_IMPORTS_DEFAULT: ClassVar[bool] = False
    """Mypy's own default when neither governed policy nor project declares it."""


__all__: list[str] = ["FlextInfraConstantsDeps"]
