"""Generated Make upgrade lifecycle and lock ownership contract.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config
from tests import c, t, u


class TestsFlextInfraCodegenMakeUpgrade:
    """Prove only ``upg`` resolves locks and publishes them transactionally."""

    @staticmethod
    @pytest.mark.remote
    @pytest.mark.slow
    def test_upg_replaces_newer_lock_revision_before_older_mise_reads_it(
        tmp_path: Path,
        resolved_make_templates: t.MappingKV[c.Infra.MakeProfile, Path],
    ) -> None:
        """The public upgrade recovers a v3 lock with a v2 Mise release."""
        profile = c.Infra.MakeProfile.STANDALONE
        project_root = u.Tests.resolved_make_checkout(
            resolved_make_templates[profile],
            tmp_path / "lock-revision",
            profile,
        )
        lock = project_root / c.Infra.MISE_LOCK_FILENAME
        previous = lock.read_text(encoding="utf-8")
        tm.that(previous, has="lockfile_version = 2")
        lock.write_text(
            previous.replace("lockfile_version = 2", "lockfile_version = 3", 1),
            encoding="utf-8",
        )

        upgraded = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "upg"],
                cwd=project_root,
            ),
        )

        tm.that(
            u.Cli.process_succeeded(upgraded.outcome),
            eq=True,
            msg=upgraded.stdout + upgraded.stderr,
        )
        tm.that(lock.read_text(encoding="utf-8"), has="lockfile_version = 2")
        tm.that(upgraded.stdout, has="setup probe: end stage=publish-lock.log exit=0")

    @staticmethod
    @pytest.mark.remote
    @pytest.mark.slow
    def test_failed_upg_lock_preserves_runtime_and_retires_own_stage(
        tmp_path: Path,
        resolved_make_templates: t.MappingKV[c.Infra.MakeProfile, Path],
    ) -> None:
        """A failed real Mise lock cannot strand a stale resolved lock."""
        profile = c.Infra.MakeProfile.STANDALONE
        project_root = u.Tests.resolved_make_checkout(
            resolved_make_templates[profile],
            tmp_path / "lock-failure",
            profile,
        )
        lock = project_root / c.Infra.MISE_LOCK_FILENAME
        previous_lock = lock.read_bytes()
        (project_root / c.Infra.MISE_TOML_FILENAME).write_text(
            "[tools\n",
            encoding="utf-8",
        )

        upgraded = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "upg"],
                cwd=project_root,
            ),
        )

        tm.that(u.Cli.process_succeeded(upgraded.outcome), eq=False)
        tm.that(upgraded.stderr, has="setup probe: failed stage=lock.log")
        tm.that(lock.read_bytes(), eq=previous_lock)
        tm.that(
            list(project_root.parent.glob(f".{project_root.name}.mise-lock-stage.*")),
            eq=[],
        )

    @staticmethod
    def _recipe_targets_containing(
        makefile: str,
        needle: str,
        *,
        regex: bool = False,
    ) -> set[str]:
        """Return every rule target whose recipe (not comments) carries *needle*.

        Returns:
            Every rule target whose recipe (not comments) carries *needle*.

        """
        targets: set[str] = set()
        current: str | None = None
        continued = False
        for line in makefile.splitlines():
            if line.startswith("\t") or continued:
                if (
                    current is not None
                    and not line.lstrip().startswith("#")
                    and (
                        re.search(needle, line) is not None
                        if regex
                        else needle in line
                    )
                ):
                    targets.add(current)
                continued = line.endswith("\\")
                continue
            continued = False
            header = re.match(r"^([A-Za-z0-9_.$()%-]+)\s*:(?![=:])", line)
            current = header.group(1) if header else None
        return targets

    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_upg_is_the_only_resolver_and_setup_installs_frozen(
        self,
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
    ) -> None:
        """Operator law 2026-09-24: only `upg` resolves and writes the locks.

        The generated Makefile confines every uv upgrade to the `upg`
        lifecycle and every `mise lock --bump` to that lifecycle or its shared
        bootstrap gated by a switch that only `upg` sets; `setup` syncs
        `--locked`, and the generated `.mise.toml` makes mise install exactly
        what the lock pins.
        """
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            profile,
            bootstrap=True,
        )
        makefile = (project_root / c.Infra.MAKEFILE_FILENAME).read_text(
            encoding="utf-8",
        )

        tm.that(
            self._recipe_targets_containing(
                makefile,
                r"\$\(UV\)\s+lock\b[^\n]*--upgrade\b",
                regex=True,
            ),
            eq={"_upg_lifecycle"},
        )
        tm.that(
            self._recipe_targets_containing(
                makefile,
                r"\bmise\b[^\n]*\block\b[^\n]*--bump\b",
                regex=True,
            ),
            eq={"_bootstrap_setup_tools", "_upg_lifecycle"},
        )
        toolchain = config.Infra.codegen.toolchain
        lifecycle = makefile.split("_upg_lifecycle: _builtin_setup_submodules\n", 1)[
            1
        ].split("\n\n", 1)[0]
        steps = lifecycle.splitlines()
        generated = next(
            i for i, step in enumerate(steps) if "$(SELF_MAKE) gen" in step
        )
        relocked = next(i for i, step in enumerate(steps) if "lock --bump" in step)
        installed = next(i for i, step in enumerate(steps) if "install --yes" in step)
        tm.that(generated < relocked < installed, eq=True)
        # Setup never locks (operator 2026-10-02): no reconcile or relock path
        # survives, and a lock that no longer satisfies the manifest stops.
        tm.that(
            makefile,
            lacks=[
                "setup reconcile",
                ' reconcile "$$project_root"',
                'relock "$(PROJECT_ROOT)"',
            ],
        )
        tm.that(makefile, has="install --yes")
        tm.that(makefile, has='if [ "$(TOOL_BOOTSTRAP_RESOLVE)" = "1" ]; then')
        resolve_assignments = re.findall(
            r"^(?:([\w-]+): )?TOOL_BOOTSTRAP_RESOLVE :=[ ]?(.*)$",
            makefile,
            flags=re.MULTILINE,
        )
        tm.that(sorted(resolve_assignments), eq=[("", ""), ("upg", "1")])
        tm.that(makefile, has="upg: TOOL_BOOTSTRAP_LIFECYCLE := _upg_lifecycle")
        sync_flags = re.search(r"^UV_SYNC_FLAGS := (.*)$", makefile, re.MULTILINE)
        assert sync_flags is not None
        tm.that(sync_flags.group(1), lacks="--upgrade")
        # Lock law (operator 2026-10-03): setup never writes uv.lock. Its only
        # uv lock call is the read-only check; a matching lock syncs --locked,
        # a drifted lock is reported and synced --frozen, and nothing deletes
        # or re-derives the committed lock.
        setup_recipe = makefile.split("SETUP_ENVIRONMENT_RECIPE = ", 1)[1].split(
            "\n\n",
            1,
        )[0]
        tm.that(
            re.findall(r"\$\(UV\) lock (--\S+)", setup_recipe),
            eq=["--check"],
        )
        tm.that(setup_recipe, has=["uv_lock_mode=--locked", "uv_lock_mode=--frozen"])
        tm.that(setup_recipe, has="$$uv_lock_mode")
        tm.that(setup_recipe, lacks=['rm -f "$(UV_PROJECT)/uv.lock"', ">/dev/null"])
        tm.that(setup_recipe, has="make upg")

        mise_toml = u.Cli.toml_mapping_from_text(
            (project_root / c.Infra.MISE_TOML_FILENAME).read_text(encoding="utf-8"),
        )
        assert mise_toml is not None
        settings = mise_toml.get("settings")
        tool_config = mise_toml.get("tool_config")
        assert isinstance(settings, Mapping)
        assert isinstance(tool_config, Mapping)
        tm.that(settings.get("lockfile"), eq=toolchain.mise_lockfile)
        tm.that(settings.get("locked"), eq=toolchain.mise_locked)
        tm.that(tool_config.get("locked"), eq=toolchain.mise_locked)
        tm.that(
            settings.get("lockfile_platforms"),
            eq=list(toolchain.mise_lockfile_platforms),
        )

    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_generated_dependency_upgrade_projects_lock_floors(
        self,
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
    ) -> None:
        """`upg` owns lock upgrade, open-floor projection, and final resolution."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            profile,
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")

        for needle in (
            "deps modernize",
            "--rewrite-constraints",
            "--upgrade --refresh",
        ):
            tm.that(
                self._recipe_targets_containing(makefile, needle),
                eq={"_upg_lifecycle"},
            )
        tm.that(
            self._recipe_targets_containing(
                makefile,
                '$(UV) lock --check --project "$(PROJECT_ROOT)"',
            ),
            eq={"_upg_lifecycle"},
        )
        tm.that(makefile, lacks="--constraint-policy")

    def test_upg_converge_verifies_the_cycle_it_upgraded(self, tmp_path: Path) -> None:
        """An upgrade publishes only after gen converges and every gate passes."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.WORKSPACE,
            bootstrap=True,
        )
        makefile = (project_root / "Makefile").read_text(encoding="utf-8")

        tm.that(makefile, has="make upg did not converge")
        tm.that(
            "_upg_lifecycle"
            in self._recipe_targets_containing(makefile, "$(SELF_MAKE) check"),
            eq=True,
        )
