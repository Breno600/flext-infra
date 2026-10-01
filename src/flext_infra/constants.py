"""Constants facade for flext-infra — c.Infra project namespace.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_cli import FlextCliConstants

from ._constants.base import FlextInfraConstantsBase
from ._constants.census import FlextInfraConstantsCensus
from ._constants.check import FlextInfraConstantsCheck
from ._constants.cli import FlextInfraConstantsCli
from ._constants.codegen import FlextInfraConstantsCodegen
from ._constants.codegen_project import FlextInfraConstantsCodegenProject
from ._constants.deps import FlextInfraConstantsDeps
from ._constants.docs import FlextInfraConstantsDocs
from ._constants.git import FlextInfraConstantsGit
from ._constants.namespace import FlextInfraConstantsNamespace
from ._constants.promoted import FlextInfraConstantsPromoted
from ._constants.promoted_messages import FlextInfraConstantsPromotedMessages
from ._constants.refactor import FlextInfraConstantsRefactor
from ._constants.release import FlextInfraConstantsRelease
from ._constants.rope import FlextInfraConstantsRope
from ._constants.source_code import FlextInfraConstantsSourceCode
from ._constants.workspace import FlextInfraConstantsWorkspace


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
