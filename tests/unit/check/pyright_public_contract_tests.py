"""Native Pyright proves exported contracts and rejects private consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from flext_infra import FlextInfraEnsurePyrightConfigPhase, m, t, u
from flext_infra.gates.pyright import FlextInfraPyrightGate

if TYPE_CHECKING:
    from pathlib import Path


class TestsPyrightPublicContract:
    """Exercise the configured semantic owner with real source and type stubs."""

    @pytest.mark.slow
    @pytest.mark.parametrize("distinct_categories", [False, True])
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
        self,
        tmp_path: Path,
        tool_config_document: m.Infra.ToolConfigDocument,
        consumer: str,
        *,
        private: bool,
        distinct_categories: bool,
    ) -> None:
        """Aliases and explicit exports stay public; shadowed receivers do not."""
        rules = tool_config_document.tools.pyright.path_rules
        if distinct_categories:
            rules = rules.model_copy(
                update={
                    "source_report_private_usage": "none",
                    "test_like_report_private_usage": "warning",
                    "other_report_private_usage": "error",
                }
            )
            pyright = tool_config_document.tools.pyright.model_copy(
                update={"path_rules": rules}
            )
            tools = tool_config_document.tools.model_copy(update={"pyright": pyright})
            tool_config_document = tool_config_document.model_copy(
                update={"tools": tools}
            )
        roots = tuple(
            dict.fromkeys((
                rules.source_dir,
                *rules.env_dirs,
                *rules.test_like_dirs,
                rules.project_root,
            ))
        )
        consumers: list[Path] = []
        for index, root in enumerate(roots):
            directory = tmp_path / root / "fixtures"
            directory.mkdir(parents=True, exist_ok=True)
            consumer_path = directory / f"consumer_{index}.py"
            consumer_path.write_text(consumer, encoding="utf-8")
            consumers.append(consumer_path)
        (tmp_path / rules.source_dir).mkdir(parents=True, exist_ok=True)
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
            repository_root=tmp_path, reports_dir=tmp_path / ".reports"
        )
        result = FlextInfraPyrightGate(tmp_path).check(tmp_path, context)

        private_issues = tuple(
            issue for issue in result.issues if issue.code == "reportPrivateUsage"
        )
        policies = [
            (tmp_path / override.root, override.report_private_usage)
            for override in rules.diagnostic_path_overrides
            if (tmp_path / override.root).is_dir()
        ]
        policies.extend(
            (
                tmp_path / root,
                rules.source_report_private_usage
                if root == rules.source_dir
                else rules.test_like_report_private_usage
                if root in rules.test_like_dirs
                else rules.other_report_private_usage,
            )
            for root in roots
        )
        expected = {
            str(path): severity
            for path in consumers
            if private
            and (
                severity := next(
                    level for root, level in policies if path.is_relative_to(root)
                )
            )
            != "none"
        }
        observed = {issue.file: issue.severity for issue in private_issues}
        assert observed == expected, result.raw_output
        assert len(private_issues) == len(expected), result.raw_output
        blocking = any(level in {"warning", "error"} for level in expected.values())
        assert result.result.passed is not blocking, result.raw_output
