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
            self._recipe_targets_containing(makefile, "--upgrade"),
            eq={"_upg_lifecycle"},
        )
        tm.that(
            self._recipe_targets_containing(makefile, "lock --bump"),
            eq={"_bootstrap_setup_tools", "_upg_lifecycle"},
        )
        toolchain = config.Infra.codegen.toolchain
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
        # Every `mise install` names exactly the declared toolchain keys: a
        # bare install would also provision the operator's global registry.
        declared = " ".join(f'"{key}"' for key in toolchain.mise_install_keys)
        installs = re.findall(r"install --yes(.*?)(?:; \\|$)", makefile, re.MULTILINE)
        tm.that(len(installs), eq=2)
        tm.that({install.strip() for install in installs}, eq={declared})
        # Setup proves the provisioned toolchain before post-setup runs.
        activated = makefile.split("_setup_activated:\n", 1)[1].split("\n\n", 1)[0]
        tm.that(activated.splitlines()[0], has="codegen mise-proof")
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

    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_upg_relocks_the_manifest_gen_projected_before_installing(
        self,
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
    ) -> None:
        """One `make upg` resolves the requirements its own `gen` projects.

        Premise (flext-5kqsx): the upgraded generator projected a declared
        runtime dependency into pyproject.toml after uv.lock was written, so
        the lock and the environment lacked it until a second `make upg`.
        """
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            profile,
            bootstrap=True,
        )
        makefile = (project_root / c.Infra.MAKEFILE_FILENAME).read_text(
            encoding="utf-8",
        )
        steps = (
            makefile
            .split("_upg_lifecycle: _builtin_setup_submodules\n", 1)[1]
            .split("\n\n", 1)[0]
            .splitlines()
        )

        def after(start: int, needle: str) -> int:
            return next(
                index
                for index, step in enumerate(steps)
                if index > start and needle in step
            )

        upgraded = after(-1, "lock --project")
        projected = after(upgraded, "$(call RUN_PUBLIC_PRODUCE,gen)")
        relocked = after(projected, "lock --project")
        checked = after(relocked, "lock --check")
        installed = after(checked, "_builtin_setup_environment")
        bumped = after(installed, "lock --bump")
        activated = after(bumped, "$(call RUN_PUBLIC_ACTIVATE,gen)")

        tm.that(steps[upgraded], has="--upgrade")
        tm.that(steps[relocked], lacks="--upgrade")
        tm.that(
            upgraded < projected < relocked < checked < installed < bumped,
            eq=True,
        )
        tm.that(bumped < activated, eq=True)

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

    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    def test_upg_activates_gen_only_after_relocking_the_rendered_manifest(
        self,
        tmp_path: Path,
        profile: c.Infra.MakeProfile,
    ) -> None:
        """One `make upg` converges when `gen` moves the Mise self-pin.

        `gen` renders the managed `.mise.toml`; its activation half demands
        the Mise release the lock pins. Activation must therefore re-enter
        the environment only after `mise lock --bump` resolved that rendered
        manifest and `mise install` provisioned it, or the first upgrade of a
        project whose manifest gains or moves the self-pin stops on a lock
        resolved from the previous manifest.
        """
        project_root, _repository_root = u.Tests.render_make_environment(
            tmp_path,
            profile,
            bootstrap=True,
        )
        makefile = (project_root / c.Infra.MAKEFILE_FILENAME).read_text(
            encoding="utf-8",
        )
        steps = (
            makefile
            .split("_upg_lifecycle: _builtin_setup_submodules\n", 1)[1]
            .split("\n\n", 1)[0]
            .splitlines()
        )
        order = [
            next(i for i, step in enumerate(steps) if needle in step)
            for needle in (
                "$(SELF_MAKE) _builtin_require_environment",
                "$(call RUN_PUBLIC_PRODUCE,gen)",
                "lock --bump",
                "install --yes",
                "$(SELF_MAKE) _builtin_require_mise",
                "$(call RUN_PUBLIC_ACTIVATE,gen)",
                "$(SELF_MAKE) gen;",
            )
        ]
        tm.that(order, eq=sorted(set(order)))
        # The upgrade writes files; staging belongs to the committer. No
        # generated recipe touches the Git index (a directory-scoped add would
        # also stage deletions of retired lock sidecars).
        tm.that(self._recipe_targets_containing(makefile, "git add"), eq=set[str]())
        tm.that(makefile, has="_activated-gen: _builtin_require_environment")
        tm.that(
            makefile,
            has="_builtin_require_environment: _builtin_require_workspace "
            "_builtin_require_mise",
        )

        # GNU Make itself expands the canned halves: the producer half never
        # re-enters the environment, the activation half does, and the public
        # verb is exactly the producer half followed by the activation half.
        probe = (
            "probe_upg_halves: ; @: "
            "$(info PRODUCE=$(strip $(call RUN_PUBLIC_PRODUCE,gen))) "
            "$(info ACTIVATE=$(strip $(call RUN_PUBLIC_ACTIVATE,gen))) "
            "$(info PUBLIC=$(strip $(call RUN_PUBLIC,gen,1)))"
        )
        expanded = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", f"--eval={probe}", "probe_upg_halves"],
                cwd=project_root,
            ),
        )
        tm.that(
            u.Cli.process_succeeded(expanded.outcome),
            eq=True,
            msg=expanded.stdout + expanded.stderr,
        )
        halves = {
            name: value
            for name, _, value in (
                line.partition("=") for line in expanded.stdout.splitlines()
            )
            if name in {"PRODUCE", "ACTIVATE", "PUBLIC"}
        }
        tm.that(halves["PRODUCE"], has="_builtin-gen")
        tm.that(halves["PRODUCE"], lacks="_activated-gen")
        tm.that(halves["ACTIVATE"], has=["direnv exec", "_activated-gen"])
        tm.that(
            halves["PUBLIC"].split(),
            eq=[*halves["PRODUCE"].split(), *halves["ACTIVATE"].split()],
        )
