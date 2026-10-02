"""Generated public verbs enforce the committed Mise runtime pin.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from flext_tests import tm

from flext_core import r
from flext_infra import config
from tests import c, m, u

pytestmark = pytest.mark.slow


class TestsFlextInfraCodegenMakeLockContract:
    """A frozen operation fails before activation or any launcher execution."""

    @staticmethod
    def test_conform_publication_preserves_committed_lock_graph(
        tmp_path: Path,
    ) -> None:
        """Test conform publication preserves committed lock graph."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        lock = root / c.Infra.UV_LOCK_FILENAME
        lock.write_bytes((Path(__file__).resolve().parents[3] / lock.name).read_bytes())
        paths = (
            lock,
            # Unlocked fleet mode commits no mise.lock; the SSOT decides.
            *(
                (root / c.Infra.MISE_LOCK_FILENAME,)
                if config.Infra.codegen.toolchain.mise_lockfile
                else ()
            ),
            root / c.Infra.MISE_VERSION_PIN_FILENAME,
            *(path for path in (root / ".mise" / "locks").rglob("*") if path.is_file()),
        )
        before = {path: path.read_bytes() for path in paths}
        repository = u.Tests.repository_ref(
            root.name,
            role=c.Infra.MakeProfile.STANDALONE,
        )
        workspace = u.Tests.workspace_spec(
            repository,
            project=u.Tests.project_spec(repository.name),
        )
        plan = u.Tests.conform_plan(root, workspace)
        tm.ok(
            u.Tests.materialize_codegen_plans(
                r[tuple[m.Infra.CodegenFilePlan, ...]].ok(tuple(plan.files)),
            ),
        )

        tm.that({path: path.read_bytes() for path in paths}, eq=before)
        tm.that(
            (root / c.Infra.MISE_LOCK_FILENAME).exists(),
            eq=config.Infra.codegen.toolchain.mise_lockfile,
        )

    @staticmethod
    def test_direnv_isolates_nested_checkout_from_parent_mise_config(
        tmp_path: Path,
    ) -> None:
        """The real Mise reader cannot observe an unrelated ancestor config."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        (root.parent / c.Infra.MISE_TOML_FILENAME).write_text(
            "invalid-parent = [\n",
            encoding="utf-8",
        )
        # The launcher bakes the pinned release itself: no MISE_VERSION is
        # injected, and an inherited one must not leak into the probe.
        process = tm.ok(
            u.Cli.run_raw(
                [
                    "direnv",
                    "exec",
                    str(root),
                    str(root / "bin" / "mise"),
                    "ls",
                    "--json",
                ],
                cwd=root,
                remove_env_keys=(
                    "MISE_VERSION",
                    *c.Tests.MAKE_ISOLATION_ENV_KEYS,
                    "GIT_CEILING_DIRECTORIES",
                    "MISE_CEILING_PATHS",
                ),
            ),
        )

        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tm.that(process.stderr, lacks="mise WARN")
        tm.that(process.stderr, lacks="invalid-parent")

    @staticmethod
    def test_direnv_runs_real_make_from_pinned_tool_paths_without_lock_changes(
        tmp_path: Path,
    ) -> None:
        """An outer direnv entry never delegates Make to an older shared shim."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        bootstrap = u.Infra.mise_bootstrap_environment()
        storage = tm.ok(
            u.Infra.prepare_mise_runtime_storage(root, os.environ, bootstrap),
        )
        sidecars = root / ".mise" / "locks"
        paths = (
            root / bootstrap.version_pin_file,
            *(
                (root / bootstrap.lock_file,)
                if config.Infra.codegen.toolchain.mise_lockfile
                else ()
            ),
            *(path for path in sidecars.rglob("*") if path.is_file()),
        )
        before = {path: path.read_bytes() for path in paths}

        identity = tm.ok(
            u.Cli.run_raw(
                ["direnv", "exec", str(root), "bash", "-c", "command -v make"],
                cwd=root,
                remove_env_keys=c.Tests.MAKE_ISOLATION_ENV_KEYS,
            ),
        )
        tm.that(
            u.Cli.process_succeeded(identity.outcome),
            eq=True,
            msg=identity.stdout + identity.stderr,
        )
        install_root = storage / next(
            relative
            for name, relative in bootstrap.persistent_environment
            if name == "MISE_INSTALLS_DIR"
        )
        tm.that(Path(identity.stdout.strip()).is_relative_to(install_root), eq=True)
        process = tm.ok(
            u.Cli.run_raw(
                ["direnv", "exec", str(root), "make", "--no-print-directory", "help"],
                cwd=root,
                remove_env_keys=c.Tests.MAKE_ISOLATION_ENV_KEYS,
            ),
        )
        tm.that(
            u.Cli.process_succeeded(process.outcome),
            eq=True,
            msg=process.stdout + process.stderr,
        )
        tm.that(process.stdout, has=f"[{c.Infra.MakeProfile.STANDALONE}]")
        tm.that(identity.stderr + process.stderr, lacks="mise WARN")
        tm.that({path: path.read_bytes() for path in paths}, eq=before)
        tm.that(
            (root / c.Infra.MISE_LOCK_FILENAME).exists(),
            eq=config.Infra.codegen.toolchain.mise_lockfile,
        )
        tm.that(
            {path for path in sidecars.rglob("*") if path.is_file()},
            eq={path for path in paths if path.is_relative_to(sidecars)},
        )

    @staticmethod
    def test_direnv_rejects_unprovisioned_runtime_without_installing(
        tmp_path: Path,
    ) -> None:
        """Activation names setup instead of downloading a missing pinned runtime."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        bootstrap = u.Infra.mise_bootstrap_environment()
        cold_storage = tmp_path / "unprovisioned-mise"
        release = tm.ok(
            u.Infra.mise_pinned_release(
                (root / bootstrap.version_pin_file).read_text(encoding="utf-8"),
            ),
        )
        # The host's direnv launcher may itself be a Mise shim that provisions
        # direnv into the storage it is handed; the activation contract is only
        # that the pinned Mise runtime is never installed.
        template = bootstrap.runtime_install_relative_template
        pinned_runtime = cold_storage / template.format(release=release)

        process = tm.ok(
            u.Cli.run_raw(
                ["direnv", "exec", str(root), "make", "--no-print-directory", "help"],
                cwd=root,
                env={bootstrap.storage_root_variable: str(cold_storage)},
                remove_env_keys=c.Tests.MAKE_ISOLATION_ENV_KEYS,
            ),
        )

        tm.that(u.Cli.process_succeeded(process.outcome), eq=False)
        tm.that(process.stderr, has=f"missing pinned Mise runtime {pinned_runtime}")
        tm.that(process.stderr, has="run make setup")
        tm.that(pinned_runtime.exists(), eq=False)

    @pytest.mark.parametrize("pin_content", [None, "latest\n", " \n", "1.2.3\n4.5.6\n"])
    def test_direnv_rejects_unresolved_runtime_pin(
        self,
        tmp_path: Path,
        pin_content: str | None,
    ) -> None:
        """Missing, symbolic, and malformed pins never launch the bootstrapper."""
        root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        pin = root / u.Infra.mise_bootstrap_environment().version_pin_file
        if pin_content is None:
            pin.unlink()
        else:
            pin.write_text(pin_content, encoding="utf-8")

        process = tm.ok(
            u.Cli.run_raw(
                ["direnv", "exec", str(root), "make", "--no-print-directory", "help"],
                cwd=root,
                remove_env_keys=c.Tests.MAKE_ISOLATION_ENV_KEYS,
            ),
        )

        tm.that(u.Cli.process_succeeded(process.outcome), eq=False)
        tm.that(process.stderr, has=str(pin))
        tm.that(process.stdout, lacks=f"[{c.Infra.MakeProfile.STANDALONE}]")

    @pytest.mark.parametrize(
        ("verb", "pin_content"),
        [
            *(
                (verb.name, None)
                for verb in config.Infra.codegen.make.verbs
                if verb.name not in {"help", "clean", "upg"}
                # The rendered Makefile is standalone: it declares only the
                # verbs whose operation applies to that profile.
                and c.Infra.MakeProfile.STANDALONE in verb.profiles
            ),
            ("status", ""),
            ("status", " \n"),
            ("status", "latest\n"),
        ],
    )
    def test_frozen_verbs_reject_an_unresolved_pin_before_effects(
        self,
        tmp_path: Path,
        verb: str,
        pin_content: str | None,
    ) -> None:
        """Test frozen verbs reject an unresolved pin before effects."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        pin = project_root / c.Infra.MISE_VERSION_PIN_FILENAME
        if pin_content is None:
            pin.unlink()
        else:
            pin.write_text(pin_content, encoding="utf-8")
        (project_root / "bin" / "mise").unlink()
        activation = project_root / "activation-effect"
        (project_root / ".envrc.local").write_text(
            f'touch "{activation}"\n',
            encoding="utf-8",
        )

        process = tm.ok(
            u.Tests.run_isolated_make(["--no-print-directory", verb], cwd=project_root),
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(process.stderr, has=str(pin))
        tm.that(process.stderr, lacks="missing generated mise launcher")
        tm.that(activation.exists(), eq=False)
        tm.that(u.Infra.runtime_environment_dir(project_root).exists(), eq=False)

    @pytest.mark.parametrize("verb", ["help", "clean", "upg"])
    def test_bootstrap_and_shell_verbs_do_not_require_the_pin(
        self,
        tmp_path: Path,
        verb: str,
    ) -> None:
        """Test bootstrap and shell verbs do not require the pin."""
        project_root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        pin = project_root / c.Infra.MISE_VERSION_PIN_FILENAME
        pin.unlink()
        (project_root / "bin" / "mise").unlink()

        process = tm.ok(
            u.Tests.run_isolated_make(["--no-print-directory", verb], cwd=project_root),
        )

        tm.that(process.stderr, lacks=str(pin))
        if verb == "upg":
            # Without its generated launcher upg still stops before resolving:
            # the cold-start repair of a deleted launcher is owned by the upg
            # self-heal slice (flext-gz7oj), which turns this into a success.
            tm.that(process.outcome.raw_return_code, ne=0)
            tm.that(process.stderr, has="missing generated mise launcher")
        else:
            tm.that(u.Cli.process_succeeded(process.outcome), eq=True)
        tm.that(pin.exists(), eq=False)

    @pytest.mark.parametrize("attached", [False, True])
    def test_setup_bootstraps_from_the_runtime_root_pin(
        self,
        tmp_path: Path,
        *,
        attached: bool,
    ) -> None:
        """Setup reads the Mise pin of the runtime that owns the checkout.

        A standalone checkout owns its runtime. An attached member runs on its
        superproject runtime, so the member pin (kept for standalone
        consumption) never contradicts the runtime pin during setup.
        """
        project_root, _ = u.Tests.render_make_environment(
            tmp_path,
            c.Infra.MakeProfile.STANDALONE,
        )
        pin = project_root / c.Infra.MISE_VERSION_PIN_FILENAME
        pinned = pin.read_text(encoding="utf-8")
        release = pinned.strip().splitlines()[-1]
        components = release.split(".")
        member_release = ".".join((*components[:-1], str(int(components[-1]) + 1)))
        if attached:
            runtime_root = project_root.parent
            u.Tests.initialize_git_repo(runtime_root)
            (runtime_root / pin.name).write_text(pinned, encoding="utf-8")
            pin.write_text(pinned.replace(release, member_release), encoding="utf-8")
            superproject = tm.ok(
                u.Cli.capture(
                    ["git", "rev-parse", "--show-superproject-working-tree"],
                    cwd=project_root,
                ),
            )
            tm.that(Path(superproject).resolve(), eq=runtime_root.resolve())
        storage_variable = u.Infra.mise_bootstrap_environment().storage_root_variable

        process = tm.ok(
            u.Tests.run_isolated_make(
                ["--no-print-directory", "setup"],
                cwd=project_root,
                env={
                    **os.environ,
                    "GITHUB_TOKEN": "invalid-test-credential",
                    storage_variable: "relative-storage",
                },
            ),
        )

        tm.that(process.outcome.raw_return_code, ne=0)
        tm.that(process.stderr, lacks="conflicts with")
        tm.that(process.stderr, lacks=member_release)
        tm.that(process.stderr, has=f"{storage_variable} must be absolute")
