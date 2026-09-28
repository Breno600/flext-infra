"""Validated environment and filesystem boundary for pytest execution."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Self

from flext_infra import c, config, m, u
from flext_infra.base import s

type PytestPolicy = m.Infra.PytestConfig


class FlextInfraPytestRunnerBase(s[int]):
    """Own immutable inputs shared by all pytest runner phases."""

    started_at_monotonic: Annotated[
        float, m.Field(gt=0, description="Clock captured before FLEXT imports.")
    ]
    target: Annotated[Path, m.Field(description="Repository-relative test root.")]
    reports: Annotated[Path, m.Field(description="Repository-relative report root.")]
    ci_context: Annotated[
        bool,
        m.Field(description="CI/pre-commit selection captured at the Make boundary."),
    ] = False

    @staticmethod
    def _environment_value(name: str) -> str:
        """Read one Make-owned runner input."""
        return u.Cli.env_read(name, dict(os.environ)).unwrap().strip()

    @classmethod
    def from_environment(cls, *, started_at_monotonic: float) -> Self:
        """Create the runner exclusively from generated Make inputs."""
        ci = config.Infra.codegen.make.ci
        return cls(
            repository_root=Path.cwd(),
            started_at_monotonic=started_at_monotonic,
            ci_context=(u.Infra.env_lookup(ci.variable) or "").strip() == ci.value,
            target=Path(cls._environment_value(c.Infra.PYTEST_ENV_TARGET)),
            reports=Path(cls._environment_value(c.Infra.PYTEST_ENV_REPORTS)),
        )

    @property
    def testmon_db(self) -> Path:
        """Pytest-testmon's own default database in the repository root."""
        return self.root / config.Infra.codegen.make.testmon_cache.database_filename

    @u.model_validator(mode="after")
    def _validate_paths(self) -> Self:
        """Require repository-contained target and report paths."""
        for name, path in (("target", self.target), ("reports", self.reports)):
            raw = str(path)
            if (
                path.is_absolute()
                or not path.parts
                or any(part in {"", ".", ".."} for part in path.parts)
                or any(character in raw for character in "\0\r\n\\")
            ):
                msg = f"{name} must be a normalized repository-relative path"
                raise ValueError(msg)
            resolved = (self.root / path).resolve()
            if not resolved.is_relative_to(self.root.resolve()):
                msg = f"{name} escapes the repository"
                raise ValueError(msg)
        target_path = self.root / self.target
        if not target_path.is_dir() or target_path.is_symlink():
            msg = f"test target must be an existing directory: {self.target}"
            raise ValueError(msg)
        return self

    @staticmethod
    def _memory_gb() -> int:
        """Read physical memory from the operating-system owner."""
        page_size = os.sysconf("SC_PAGE_SIZE")
        pages = os.sysconf("SC_PHYS_PAGES")
        if page_size <= 0 or pages <= 0:
            msg = "physical memory capacity is unavailable"
            raise ValueError(msg)
        memory_gb = (page_size * pages) // (1024**3)
        if memory_gb <= 0:
            msg = "physical memory is below one GiB"
            raise ValueError(msg)
        return memory_gb

    def _declared_worker_ceiling(self, policy: PytestPolicy) -> int:
        """Resolve the declared project's ceiling over the fleet default.

        A tree without a declared ``[project].name`` (fixture projects, raw
        workbenches) is an expected state and takes the fleet-wide default.
        """
        if not policy.parallel_worker_overrides:
            return policy.parallel_workers
        pyproject_path = self.root / c.PYPROJECT_FILENAME
        try:
            name = u.Infra.project_name_from_payload(
                pyproject_path, u.Infra.pyproject_payload(pyproject_path)
            )
        except (TypeError, ValueError):
            return policy.parallel_workers
        return policy.parallel_worker_overrides.get(name, policy.parallel_workers)

    def parallel_worker_budget(self, policy: PytestPolicy) -> int:
        """Bound xdist by configuration, CPU, and physical memory.

        The per-project override map (``[project].name`` → workers) is where
        a consumer whose measured suite cannot fit the single-worker process
        boundary declares its ceiling; the fleet-wide default stays one
        worker so ``max-failures: 1`` remains exact everywhere else.
        """
        ceiling = self._declared_worker_ceiling(policy)
        cpu_count = os.cpu_count()
        if cpu_count is None or cpu_count <= 0:
            msg = "CPU capacity is unavailable"
            raise ValueError(msg)
        memory_workers = self._memory_gb() // policy.parallel_worker_memory_gb
        if memory_workers <= 0:
            msg = "physical memory cannot support one pytest worker"
            raise ValueError(msg)
        return min(ceiling, cpu_count, memory_workers)

    def _report_directory(self) -> Path:
        """Create a collision-resistant report directory."""
        run_id = datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%S.%fZ") + f"-{os.getpid()}"
        report_dir: Path = self.root / self.reports / run_id
        u.Cli.ensure_dir(report_dir).unwrap()
        return report_dir


__all__: list[str] = ["FlextInfraPytestRunnerBase"]
