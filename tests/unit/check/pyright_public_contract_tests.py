"""Native Pyright proves exported contracts and rejects private consumers.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from flext_infra import FlextInfraEnsurePyrightConfigPhase, m, t, u
from flext_infra.gates.pyright import FlextInfraPyrightGate

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraPyrightPublicContract:
    """Exercise the configured semantic owner with real source and type stubs."""

    @staticmethod
    @pytest.mark.slow
    @pytest.mark.parametrize(
        ("consumer", "private"),
        [
            (
                (
                    "import os as operating_system\n"
                    "def exit_child() -> None:\n"
                    "    operating_system._exit(0)\n"
                ),
                False,
            ),
            (
                (
                    "from owner import Owner\n"
                    "def observe(value: Owner) -> int:\n"
                    "    return value._secret\n"
                ),
                True,
            ),
            (
                (
                    "from owner import Owner\n"
                    "def exit_child(os: Owner) -> None:\n"
                    "    os._exit(0)\n"
                ),
                True,
            ),
            (
                (
                    "from owner import _public\n"
                    "def observe() -> int:\n"
                    "    return _public()\n"
                ),
                False,
            ),
        ],
    )
    def test_publicness_uses_resolved_owner(
        tmp_path: Path,
        tool_config_document: m.Infra.ToolConfigDocument,
        consumer: str,
        *,
        private: bool,
    ) -> None:
        """Aliases and explicit exports stay public; shadowed receivers do not."""
        rules = tool_config_document.tools.pyright.path_rules
        roots = tuple(dict.fromkeys((*rules.env_dirs, rules.project_root)))
        for index, root in enumerate(roots):
            directory = tmp_path / root / "fixtures"
            directory.mkdir(parents=True, exist_ok=True)
            (directory / f"consumer_{index}.py").write_text(consumer, encoding="utf-8")
        (tmp_path / rules.source_dir / "owner.py").write_text(
            '__all__ = ["Owner", "_public"]\n'
            "class Owner:\n"
            "    _secret: int = 1\n"
            "    def _exit(self, code: int) -> None:\n"
            "        self._secret = code\n"
            "def _public() -> int:\n"
            "    return 1\n",
            encoding="utf-8",
        )
        payload = t.Infra.MUTABLE_INFRA_MAPPING_ADAPTER.validate_python({})
        FlextInfraEnsurePyrightConfigPhase(tool_config_document).apply_payload(
            payload,
            context=m.Infra.PyprojectAnalyzerContext(
                is_root=False,
                project_dir=tmp_path,
                declared_python_dirs=roots,
                declared_python_dirs_are_complete=True,
            ),
        )
        (tmp_path / "pyproject.toml").write_text(
            u.Cli.toml_dumps(u.Cli.toml_document_from_mapping(payload)),
            encoding="utf-8",
        )
        context = m.Infra.GateContext(
            repository_root=tmp_path,
            reports_dir=tmp_path / ".reports",
        )
        result = FlextInfraPyrightGate(tmp_path).check(tmp_path, context)

        private_issues = tuple(
            issue for issue in result.issues if issue.code == "reportPrivateUsage"
        )
        assert bool(private_issues) is private
        assert result.result.passed is not private, result.raw_output
        if private:
            assert len(private_issues) == len(roots), result.raw_output
