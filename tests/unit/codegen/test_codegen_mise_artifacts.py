"""Offline contracts for generated Mise declarations and launchers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, u
from flext_infra.codegen.mise_artifacts import FlextInfraCodegenMiseArtifacts
from tests import u as test_u


class TestsFlextInfraCodegenMiseArtifacts:
    """Keep ordinary generation checks independent from remote resolution."""

    RELEASE = "1.2.3"
    "Any resolved release; the pin and both launchers must agree on it."

    @pytest.mark.parametrize(
        ("invalid", "reported"),
        [
            ("missing", "run make upg"),
            ("live-resolution", c.Infra.MISE_LATEST_RESOLUTION_MARKER),
            ("release-drift", "bakes Mise"),
            ("nonexecutable", "not executable"),
        ],
    )
    def test_launcher_derivation_guards(
        self,
        tmp_path: Path,
        invalid: str,
        reported: str,
    ) -> None:
        """Every launcher must be the generator's output for the pinned release."""
        root = self._project(tmp_path / "project")
        unix = root / c.Infra.ARTIFACT_SPECS[0][0]
        if invalid == "missing":
            unix.unlink()
        elif invalid == "live-resolution":
            unix.write_text(
                unix.read_text(encoding="utf-8")
                + f"# {c.Infra.MISE_LATEST_RESOLUTION_MARKER}\n",
                encoding="utf-8",
            )
        elif invalid == "release-drift":
            self._write_triple(root, release="1.2.4", pin=self.RELEASE)
        else:
            unix.chmod(0o644)

        result = FlextInfraCodegenMiseArtifacts.model_validate({
            "repository_root": root,
            "check_only": True,
        }).execute()

        tm.fail(result, has=reported)

    def test_member_triple_must_equal_its_runtime_root(self, tmp_path: Path) -> None:
        """A member's pin and launchers are a byte projection of its runtime root."""
        runtime_root = self._project(tmp_path / "workspace")
        member = self._project(tmp_path / "member")
        service = FlextInfraCodegenMiseArtifacts.model_validate({
            "repository_root": member,
            "check_only": True,
        })
        tm.ok(service.validate_artifacts(member, runtime_root))

        self._write_triple(member, release="1.2.4", pin="1.2.4")

        tm.fail(
            service.validate_artifacts(member, runtime_root),
            has="differs from the runtime root",
        )

    def test_runtime_root_seed_falls_back_to_the_packaged_triple(
        self,
        tmp_path: Path,
    ) -> None:
        """A scope root still carrying the bootstrap seed starts from the packaged triple."""
        from flext_infra.codegen.mise_artifacts_workspace import (
            FlextInfraMiseWorkspacePlanner,
        )

        root = tmp_path / "seed-project"
        for relative, _mode in c.Infra.ARTIFACT_SPECS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative == c.Infra.MISE_VERSION_PIN_FILENAME:
                lines = (*c.Infra.MISE_VERSION_PIN_HEADER, self.RELEASE)
            elif path.suffix == ".cmd":
                lines = ("@echo off",)
            else:
                lines = (
                    "#!/usr/bin/env bash",
                    f"# {c.Infra.MISE_LATEST_RESOLUTION_MARKER}",
                )
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = FlextInfraMiseWorkspacePlanner.runtime_artifacts(root)

        packaged = files("flext_infra").joinpath(c.Infra.MISE_COLD_START_DIRECTORY)
        tm.ok(result)
        for state, (relative, _mode) in zip(
            result.value.states,
            c.Infra.ARTIFACT_SPECS,
            strict=True,
        ):
            expected = packaged.joinpath(Path(relative).name).read_bytes()
            tm.that(state.content, eq=expected)

    @staticmethod
    @pytest.mark.parametrize("shape", ["absolute", "tilde"])
    def test_packaged_launcher_runs_its_baked_release_offline(
        tmp_path: Path,
        shape: str,
    ) -> None:
        """The packaged cold-start launcher runs its pinned release, offline.

        No ``MISE_VERSION`` is passed: the launcher bakes the release its
        ``mise.version`` records. A binary planted at that release under the
        declared data dir proves resolution without any download, for both an
        absolute and a ``~``-relative data dir (an unquoted ``~/*)`` pattern
        once doubled ``${HOME}``).
        """
        packaged = files("flext_infra").joinpath(c.Infra.MISE_COLD_START_DIRECTORY)
        release = tm.ok(
            u.Infra.mise_pinned_release(
                packaged.joinpath(c.Infra.MISE_VERSION_PIN_FILENAME).read_text(
                    encoding="utf-8",
                ),
            ),
        )
        home = tmp_path / "home"
        data_dir = home / "mise-data"
        planted = data_dir / "bootstrap" / f"mise-{release}"
        planted.parent.mkdir(parents=True)
        planted.write_text('#!/bin/sh\necho "planted-mise $*"\n', encoding="utf-8")
        planted.chmod(0o755)
        launcher = tmp_path / "mise"
        launcher.write_bytes(packaged.joinpath("mise").read_bytes())
        launcher.chmod(0o755)
        declared = str(data_dir) if shape == "absolute" else "~/mise-data"

        executed = tm.ok(
            u.Cli.run(
                [str(launcher), "version"],
                env={
                    "HOME": str(home),
                    c.Infra.MISE_BOOTSTRAP_STORAGE_ROOT_VARIABLE: declared,
                },
                # An explicit MISE_INSTALL_PATH or MISE_VERSION outranks the
                # baked release; the generated Make harness exports both into
                # every child, so this probe must not inherit them.
                remove_env_keys=("MISE_INSTALL_PATH", "MISE_VERSION"),
                timeout=10,
            ),
        )

        tm.that(executed.stdout.strip(), eq="planted-mise version")

    @staticmethod
    def test_resource_read_accepts_installer_hard_links(tmp_path: Path) -> None:
        """A hard-linked package file (uv cache + venv) is readable as a resource."""
        owner = tmp_path / "seed"
        owner.write_bytes(b"#!/bin/sh\n")
        linked = tmp_path / "linked"
        linked.hardlink_to(owner)
        tm.that(linked.stat().st_nlink, eq=2)
        tm.that(tm.ok(u.Cli.files_read_binary(linked)), eq=b"#!/bin/sh\n")

    @classmethod
    def _write_triple(
        cls,
        root: Path,
        *,
        release: str | None = None,
        pin: str | None = None,
    ) -> None:
        """Write the `make upg` triple in the shapes the upstream generator bakes.

        ``mise generate install-script --version R`` defaults the Unix launcher
        to ``${MISE_VERSION:-R}`` and the Windows launcher to
        ``set "pinned_version=R"``; ``mise.version`` carries the generated
        header and ``R``. ``release`` and ``pin`` diverge only to model drift.
        """
        launcher_release = release or cls.RELEASE
        for relative, mode in c.Infra.ARTIFACT_SPECS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative == c.Infra.MISE_VERSION_PIN_FILENAME:
                lines = (*c.Infra.MISE_VERSION_PIN_HEADER, pin or cls.RELEASE)
            elif path.suffix == ".cmd":
                lines = ("@echo off", f'set "pinned_version={launcher_release}"')
            else:
                lines = (
                    "#!/usr/bin/env bash",
                    f'local mise_version="${{MISE_VERSION:-{launcher_release}}}"',
                )
            path.write_text("\n".join((*lines, "")), encoding="utf-8")
            path.chmod(mode)

    @staticmethod
    def _write_config(
        root: Path,
        *,
        selector: str = "github:example/tool",
        version: str = "latest",
    ) -> None:
        (root / ".mise.toml").write_text(
            "\n".join((
                "[tools]",
                f'python = "{config.Infra.codegen.toolchain.python_version}"',
                f'"{selector}" = "{version}"',
                "",
            )),
            encoding="utf-8",
        )

    @classmethod
    def _project(
        cls,
        root: Path,
        *,
        selector: str = "github:example/tool",
        version: str = "latest",
    ) -> Path:
        root.mkdir(parents=True)
        test_u.Tests.initialize_git_repo(root)
        cls._write_triple(root)
        cls._write_config(root, selector=selector, version=version)
        (root / "pyproject.toml").write_text(
            "[project]\n"
            f'name = "{config.Infra.name}"\n'
            'version = "0.1.0"\n'
            f'requires-python = "{config.Infra.codegen.toolchain.python_required_version}"\n'
            "dependencies = []\n",
            encoding="utf-8",
        )
        return root

    def test_complete_artifacts_validate_without_running_mise(
        self,
        tmp_path: Path,
    ) -> None:
        """Test complete artifacts validate without running mise."""
        root = self._project(tmp_path / "project")

        service = FlextInfraCodegenMiseArtifacts.model_validate({
            "repository_root": root,
            "check_only": True,
        })
        tm.that(service.repository_root, eq=root)
        result = service.execute()

        tm.ok(result, eq=True)

    def test_config_only_validation_skips_launcher_contract(
        self,
        tmp_path: Path,
    ) -> None:
        """Config-only mode validates the declaration without tool-owned effects."""
        root = tmp_path / "project"
        root.mkdir()
        self._write_config(root)

        result = FlextInfraCodegenMiseArtifacts.model_validate({
            "repository_root": root,
            "config_only": True,
        }).execute()

        tm.ok(result, eq=True)
        tm.that((root / "bin").exists(), eq=False)

    def test_full_validation_requires_committed_launchers(self, tmp_path: Path) -> None:
        """Test full validation requires committed launchers."""
        root = tmp_path / "project"
        root.mkdir()
        test_u.Tests.initialize_git_repo(root)
        self._write_config(root)

        result = FlextInfraCodegenMiseArtifacts.model_validate({
            "repository_root": root,
            "check_only": True,
        }).execute()

        # Only `make upg` writes the pin and launchers, so a project without
        # them names that verb as its single repair.
        tm.fail(result, has="run make upg")

    @staticmethod
    def test_tools_section_is_mandatory(tmp_path: Path) -> None:
        """Test tools section is mandatory."""
        root = tmp_path / "project"
        root.mkdir()
        (root / ".mise.toml").write_text("[settings]\n", encoding="utf-8")

        result = FlextInfraCodegenMiseArtifacts.model_validate({
            "repository_root": root,
            "config_only": True,
        }).execute()

        tm.fail(result, has="[tools]")

    @staticmethod
    def test_lock_annotation_in_a_selector_is_rejected(tmp_path: Path) -> None:
        """A ``<version>~<hash>`` lock cache key never becomes a selector."""
        root = tmp_path / "project"
        root.mkdir()
        (root / ".mise.toml").write_text(
            '[tools]\n"npm:@ast-grep/cli" = { version = "0.45.3~7a027ead" }\n',
            encoding="utf-8",
        )

        result = FlextInfraCodegenMiseArtifacts.model_validate({
            "repository_root": root,
            "config_only": True,
        }).execute()

        tm.fail(result, has="lockfile annotation")

    def test_apply_validates_the_same_offline_contract(self, tmp_path: Path) -> None:
        """Apply mode owns no tool effect: it validates declarations and launchers."""
        root = self._project(tmp_path / "project")

        result = FlextInfraCodegenMiseArtifacts.model_validate({
            "repository_root": root,
            "apply_changes": True,
        }).execute()

        tm.ok(result, eq=True)

    def test_latest_selectors_validate_without_resolution(self, tmp_path: Path) -> None:
        """Moving selectors validate offline; only `make upg` resolves them."""
        root = self._project(tmp_path / "project", selector="npm:jscpd")

        result = FlextInfraCodegenMiseArtifacts.model_validate({
            "repository_root": root,
            "check_only": True,
        }).execute()

        tm.ok(result, eq=True)

    @staticmethod
    def test_shipped_jscpd_plan_uses_only_configured_route() -> None:
        """The generated plan must contain only the typed jscpd route."""
        toolchain = config.Infra.codegen.toolchain
        plan = test_u.Tests.toml_payload(
            (Path(__file__).parents[3] / ".mise.toml").read_text(encoding="utf-8"),
        )
        tools = test_u.Tests.toml_mapping(plan["tools"])

        # jscpd declares a host-invariant version so mise writes one lock
        # entry per tool; the per-platform asset patterns were removed.
        tm.that(
            tools.get(toolchain.jscpd_selector),
            eq={"version": toolchain.jscpd_version},
        )
        tm.that("npm:jscpd" in tools, eq=False)

    @staticmethod
    def test_project_filter_is_internal_to_make_propagation() -> None:
        """Keep project selection on the Make propagation boundary."""
        field = FlextInfraCodegenMiseArtifacts.model_fields["project_filter"]

        tm.that(field.alias, none=True)
        tm.that(field.exclude, eq=True)
