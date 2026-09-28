"""Behavior tests for local SSH-signed gate attestations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from flext_cli import u as cli_u
from flext_tests import tm

from flext_infra import c, m, p, u
from tests import u as test_u


class TestsFlextInfraGithubGateAttestation:
    """Behavior tests for local SSH-signed gate attestations."""

    def _signed_repository(self, root: Path) -> Path:
        test_u.Tests.git_bootstrap(root, ("init", "-b", c.Infra.GIT_MAIN))
        for key, value in (
            ("user.name", "Attestation Test"),
            ("user.email", "attestation@example.test"),
            ("gpg.format", "ssh"),
            ("commit.gpgsign", "false"),
        ):
            test_u.Tests.git_bootstrap(root, ("config", key, value))
        test_u.Tests.git_bootstrap(
            root,
            (
                "remote",
                "add",
                c.Infra.GIT_ORIGIN,
                "https://github.example/flext/fixture.git",
            ),
        )
        key_path = root / "signing_key"
        tm.ok(
            cli_u.Cli.run_raw(
                ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key_path)],
                cwd=root,
            )
        )
        test_u.Tests.git_bootstrap(root, ("config", "user.signingkey", str(key_path)))
        (root / "tracked.txt").write_text("attested\n", encoding="utf-8")
        (root / "Makefile").write_text(
            ".PHONY: gen check test\n"
            "gen:\n\t@printf 'gen ok\\n'\n"
            "check:\n\t@printf 'check ok\\n'\n"
            "test:\n\t@printf 'test ok\\n'\n",
            encoding="utf-8",
        )
        (root / "pyproject.toml").write_text(
            "[project]\nname='fixture'\n", encoding="utf-8"
        )
        tm.ok(
            u.Infra.git_add_paths(
                m.Infra.GitPathsRequest(
                    repo_root=root, paths=("Makefile", "pyproject.toml", "tracked.txt")
                )
            )
        )
        tm.ok(
            u.Infra.git_commit(
                m.Infra.GitCommitRequest(
                    repo_root=root, message="test: create base revision"
                )
            )
        )
        allowed_signers = root / "allowed_signers"
        public_key = key_path.with_suffix(".pub").read_text(encoding="utf-8").strip()
        allowed_signers.write_text(
            f"attester@example.test {public_key}\n", encoding="utf-8"
        )
        return allowed_signers

    def _head(self, root: Path) -> str:
        oid: str = tm.ok(
            u.Infra.git_repository_head(m.Infra.GitRepoRequest(repo_root=root))
        ).oid
        return oid

    def _rev_parse(self, root: Path, commitish: str) -> str:
        oid: str = tm.ok(
            u.Infra.git_rev_parse(
                m.Infra.GitCommitishRequest(repo_root=root, commitish=commitish)
            )
        ).oid
        return oid

    @pytest.fixture
    def signed_repository_factory(self) -> Callable[[Path], Path]:
        """Create one SSH-signing fixture repository per test invocation."""
        return self._signed_repository

    def _request(self, root: Path) -> m.Infra.GateAttestationCreateRequest:
        return m.Infra.GateAttestationCreateRequest(
            workspace=str(root),
            signer="attester@example.test",
            gates=("gen", "check", "test"),
        )

    def _verify(
        self, root: Path, allowed_signers: Path, commit_sha: str, *gates: str
    ) -> p.Result[m.Infra.GateAttestationReport]:
        return u.Infra.git_verify_gate_attestation(
            m.Infra.GateAttestationVerifyRequest(
                workspace=str(root),
                allowed_signers=str(allowed_signers),
                expected_gates=gates,
                commit_sha=commit_sha,
            )
        )

    def test_signed_gate_attestation_round_trip_is_local(
        self, tmp_path: Path, signed_repository_factory: Callable[[Path], Path]
    ) -> None:
        allowed_signers = signed_repository_factory(tmp_path)
        created = u.Infra.git_create_gate_attestation(self._request(tmp_path))

        tm.ok(created)
        head = self._head(tmp_path)
        tm.that(created.unwrap().tag, eq=f"attest/gates/v1/{head}")
        tm.that(self._rev_parse(tmp_path, f"{created.unwrap().tag}^{{}}"), eq=head)
        verified = self._verify(tmp_path, allowed_signers, head, "gen", "check", "test")
        tm.ok(verified)
        tm.that(verified.unwrap().signer, eq="attester@example.test")

    def test_gate_attestation_normalizes_network_remote_git_suffix(
        self, tmp_path: Path, signed_repository_factory: Callable[[Path], Path]
    ) -> None:
        allowed_signers = signed_repository_factory(tmp_path)
        tm.ok(u.Infra.git_create_gate_attestation(self._request(tmp_path)))
        remote = tm.ok(
            u.Infra.git_remote_url(m.Infra.GitRemoteUrlRequest(repo_root=tmp_path))
        ).text
        test_u.Tests.git_bootstrap(
            tmp_path,
            ("remote", "set-url", c.Infra.GIT_ORIGIN, remote.removesuffix(".git")),
        )

        tm.ok(
            self._verify(
                tmp_path, allowed_signers, self._head(tmp_path), "gen", "check", "test"
            )
        )

    def test_gate_attestation_verifies_selected_commit_with_equal_tree(
        self, tmp_path: Path, signed_repository_factory: Callable[[Path], Path]
    ) -> None:
        allowed_signers = signed_repository_factory(tmp_path)
        tm.ok(u.Infra.git_create_gate_attestation(self._request(tmp_path)))
        selected_sha = self._head(tmp_path)
        selected_tree = self._rev_parse(tmp_path, "HEAD^{tree}")
        tm.ok(
            u.Infra.git_commit(
                m.Infra.GitCommitRequest(
                    repo_root=tmp_path, message="test: later equal-tree commit"
                )
            )
        )
        tm.that(self._rev_parse(tmp_path, "HEAD^{tree}"), eq=selected_tree)

        verified = self._verify(
            tmp_path, allowed_signers, selected_sha, "gen", "check", "test"
        )
        tm.ok(verified)
        tm.that(verified.unwrap().commit_sha, eq=selected_sha)

    def test_gate_attestation_rejects_incomplete_coverage(
        self, tmp_path: Path, signed_repository_factory: Callable[[Path], Path]
    ) -> None:
        allowed_signers = signed_repository_factory(tmp_path)
        tm.ok(u.Infra.git_create_gate_attestation(self._request(tmp_path)))

        verified = self._verify(
            tmp_path, allowed_signers, self._head(tmp_path), "check"
        )

        tm.fail(verified)
        tm.that(verified.error or "", has="exactly match")

    def test_gate_attestation_rejects_duplicate_gate_coverage(
        self, tmp_path: Path, signed_repository_factory: Callable[[Path], Path]
    ) -> None:
        _allowed_signers = signed_repository_factory(tmp_path)
        values = self._request(tmp_path).model_dump()
        values["gates"] = ("gen", "check", "test", "test")

        with pytest.raises(ValueError, match="gates must be unique"):
            m.Infra.GateAttestationCreateRequest.model_validate(values)
