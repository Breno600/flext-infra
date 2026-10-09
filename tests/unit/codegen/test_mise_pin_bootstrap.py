"""Exercise missing-pin recovery through native Mise and generated Make.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from flext_tests import tm

from flext_infra import config
from tests import u

pytestmark = pytest.mark.remote


class TestsFlextInfraMisePinBootstrap:
    """Setup stays frozen while upgrade can establish the first self pin."""

    @staticmethod
    def _project(tmp_path: Path) -> None:
        """Render the real bootstrap macro with the declared self-managed tool."""
        toolchain = config.Infra.codegen.toolchain
        template_root = u.Infra.codegen_templates_root(config.Infra.codegen)
        shutil.copyfile(
            template_root / "base" / "tool_bootstrap_recipe.j2",
            tmp_path / "tool_bootstrap_recipe.j2",
        )
        template = tmp_path / "bootstrap.j2"
        template.write_text(
            '{% from "tool_bootstrap_recipe.j2" import tool_bootstrap_recipe %}'
            '{{ tool_bootstrap_recipe("bootstrap", "$(PROJECT_ROOT)", '
            "toolchain.mise_selector, [toolchain.mise_selector], "
            '"printf recovered > recovered.txt", make) }}',
            encoding="utf-8",
        )
        recipe = tm.ok(u.Cli.template_render(template, config.Infra.codegen))
        (tmp_path / "Makefile").write_text(
            "PROJECT_ROOT := $(CURDIR)\n"
            "setup: bootstrap\n"
            "upg: TOOL_BOOTSTRAP_RESOLVE := 1\n"
            "upg: bootstrap\n" + recipe,
            encoding="utf-8",
        )
        (tmp_path / ".mise.toml").write_text(
            "[settings]\nlockfile = true\nlocked = true\n"
            "[tools]\n"
            f'"{toolchain.mise_selector}" = "{toolchain.mise_version}"\n',
            encoding="utf-8",
        )
        tm.ok(u.Cli.run_checked(["mise", "trust", str(tmp_path / ".mise.toml")]))

    def test_setup_preserves_a_missing_self_pin(self, tmp_path: Path) -> None:
        """Frozen setup cannot resolve a missing lock or start its lifecycle."""
        self._project(tmp_path)
        setup = tm.ok(u.Tests.run_isolated_make(["setup"], cwd=tmp_path))
        tm.that(u.Cli.process_succeeded(setup.outcome), eq=False)
        tm.that(setup.stderr, has="pins no")
        tm.that((tmp_path / "mise.lock").exists(), eq=False)
        tm.that((tmp_path / "recovered.txt").exists(), eq=False)

    @pytest.mark.slow
    def test_upgrade_recovers_a_missing_self_pin(self, tmp_path: Path) -> None:
        """Upgrade resolves the first pin and runs the verified native release."""
        self._project(tmp_path)
        upgrade = tm.ok(u.Tests.run_isolated_make(["upg"], cwd=tmp_path))
        tm.that(
            u.Cli.process_succeeded(upgrade.outcome),
            eq=True,
            msg=upgrade.stdout + upgrade.stderr,
        )
        tm.that((tmp_path / "mise.lock").exists(), eq=True)
        tm.that((tmp_path / "recovered.txt").read_text(), eq="recovered")

    @staticmethod
    def test_git_mirrors_use_native_uv_cache(tmp_path: Path) -> None:
        """Read each locked Git commit back from the locally provisioned mirror."""
        project = Path(__file__).resolve().parents[3]
        sources = u.Tests.locked_git_sources(project)
        mirrored = u.Tests.build_git_mirrors(project, tmp_path)
        tm.that(len(mirrored), eq=len(sources))
        for url, revision, commit in sources:
            parsed = urlsplit(url)
            mirror = tmp_path / parsed.netloc / parsed.path.lstrip("/")
            resolved = tm.ok(
                u.Cli.capture(
                    ["git", "rev-parse", f"refs/heads/{revision}"],
                    cwd=mirror,
                ),
            ).strip()
            tm.that(resolved, eq=commit)
