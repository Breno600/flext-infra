"""Constants for the unified census pipeline — accessed via c.Infra.*."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsCensus:
    """Census pipeline constants for object detection and classification."""

    CENSUS_UNSUPPORTED_SIMPLE_REMOVAL_CODE: ClassVar[str] = (
        "CENSUS_UNSUPPORTED_SIMPLE_REMOVAL"
    )
    "Error code marking a candidate outside the simple-removal contract (not a failure)."

    """Regex patterns for violation census detection."""

    COMPAT_ALIAS_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^([A-Z]\w+)\s*=\s*([A-Z]\w+)\s*$",
        re.MULTILINE,
    )
    "Detect compatibility alias assignments (X = Y)."


__all__: list[str] = ["FlextInfraConstantsCensus"]
