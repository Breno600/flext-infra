"""Documentation, GitHub workflow, maintenance, and validation CLI route ownership.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from typing import TYPE_CHECKING, ClassVar

from flext_infra import c, m
from flext_infra.api import infra
from flext_infra.docs.auditor import FlextInfraDocAuditor
from flext_infra.docs.builder import FlextInfraDocBuilder
from flext_infra.docs.collector import FlextInfraDocCollector
from flext_infra.docs.fixer import FlextInfraDocFixer
from flext_infra.docs.formatter import FlextInfraDocFormatter
from flext_infra.docs.generator import FlextInfraDocGenerator
from flext_infra.docs.server import FlextInfraDocServer
from flext_infra.docs.validator import FlextInfraDocValidator
from flext_infra.maintenance.clean import FlextInfraCleanService
from flext_infra.maintenance.python_version import FlextInfraPythonVersionEnforcer
from flext_infra.maintenance.sonarcloud import FlextInfraSonarcloudSettingsSync
from flext_infra.maintenance.sonarcloud_issues import FlextInfraSonarcloudIssues
from flext_infra.services.cli_routes_validate_commands import (
    FlextInfraValidationCommandRoutes,
)

if TYPE_CHECKING:
    from flext_infra import t


class FlextInfraValidationRoutes(FlextInfraValidationCommandRoutes):
    """Own documentation, GitHub workflow, maintenance, and validation routes."""

    validation_routes: ClassVar[
        MutableMapping[str, t.VariadicTuple[m.Cli.ResultCommandRoute]]
    ] = {
        c.Infra.CLI_GROUP_DOCS: (
            m.Cli.ResultCommandRoute(
                name="collect",
                help_text=(
                    "Collect associated plan sources "
                    "and publish authenticated projections"
                ),
                model_cls=m.Infra.DocsCollectRequest,
                handler=FlextInfraValidationCommandRoutes.result_handler(
                    FlextInfraDocCollector.collect,
                ),
                success_message="Configured plan sources collected and published",
            ),
            m.Cli.ResultCommandRoute(
                name="generate",
                help_text="Generate project docs through the publication transaction",
                model_cls=m.Infra.DocsGenerateRequest,
                handler=FlextInfraValidationCommandRoutes.result_handler(
                    FlextInfraDocGenerator.execute_request,
                ),
                success_message="Generated documentation committed and verified",
            ),
            m.Cli.ResultCommandRoute(
                name="fmt",
                help_text=(
                    "Format documentation through the canonical markdown-format gate"
                ),
                model_cls=FlextInfraDocFormatter,
                handler=FlextInfraValidationCommandRoutes.result_handler(
                    infra.docs_format,
                ),
                success_message="Format completed successfully",
            ),
            *tuple(
                m.Cli.ResultCommandRoute(
                    name=route_name,
                    help_text=help_text,
                    model_cls=model_cls,
                    handler=FlextInfraValidationCommandRoutes.result_handler(
                        model_cls.execute_command,
                    ),
                    success_message=success_message,
                )
                for route_name, help_text, model_cls, success_message in (
                    (
                        "audit",
                        "Audit documentation for broken links and forbidden terms",
                        FlextInfraDocAuditor,
                        "Audit completed successfully",
                    ),
                    (
                        "fix",
                        "Fix documentation issues",
                        FlextInfraDocFixer,
                        "Fix completed successfully",
                    ),
                    (
                        "build",
                        "Build MkDocs sites",
                        FlextInfraDocBuilder,
                        "Build completed successfully",
                    ),
                    (
                        "serve",
                        "Serve one MkDocs site in dev mode (blocking preview)",
                        FlextInfraDocServer,
                        "Serve completed successfully",
                    ),
                    (
                        "validate",
                        "Validate documentation",
                        FlextInfraDocValidator,
                        "Validate completed successfully",
                    ),
                )
            ),
        ),
        c.Infra.CLI_GROUP_MAINTENANCE: (
            m.Cli.ResultCommandRoute(
                name=c.Infra.VERB_RUN,
                help_text="Enforce Python version constraints",
                model_cls=FlextInfraPythonVersionEnforcer,
                handler=FlextInfraPythonVersionEnforcer.execute_command,
                success_message="Maintenance completed",
            ),
            m.Cli.ResultCommandRoute(
                name=c.Infra.VERB_CLEAN,
                help_text="Report or remove disposable build artifacts",
                model_cls=FlextInfraCleanService,
                handler=FlextInfraCleanService.execute_command,
                success_message="Clean completed",
            ),
            m.Cli.ResultCommandRoute(
                name=c.Infra.VERB_SONARCLOUD_SYNC,
                help_text=(
                    "Write the SSOT SonarCloud issue exclusions to the server-side "
                    "project settings (requires SONAR_TOKEN)"
                ),
                model_cls=FlextInfraSonarcloudSettingsSync,
                handler=FlextInfraSonarcloudSettingsSync.execute_command,
                success_message="SonarCloud issue exclusions match the SSOT",
            ),
            m.Cli.ResultCommandRoute(
                name=c.Infra.VERB_SONARCLOUD_ISSUES,
                help_text=(
                    "Read unresolved new-code SonarCloud issues (requires SONAR_TOKEN)"
                ),
                model_cls=FlextInfraSonarcloudIssues,
                handler=FlextInfraSonarcloudIssues.execute_command,
                success_message="SonarCloud issue search completed",
            ),
        ),
        c.Infra.CLI_GROUP_VALIDATE: (
            FlextInfraValidationCommandRoutes.validate_command_routes
        ),
    }


__all__: list[str] = ["FlextInfraValidationRoutes"]
