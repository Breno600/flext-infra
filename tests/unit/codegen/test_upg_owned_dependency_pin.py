"""uv.lock, written only by ``make upg``, owns every internal dependency pin.

A consumer declares each ``flext-*`` dependency on its integration line. ``make
upg`` re-resolves that line (``uv lock --upgrade --refresh``) to the branch tip
and records the commit in uv.lock; generation never writes a commit back into
pyproject, and no manifest or override pins one beside the lock (flext-oe420).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from flext_tests import tm

from flext_infra import c, config, m, p, t, u
from tests import TestsFlextInfraUtilities as tu, u as test_u


class TestsFlextInfraUpgOwnedDependencyPin:
    """Generation keeps the line; only the lock carries the commit."""

    PROVIDER = "https://example.org/flext"
    LINE = "0.12.0-dev"
    COMMIT = "b" * 40

    @classmethod
    def _requirement(cls, name: str, ref: str) -> str:
        return f"{name} @ git+{cls.PROVIDER}/{name}.git@{ref}"

    @classmethod
    def _consumer(cls, root: Path, core_ref: str) -> str:
        """Write one standalone consumer declaring the family on ``core_ref``."""
        (root / "config").mkdir(parents=True)
        repository: t.MappingKV[str, t.JsonValue] = {
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
        tm.ok(
            u.Cli.yaml_dump(
                root / "config" / "workspace.yaml",
                {"version": 3, "name": "consumer", "repository": repository},
            )
        )
        source = (
            '[project]\nname = "consumer"\nversion = "0.1.0"\n'
            f'dependencies = ["{cls._requirement("flext-core", core_ref)}"]\n'
            "[dependency-groups]\n"
            f'codegen = ["{cls._requirement("flext-infra", cls.LINE)}"]\n'
            f'dev = ["{cls._requirement("flext-core", core_ref)}"]\n'
            "[tool.uv]\n"
            f'override-dependencies = ["{cls._requirement("flext-core", cls.COMMIT)}"]\n'
        )
        (root / c.PYPROJECT_FILENAME).write_text(source, encoding="utf-8")
        return source

    @staticmethod
    def _conform(source: str) -> p.Result[str]:
        toolchain = config.Infra.codegen.toolchain
        workspace = test_u.Tests.workspace_spec(test_u.Tests.repository_ref("consumer"))
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
        )

    def test_generation_keeps_the_line_and_drops_override_pins(
        self, tmp_path: Path
    ) -> None:
        """Every internal requirement stays on its line; no override survives."""
        source = self._consumer(tmp_path, self.LINE)
        rendered = tm.ok(self._conform(source))
        for section, key in (
            ("project", "dependencies"),
            ("dependency-groups", "dev"),
            ("dependency-groups", "codegen"),
        ):
            for requirement in tu.Tests.toml_strings_at(rendered, section, key):
                tm.that(requirement.endswith(f".git@{self.LINE}"), eq=True)
        tm.that(rendered, lacks=self.COMMIT)
        tm.that(rendered, lacks="override-dependencies")
        tm.that(tm.ok(self._conform(rendered)), eq=rendered)
        line = tm.ok(
            u.Infra.flext_integration_line(
                codegen=config.Infra.codegen, repository_root=tmp_path
            )
        )
        tm.that((line.base_url, line.branch), eq=(self.PROVIDER, self.LINE))

    def test_a_commit_ref_fails_instead_of_being_written_back(
        self, tmp_path: Path
    ) -> None:
        """A commit in pyproject is a pin beside uv.lock: generation refuses it."""
        source = self._consumer(tmp_path, self.COMMIT)
        tm.fail(self._conform(source), has="only `make upg` moves it")
        tm.fail(
            u.Infra.flext_integration_line(
                codegen=config.Infra.codegen, repository_root=tmp_path
            ),
            has="only `make upg` moves it",
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
                codegen=config.Infra.codegen, repository_root=tmp_path
            ),
            has="conflicting flext-* line sources",
        )

    def test_the_manifest_carries_no_revision_pins(self) -> None:
        """The retired manifest pin is rejected, never silently ignored."""
        retired = {
            **test_u.Tests.project_spec("consumer").model_dump(),
            "dependency_revisions": {"flext-core": self.COMMIT},
        }
        with pytest.raises(ValueError, match="dependency_revisions"):
            m.Infra.ProjectSpec.model_validate(retired)
