"""HTTPS, SSH, and deploy-key host aliases share one repository identity.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from flext_tests import tm

from tests import u


class TestsFlextInfraGitRemoteIdentity:
    """Private CI may rewrite origin to aliased SSH without changing the repo."""

    @staticmethod
    def test_https_ssh_and_host_alias_urls_match() -> None:
        """Test https ssh and host alias urls match."""
        repository = u.Tests.repository_ref("remote-identity")
        expected = f"{u.Tests.provider().organization}/{repository.name}"
        https = repository.url
        ssh = f"git@github.com:{expected}.git"
        alias = f"git@provider-alias:{expected}.git"
        identity = u.Infra.git_remote_identity(https)
        tm.that(identity, eq=expected)
        tm.that(u.Infra.git_remote_identity(ssh), eq=identity)
        tm.that(u.Infra.git_remote_identity(alias), eq=identity)

    @staticmethod
    def test_different_repositories_do_not_match() -> None:
        """Test different repositories do not match."""
        left = u.Tests.repository_ref("left-repository").url
        right = u.Tests.repository_ref("right-repository").url
        tm.that(
            u.Infra.git_remote_identity(left) == u.Infra.git_remote_identity(right),
            eq=False,
        )
