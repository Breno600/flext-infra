"""Tests for the module-cap SUPREME LAW (§3.1) gate.

The gate flags any module whose real scc `Code` line count exceeds the
config-owned ceiling and accepts modules under it, exercised through the public
gate runner. Fixtures derive from that config-owned ceiling so a legitimate cap
change never silently inverts these assertions (UNIVERSAL_CORE P0).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import config, m
from flext_infra.gates.loc_cap import FlextInfraLocCapGate
from tests import c, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraLocCapGate:
    @staticmethod
    def gate_project(tmp_path: Path, *, code_lines: int) -> Path:
        """Create one real project whose sample module carries ``code_lines``."""
        module = "from __future__ import annotations\n\n" + "".join(
            f"x{index} = {index}\n" for index in range(code_lines)
        )
        return u.Tests.create_codegen_project(
            tmp_path=tmp_path,
            name="demo-project",
            pkg_name="demo_project",
            files={"sample.py": module},
        )

    def test_gate_identity(self) -> None:
        tm.that(FlextInfraLocCapGate.gate_id, eq="loc-cap")
        tm.that(FlextInfraLocCapGate.can_fix, eq=False)

    @pytest.mark.parametrize(
        ("code_lines", "passed"),
        [(config.Infra.codegen.loc_cap.max_lines + 50, False), (1, True)],
    )
    def test_cap_is_enforced_on_real_scc_counts(
        self, tmp_path: Path, code_lines: int, *, passed: bool
    ) -> None:
        project = self.gate_project(tmp_path, code_lines=code_lines)

        result = u.Tests.run_gate_check(FlextInfraLocCapGate, tmp_path, project)

        tm.that(result.result.passed, eq=passed)
        flagged = [issue.file for issue in result.issues if issue.code == "LOC_CAP"]
        tm.that(len(flagged), eq=0 if passed else 1)
        tm.that(all(path.endswith("sample.py") for path in flagged), eq=True)

    def test_unavailable_scanner_is_not_silenced(self, tmp_path: Path) -> None:
        project = self.gate_project(tmp_path, code_lines=1)
        empty_path = tmp_path / "empty-path"
        empty_path.mkdir()

        with (
            tm.scope(env={"PATH": str(empty_path)}),
            pytest.raises(RuntimeError, match=c.Infra.SCC_BINARY),
        ):
            u.Tests.run_gate_check(FlextInfraLocCapGate, tmp_path, project)

    @pytest.mark.parametrize(
        "payload",
        [
            "",
            "not-json",
            "null",
            "{}",
            "[null]",
            '[{"Files":[]}]',
            '[{"Name":"Python"}]',
            '[{"Name":"Python","Files":null}]',
            '[{"Name":"Python","Files":[null]}]',
            '[{"Name":"Python","Files":[{"Code":1}]}]',
            '[{"Name":"Python","Files":[{"Location":"sample.py"}]}]',
            '[{"Name":"Python","Files":[{"Location":"","Code":1}]}]',
            '[{"Name":"Python","Files":[{"Location":"sample.py","Code":-1}]}]',
            '[{"Name":"Python","Files":[{"Location":"sample.py","Code":"1"}]}]',
            '[{"Name":"Python","Files":[{"Location":"sample.py","Code":true}]}]',
        ],
    )
    def test_scc_boundary_rejects_incomplete_or_malformed_output(
        self, payload: str
    ) -> None:
        """Invalid native reports cannot become an empty successful scan."""
        with pytest.raises(c.ValidationError):
            m.Infra.SccReport.model_validate_json(payload, strict=True)

    @pytest.mark.parametrize("payload", ["[]", '[{"Name":"Python","Files":[]}]'])
    def test_scc_boundary_accepts_valid_empty_collections(self, payload: str) -> None:
        """Empty scanner collections differ from absent or malformed output."""
        report = m.Infra.SccReport.model_validate_json(payload, strict=True)

        tm.that(tuple(file for group in report.root for file in group.files), eq=())

    def test_generated_header_is_read_relative_to_scanned_project(
        self, tmp_path: Path
    ) -> None:
        """A real SCC relative path resolves under the project, not the caller."""
        project = self.gate_project(
            tmp_path, code_lines=config.Infra.codegen.loc_cap.max_lines + 1
        )
        module = project / "src" / "demo_project" / "sample.py"
        source = module.read_text(encoding=c.Cli.ENCODING_DEFAULT)
        module.write_text(
            f"{c.Infra.AUTOGEN_HEADER}\n{source}", encoding=c.Cli.ENCODING_DEFAULT
        )
        gate = FlextInfraLocCapGate(tmp_path)

        result = gate.check_files((module,), project, u.Tests.gate_context(tmp_path))

        tm.that(result.result.passed, eq=True)
        tm.that(result.issues, eq=())
        report = m.Infra.SccReport.model_validate_json(result.raw_output, strict=True)
        scanned_paths = tuple(
            project / file.location
            for language in report.root
            for file in language.files
        )
        tm.that(scanned_paths, has=module)

    def test_invalid_source_encoding_is_not_a_generated_header_fallback(
        self, tmp_path: Path
    ) -> None:
        """SCC counts bytes; reading an invalid Python UTF-8 header must fail."""
        project = self.gate_project(
            tmp_path, code_lines=config.Infra.codegen.loc_cap.max_lines + 1
        )
        module = project / "src" / "demo_project" / "sample.py"
        module.write_bytes(b"# \xff\n" + module.read_bytes())
        gate = FlextInfraLocCapGate(tmp_path)

        with pytest.raises(UnicodeDecodeError):
            gate.check_files((module,), project, u.Tests.gate_context(tmp_path))
