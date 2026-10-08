"""SonarCloud server-side issue exclusions written from the ``codegen`` SSOT.

SonarCloud automatic analysis ignores ``sonar.issue.ignore.*`` in
``.sonarcloud.properties`` and honors only the project setting
``sonar.issue.ignore.multicriteria``. ``codegen.sonarcloud.issue_exclusions``
is that setting's single fleet owner; this service converges one project's
server value onto it through the proven web API contract (bead flext-c8yle).

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from flext_infra import c, config, m, r, t, u
from flext_infra.maintenance.sonarcloud_client import FlextInfraSonarcloudClient

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraSonarcloudSettingsSync(FlextInfraSonarcloudClient[bool]):
    """Converge one project's SonarCloud issue exclusions onto the SSOT.

    Every input — token, project key, SSOT exclusions — is validated before
    the first request. The setting is written only when the server value
    differs from the SSOT, then read back and compared; any divergence fails.
    """

    @staticmethod
    def settings_plan(
        sonarcloud: m.Infra.SonarcloudSpec,
        project_key: str,
    ) -> p.Result[m.Infra.SonarcloudSettingsPlan]:
        """Build the complete server state one project must carry.

        Returns:
            The resulting ``p.Result[m.Infra.SonarcloudSettingsPlan]``.

        """
        # model_validate by field name: the constructor signature type checkers
        # synthesize speaks the wire aliases, which only the API boundary uses.
        values = tuple(
            m.Infra.SonarcloudIssueFieldValue.model_validate({
                "rule_key": exclusion.rule_key,
                "resource_key": exclusion.resource_key,
            })
            for exclusion in sonarcloud.issue_exclusions
        )
        if len(frozenset(values)) != len(values):
            return r[m.Infra.SonarcloudSettingsPlan].fail(
                "codegen.sonarcloud.issue_exclusions repeats a rule/resource pair",
            )
        return r[m.Infra.SonarcloudSettingsPlan].ok(
            m.Infra.SonarcloudSettingsPlan(
                api_url=sonarcloud.api_url,
                timeout_seconds=sonarcloud.api_timeout_seconds,
                project_key=project_key,
                setting_key=c.Infra.SONARCLOUD_ISSUE_IGNORE_KEY,
                field_values=values,
            ),
        )

    @staticmethod
    def settings_write_request(
        plan: m.Infra.SonarcloudSettingsPlan,
    ) -> m.Infra.SonarcloudSettingsWriteRequest:
        """Select reset for an empty SSOT or set for its complete property set.

        Returns:
            The resulting ``m.Infra.SonarcloudSettingsWriteRequest``.

        """
        if not plan.field_values:
            return m.Infra.SonarcloudSettingsWriteRequest(
                api_path=c.Infra.SONARCLOUD_API_SETTINGS_RESET_PATH,
                form=(("component", plan.project_key), ("keys", plan.setting_key)),
            )
        return m.Infra.SonarcloudSettingsWriteRequest(
            api_path=c.Infra.SONARCLOUD_API_SETTINGS_SET_PATH,
            form=(
                ("component", plan.project_key),
                ("key", plan.setting_key),
                *(
                    ("fieldValues", value.model_dump_json(by_alias=True))
                    for value in plan.field_values
                ),
            ),
        )

    @staticmethod
    def current_field_values(
        plan: m.Infra.SonarcloudSettingsPlan,
        current: m.Infra.SonarcloudSettingsValues,
    ) -> t.VariadicTuple[m.Infra.SonarcloudIssueFieldValue]:
        """Read effective entries without excluding values inherited from a parent.

        Returns:
            The resulting ``t.VariadicTuple[m.Infra.SonarcloudIssueFieldValue]``.

        """
        return tuple(
            value
            for setting in current.settings
            if setting.key == plan.setting_key
            for value in setting.field_values
        )

    @classmethod
    def in_sync_with(
        cls,
        plan: m.Infra.SonarcloudSettingsPlan,
        current: m.Infra.SonarcloudSettingsValues,
    ) -> bool:
        """Require every SSOT entry exactly once, regardless of server ordering.

        Returns:
            The resulting ``bool``.

        """
        values = cls.current_field_values(plan, current)
        return len(values) == len(plan.field_values) and frozenset(values) == frozenset(
            plan.field_values,
        )

    @classmethod
    def _server_values(
        cls,
        plan: m.Infra.SonarcloudSettingsPlan,
        token: t.SecretStr,
    ) -> p.Result[m.Infra.SonarcloudSettingsValues]:
        """Read the project's current value of the plan's setting.

        Returns:
            The resulting ``p.Result[m.Infra.SonarcloudSettingsValues]``.
        """
        body = cls.call(
            plan.api_url,
            plan.timeout_seconds,
            token,
            (
                "GET",
                c.Infra.SONARCLOUD_API_SETTINGS_VALUES_PATH,
                (("component", plan.project_key), ("keys", plan.setting_key)),
            ),
        )
        if body.failure:
            return r[m.Infra.SonarcloudSettingsValues].from_failure(body)
        return u.validate_value(
            m.Infra.SonarcloudSettingsValues,
            body.value,
            from_json=True,
        )

    def _write_settings(
        self,
        plan: m.Infra.SonarcloudSettingsPlan,
        token: t.SecretStr,
    ) -> p.Result[bool]:
        """Write the SSOT settings, then prove the server readback holds them.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        request = self.settings_write_request(plan)
        written = self.call(
            plan.api_url,
            plan.timeout_seconds,
            token,
            ("POST", request.api_path, request.form),
        )
        if written.failure:
            return r[bool].from_failure(written)
        readback = self._server_values(plan, token)
        if readback.failure:
            return r[bool].from_failure(readback)
        diverged = self._readback_divergence(plan, readback.value)
        if diverged is not None:
            return diverged
        u.Cli.info(
            f"sonarcloud-sync: {plan.project_key} now holds "
            f"{len(plan.field_values)} SSOT issue exclusion(s)",
        )
        self.log.info(
            "sonarcloud_settings_synced",
            project_key=plan.project_key,
            exclusions=len(plan.field_values),
        )
        return r[bool].ok(value=True)

    def _readback_divergence(
        self,
        plan: m.Infra.SonarcloudSettingsPlan,
        readback: m.Infra.SonarcloudSettingsValues,
    ) -> p.Result[bool] | None:
        """Report the divergent server state after a write, or ``None`` when synced.

        Returns:
            The divergence failure, or ``None`` when the server now holds the SSOT.

        """
        if self.in_sync_with(plan, readback):
            return None
        held = ", ".join(
            value.model_dump_json(by_alias=True)
            for value in self.current_field_values(plan, readback)
        )
        return r[bool].fail(
            f"sonarcloud-sync: {plan.project_key} readback differs from the "
            f"SSOT; server holds [{held}]",
        )

    def _authenticate(
        self,
        plan: m.Infra.SonarcloudSettingsPlan,
        token: t.SecretStr,
    ) -> p.Result[bool]:
        """Prove the configured token against SonarCloud's auth validate endpoint.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        auth_body = self.call(
            plan.api_url,
            plan.timeout_seconds,
            token,
            ("GET", c.Infra.SONARCLOUD_API_AUTH_VALIDATE_PATH, ()),
        )
        if auth_body.failure:
            return r[bool].from_failure(auth_body)
        auth = u.validate_value(
            m.Infra.SonarcloudAuthentication,
            auth_body.value,
            from_json=True,
        )
        if auth.failure:
            return r[bool].from_failure(auth)
        if not auth.value.valid:
            return r[bool].fail("SonarCloud rejected SONAR_TOKEN as invalid")
        return r[bool].ok(value=True)

    @override
    def execute(self) -> p.Result[bool]:
        """Converge the server value; the payload is whether a write happened.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        credentials = self.project_credentials()
        if credentials.failure:
            return r[bool].from_failure(credentials)
        token, key = credentials.value
        planned = self.settings_plan(config.Infra.codegen.sonarcloud, key)
        if planned.failure:
            return r[bool].from_failure(planned)
        plan = planned.value
        authentication = self._authenticate(plan, token)
        if authentication.failure:
            return r[bool].from_failure(authentication)
        current = self._server_values(plan, token)
        if current.failure:
            return r[bool].from_failure(current)
        if self.in_sync_with(plan, current.value):
            u.Cli.info(f"sonarcloud-sync: {plan.project_key} already matches the SSOT")
            return r[bool].ok(value=False)
        return self._write_settings(plan, token)


__all__: list[str] = ["FlextInfraSonarcloudSettingsSync"]
