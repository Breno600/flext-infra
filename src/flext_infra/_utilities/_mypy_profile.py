"""Profile the public Mypy API without its command-line hard exit.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import cProfile
import sys

from mypy import api

from flext_infra import m


class FlextInfraMypyProfiler:
    """Preserve native reports and status while recording the checker profile."""

    @staticmethod
    def run(invocation: m.Infra.MypyInvocation) -> int:
        """Run the public checker API, whose clean exit lets cProfile save data.

        Returns:
            The resulting ``int``.

        Raises:
            ValueError: If Mypy profiling requires an output destination.

        """
        from flext_infra import u

        destination = invocation.profile_output
        if destination is None:
            msg = "Mypy profiling requires an output destination"
            raise ValueError(msg)
        profile = cProfile.Profile()
        stdout, stderr, status = profile.runcall(
            api.run,
            list(u.Infra.mypy_arguments(invocation)),
        )
        profile.dump_stats(str(destination.resolve()))
        sys.stdout.write(stdout)
        sys.stderr.write(stderr)
        return status


if __name__ == "__main__":
    (request,) = sys.argv[1:]
    raise SystemExit(
        FlextInfraMypyProfiler.run(m.Infra.MypyInvocation.model_validate_json(request)),
    )
