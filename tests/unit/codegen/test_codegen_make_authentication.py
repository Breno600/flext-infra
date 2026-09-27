"""Generated Make authentication through the real GitHub and Mise boundaries."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeAuthentication:
    """Prove credentials reach managed tools and missing authentication fails."""

    @pytest.mark.parametrize(
        "credential_source", ["stored", "GH_TOKEN", "GITHUB_TOKEN"]
    )
    def test_make_authenticates_real_mise_without_interactive_login(
        self, tmp_path: Path, credential_source: str
    ) -> None:
        """A generated public verb supplies gh's credential to the real Mise child."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        tm.ok(u.Tests.create_python_environment(project_root))
        (project_root / "auth_probe.py").write_text(
            "import os, subprocess, sys\n"
            "from pathlib import Path\n"
            "credential = subprocess.run(['gh', 'auth', 'token'], "
            "check=True, capture_output=True, text=True).stdout.rstrip('\\n')\n"
            "assert credential\n"
            "assert all(os.environ[name] == credential for name in "
            "('GITHUB_TOKEN', 'GH_TOKEN', 'MISE_GITHUB_TOKEN'))\n"
            "assert all(os.environ[name] == str(Path(sys.argv[1]).parent) "
            "for name in ('GIT_CEILING_DIRECTORIES', 'MISE_CEILING_PATHS'))\n"
            "print('mise-authenticated')\n",
            encoding="utf-8",
        )
        (project_root / "custom.mk").write_text(
            "pre-setup:\n"
            '\t@"$(SETUP_MISE)" -C "$(PROJECT_ROOT)" exec -- '
            '"$(RUNTIME_PYTHON)" "$(PROJECT_ROOT)/auth_probe.py" '
            '"$(REPOSITORY_ROOT)"\n'
            "\t@exit 37\n"
            "_custom-status:\n"
            '\t@"$(SETUP_MISE)" -C "$(PROJECT_ROOT)" exec -- '
            '"$(RUNTIME_PYTHON)" "$(PROJECT_ROOT)/auth_probe.py" '
            '"$(REPOSITORY_ROOT)"\n',
            encoding="utf-8",
        )
        empty_config = tmp_path / "empty-gh-config"
        empty_config.mkdir()
        runner = project_root / "authenticated_make.py"
        runner.write_text(
            "import os, subprocess, sys\n"
            "credential = subprocess.run(['gh', 'auth', 'token'], "
            "check=True, capture_output=True, text=True).stdout.rstrip('\\n')\n"
            "assert credential\n"
            "environment = os.environ.copy()\n"
            "environment.pop('GH_TOKEN', None)\n"
            "environment.pop('GITHUB_TOKEN', None)\n"
            "if sys.argv[1] != 'stored':\n"
            f"    environment['GH_CONFIG_DIR'] = {str(empty_config)!r}\n"
            "    environment['GH_TOKEN'] = ''\n"
            "    environment['GITHUB_TOKEN'] = 'invalid-lower-precedence-token'\n"
            "    environment[sys.argv[1]] = credential\n"
            "    environment['GH_ENTERPRISE_TOKEN'] = ''\n"
            "    environment['GITHUB_ENTERPRISE_TOKEN'] = ''\n"
            f"    environment[{config.Infra.codegen.make.ci.variable!r}] = "
            f"{config.Infra.codegen.make.ci.value!r}\n"
            "verb = 'setup' if sys.argv[1] == 'stored' else 'status'\n"
            f"process = subprocess.run([{c.Infra.MAKE!r}, "
            "'--no-print-directory', verb], "
            "env=environment, capture_output=True, text=True)\n"
            "assert credential not in process.stdout\n"
            "assert credential not in process.stderr\n"
            "print(process.stdout, end='')\n"
            "print(process.stderr, end='', file=sys.stderr)\n"
            "sys.exit(process.returncode)\n",
            encoding="utf-8",
        )
        process = tm.ok(
            u.Cli.run_raw(
                [sys.executable, str(runner), credential_source],
                cwd=project_root,
                env={"MISE_GITHUB_TOKEN": "stale-token-must-not-reach-mise"},
                remove_env_keys=c.Tests.MAKE_ISOLATION_ENV_KEYS,
            )
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=credential_source != "stored",
            msg=process.stdout + process.stderr,
        )
        tm.that(process.stdout, has="mise-authenticated")
        if credential_source == "stored":
            tm.that(process.stderr, has="pre-setup] Error 37")

    @pytest.mark.parametrize("verb", ["setup", "upg", "status", "help", "clean"])
    def test_make_handles_missing_gh_auth_at_the_declared_boundary(
        self, tmp_path: Path, verb: str
    ) -> None:
        """Network bootstrap preserves credential-source failure; local verbs run."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
        )
        empty_config = tmp_path / "empty-gh-config"
        empty_config.mkdir()
        # The host gh reads its stored credential from the system keyring even
        # with an empty GH_CONFIG_DIR, so the fixture provisions the credential
        # source itself: a gh that holds no credential and fails like gh does.
        gh_bin = tmp_path / "gh-without-credential"
        u.Tests.write_executable(
            gh_bin / "gh",
            "#!/bin/sh\nprintf 'no oauth token found for github.com\\n' >&2\nexit 1\n",
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
                env={
                    "GH_CONFIG_DIR": str(empty_config),
                    "GH_TOKEN": "",
                    "GITHUB_TOKEN": "",
                    "GH_ENTERPRISE_TOKEN": "",
                    "GITHUB_ENTERPRISE_TOKEN": "",
                    "GH_HOST": "github.com",
                    "MISE_GITHUB_TOKEN": "must-not-be-a-fallback",
                    "PATH": os.pathsep.join((str(gh_bin), os.environ["PATH"])),
                    # gh reads a stored credential from the session keyring
                    # over D-Bus even with an empty GH_CONFIG_DIR, and finds
                    # the session bus on its own when the variable is unset;
                    # a bus address inside the sandbox leaves it none.
                    "DBUS_SESSION_BUS_ADDRESS": f"unix:path={tmp_path / 'no-bus'}",
                },
            )
        )
        if verb in {"setup", "upg"}:
            tm.that(process.outcome.raw_return_code, ne=0)
            tm.that(process.stderr, has="gh credential source failed")
            tm.that(process.stderr, lacks="missing or empty")
            tm.that(process.stderr, lacks="mise.version")
        else:
            tm.that(u.Cli.process_succeeded(process.outcome), eq=True)
        tm.that((project_root / ".venv").exists(), eq=verb == "status")

    @pytest.mark.remote
    def test_invalid_explicit_token_fails_at_the_native_mise_backend(
        self, tmp_path: Path
    ) -> None:
        """A selected invalid credential never falls back to a stored account."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path, c.Infra.MakeProfile.STANDALONE
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
                    "GH_TOKEN": "invalid-test-credential",
                    "GITHUB_TOKEN": "",
                    u.Infra.mise_bootstrap_environment().storage_root_variable: str(
                        u.Tests.isolated_mise_bootstrap_storage(project_root)
                    ),
                },
            )
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        # The loud failure must come from the mise backend stage itself. The
        # exact GitHub response body is external evidence, not the contract:
        # an invalid token measures `401 Unauthorized: Bad credentials`, and
        # fleet-load rate limiting measures `403` with a rate-limit body — the
        # run still dies loudly at the backend in both shapes.
        tm.that(process.stdout + process.stderr, has="mise ERROR")
        tm.that(process.stderr, lacks="gh credential source failed")
