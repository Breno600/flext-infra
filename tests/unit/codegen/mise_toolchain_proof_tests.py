"""Npm-free toolchain contract and the setup reality proof.

The toolchain model refuses an npm-backed tool at load, and the reality proof
runs real executables on the real filesystem: a binary escaping its install
root or reporting another version fails, and the defects surface in proof
order (lock identity, then containment, then version).

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import config, m, t
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_infra.codegen.mise_toolchain_proof import FlextInfraCodegenMiseToolchainProof
from tests import c


class TestsFlextInfraMiseToolchainProof:
    """Public behavior of the npm-free toolchain and its reality proof."""

    TOOL = "probe-tool"
    VERSION = "1.2.3"
    PLATFORM = "linux-x64"
    CHECKSUM = "sha256:00"

    @classmethod
    def _entry(cls) -> m.Infra.MiseToolEntry:
        """Declare one scenario tool whose probe prints its version.

        Returns:
            The scenario tool entry.

        """
        return m.Infra.MiseToolEntry.model_validate({
            "name": cls.TOOL,
            "version": "latest",
            "version_probe": {
                "binary": cls.TOOL,
                "arguments": ["--version"],
                "pattern": f"^{cls.TOOL} {{version}}$",
            },
        })

    @classmethod
    def _lock(cls, *, checksum: bool = True) -> t.JsonMapping:
        """Build the scenario mise.lock mapping of the tool.

        Returns:
            The scenario lock mapping.

        """
        platform_key = c.Infra.MISE_LOCK_PLATFORM_KEY.format(platform=cls.PLATFORM)
        section: t.JsonDict = (
            {"checksum": cls.CHECKSUM} if checksum else {"url": cls.PLATFORM}
        )
        locked: t.JsonDict = {"version": cls.VERSION, platform_key: section}
        versions: list[t.JsonValue] = [locked]
        tools: t.JsonDict = {cls.TOOL: versions}
        return {"tools": tools}

    @classmethod
    def _executable(cls, path: Path, printed: str) -> Path:
        """Write one real executable that prints ``<tool> <printed>``.

        Returns:
            The executable path.

        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"#!/bin/sh\necho '{cls.TOOL} {printed}'\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    @classmethod
    def _prove(
        cls,
        root: Path,
        binary: Path,
        *,
        checksum: bool = True,
    ) -> str | None:
        """Run the public proof and return its first defect, if any.

        Returns:
            The failure message, or None when the tool is proven.

        """
        result = FlextInfraCodegenMiseToolchainProof.prove(
            cls._entry(),
            cls._lock(checksum=checksum),
            cls.PLATFORM,
            (root, binary),
        )
        return result.error if result.failure else None

    def test_contained_binary_reporting_the_lock_version_is_proven(
        self,
        tmp_path: Path,
    ) -> None:
        """A self-contained binary that reports the locked version passes."""
        root = tmp_path / "installs" / self.TOOL / self.VERSION
        self._executable(root / "libexec" / self.TOOL, self.VERSION)
        link = root / "bin" / self.TOOL
        link.parent.mkdir(parents=True)
        link.symlink_to(Path("..") / "libexec" / self.TOOL)

        result = FlextInfraCodegenMiseToolchainProof.prove(
            self._entry(),
            self._lock(),
            self.PLATFORM,
            (root, link),
        )

        tm.that(tm.ok(result), has=self.CHECKSUM)

    def test_binary_escaping_its_install_root_fails(self, tmp_path: Path) -> None:
        """A bin link into a foreign tree (the bun walk-up shape) fails."""
        root = tmp_path / "installs" / self.TOOL / self.VERSION
        foreign = self._executable(tmp_path / "node_modules" / self.TOOL, self.VERSION)
        link = root / "bin" / self.TOOL
        link.parent.mkdir(parents=True)
        link.symlink_to(foreign)

        tm.that(self._prove(root, link) or "", has="outside its install root")

    def test_version_mismatch_fails(self, tmp_path: Path) -> None:
        """A contained binary reporting another release fails."""
        root = tmp_path / "installs" / self.TOOL / self.VERSION
        binary = self._executable(root / "bin" / self.TOOL, "9.9.9")

        tm.that(self._prove(root, binary) or "", has="does not report the locked")

    def test_proof_reports_defects_in_order(self, tmp_path: Path) -> None:
        """Lock identity precedes containment, which precedes the version."""
        root = tmp_path / "installs" / self.TOOL / self.VERSION
        foreign = self._executable(tmp_path / "outside" / self.TOOL, "9.9.9")
        escaping = root / "bin" / self.TOOL
        escaping.parent.mkdir(parents=True)
        escaping.symlink_to(foreign)
        contained = self._executable(root / "libexec" / self.TOOL, "9.9.9")

        tm.that(self._prove(root, escaping, checksum=False) or "", has="checksum")
        tm.that(self._prove(root, escaping) or "", has="outside its install root")
        tm.that(
            self._prove(root, contained) or "",
            has="does not report the locked",
        )

    @staticmethod
    def test_toolchain_rejects_an_npm_selector_at_load() -> None:
        """The fleet toolchain has no npm backend: an npm: tool is refused."""
        toolchain = config.Infra.codegen.toolchain
        declared = {
            name: value
            for name, value in toolchain.model_dump().items()
            if name in m.Infra.ToolchainSpec.model_fields
        }
        npm_tool = {
            "name": "npm-tool",
            "selector": "npm:some-cli",
            "version": "latest",
            "version_probe": {
                "binary": "some-cli",
                "arguments": ["--version"],
                "pattern": "{version}",
            },
        }

        with pytest.raises(ValueError, match="no npm backend"):
            m.Infra.ToolchainSpec.model_validate({
                **declared,
                "tools": [*declared["tools"], npm_tool],
            })

    @staticmethod
    def test_declared_toolchain_carries_no_npm_tool() -> None:
        """Every loaded tool key is a native, checksum-locked selector."""
        keys = config.Infra.codegen.toolchain.tool_keys.values()

        tm.that([key for key in keys if key.startswith("npm:")], eq=[])

    @staticmethod
    def test_generation_retires_the_prettier_projections(tmp_path: Path) -> None:
        """Generated .prettierrc/.prettierignore retire; a hand-owned one stays."""
        evidence = {
            retired.path: retired.evidence
            for retired in config.Infra.codegen.retired_projections
            if not isinstance(retired, str)
        }
        generated = tmp_path / "generated"
        hand_owned = tmp_path / "hand-owned"
        for name in (".prettierrc", ".prettierignore"):
            generated.mkdir(exist_ok=True)
            hand_owned.mkdir(exist_ok=True)
            (generated / name).write_text(f"{evidence[name]}\n", encoding="utf-8")
            (hand_owned / name).write_text("{}\n", encoding="utf-8")

        retired = {
            plan.path.name
            for plan in tm.ok(
                FlextInfraCodegenConform.retired_projection_plans(
                    generated,
                    c.Infra.MakeProfile.STANDALONE,
                ),
            )
            if plan.desired_content is None
        }
        preserved = {
            plan.path.name
            for plan in tm.ok(
                FlextInfraCodegenConform.retired_projection_plans(
                    hand_owned,
                    c.Infra.MakeProfile.STANDALONE,
                ),
            )
            if plan.desired_content is None
        }

        tm.that(retired >= {".prettierrc", ".prettierignore"}, eq=True)
        tm.that(preserved & {".prettierrc", ".prettierignore"}, eq=set[str]())
