"""Detector configuration constants.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import ClassVar


class FlextInfraConstantsDetectors:
    """Detector constants — accessed via c.Infra.*."""

    IMPORTLIB_IMPORT_MODULE: ClassVar[str] = "importlib.import_module"
    "Dotted name for the dynamic import helper flagged by the inline-import detector."

    CONTEXTLIB_SUPPRESS: ClassVar[str] = "contextlib.suppress"
    "Dotted name for the failure-swallowing context manager flagged by the silent-failure detector."

    INLINE_IMPORT_EXEMPT_PATH_PARTS: ClassVar[frozenset[str]] = frozenset({"beartype"})
    "Path parts that exempt a file from inline-import detection (SSOT: detector-local)."

    INLINE_IMPORT_EXEMPT_FILE_NAMES: ClassVar[frozenset[str]] = frozenset({
        "__init__.py"
    })
    "File names that exempt a module from inline-import detection."


__all__: list[str] = ["FlextInfraConstantsDetectors"]
