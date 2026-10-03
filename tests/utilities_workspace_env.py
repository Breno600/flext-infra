"""Workspace profile and environment test utilities for flext-infra.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from flext_tests import tm

from flext_infra import config, u
from tests import c, m, p, t


class TestsFlextInfraUtilitiesWorkspaceEnvMixin:
    """Workspace profile, gitignore, and process-environment helpers."""

    @staticmethod
    def restore_env(name: str, original: str | None) -> None:
        """Restore one environment variable to its original value or remove it."""
        if original:
            os.environ[name] = original
        else:
            os.environ.pop(name, None)

    @staticmethod
    def repository_profile(root: Path) -> c.Infra.MakeProfile:
        """Return the Make profile derived from the repository itself.

        Returns:
            The Make profile derived from the repository itself.

        """
        from flext_infra.workspace.detector import FlextInfraWorkspaceDetector

        mode = tm.ok(FlextInfraWorkspaceDetector().detect(root))
        by_mode: t.MutableMappingKV[c.Infra.MakeProfile, c.Infra.MakeProfile] = {
            c.Infra.MakeProfile.WORKSPACE: c.Infra.MakeProfile.WORKSPACE,
            c.Infra.MakeProfile.STANDALONE: c.Infra.MakeProfile.STANDALONE,
        }
        return by_mode[mode]

    @staticmethod
    def ignore_patterns_for_profile(profile: c.Infra.MakeProfile) -> t.StrTuple:
        """Return every SSOT ignore pattern whose section targets *profile*.

        Taking the profile rather than a root lets a test state both sides of a
        profile-split rule from the SSOT alone. Deriving it from a path makes
        the same assertion depend on where the checkout happens to sit, which
        differs between the workspace and a standalone CI clone.

        Returns:
            Every SSOT ignore pattern whose section targets *profile*.

        """
        gitignore_sections: t.VariadicTuple[m.Infra.ScaffoldGitignoreSectionSpec] = (
            config.Infra.codegen.gitignore_sections
        )
        return tuple(
            pattern
            for section in gitignore_sections
            if not section.profiles or profile in section.profiles
            for pattern in section.patterns
        )

    @staticmethod
    def ignore_patterns_for(root: Path) -> t.StrTuple:
        """Return the ignore patterns that apply to *root*'s declared profile.

        Returns:
            Every SSOT pattern whose section targets that profile.

        """
        return TestsFlextInfraUtilitiesWorkspaceEnvMixin.ignore_patterns_for_profile(
            TestsFlextInfraUtilitiesWorkspaceEnvMixin.repository_profile(root),
        )

    @staticmethod
    def is_tracked_under(rendered: str, relative_path: str) -> bool:
        """Return whether git tracks *relative_path* under *rendered*.

        Ignore semantics are subtle (ordering, negation, directory
        prefixes), so the question is delegated to git itself against a
        throwaway repository, never reimplemented here.

        Returns:
            ``True`` when git would track the path.

        """
        with tempfile.TemporaryDirectory() as raw_root:
            probe_root = Path(raw_root)
            tm.ok(u.Cli.run_checked(["git", "init", "-q", str(probe_root)]))
            (probe_root / ".gitignore").write_text(rendered, encoding="utf-8")
            target = probe_root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")
            # `git check-ignore` exits 0 when the path IS ignored, so a
            # failed run is the success case for a tracked artifact.
            probe: p.Cli.CommandOutput = tm.ok(
                u.Cli.run_raw(
                    ["git", "check-ignore", "-q", relative_path],
                    cwd=probe_root,
                ),
            )
        code = probe.outcome.raw_return_code
        tm.that(code in {0, 1}, eq=True)
        return code == 1


__all__: list[str] = ["TestsFlextInfraUtilitiesWorkspaceEnvMixin"]
