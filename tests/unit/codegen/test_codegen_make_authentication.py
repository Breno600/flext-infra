"""Generated Make authentication through explicit environment credentials.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
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
            "import os\n"
            "assert all(os.environ[name] == os.environ['EXPECTED_CREDENTIAL'] "
            "for name in ('GITHUB_TOKEN', 'GH_TOKEN', 'MISE_GITHUB_TOKEN'))\n"
            "assert 'GITHUB_API_TOKEN' not in os.environ\n"
            "print('environment-authenticated')\n",
            encoding="utf-8",
        )
        (project_root / "custom.mk").write_text(
            "_custom-status:\n"
            "\t@$(GITHUB_AUTH_DIAGNOSTICS)\n"
            '\t@mise -C "$(PROJECT_ROOT)" exec -- '
            '"$(RUNTIME_PYTHON)" "$(PROJECT_ROOT)/auth_probe.py"\n',
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
        source = next(
            (
                name
                for name in ("GITHUB_TOKEN", "GH_TOKEN", "MISE_GITHUB_TOKEN")
                if env.get(name)
            ),
            "gh",
        )
        extraction = "0" if source == "gh" else "not-selected"
        tm.that(
            process.stdout,
            has=f"github-auth source={source} extraction-exit={extraction} present=yes",
        )
        tm.that(
            process.stdout,
            has=(
                "github-auth source=GITHUB_TOKEN "
                "extraction-exit=not-selected present=yes"
            ),
        )
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
        process = TestsFlextInfraCodegenMakeAuthentication._probe_credential(
            tmp_path / "project",
            selected,
            {"GH_CONFIG_DIR": str(gh_config)},
        )
        tm.that(process.stdout, has="command-exit=0 command=")
        tm.that(process.stdout, has="physical-command=")
        tm.that(process.stdout, has="gh-config-override=yes")

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
        if verb == "status":
            tm.that(process.stdout, has="github-auth source=gh extraction-exit=")
            tm.that(process.stdout, has="present=no ci=unset")
        tm.that(
            u.Infra.runtime_environment_dir(project_root).exists(),
            eq=verb == "status",
        )

    @staticmethod
    @pytest.mark.parametrize("verb", ["setup", "upg"])
    @pytest.mark.parametrize("local_ci", [False, True])
    def test_network_bootstrap_retains_credential_failure_before_first_lock(
        tmp_path: Path,
        verb: str,
        *,
        local_ci: bool,
    ) -> None:
        """Real gh failure stops public provisioning before Mise can write locks."""
        profile = c.Infra.MakeProfile.STANDALONE
        project_root, _ = u.Tests.render_make_environment(
            tmp_path,
            profile,
        )
        locks = {
            path: path.read_bytes()
            for path in (
                project_root / c.Infra.MISE_LOCK_FILENAME,
                project_root / "uv.lock",
            )
            if path.exists()
        }
        ci = config.Infra.codegen.make.ci
        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", verb],
                cwd=project_root,
                env={ci.variable: ci.local_value} if local_ci else None,
            ),
        )
        tm.that(u.Cli.process_succeeded(process.outcome), eq=False)
        diagnostic = next(
            line
            for line in process.stdout.splitlines()
            if line.startswith("github-auth ")
        )
        tm.that(diagnostic, has="source=gh")
        tm.that(diagnostic, has="present=no")
        tm.that(
            diagnostic,
            has=f"ci={'local' if local_ci else 'unset'}",
        )
        extraction_exit = diagnostic.split("extraction-exit=", 1)[1].split()[0]
        tm.that(int(extraction_exit), ne=0)
        tm.that(
            process.stderr,
            has=f"selected gh auth token failed (exit {extraction_exit})",
        )
        tm.that(process.stderr, has=f"Error {extraction_exit}")
        tm.that(process.stdout + process.stderr, lacks="oauth_token")
        tm.that(u.Infra.runtime_environment_dir(project_root).exists(), eq=False)
        for path, content in locks.items():
            tm.that(path.read_bytes(), eq=content)
