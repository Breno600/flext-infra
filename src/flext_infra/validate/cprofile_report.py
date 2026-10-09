"""Typed renderer for canonical focused cProfile artifacts.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import io
import pstats
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal, Self, override

from flext_infra import m, r, u
from flext_infra.base import s

if TYPE_CHECKING:
    from flext_infra import p, t


class FlextInfraCProfileReport(s[bool]):
    """Render one bounded human-readable report from a pstats artifact."""

    profile: Annotated[Path, m.Field(description="Input cProfile pstats path")]
    output: Annotated[Path, m.Field(description="Output text report path")]
    sort: Annotated[
        Literal[
            "calls",
            "cumulative",
            "filename",
            "line",
            "name",
            "nfl",
            "pcalls",
            "stdname",
            "time",
        ],
        m.Field(description="Validated pstats sort key"),
    ]
    limit: Annotated[int, m.Field(gt=0, le=1000, description="Maximum rows to print")]
    run_receipt: Annotated[
        Path | None,
        m.Field(
            description="Parent profile receipt for a collection profiling run",
        ),
    ] = None

    @u.model_validator(mode="after")
    def _validate_report_paths(self) -> Self:
        """Keep profile input and output inside the workspace report tree.

        Returns:
            The resulting ``Self``.

        Raises:
            ValueError: If cProfile path must stay under.

        """
        report_root = (self.repository_root / ".reports").resolve()
        for path in (
            self.profile,
            self.output,
            *((self.run_receipt,) if self.run_receipt is not None else ()),
        ):
            try:
                path.resolve().relative_to(report_root)
            except ValueError as exc:
                msg = f"cProfile path must stay under {report_root}: {path}"
                raise ValueError(msg) from exc
        return self

    def _run_profiles(self) -> t.VariadicTuple[Path]:
        """Validate run identity and artifact digests without consulting latest.

        Returns:
            The resulting ``t.VariadicTuple[Path]``.

        Raises:
            ValueError: If profile run receipt has no valid report directory; or if
                profile run receipt does not match the recorded run context; or if
                profile selection plan does not match its run directory; or if stale or
                mismatched profile run receipt.

        """
        if self.run_receipt is None:
            return (self.profile,)
        parent = m.Infra.PytestRunContext.model_validate_json(
            self.run_receipt.read_text(encoding="utf-8"),
        )
        directory = parent.report_directory
        if directory is None or not directory.resolve().is_relative_to(
            (self.repository_root / ".reports").resolve(),
        ):
            msg = "profile run receipt has no valid report directory"
            raise ValueError(msg)
        context = m.Infra.PytestRunContext.model_validate_json(
            (directory / "run-context.json").read_text(encoding="utf-8"),
        )
        if (
            context.report_directory != directory
            or context.profile_sha256 is not None
            or parent.model_copy(update={"profile_sha256": None}) != context
        ):
            msg = "profile run receipt does not match the recorded run context"
            raise ValueError(msg)
        plan = m.Infra.PytestSelectionPlan.model_validate_json(
            (directory / "selection-plan.json").read_text(encoding="utf-8"),
        )
        if plan.manifest_path.parent.resolve() != directory.resolve():
            msg = "profile selection plan does not match its run directory"
            raise ValueError(msg)
        profiles = (
            self.profile,
            directory / "testmon-selection.pstats",
            *(
                (directory / "testmon-inventory.pstats",)
                if plan.inventory_collected
                else ()
            ),
        )
        for profile in profiles:
            receipt = (
                parent
                if profile == self.profile
                else m.Infra.PytestRunContext.model_validate_json(
                    profile.with_suffix(".pstats.json").read_text(encoding="utf-8"),
                )
            )
            if receipt.model_copy(
                update={"profile_sha256": None},
            ) != context or receipt.profile_sha256 != u.Cli.sha256_bytes(
                profile.read_bytes(),
            ):
                msg = f"stale or mismatched profile run receipt: {profile}"
                raise ValueError(msg)
        return profiles

    @override
    def execute(self) -> p.Result[bool]:
        """Load, sort, and render the profile without executing user code.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        if not self.profile.is_file():
            return r[bool].fail(f"cProfile artifact does not exist: {self.profile}")
        try:
            stream = io.StringIO()
            for profile in self._run_profiles():
                stream.write(f"Profile: {profile}\n")
                stats = pstats.Stats(str(profile), stream=stream)
                stats.strip_dirs().sort_stats(self.sort).print_stats(self.limit)
            self.output.parent.mkdir(parents=True, exist_ok=True)
        except (OSError, ValueError, TypeError) as exc:
            return r[bool].fail(f"render cProfile report failed: {exc}", exception=exc)
        written = u.Cli.atomic_write_text_file(self.output, stream.getvalue())
        if written.failure:
            return r[bool].from_failure(written)
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraCProfileReport"]
