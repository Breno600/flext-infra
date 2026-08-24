"""Tests for the public constants consolidator command service."""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_cli import m as cli_m
from flext_infra import c
from flext_infra.codegen.consolidator import FlextInfraCodegenConsolidator
from flext_tests import tm

from tests import t, u


class _ConsolidatorFilePayload(cli_m.ContractModel):
    """Typed JSON row emitted by the consolidator command."""

    file: str = cli_m.Field(description="Relative file path")
    status: str = cli_m.Field(description="File processing status")
    changes: t.StrSequence = cli_m.Field(description="Changes applied to the file")


class _ConsolidatorJsonPayload(cli_m.ContractModel):
    """Typed JSON payload emitted by the consolidator command."""

    total_found: int = cli_m.Field(description="Total replacements found")
    total_applied: int = cli_m.Field(description="Total replacements applied")
    total_failed: int = cli_m.Field(description="Total files that failed")
    files: t.SequenceOf[_ConsolidatorFilePayload] = cli_m.Field(
        description="Per-file consolidator results"
    )


def _consolidator_payload(value: str) -> _ConsolidatorJsonPayload:
    """Load and validate consolidator JSON output."""
    payload: _ConsolidatorJsonPayload = _ConsolidatorJsonPayload.model_validate_json(
        value
    )
    return payload


def test_execute_scans_real_package_layout(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    (workspace_root / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["flext-demo"]\n', encoding="utf-8"
    )
    project_root = workspace_root / "flext-demo"
    package_dir = project_root / "src" / "flext_demo"
    package_dir.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text(
        "[project]\nname='flext-demo'\nversion='0.1.0'\n"
        "\n"
        "[tool.mypy]\n"
        'mypy_path = ["src"]\n',
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "constants.py").write_text(
        "class FlextDemoConstants:\n    pass\n\nc = FlextDemoConstants\n",
        encoding="utf-8",
    )
    (package_dir / "module.py").write_text("VALUE = 1\n", encoding="utf-8")

    result = u.Tests.consolidate_codegen(workspace_root=workspace_root, dry_run=True)

    tm.ok(result)
    tm.that(result.value, has="Found")


def _build_consolidator_workspace(tmp_path: Path) -> Path:
    """Create a workspace with one project whose constants define a demo value."""
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)
    (workspace_root / "pyproject.toml").write_text(
        '[tool.uv.workspace]\nmembers = ["flext-demo"]\n', encoding="utf-8"
    )
    project_root = workspace_root / "flext-demo"
    package_dir = project_root / "src" / "flext_demo"
    package_dir.mkdir(parents=True)
    (project_root / "pyproject.toml").write_text(
        "[project]\nname='flext-demo'\nversion='0.1.0'\n"
        "\n"
        "[tool.mypy]\n"
        'mypy_path = ["src"]\n',
        encoding="utf-8",
    )
    (package_dir / "__init__.py").write_text("", encoding="utf-8")
    (package_dir / "__init__.py").write_text(
        "from flext_demo.constants import c\n", encoding="utf-8"
    )
    (package_dir / "constants.py").write_text(
        "from __future__ import annotations\n"
        "\n"
        "from types import SimpleNamespace\n"
        "from typing import Final\n"
        "\n"
        'DEMO_VALUE: Final[str] = "demo"\n'
        "c = SimpleNamespace(DEMO_VALUE=DEMO_VALUE)\n",
        encoding="utf-8",
    )
    (package_dir / "consumer.py").write_text(
        'from __future__ import annotations\n\nVALUE = "demo"\n', encoding="utf-8"
    )
    return workspace_root


def _write_wrapper_consumer(workspace_root: Path, segment: str) -> Path:
    """Create one wrapper-surface consumer for constants consolidation."""
    project_root = workspace_root / "flext-demo"
    consumer_path = project_root / segment / "consumer.py"
    consumer_path.parent.mkdir(parents=True, exist_ok=True)
    consumer_path.write_text(
        'from __future__ import annotations\n\nVALUE = "demo"\n', encoding="utf-8"
    )
    return consumer_path


def test_execute_apply_mode_replaces_literal_with_canonical_reference(
    tmp_path: Path,
) -> None:
    workspace_root = _build_consolidator_workspace(tmp_path)
    consumer_path = workspace_root / "flext-demo" / "src" / "flext_demo" / "consumer.py"

    result = u.Tests.consolidate_codegen(workspace_root=workspace_root, dry_run=False)

    tm.ok(result)
    tm.that(result.value, has="Applied 1 replacements")
    updated_source = consumer_path.read_text(encoding="utf-8")
    tm.that(updated_source, has="VALUE = c.DEMO_VALUE")
    tm.that(updated_source, has="from flext_demo import c")


@pytest.mark.parametrize(
    "wrapper_segment", sorted(c.Infra.ROOT_WRAPPER_SEGMENTS - {"src"})
)
def test_execute_apply_mode_scans_wrapper_surfaces(
    tmp_path: Path, wrapper_segment: str
) -> None:
    workspace_root = _build_consolidator_workspace(tmp_path)
    package_consumer_path = (
        workspace_root / "flext-demo" / "src" / "flext_demo" / "consumer.py"
    )
    package_consumer_path.write_text(
        'from __future__ import annotations\n\nVALUE = "covered-elsewhere"\n',
        encoding="utf-8",
    )
    wrapper_consumer_path = _write_wrapper_consumer(workspace_root, wrapper_segment)
    constants_family_path = (
        workspace_root
        / "flext-demo"
        / "src"
        / "flext_demo"
        / c.Infra.FAMILY_DIRECTORIES["c"]
        / "internal.py"
    )
    constants_family_path.parent.mkdir(parents=True, exist_ok=True)
    constants_family_path.write_text(
        'from __future__ import annotations\n\nVALUE = "demo"\n', encoding="utf-8"
    )
    service = FlextInfraCodegenConsolidator(
        workspace_root=workspace_root, dry_run=False, output_format="json"
    )

    result = service.execute()

    tm.ok(result)
    payload = _consolidator_payload(result.value)
    tm.that(payload.total_found, eq=1)
    tm.that(payload.total_applied, eq=1)
    tm.that(payload.total_failed, eq=0)
    tm.that(len(payload.files), eq=1)
    updated_source = wrapper_consumer_path.read_text(encoding="utf-8")
    tm.that(updated_source, has="VALUE = c.DEMO_VALUE")
    tm.that(updated_source, has="from flext_demo import c")
    tm.that(
        package_consumer_path.read_text(encoding="utf-8"),
        has='VALUE = "covered-elsewhere"',
    )
    constants_family_source = constants_family_path.read_text(encoding="utf-8")
    tm.that(constants_family_source, has='VALUE = "demo"')
    tm.that(constants_family_source, lacks="c.DEMO_VALUE")


@pytest.mark.slow
def test_execute_apply_mode_json_output(tmp_path: Path) -> None:
    workspace_root = _build_consolidator_workspace(tmp_path)
    service = FlextInfraCodegenConsolidator(
        workspace_root=workspace_root, dry_run=False, output_format="json"
    )

    result = service.execute()

    tm.ok(result)
    payload = _consolidator_payload(result.value)
    tm.that(payload.total_found, eq=1)
    tm.that(payload.total_applied, eq=1)
    tm.that(payload.total_failed, eq=0)
    tm.that(len(payload.files), eq=1)
    tm.that(payload.files[0].status, eq="applied")


def test_execute_dry_run_json_output(tmp_path: Path) -> None:
    workspace_root = _build_consolidator_workspace(tmp_path)
    service = FlextInfraCodegenConsolidator(
        workspace_root=workspace_root, dry_run=True, output_format="json"
    )

    result = service.execute()

    tm.ok(result)
    payload = _consolidator_payload(result.value)
    tm.that(payload.total_found, eq=1)
    tm.that(payload.total_applied, eq=0)
    tm.that(payload.total_failed, eq=0)
    tm.that(payload.files, eq=[])


__all__: t.StrSequence = []
