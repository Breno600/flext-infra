"""Prove the generated ignore file tracks the committed dependency locks."""

from __future__ import annotations

import pytest
from flext_tests import tm

from flext_infra import c, config
from flext_infra.codegen.conform import FlextInfraCodegenConform
from tests import u


class TestsFlextInfraLockfilePolicyProjection:
    """Every profile commits the locks `make upg` writes (operator 2026-09-24)."""

    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    @pytest.mark.parametrize(
        "lock_filename",
        [
            c.Infra.UV_LOCK_FILENAME,
            c.Infra.MISE_LOCK_FILENAME,
            c.Infra.MISE_VERSION_PIN_FILENAME,
            ".mise/locks/npm-fixture/1.0.0/package.json",
            ".mise/locks/npm-fixture/1.0.0/aube-lock.yaml",
            ".mise/locks/pypi-fixture/1.0.0/pyproject.toml",
            ".mise/locks/pypi-fixture/1.0.0/uv.lock",
        ],
    )
    def test_rendered_gitignore_tracks_dependency_locks(
        self, profile: c.Infra.MakeProfile, lock_filename: str
    ) -> None:
        """Git itself decides that the rendered ignore file keeps the lock tracked."""
        rendered = tm.ok(
            FlextInfraCodegenConform.render_project_gitignore(
                config.Infra.codegen, profile=profile, project_name="fixture-project"
            )
        )

        tm.that(u.Tests.is_tracked_under(rendered, lock_filename), eq=True)

    @pytest.mark.parametrize("profile", tuple(c.Infra.MakeProfile))
    @pytest.mark.parametrize(
        "relative_path",
        [
            ".mise/cache/download.tar.gz",
            ".mise/installs/tool/bin/tool",
            "mise.local.lock",
            "mise.test.local.lock",
            ".mise/locks/mise.local/npm-fixture/1.0.0/aube-lock.yaml",
            ".mise/locks/mise.test.local/npm-fixture/1.0.0/aube-lock.yaml",
        ],
    )
    def test_rendered_gitignore_keeps_local_mise_state_untracked(
        self, profile: c.Infra.MakeProfile, relative_path: str
    ) -> None:
        """Track native dependency graphs without tracking local installation state."""
        rendered = tm.ok(
            FlextInfraCodegenConform.render_project_gitignore(
                config.Infra.codegen, profile=profile, project_name="fixture-project"
            )
        )

        tm.that(u.Tests.is_tracked_under(rendered, relative_path), eq=False)


__all__: list[str] = ["TestsFlextInfraLockfilePolicyProjection"]
