"""Tests for FlextInfraValidateTierWhitelist.

Guard 5: Abstraction-boundary + tier-whitelist enforcer. Flags runtime
imports of flext-core-abstracted third-party libraries (pydantic,
structlog, returns, orjson, pyyaml, dependency_injector) anywhere
outside ``flext-core/src/``. Uses rope's semantic import resolution so
``if TYPE_CHECKING:`` imports are exempt.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tf, tm

from flext_infra.validate.tier_whitelist import FlextInfraValidateTierWhitelist
from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraTierWhitelist:
    """Abstraction-boundary rule and summary content for tier-whitelist validation."""

    @pytest.fixture
    def v(self) -> FlextInfraValidateTierWhitelist:
        """Shared validator instance."""
        return FlextInfraValidateTierWhitelist()

    @pytest.mark.parametrize("placement", [".claude/worktrees/lane", "worktrees/lane"])
    def test_linked_checkout_ancestors_do_not_hide_violations(
        self, tmp_path: Path, v: FlextInfraValidateTierWhitelist, placement: str
    ) -> None:
        project = tmp_path / placement
        pkg = u.Tests.write_package_init(project / "src" / "pkg", "").parent
        (project / ".git").write_text("gitdir: ../metadata\n", encoding="utf-8")
        tf(base_dir=pkg).create("from pydantic import BaseModel\n", "bad.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(project))
        tm.that(report.passed, eq=False)
        tm.that(" | ".join(report.violations), has="bad.py")

    def test_empty_workspace_passes(
        self, tmp_path: Path, v: FlextInfraValidateTierWhitelist
    ) -> None:
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report, is_=m.Infra.ValidationReport)
        tm.that(report.passed, eq=True)

    def test_clean_imports_pass(
        self, tmp_path: Path, v: FlextInfraValidateTierWhitelist
    ) -> None:
        pkg = u.Tests.write_package_init(tmp_path / "src" / "pkg", "").parent
        tf(base_dir=pkg).create(
            "from flext_core import m, c\nX = m.BaseModel\n", "good.py"
        )
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=True)

    @pytest.mark.parametrize(
        "source", ["from .yaml import value\n", "from . import yaml\n"]
    )
    def test_relative_module_is_not_a_third_party_import(
        self, tmp_path: Path, v: FlextInfraValidateTierWhitelist, source: str
    ) -> None:
        """A local module named like a library retains its package identity."""
        pkg = u.Tests.write_package_init(tmp_path / "src" / "pkg", "").parent
        tf(base_dir=pkg).create("value = 1\n", "yaml.py")
        tf(base_dir=pkg).create(source, "consumer.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=True, msg=str(report.violations))

    @pytest.mark.parametrize(
        ("source", "filename", "expected_substring"),
        [
            ("from pydantic import BaseModel\n", "bad.py", "pydantic"),
            ("import structlog\n", "bad_structlog.py", "structlog"),
            ("from returns.result import Result\n", "bad_returns.py", "returns"),
        ],
    )
    def test_bare_abstracted_import_flagged(
        self,
        tmp_path: Path,
        v: FlextInfraValidateTierWhitelist,
        source: str,
        filename: str,
        expected_substring: str,
    ) -> None:
        pkg = u.Tests.write_package_init(tmp_path / "src" / "pkg", "").parent
        tf(base_dir=pkg).create(source, filename)
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=False)
        tm.that(" | ".join(report.violations), has=expected_substring)

    def test_flext_core_src_is_allowlisted(
        self, tmp_path: Path, v: FlextInfraValidateTierWhitelist
    ) -> None:
        # Emulate a flext-core layout — bare pydantic is legal here.
        project = tmp_path / "flext-core"
        src = project / "src" / "flext_core"
        src.mkdir(parents=True, exist_ok=True)
        (src / "__init__.py").write_text("", encoding="utf-8")
        # A project declares its own name; the exemption is granted to the
        # declaring project, never to a directory that merely looks like it.
        (project / "pyproject.toml").write_text(
            '[project]\nname = "flext-core"\nversion = "0.1.0"\n', encoding="utf-8"
        )
        tf(base_dir=src).create(
            "from pydantic import BaseModel\nX = BaseModel\n", "abstractions.py"
        )
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.passed, eq=True)

    def test_failing_summary_reports_count(
        self, tmp_path: Path, v: FlextInfraValidateTierWhitelist
    ) -> None:
        pkg = u.Tests.write_package_init(tmp_path / "src" / "pkg", "").parent
        tf(base_dir=pkg).create("from pydantic import BaseModel\n", "a.py")
        tf(base_dir=pkg).create("import structlog\n", "b.py")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.summary, has="2")

    def test_passing_summary_mentions_boundary(
        self, tmp_path: Path, v: FlextInfraValidateTierWhitelist
    ) -> None:
        u.Tests.write_package_init(tmp_path / "src" / "pkg", "")
        report: m.Infra.ValidationReport = tm.ok(v.build_report(tmp_path))
        tm.that(report.summary, has="boundary")
