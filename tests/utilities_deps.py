"""Public dependency-test execution utilities for flext-infra."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from flext_infra import config, u
from tests import c, m, p, t


class TestsFlextInfraUtilitiesDepsMixin:
    """Shared dependency-test execution and service fixture owners."""

    @staticmethod
    def record_dependency_command_output(output: p.Cli.CommandOutput) -> None:
        """Keep the original subprocess evidence outside disposable test scratch."""
        receipt = (
            Path(__file__).resolve().parents[1]
            / config.Infra.codegen.make.testmon_cache.reports_directory
            / "dependency-commands"
            / f"{uuid4()}.json"
        )
        recorded = m.Cli.CommandOutput.model_validate(output, from_attributes=True)
        u.Cli.atomic_write_text_file(
            receipt, recorded.model_dump_json(indent=2) + "\n"
        ).unwrap()

    @staticmethod
    def run_real_detector(
        root: Path,
        *arguments: str,
        env: t.StrMapping | None = None,
        repository_root: Path | None = None,
    ) -> p.Result[p.Cli.CommandOutput]:
        """Run the public detector in its provisioned interpreter, without overrides."""
        runtime = root / Path(c.Infra.VENV_BIN_REL).parent
        environment = {
            "UV_PROJECT_ENVIRONMENT": str(runtime),
            "VIRTUAL_ENV": str(runtime),
        }
        if env is not None:
            environment.update(env)
        result = u.Cli.run_raw(
            [
                str(runtime / "bin" / "python"),
                "-m",
                "flext_infra",
                "deps",
                "detect",
                "--repository-root",
                str(repository_root if repository_root is not None else root),
                "--limits",
                str(root / "limits.toml"),
                *arguments,
            ],
            cwd=root,
            env=environment,
        )
        if result.success:
            TestsFlextInfraUtilitiesDepsMixin.record_dependency_command_output(
                result.value
            )
        return result

    @staticmethod
    def detect_command(
        repository_root: Path, **overrides: t.JsonValue
    ) -> m.Infra.DetectCommand:
        """Create a validated dependency-detection command."""
        validated: m.Infra.DetectCommand = m.Infra.DetectCommand.model_validate({
            "repository_root": str(repository_root),
            **overrides,
        })
        return validated


__all__: list[str] = ["TestsFlextInfraUtilitiesDepsMixin"]
