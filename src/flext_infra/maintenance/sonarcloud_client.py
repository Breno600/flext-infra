"""Shared authenticated SonarCloud web API boundary for maintenance services.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from flext_infra import c, m, r, settings, t, u
from flext_infra.base import s

if TYPE_CHECKING:
    from flext_infra import p


class FlextInfraSonarcloudClient[TResult: t.Cli.ResultValue](s[TResult]):
    """Derive one project identity and authenticate without persisting secrets."""

    @staticmethod
    def required_token() -> p.Result[t.SecretStr]:
        """Return ``SONAR_TOKEN`` exactly as the process environment holds it."""
        token = settings.Infra.sonar_token
        if token is None or not token.get_secret_value().strip():
            return r[t.SecretStr].fail(
                "SONAR_TOKEN is required in the process environment and must "
                "not be empty or whitespace",
            )
        raw = token.get_secret_value()
        if raw != raw.strip():
            return r[t.SecretStr].fail(
                "SONAR_TOKEN carries surrounding whitespace; supply the exact token",
            )
        return r[t.SecretStr].ok(token)

    @staticmethod
    def project_key(repository_root: Path) -> p.Result[str]:
        """Derive ``<organization>_<repository>`` from the checkout's origin.

        Returns:
            The resulting ``p.Result[str]``.
        """
        origin = u.Infra.git_remote_url(
            m.Infra.GitRemoteUrlRequest(repo_root=repository_root),
        )
        if origin.failure:
            return r[str].from_failure(origin)
        identity = u.Infra.git_remote_identity(origin.value.text)
        organization, _, repository = identity.partition("/")
        if not organization or not repository or "/" in repository:
            return r[str].fail(
                f"origin does not identify an organization and repository: {identity}",
            )
        return r[str].ok(
            f"{organization}{c.Infra.SONARCLOUD_PROJECT_KEY_SEPARATOR}{repository}",
        )

    @staticmethod
    def call(
        api_url: str,
        timeout_seconds: int,
        token: t.SecretStr,
        method: str,
        path: str,
        form: t.SequenceOf[t.Pair[str, str]],
    ) -> p.Result[str]:
        """Send one authenticated request to the configured web API origin.

        Returns:
            The resulting ``p.Result[str]``.
        """
        return u.Infra.http_bearer_text(
            method,
            f"{api_url}{path}",
            bearer_token=token,
            form=form,
            timeout_seconds=timeout_seconds,
        )


__all__: list[str] = ["FlextInfraSonarcloudClient"]
