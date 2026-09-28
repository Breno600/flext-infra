"""Pure Pydantic settings declarations for flext-infra."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

from flext_cli import m, t


class FlextInfraSettingsModels:
    """Private namespace for validated settings payloads."""

    class Infra(m.BaseSettings):
        """Validated process-start settings owned by flext-infra."""

        # flext-wkii.4.15: validate every external alias before singleton export.
        model_config = m.SettingsConfigDict(
            env_prefix="",
            env_ignore_empty=True,
            case_sensitive=True,
            populate_by_name=True,
            frozen=True,
            extra="forbid",
        )

        standalone: Annotated[
            bool,
            m.Field(
                default=False,
                validation_alias="FLEXT_STANDALONE",
                description="Force standalone mode and skip workspace auto-detection.",
            ),
        ]
        repository_root: Annotated[
            Path | None,
            m.Field(
                default=None,
                validation_alias="FLEXT_REPOSITORY_ROOT",
                description="Explicit repository root for dependency orchestration.",
            ),
        ]
        use_https: Annotated[
            bool,
            m.Field(
                default=False,
                validation_alias="FLEXT_USE_HTTPS",
                description="Prefer HTTPS repository URLs during dependency sync.",
            ),
        ]
        github_actions: Annotated[
            bool,
            m.Field(
                default=False,
                validation_alias="GITHUB_ACTIONS",
                description="Whether the process runs in GitHub Actions.",
            ),
        ]
        github_head_ref: Annotated[
            str | None,
            m.Field(
                default=None,
                validation_alias="GITHUB_HEAD_REF",
                description="GitHub Actions head ref for dependency sync.",
            ),
        ]
        github_ref_name: Annotated[
            str | None,
            m.Field(
                default=None,
                validation_alias="GITHUB_REF_NAME",
                description="GitHub Actions ref name for dependency sync.",
            ),
        ]
        uv_executable: Annotated[
            str | None,
            m.Field(
                default=None,
                validation_alias="UV",
                description="uv launcher path resolved for dependency orchestration.",
            ),
        ]
        virtual_env: Annotated[
            str | None,
            m.Field(
                default=None,
                validation_alias="VIRTUAL_ENV",
                description="Active virtualenv root for promoted Python commands.",
            ),
        ]
        dispatch_what: Annotated[
            str | None,
            m.Field(
                default=None,
                validation_alias="WHAT",
                description="Make-dispatch WHAT verb for promoted commands.",
            ),
        ]
        cosmos_command_dispatched: Annotated[
            str | None,
            m.Field(
                default=None,
                validation_alias="COSMOS_COMMAND_DISPATCHED",
                description="Gas City command-dispatch marker for promoted verbs.",
            ),
        ]
        cosmos_command_path: Annotated[
            str | None,
            m.Field(
                default=None,
                validation_alias="COSMOS_COMMAND_PATH",
                description="Gas City command path for promoted verb dispatch.",
            ),
        ]
        system_path: Annotated[
            str | None,
            m.Field(
                default=None,
                validation_alias="PATH",
                description="Process PATH captured for isolated subprocess builds.",
            ),
        ]
        sonar_token: Annotated[
            t.SecretStr | None,
            m.Field(
                default=None,
                validation_alias="SONAR_TOKEN",
                description=(
                    "SonarCloud web API token; required only by the explicit "
                    "sonarcloud-sync verb, never read from any other source."
                ),
            ),
        ]
        mise_github_credential_command: Annotated[
            str | None,
            m.Field(
                default=None,
                validation_alias="MISE_GITHUB_CREDENTIAL_COMMAND",
                description="Mise credential command forwarded to isolated builds.",
            ),
        ]


__all__: list[str] = ["FlextInfraSettingsModels"]
