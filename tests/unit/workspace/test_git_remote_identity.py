"""HTTPS, SSH, and deploy-key host aliases share one repository identity."""

from __future__ import annotations

from flext_tests import tm

from tests import u


class TestsFlextInfraGitRemoteIdentity:
    """Private CI may rewrite origin to aliased SSH without changing the repo."""

    def test_https_ssh_and_host_alias_urls_match(self) -> None:
        repository = u.Tests.repository_ref("remote-identity")
        expected = f"{u.Tests.provider().organization}/{repository.name}"
        https = repository.url
        ssh = f"git@github.com:{expected}.git"
        alias = f"git@provider-alias:{expected}.git"
        identity = u.Infra.git_remote_identity(https)
        tm.that(identity, eq=expected)
        tm.that(u.Infra.git_remote_identity(ssh), eq=identity)
        tm.that(u.Infra.git_remote_identity(alias), eq=identity)

    def test_different_repositories_do_not_match(self) -> None:
        left = u.Tests.repository_ref("left-repository").url
        right = u.Tests.repository_ref("right-repository").url
        tm.that(
            u.Infra.git_remote_identity(left) == u.Infra.git_remote_identity(right),
            eq=False,
        )
