"""uv.lock, written only by ``make upg``, owns every internal dependency pin.

Each ``flext-*`` requirement renders on its integration line. ``make upg``
re-resolves that line (``uv lock --upgrade --refresh``) to the branch tip and
records the commit in uv.lock; generation re-renders any commit left in the
pyproject projection on the detected line instead of writing it back, and no
manifest or override pins one beside the lock (flext-oe420).

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m, p, t
from tests import u


class TestsFlextInfraUpgOwnedDependencyPin:
    """Generation keeps the line; only the lock carries the commit."""

    PROVIDER = "https://example.org/flext"
    LINE = "0.12.0-dev"
    COMMIT = "b" * 40

    @classmethod
    def _requirement(cls, name: str, ref: str) -> str:
        return f"{name} @ git+{cls.PROVIDER}/{name}.git@{ref}"

    @classmethod
    def _consumer(
        cls,
        root: Path,
        core_ref: str,
        infra_ref: str = LINE,
        flext_source: str = "",
    ) -> str:
        """Write one standalone consumer declaring the family on the given refs.

        Returns:
            The resulting ``str``.

        """
        (root / "config").mkdir(parents=True)
        repository: t.JsonDict = {
            "name": "consumer",
            "distribution": "consumer",
            "provider": "example",
            "url": "https://example.org/consumer.git",
            "path": ".",
            "role": "standalone",
            "codegen": "conform",
            "package": True,
            "editable": False,
            "read_only": False,
        }
        manifest: t.JsonDict = {
            "version": 3,
            "name": "consumer",
            "repository": repository,
        }
        if flext_source:
            manifest["project"] = {
                **u.Tests.project_spec("consumer").model_dump(mode="json"),
                "flext_source": flext_source,
            }
        tm.ok(u.Cli.yaml_dump(root / "config" / "workspace.yaml", manifest))
        source = (
            '[project]\nname = "consumer"\nversion = "0.1.0"\n'
            f'dependencies = ["{cls._requirement("flext-core", core_ref)}"]\n'
            "[dependency-groups]\n"
            f'codegen = ["{cls._requirement("flext-infra", infra_ref)}"]\n'
            f'dev = ["{cls._requirement("flext-core", core_ref)}"]\n'
            "[tool.uv]\n"
            "override-dependencies = "
            f'["{cls._requirement("flext-core", cls.COMMIT)}"]\n'
        )
        (root / c.PYPROJECT_FILENAME).write_text(source, encoding="utf-8")
        return source

    @staticmethod
    def _conform(
        source: str,
        flext_line: m.Infra.WorkspaceIntegrationSpec | None = None,
    ) -> p.Result[str]:
        toolchain = config.Infra.codegen.toolchain
        workspace = u.Tests.workspace_spec(u.Tests.repository_ref("consumer"))
        return u.Infra.pyproject_conform(
            source,
            workspace=workspace,
            required_dev_dependencies=(),
            uv_resolution=m.Infra.UvResolutionSpec(
                link_mode=toolchain.uv_link_mode,
                constraint_dependencies=tuple(toolchain.uv_constraint_dependencies),
                exclude_dependencies=(),
                environments=tuple(toolchain.uv_environments),
            ),
            options=u.Infra.PyprojectConformOptions(
                flext_line=flext_line,
            ),
        )

    def test_generation_keeps_the_line_and_drops_override_pins(
        self,
        tmp_path: Path,
    ) -> None:
        """Every internal requirement stays on its line; no override survives."""
        source = self._consumer(tmp_path, self.LINE)
        rendered = tm.ok(self._conform(source))
        for section, key in (
            ("project", "dependencies"),
            ("dependency-groups", "dev"),
            ("dependency-groups", "codegen"),
        ):
            for requirement in u.Tests.toml_strings_at(rendered, section, key):
                tm.that(requirement.endswith(f".git@{self.LINE}"), eq=True)
        tm.that(rendered, lacks=self.COMMIT)
        tm.that(rendered, lacks="override-dependencies")
        tm.that(tm.ok(self._conform(rendered)), eq=rendered)
        line = tm.ok(
            u.Infra.flext_integration_line(
                codegen=config.Infra.codegen,
                repository_root=tmp_path,
            ),
        )
        tm.that((line.base_url, line.branch), eq=(self.PROVIDER, self.LINE))

    def test_commit_residue_is_re_rendered_on_the_detected_line(
        self,
        tmp_path: Path,
    ) -> None:
        """A retired pin left in the projection never survives generation."""
        source = self._consumer(tmp_path, self.COMMIT, self.COMMIT)
        line = m.Infra.WorkspaceIntegrationSpec(
            provider=u.Tests.provider().name,
            branch=self.LINE,
            base_url=self.PROVIDER,
        )
        rendered = tm.ok(self._conform(source, line))
        tm.that(rendered, lacks=self.COMMIT)
        tm.that(rendered, has=self._requirement("flext-core", self.LINE))
        tm.that(tm.ok(self._conform(rendered, line)), eq=rendered)
        tm.fail(self._conform(source), has="only `make upg` moves it")

    def test_a_fully_pinned_projection_takes_the_line_from_the_manifest(
        self,
        tmp_path: Path,
    ) -> None:
        """Commit residue declares no line: the hand-authored source does."""
        pinned = tmp_path / "pinned"
        self._consumer(pinned, self.COMMIT, self.COMMIT)
        tm.fail(
            u.Infra.flext_integration_line(
                codegen=config.Infra.codegen,
                repository_root=pinned,
            ),
            has="no manifest flext_source",
        )
        declared = tmp_path / "declared"
        self._consumer(
            declared,
            self.COMMIT,
            self.COMMIT,
            flext_source=self._requirement("flext-infra", self.LINE),
        )
        line = tm.ok(
            u.Infra.flext_integration_line(
                codegen=config.Infra.codegen,
                repository_root=declared,
            ),
        )
        tm.that((line.base_url, line.branch), eq=(self.PROVIDER, self.LINE))

    def test_a_hand_authored_commit_fails_loudly(self, tmp_path: Path) -> None:
        """A commit in the manifest's flext_source is a pin beside uv.lock."""
        self._consumer(
            tmp_path,
            self.COMMIT,
            self.COMMIT,
            flext_source=self._requirement("flext-infra", self.COMMIT),
        )
        tm.fail(
            u.Infra.flext_integration_line(
                codegen=config.Infra.codegen,
                repository_root=tmp_path,
            ),
            has="never a commit",
        )

    def test_mixed_providers_remain_ambiguous(self, tmp_path: Path) -> None:
        """One family line: two providers on the same line still fail loudly."""
        source = self._consumer(tmp_path, self.LINE)
        (tmp_path / c.PYPROJECT_FILENAME).write_text(
            source.replace(self.PROVIDER, "https://other.example.org/flext", 1),
            encoding="utf-8",
        )
        tm.fail(
            u.Infra.flext_integration_line(
                codegen=config.Infra.codegen,
                repository_root=tmp_path,
            ),
            has="conflicting flext-* line sources",
        )

    def test_the_manifest_carries_no_revision_pins(self) -> None:
        """The retired manifest pin is rejected, never silently ignored."""
        retired = {
            **u.Tests.project_spec("consumer").model_dump(),
            "dependency_revisions": {"flext-core": self.COMMIT},
        }
        with pytest.raises(ValueError, match="dependency_revisions"):
            m.Infra.ProjectSpec.model_validate(retired)
