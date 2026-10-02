"""Typed SonarCloud web API contracts for the server-side settings sync."""

from __future__ import annotations

from typing import Annotated, ClassVar

from flext_core import m
from flext_infra import t


class FlextInfraModelsSonarcloud:
    """Strict boundary models for the proven SonarCloud settings contract."""

    class SonarcloudIssueFieldValue(m.ContractModel):
        """One ``sonar.issue.ignore.multicriteria`` entry as the API spells it."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="forbid", frozen=True, populate_by_name=True
        )

        rule_key: Annotated[
            t.NonEmptyStr,
            m.Field(
                validation_alias="ruleKey",
                serialization_alias="ruleKey",
                description="Sonar rule key",
            ),
        ]
        resource_key: Annotated[
            t.NonEmptyStr,
            m.Field(
                validation_alias="resourceKey",
                serialization_alias="resourceKey",
                description="Project-relative resource",
            ),
        ]

    class SonarcloudSetting(m.ContractModel):
        """One setting returned by ``api/settings/values``.

        ``fieldValues`` contains the effective value, including inherited
        entries. Origin bookkeeping does not change which entries are active.
        Unread metadata is ignored rather than forbidden.
        """

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(
            extra="ignore", frozen=True, populate_by_name=True
        )

        key: Annotated[t.NonEmptyStr, m.Field(description="Setting key")]
        field_values: Annotated[
            t.VariadicTuple[FlextInfraModelsSonarcloud.SonarcloudIssueFieldValue],
            m.Field(
                validation_alias="fieldValues",
                serialization_alias="fieldValues",
                description="PROPERTY_SET entries",
            ),
        ] = ()

    class SonarcloudSettingsValues(m.ContractModel):
        """The ``api/settings/values`` response body."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        settings: Annotated[
            t.VariadicTuple[FlextInfraModelsSonarcloud.SonarcloudSetting],
            m.Field(description="Effective settings for the requested keys"),
        ]

    class SonarcloudAuthentication(m.ContractModel):
        """The ``api/authentication/validate`` response body."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        valid: Annotated[bool, m.Field(description="Whether the token is valid")]

    class SonarcloudSettingsPlan(m.ContractModel):
        """The complete server-side state one project must carry, from the SSOT."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="forbid", frozen=True)

        api_url: Annotated[t.NonEmptyStr, m.Field(description="Web API origin")]
        timeout_seconds: Annotated[
            t.PositiveInt, m.Field(description="Per-request timeout")
        ]
        project_key: Annotated[
            t.NonEmptyStr, m.Field(description="<organization>_<repository>")
        ]
        setting_key: Annotated[
            t.NonEmptyStr, m.Field(description="PROPERTY_SET setting key")
        ]
        field_values: Annotated[
            t.VariadicTuple[FlextInfraModelsSonarcloud.SonarcloudIssueFieldValue],
            m.Field(description="Entries in SSOT order; empty means reset"),
        ]

    class SonarcloudSettingsWriteRequest(m.ContractModel):
        """One complete POST request selected from a validated settings plan."""

        api_path: Annotated[t.NonEmptyStr, m.Field(description="Web API endpoint")]
        form: Annotated[
            t.VariadicTuple[t.Pair[str, str]],
            m.Field(min_length=2, description="Ordered form fields for the endpoint"),
        ]

    class SonarcloudIssue(m.ContractModel):
        """One issue in a SonarCloud issue-search response."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore", frozen=True)

        key: Annotated[t.NonEmptyStr, m.Field(description="Stable issue key")]
        rule: Annotated[t.NonEmptyStr, m.Field(description="Rule key")]
        component: Annotated[t.NonEmptyStr, m.Field(description="Project and file key")]
        line: Annotated[int | None, m.Field(description="Source line, when assigned")] = None
        message: Annotated[t.NonEmptyStr, m.Field(description="Observed finding")]

    class SonarcloudIssuePaging(m.ContractModel):
        """Server-side page accounting required before reporting completeness."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore", frozen=True)

        page_index: Annotated[t.PositiveInt, m.Field(validation_alias="pageIndex")]
        page_size: Annotated[t.PositiveInt, m.Field(validation_alias="pageSize")]
        total: Annotated[int, m.Field(ge=0)]

    class SonarcloudIssueSearch(m.ContractModel):
        """A complete typed page returned by ``api/issues/search``."""

        model_config: ClassVar[m.ConfigDict] = m.ConfigDict(extra="ignore", frozen=True)

        paging: FlextInfraModelsSonarcloud.SonarcloudIssuePaging
        issues: t.VariadicTuple[FlextInfraModelsSonarcloud.SonarcloudIssue]


__all__: list[str] = ["FlextInfraModelsSonarcloud"]
