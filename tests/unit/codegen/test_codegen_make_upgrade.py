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

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeUpgrade:
    """Prove only ``upg`` resolves locks and publishes them transactionally."""

    @staticmethod
    @pytest.mark.remote
    def test_upg_replaces_newer_lock_revision_before_older_mise_reads_it(
        tmp_path: Path,
        resolved_make_templates: t.MappingKV[c.Infra.MakeProfile, Path],
    ) -> None:
        """The public upgrade recovers a v3 lock with a v2 Mise release."""
        u.Tests.upgrade_recovers_newer_lock_revision(tmp_path, resolved_make_templates)

    @staticmethod
    @pytest.mark.remote
    def test_failed_upg_lock_preserves_runtime_and_retires_own_stage(
        tmp_path: Path,
        resolved_make_templates: t.MappingKV[c.Infra.MakeProfile, Path],
    ) -> None:
        """A failed real Mise lock cannot strand a stale resolved lock."""
        u.Tests.failed_upgrade_preserves_runtime_and_retires_stage(
            tmp_path,
            resolved_make_templates,
        )

    @staticmethod
    def _recipe_targets_containing(makefile: str, needle: str) -> set[str]:
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
                    and needle in line
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
        lifecycle and every `mise lock --bump` to the shared bootstrap gated by
        a switch that only `upg` sets; `setup` syncs `--locked`, and the
        generated `.mise.toml` makes mise install exactly what the lock pins.
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
            self._recipe_targets_containing(makefile, "--upgrade"),
            eq={"_upg_lifecycle"},
        )
        tm.that(
            self._recipe_targets_containing(makefile, "lock --bump"),
            eq={"_bootstrap_setup_tools"},
        )
        toolchain = config.Infra.codegen.toolchain
        lock_invocations = re.findall(r"lock --bump([^;]*);", makefile)
        tm.that(tuple(arguments.strip() for arguments in lock_invocations), eq=("",))
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
        tm.that(sync_flags.group(1), has="--locked")
        tm.that(sync_flags.group(1), lacks="--upgrade")

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

    @staticmethod
    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_upg_hands_the_staged_lock_to_the_transaction_publisher(
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
    ) -> None:
        """The staged lock and its sidecars reach the tree through one publisher.

        ``mise lock`` writes the lock and each tool's sidecar into a stage
        beside the project; the generated transaction publisher is the one
        owner that publishes them, sidecars before the lock. The converge
        step keeps ``gen`` output so a failure carries its cause.
        """
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            profile,
            bootstrap=True,
        )
        makefile = (project_root / c.Infra.MAKEFILE_FILENAME).read_text(
            encoding="utf-8",
        )
        tm.that(makefile, has='publish "$$project_root" "$$lock_stage"')
        tm.that(makefile, has="$(SELF_MAKE) gen; \\")
        tm.that(makefile, lacks=["gen > /dev/null", "could not be staged"])

    def test_generated_dependency_upgrade_projects_lock_floors(
        self,
        tmp_path: Path,
    ) -> None:
        """`upg` owns lock upgrade, open-floor projection, and final resolution."""
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
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
            eq={"_upg_converge"},
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
            "_upg_converge"
            in self._recipe_targets_containing(makefile, "$(SELF_MAKE) check"),
            eq=True,
        )
