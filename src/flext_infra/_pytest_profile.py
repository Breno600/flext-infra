"""Cold-start pytest execution adapter; runtime imports here are stdlib only.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import cProfile
import os
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
        """Start profiling before importing the runner or any FLEXT service.

        Returns:
            The resulting ``int``.

        Raises:
            ValueError: If profile execution requires an injected collection command
                prefix; or if parent profile must stay under the repository reports
                directory.

        """
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
        """Measure receipt/model imports and pytest itself; restore the original argv.

        Returns:
            The resulting ``int``.

        """
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
            profile_enabled=True,
        )
        # The runner publishes its run context before any child can fail; the
        # parent binds the profile to the receipt THIS invocation wrote, also
        # when the run fails (a blocked collection is a profiled run too). The
        # runner executes in this process and names its report directory with
        # this pid, so a concurrent run under the shared reports root (another
        # pid) and a receipt that predates this run are both excluded.
        from flext_infra import m

        reports_root = runner.root / runner.reports
        preexisting = frozenset(reports_root.glob("*/run-context.json"))

        def owned_receipts() -> list[Path]:
            return [
                receipt
                for receipt in reports_root.glob(f"*-{os.getpid()}/run-context.json")
                if receipt not in preexisting
            ]

        def bind(owned: list[Path]) -> None:
            if owned:
                self._record_context(
                    m.Infra.PytestRunContext.model_validate_json(
                        owned[0].read_text(encoding="utf-8"),
                    ),
                )

        try:
            outcome = runner.execute().unwrap()
        except BaseException as failure:
            owned = owned_receipts()
            if len(owned) > 1:
                # The original failure stays the one raised; the ambiguity
                # travels with it instead of replacing it.
                failure.add_note(f"profile left unbound: run contexts {owned}")
            else:
                bind(owned)
            raise
        owned = owned_receipts()
        if len(owned) > 1:
            msg = f"profiled run published more than one run context: {owned}"
            raise RuntimeError(msg)
        bind(owned)
        return outcome

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
        from flext_infra import config

        policy = config.Infra.tooling.tools.pytest
        if self.output.name == policy.profile_suite_filename:
            process_dir = self.output.parent / policy.profile_process_directory
            process_dir.mkdir(parents=True, exist_ok=True)
            (process_dir / f"{os.getpid()}{self.output.suffix}").hardlink_to(
                self.output,
            )
        if self.context is not None:
            from flext_infra import u

            receipt = self.context.model_copy(
                update={"profile_sha256": u.Cli.sha256_bytes(self.output.read_bytes())},
            )
            u.Cli.atomic_write_text_file(
                self.output.with_suffix(".pstats.json"),
                receipt.model_dump_json(indent=2) + "\n",
            ).unwrap()
