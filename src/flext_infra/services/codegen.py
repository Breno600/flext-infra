"""Ultra-thin codegen service facade composed through FLEXT.

Owns no business logic itself: it composes the private ``_codegen`` service
parts (VS Code settings today) so callers reach one canonical codegen surface
instead of importing scattered generators.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_infra.services._codegen.vscode import FlextInfraCodegenVscodeMixin


class FlextInfraCodegen(FlextInfraCodegenVscodeMixin):
    """Public codegen service facade composed via FLEXT."""


__all__: list[str] = ["FlextInfraCodegen"]
