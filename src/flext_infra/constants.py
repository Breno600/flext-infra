"""Constants facade for flext-infra — c.Infra project namespace.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import FlextCliConstants

from flext_infra._constants import FlextInfraConstantsBase
from flext_infra._constants import FlextInfraConstantsCensus
from flext_infra._constants import FlextInfraConstantsCheck
from flext_infra._constants import FlextInfraConstantsCli
from flext_infra._constants import FlextInfraConstantsCodegen
from flext_infra._constants import FlextInfraConstantsCodegenProject
from flext_infra._constants import FlextInfraConstantsDeps
from flext_infra._constants import FlextInfraConstantsDocs
from flext_infra._constants import FlextInfraConstantsGit
from flext_infra._constants import FlextInfraConstantsNamespace
from flext_infra._constants import FlextInfraConstantsPromoted
from flext_infra._constants import FlextInfraConstantsPromotedMessages
from flext_infra._constants import FlextInfraConstantsRefactor
from flext_infra._constants import FlextInfraConstantsRelease
from flext_infra._constants import FlextInfraConstantsRope
from flext_infra._constants import FlextInfraConstantsSourceCode
from flext_infra._constants import FlextInfraConstantsWorkspace


class FlextInfraConstants(FlextCliConstants):
    """Infra constants facade — access via c.Infra.*."""

    class Infra(
        FlextInfraConstantsBase,
        FlextInfraConstantsCensus,
        FlextInfraConstantsCheck,
        FlextInfraConstantsCli,
        FlextInfraConstantsCodegen,
        FlextInfraConstantsCodegenProject,
        FlextInfraConstantsRope,
        FlextInfraConstantsDeps,
        FlextInfraConstantsDocs,
        FlextInfraConstantsGit,
        FlextInfraConstantsNamespace,
        FlextInfraConstantsPromoted,
        FlextInfraConstantsPromotedMessages,
        FlextInfraConstantsSourceCode,
        FlextInfraConstantsRefactor,
        FlextInfraConstantsRelease,
        FlextInfraConstantsWorkspace,
    ):
        """Infra-domain constants — merged mixin namespace."""


c = FlextInfraConstants

__all__: tuple[str, ...] = ("FlextInfraConstants", "c")
