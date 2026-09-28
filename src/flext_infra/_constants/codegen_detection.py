"""Detection constants for the codegen package."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraConstantsCodegenDetection:
    """Constant detection policy for codegen."""

    DETECTION_MIN_QUOTED_LITERAL_LEN: ClassVar[int] = 2
    "Minimum length for a quoted string to be considered a literal."
    DETECTION_TRIVIAL_VALUES: ClassVar[frozenset[str]] = frozenset({
        "True",
        "False",
        "None",
        "0",
        "1",
        "2",
        "3",
        "4",
        "5",
        "-1",
        '""',
        "''",
        "[]",
        "{}",
        "()",
    })
    "Literal values considered trivial for constant detection heuristics."
    DETECTION_FINAL_DECL_RE: ClassVar[t.RegexPattern] = re.compile(
        r"^(?P<indent>\s*)(?P<name>[A-Z_][A-Z0-9_]*)"
        r"\s*:\s*(?P<ann>Final\[.*?\])\s*=\s*(?P<value>.+?)\s*(?:#.*)?$",
        re.MULTILINE,
    )
    "Regex: NAME: ClassVar[TYPE] = VALUE (with optional inline comment)."
    DETECTION_CLASS_DECL_RE: ClassVar[t.RegexPattern] = re.compile(r"class\s+(\w+)")
    "Regex: class ClassName (captures class name)."
    DETECTION_CANONICAL_ALIASES: ClassVar[frozenset[str]] = frozenset({
        "c",
        "m",
        "p",
        "t",
        "u",
        "r",
        "e",
        "s",
        "d",
        "h",
        "x",
    })
    "Canonical single-letter runtime aliases."


__all__: list[str] = ["FlextInfraConstantsCodegenDetection"]
