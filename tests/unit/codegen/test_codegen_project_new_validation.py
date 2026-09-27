"""Declared remote validation contract for ``codegen new`` bootstrap inputs.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import c, config
from flext_infra.codegen.project_new import FlextInfraCodegenProjectNew
from tests import u


class TestsFlextInfraCodegenProjectNewValidation:
    """Prove declared bootstrap remotes are validated before any effect."""

    @staticmethod
    def _service(root: Path, **overrides: str) -> FlextInfraCodegenProjectNew:
        """Build one apply-mode project-new service with overridable inputs."""
        defaults: dict[str, str] = {
            "repository_url": "git@github.com:flext-sh/flext-demo.git",
            "repository_branch": "0.12.0-dev",
            "flext_repository_url": u.Tests.repository_ref(config.Infra.name).url,
            "flext_repository_ref": u.Tests.provider_branch(),
        }
        resolved = {**defaults, **overrides}
        return FlextInfraCodegenProjectNew(
            flext_source=u.Tests.flext_source(),
            name="flext-demo",
            kind=c.Infra.ProjectKind.INTERNAL_FLEXT,
            output_root=root,
            provider="flext-sh",
            license="MIT",
            author_name="FLEXT Team",
            author_email="team@flext.dev",
            upstream="flext_cli",
            year=2026,
            apply_changes=True,
            repository_url=resolved["repository_url"],
            repository_branch=resolved["repository_branch"],
            flext_repository_url=resolved["flext_repository_url"],
            flext_repository_ref=resolved["flext_repository_ref"],
        )

    def test_whitespace_flext_ref_is_rejected_without_effects(
        self, tmp_path: Path
    ) -> None:
        """A whitespace-only FLEXT ref fails before any directory exists."""
        result = self._service(
            tmp_path / "project", flext_repository_ref="   "
        ).execute()
        tm.fail(result, has="flext repository ref is required")
        tm.that(not (tmp_path / "project").exists())

    def test_hostless_flext_url_is_rejected_without_effects(
        self, tmp_path: Path
    ) -> None:
        """A URL without a host fails before any directory exists."""
        result = self._service(
            tmp_path / "project", flext_repository_url="https:///flext-demo.git"
        ).execute()
        tm.fail(result, has="must name a host and repository path")
        tm.that(not (tmp_path / "project").exists())

    def test_unparseable_origin_is_rejected_without_effects(
        self, tmp_path: Path
    ) -> None:
        """A project origin that is not a Git URL fails before any effect."""
        result = self._service(
            tmp_path / "project", repository_url="not-a-url"
        ).execute()
        tm.fail(result, has="not canonicalizable to HTTPS")
        tm.that(not (tmp_path / "project").exists())

    def test_ssh_origin_canonicalizes_to_https(self) -> None:
        """The declared origin is stored in its canonical HTTPS form."""
        canonical = u.Infra.validate_git_remote_url(
            "git@github.com:flext-sh/flext-demo.git"
        )
        tm.ok(canonical)
        tm.that(canonical.value, eq="https://github.com/flext-sh/flext-demo.git")

    def test_surrounding_whitespace_is_stripped_before_validation(self) -> None:
        """A padded but valid URL validates to the same canonical form."""
        padded = f"  {u.Tests.repository_ref(config.Infra.name).url}  "
        canonical = u.Infra.validate_git_remote_url(padded)
        tm.ok(canonical)
        tm.that(canonical.value, eq=u.Tests.repository_ref(config.Infra.name).url)

    def test_pathless_url_is_rejected(self) -> None:
        """A URL naming only a host carries no repository identity."""
        result = u.Infra.validate_git_remote_url("https://github.com")
        tm.fail(result, has="must name a host and repository path")
