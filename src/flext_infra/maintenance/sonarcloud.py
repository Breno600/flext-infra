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

from pathlib import Path
from typing import TYPE_CHECKING, override

from flext_core import r
from flext_infra import c, config, m, settings, t, u

from ..base import s

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraSonarcloudSettingsSync(s[bool]):
    """Converge one project's SonarCloud issue exclusions onto the SSOT.

    Every input — token, project key, SSOT exclusions — is validated before
    the first request. The setting is written only when the server value
    differs from the SSOT, then read back and compared; any divergence fails.
    """

    @staticmethod
    def required_token() -> p.Result[t.SecretStr]:
        """Return ``SONAR_TOKEN`` exactly as the process environment holds it."""
        token = settings.Infra.sonar_token
        if token is None or not token.get_secret_value().strip():
            return r[t.SecretStr].fail(
                "SONAR_TOKEN is required in the process environment and must "
                "not be empty or whitespace"
            )
        raw = token.get_secret_value()
        if raw != raw.strip():
            return r[t.SecretStr].fail(
                "SONAR_TOKEN carries surrounding whitespace; supply the exact token"
            )
        return r[t.SecretStr].ok(token)

    @staticmethod
    def project_key(repository_root: Path) -> p.Result[str]:
        """Derive ``<organization>_<repository>`` from the checkout's origin."""
        origin = u.Infra.git_remote_url(
            m.Infra.GitRemoteUrlRequest(repo_root=repository_root)
        )
        if origin.failure:
            return r[str].from_failure(origin)
        identity = u.Infra.git_remote_identity(origin.value.text)
        organization, _, repository = identity.partition("/")
        if not organization or not repository or "/" in repository:
            return r[str].fail(
                f"origin does not identify an organization and repository: {identity}"
            )
        return r[str].ok(
            f"{organization}{c.Infra.SONARCLOUD_PROJECT_KEY_SEPARATOR}{repository}"
        )

    @staticmethod
    def settings_plan(
        sonarcloud: m.Infra.SonarcloudSpec, project_key: str
    ) -> p.Result[m.Infra.SonarcloudSettingsPlan]:
        """Build the complete server state one project must carry."""
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
                "codegen.sonarcloud.issue_exclusions repeats a rule/resource pair"
            )
        return r[m.Infra.SonarcloudSettingsPlan].ok(
            m.Infra.SonarcloudSettingsPlan(
                api_url=sonarcloud.api_url,
                timeout_seconds=sonarcloud.api_timeout_seconds,
                project_key=project_key,
                setting_key=c.Infra.SONARCLOUD_ISSUE_IGNORE_KEY,
                field_values=values,
            )
        )

    @staticmethod
    def settings_write_request(
        plan: m.Infra.SonarcloudSettingsPlan,
    ) -> m.Infra.SonarcloudSettingsWriteRequest:
        """Select reset for an empty SSOT or set for its complete property set."""
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
        plan: m.Infra.SonarcloudSettingsPlan, current: m.Infra.SonarcloudSettingsValues
    ) -> t.VariadicTuple[m.Infra.SonarcloudIssueFieldValue]:
        """Read effective entries without excluding values inherited from a parent."""
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
        """Require every SSOT entry exactly once, regardless of server ordering."""
        values = cls.current_field_values(plan, current)
        return len(values) == len(plan.field_values) and frozenset(values) == frozenset(
            plan.field_values
        )

    @staticmethod
    def _call(
        plan: m.Infra.SonarcloudSettingsPlan,
        token: t.SecretStr,
        method: str,
        path: str,
        form: t.SequenceOf[t.Pair[str, str]],
    ) -> p.Result[str]:
        """Send one authenticated request to the plan's web API origin."""
        return u.Infra.http_bearer_text(
            method,
            f"{plan.api_url}{path}",
            bearer_token=token,
            form=form,
            timeout_seconds=plan.timeout_seconds,
        )

    @classmethod
    def _server_values(
        cls, plan: m.Infra.SonarcloudSettingsPlan, token: t.SecretStr
    ) -> p.Result[m.Infra.SonarcloudSettingsValues]:
        """Read the project's current value of the plan's setting."""
        body = cls._call(
            plan,
            token,
            "GET",
            c.Infra.SONARCLOUD_API_SETTINGS_VALUES_PATH,
            (("component", plan.project_key), ("keys", plan.setting_key)),
        )
        if body.failure:
            return r[m.Infra.SonarcloudSettingsValues].from_failure(body)
        return u.validate_value(
            m.Infra.SonarcloudSettingsValues, body.value, from_json=True
        )

    @override
    def execute(self) -> p.Result[bool]:
        """Converge the server value; the payload is whether a write happened."""
        token = self.required_token()
        if token.failure:
            return r[bool].from_failure(token)
        key = self.project_key(self.repository_root)
        if key.failure:
            return r[bool].from_failure(key)
        planned = self.settings_plan(config.Infra.codegen.sonarcloud, key.value)
        if planned.failure:
            return r[bool].from_failure(planned)
        plan = planned.value
        auth_body = self._call(
            plan, token.value, "GET", c.Infra.SONARCLOUD_API_AUTH_VALIDATE_PATH, ()
        )
        if auth_body.failure:
            return r[bool].from_failure(auth_body)
        auth = u.validate_value(
            m.Infra.SonarcloudAuthentication, auth_body.value, from_json=True
        )
        if auth.failure:
            return r[bool].from_failure(auth)
        if not auth.value.valid:
            return r[bool].fail("SonarCloud rejected SONAR_TOKEN as invalid")
        current = self._server_values(plan, token.value)
        if current.failure:
            return r[bool].from_failure(current)
        if self.in_sync_with(plan, current.value):
            u.Cli.info(f"sonarcloud-sync: {plan.project_key} already matches the SSOT")
            return r[bool].ok(False)
        request = self.settings_write_request(plan)
        written = self._call(plan, token.value, "POST", request.api_path, request.form)
        if written.failure:
            return r[bool].from_failure(written)
        readback = self._server_values(plan, token.value)
        if readback.failure:
            return r[bool].from_failure(readback)
        if not self.in_sync_with(plan, readback.value):
            held = ", ".join(
                value.model_dump_json(by_alias=True)
                for value in self.current_field_values(plan, readback.value)
            )
            return r[bool].fail(
                f"sonarcloud-sync: {plan.project_key} readback differs from the "
                f"SSOT; server holds [{held}]"
            )
        u.Cli.info(
            f"sonarcloud-sync: {plan.project_key} now holds "
            f"{len(plan.field_values)} SSOT issue exclusion(s)"
        )
        self.log.info(
            "sonarcloud_settings_synced",
            project_key=plan.project_key,
            exclusions=len(plan.field_values),
        )
        return r[bool].ok(True)


__all__: list[str] = ["FlextInfraSonarcloudSettingsSync"]
