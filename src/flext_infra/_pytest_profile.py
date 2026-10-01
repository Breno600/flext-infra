"""Cold-start pytest execution adapter; runtime imports here are stdlib only."""

from __future__ import annotations

import cProfile
import runpy
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from flext_infra import m, t


class FlextInfraPytestProfile:
    """Profile pytest imports and execution without replacing its exit handling."""

    def __init__(self, output: Path) -> None:
        """Keep the profile bound to only the context observed in this invocation."""
        self.output = output
        self.context: m.Infra.PytestRunContext | None = None

    def run_parent(
        self,
        *,
        started_at_monotonic: float,
        collection_command_prefix: t.StrTuple,
    ) -> int:
        """Start profiling before importing the runner or any FLEXT service."""
        if not collection_command_prefix:
            msg = "profile execution requires an injected collection command prefix"
            raise ValueError(msg)
        if not self.output.resolve().is_relative_to(
            (Path.cwd() / ".reports").resolve(),
        ):
            msg = "parent profile must stay under the repository reports directory"
            raise ValueError(msg)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.context = None
        self.output.with_suffix(".pstats.json").unlink(missing_ok=True)
        profile = cProfile.Profile()
        try:
            return profile.runcall(
                self._run_parent,
                started_at_monotonic,
                collection_command_prefix,
            )
        finally:
            self._finish(profile)

    def run_collection(self, receipt_path: Path, arguments: t.StrTuple) -> int:
        """Measure receipt/model imports and pytest itself; restore the original argv."""
        self.context = None
        self.output.with_suffix(".pstats.json").unlink(missing_ok=True)
        original_argv = sys.argv
        profile = cProfile.Profile()
        try:
            sys.argv = ["pytest", *arguments]
            return profile.runcall(self._run_collection, receipt_path)
        finally:
            sys.argv = original_argv
            self._finish(profile)

    def _record_context(self, context: m.Infra.PytestRunContext) -> None:
        """Receive the runner's actual context, never a latest-run pointer."""
        self.context = context

    def _run_parent(self, started_at_monotonic: float, prefix: t.StrTuple) -> int:
        from flext_infra.validate.pytest_runner import FlextInfraPytestRunner

        runner = FlextInfraPytestRunner.from_environment(
            started_at_monotonic=started_at_monotonic,
            collection_command_prefix=prefix,
        )
        exit_code = runner.execute().unwrap()
        # The runner publishes its run context itself; the parent binds the
        # profile artifacts to the receipt that invocation just wrote.
        from flext_infra import m

        reports_root = runner.root / runner.reports
        latest = max(
            reports_root.glob("*/run-context.json"),
            key=lambda receipt: receipt.stat().st_mtime,
        )
        self._record_context(
            m.Infra.PytestRunContext.model_validate_json(
                latest.read_text(encoding="utf-8"),
            ),
        )
        return exit_code

    def _run_collection(self, receipt_path: Path) -> int:
        from flext_infra import m

        context = m.Infra.PytestRunContext.model_validate_json(
            receipt_path.read_text(encoding="utf-8"),
        )
        if (
            context.report_directory is None
            or context.report_directory.resolve() != receipt_path.parent.resolve()
            or self.output.parent.resolve() != receipt_path.parent.resolve()
            or context.profile_sha256 is not None
        ):
            msg = "collection profile run receipt does not match its report directory"
            raise ValueError(msg)
        if time.monotonic() >= context.deadline_monotonic:
            msg = "collection profile run receipt has an expired deadline"
            raise ValueError(msg)
        self.context = context
        runpy.run_module("pytest", run_name="__main__", alter_sys=True)
        return 0

    def _finish(self, profile: cProfile.Profile) -> None:
        """Keep raw profiles on early failure, but publish only this run's receipt."""
        profile.dump_stats(str(self.output))
        if self.context is not None:
            from flext_infra import u

            receipt = self.context.model_copy(
                update={"profile_sha256": u.Cli.sha256_bytes(self.output.read_bytes())},
            )
            u.Cli.atomic_write_text_file(
                self.output.with_suffix(".pstats.json"),
                receipt.model_dump_json(indent=2) + "\n",
            ).unwrap()
