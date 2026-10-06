"""Generated Make authentication through explicit environment credentials.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from tests import c, p, t, u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeAuthentication:
    """Prove the one credential reaches tools and local operations need none."""

    @staticmethod
    def _probe_credential(
        tmp_path: Path,
        expected: str,
        env: t.StrMapping,
    ) -> p.Cli.CommandOutput:
        """Run a public verb whose tool child asserts every credential name.

        Returns:
            The successful make process output.

        """
        project_root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        tm.ok(u.Tests.create_python_environment(project_root))
        (project_root / "auth_probe.py").write_text(
            "import os, sys\n"
            "assert all(os.environ[name] == sys.argv[1] for name in "
            "('GITHUB_TOKEN', 'GH_TOKEN', 'MISE_GITHUB_TOKEN'))\n"
            "assert 'GITHUB_API_TOKEN' not in os.environ\n"
            "print('environment-authenticated')\n",
            encoding="utf-8",
        )
        (project_root / "custom.mk").write_text(
            "_custom-status:\n"
            '\t@"$(SETUP_MISE)" -C "$(PROJECT_ROOT)" exec -- '
            '"$(RUNTIME_PYTHON)" "$(PROJECT_ROOT)/auth_probe.py" '
            '"$(EXPECTED_CREDENTIAL)"\n',
            encoding="utf-8",
        )
        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "status"],
                cwd=project_root,
                env={"EXPECTED_CREDENTIAL": expected, **env},
            ),
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tm.that(process.stdout, has="environment-authenticated")
        tm.that(process.stdout + process.stderr, lacks=expected)
        return process

    @staticmethod
    def test_make_exports_the_caller_credential_under_every_name(
        tmp_path: Path,
    ) -> None:
        """GITHUB_TOKEN wins and replaces every inherited alias."""
        selected = "fixture-github-token"
        TestsFlextInfraCodegenMakeAuthentication._probe_credential(
            tmp_path,
            selected,
            {
                "GITHUB_TOKEN": selected,
                "GH_TOKEN": "stale-alias",
                "MISE_GITHUB_TOKEN": "stale-alias",
                "GITHUB_API_TOKEN": "stale-alias",
            },
        )

    @staticmethod
    @pytest.mark.parametrize("alias", ["GH_TOKEN", "MISE_GITHUB_TOKEN"])
    def test_make_promotes_an_alias_when_github_token_is_absent(
        tmp_path: Path,
        alias: str,
    ) -> None:
        """A caller that supplies only an alias authenticates every tool."""
        selected = "fixture-alias-token"
        TestsFlextInfraCodegenMakeAuthentication._probe_credential(
            tmp_path,
            selected,
            {alias: selected},
        )

    @staticmethod
    def test_make_reads_the_declared_credential_command(tmp_path: Path) -> None:
        """Without a caller credential, gh's stored token authenticates every tool."""
        selected = "fixture-gh-stored-token"
        gh_config = tmp_path / "gh-config"
        gh_config.mkdir()
        (gh_config / "hosts.yml").write_text(
            "github.com:\n"
            f"    oauth_token: {selected}\n"
            "    user: fixture\n"
            "    git_protocol: https\n",
            encoding="utf-8",
        )
        TestsFlextInfraCodegenMakeAuthentication._probe_credential(
            tmp_path / "project",
            selected,
            {"GH_CONFIG_DIR": str(gh_config)},
        )

    @staticmethod
    @pytest.mark.parametrize("verb", ["status", "help", "clean"])
    def test_local_verbs_need_no_credential(tmp_path: Path, verb: str) -> None:
        """Local public verbs complete without a GitHub credential."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        if verb == "status":
            tm.ok(u.Tests.create_python_environment(project_root))
            (project_root / "custom.mk").write_text(
                '_custom-status:\n\t@"$(RUNTIME_PYTHON)" -c "print(37)"\n',
                encoding="utf-8",
            )
        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", verb],
                cwd=project_root,
            ),
        )
        tm.that(u.Cli.process_succeeded(process.outcome), eq=True)
        tm.that(
            u.Infra.runtime_environment_dir(project_root).exists(),
            eq=verb == "status",
        )

    @staticmethod
    @pytest.mark.remote
    def test_setup_reuses_provisioned_tools_without_credential(
        tmp_path: Path,
        resolved_make_templates: t.MappingKV[c.Infra.MakeProfile, Path],
    ) -> None:
        """A locked checkout provisions its own environment without authentication.

        No GITHUB_TOKEN is set and the isolated harness leaves gh without a
        stored credential, so the bootstrap runs with no credential at all.
        """
        profile = c.Infra.MakeProfile.STANDALONE
        project_root = u.Tests.resolved_make_checkout(
            resolved_make_templates[profile],
            tmp_path,
            profile,
        )
        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "setup"],
                cwd=project_root,
            ),
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tm.that(u.Infra.runtime_environment_dir(project_root).exists(), eq=True)

    @staticmethod
    @pytest.mark.remote
    def test_invalid_explicit_token_fails_at_the_native_mise_backend(
        tmp_path: Path,
    ) -> None:
        """A selected invalid credential fails at the backend without a retry."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        # The credential proves itself only where mise actually consults it:
        # the GitHub artifact-attestation verification of a cold install. A
        # warm storage skips installation entirely and would never reach the
        # rejection, so the bootstrap runs on this fixture's own isolated
        # Mise storage.
        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "upg"],
                cwd=project_root,
                env={
                    "GITHUB_TOKEN": "invalid-test-credential",
                    u.Infra.mise_bootstrap_environment().storage_root_variable: str(
                        u.Tests.isolated_mise_bootstrap_storage(project_root),
                    ),
                },
            ),
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        # The loud failure must come from the mise backend stage itself. The
        # exact GitHub response body is external evidence, not the contract:
        # an invalid token measures `401 Unauthorized: Bad credentials`, and
        # fleet-load rate limiting measures `403` with a rate-limit body — the
        # run still dies loudly at the backend in both shapes.
        tm.that(process.stdout + process.stderr, has="mise ERROR")
        tm.that(process.stderr, lacks="GitHub credential is absent")
