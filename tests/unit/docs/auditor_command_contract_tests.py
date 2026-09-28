"""Behavior tests for the public documentation command-contract audit."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import pytest
from flext_tests import tm

from flext_infra import config
from tests import m, u

if TYPE_CHECKING:
    from pathlib import Path


class TestsFlextInfraAuditorCommandContract:
    """Prove canonical Make, Testmon, and public-test documentation policy."""

    @pytest.fixture
    def command_contract_scope(self, infra_test_workspace: Path) -> m.Infra.DocScope:
        """Declare the same repository identity in Git and the typed topology."""
        name = "infra-pkg"
        u.Tests.write_project_beads_config(infra_test_workspace, name)
        u.Tests.write_standalone_workspace_manifest(infra_test_workspace, name)
        u.Tests.initialize_git_repo(
            infra_test_workspace, origin_url=u.Tests.repository_ref(name).url
        )
        return m.Infra.DocScope(
            name=name,
            path=infra_test_workspace,
            report_dir=infra_test_workspace / ".reports" / "docs",
            package_name="infra_pkg",
        )

    @staticmethod
    @pytest.mark.parametrize("tool", ["uv", "mkdocs", "ruff", "pyright", "pre-commit"])
    def test_tool_filename_is_not_a_command(tool: str) -> None:
        """Filename prefixes remain prose; actual tool invocations are rejected."""
        for content, expected in (
            (f"Configuration is stored in `{tool}.toml`.", 0),
            (f"The documentation uses `{tool}`.", 0),
            (f"```bash\n{tool}\n```", 1),
            (f"```bash\n{tool} --help\n```", 1),
        ):
            issues = u.Infra.docs_command_contract_content_issues(
                content,
                relative_path="docs/guides/commands.md",
                effective_verbs=config.Infra.codegen.make.verbs,
            )
            tm.that(len(issues), eq=expected)

    @staticmethod
    def test_accepts_every_declared_verb_rendered_from_the_ssot() -> None:
        """Each declared verb passes without the exterminated apply token."""
        lines = "\n".join(
            f"make {spec.name}" for spec in config.Infra.codegen.make.verbs
        )
        content = f"# Commands\n\n```bash\n{lines}\n```\n"

        issues = u.Infra.docs_command_contract_content_issues(
            content,
            relative_path="docs/guides/testing.md",
            effective_verbs=config.Infra.codegen.make.verbs,
        )

        tm.that(issues, eq=[])

    @staticmethod
    def test_ignores_prose_that_begins_with_make() -> None:
        content = """# Scope

Make surfaces and documentation are changed at their canonical owner.
"""

        issues = u.Infra.docs_command_contract_content_issues(
            content,
            relative_path="docs/guides/make-commands.md",
            effective_verbs=config.Infra.codegen.make.verbs,
        )

        tm.that(issues, eq=[])

    @staticmethod
    def test_rejects_invented_make_selectors() -> None:
        content = """```bash
make test PROJECT=flext-demo MATCH=unit
```
"""

        issues = u.Infra.docs_command_contract_content_issues(
            content,
            relative_path="docs/guides/testing.md",
            effective_verbs=config.Infra.codegen.make.verbs,
        )

        tm.that(len(issues), eq=1)
        tm.that(issues[0].issue_type, eq="command_contract")
        tm.that(issues[0].message, has="invented Make selector")

    @staticmethod
    @pytest.mark.parametrize("value", ["Y", "N", "", "invalid"])
    def test_rejects_legacy_apply_flag_on_a_declared_verb(value: str) -> None:
        """The exterminated `APPLY` flag is rejected in documented commands."""
        verb = next(spec.name for spec in config.Infra.codegen.make.verbs)
        content = f"```bash\nmake {verb} APPLY={value}\n```\n"

        issues = u.Infra.docs_command_contract_content_issues(
            content,
            relative_path="docs/guides/getting-started.md",
            effective_verbs=config.Infra.codegen.make.verbs,
        )

        tm.that(len(issues), eq=1)
        tm.that(issues[0].message, has="legacy `APPLY` flag is exterminated")

    @staticmethod
    def test_accepts_plain_declared_verbs() -> None:
        """Every declared verb documented without variables passes."""
        plain = "\n".join(
            f"make {spec.name}" for spec in config.Infra.codegen.make.verbs
        )

        ok = u.Infra.docs_command_contract_content_issues(
            f"```bash\n{plain}\n```\n",
            relative_path="docs/guides/getting-started.md",
            effective_verbs=config.Infra.codegen.make.verbs,
        )
        tm.that(ok, eq=[])

        legacy = "\n".join(
            f"make {spec.name} APPLY=Y" for spec in config.Infra.codegen.make.verbs
        )
        bad = u.Infra.docs_command_contract_content_issues(
            f"```bash\n{legacy}\n```\n",
            relative_path="docs/guides/getting-started.md",
            effective_verbs=config.Infra.codegen.make.verbs,
        )
        tm.that(len(bad), eq=len(config.Infra.codegen.make.verbs))

    @staticmethod
    def test_rejects_raw_pytest_execution() -> None:
        content = """```bash
PYTHONPATH=src python -m pytest tests/unit
```
"""

        issues = u.Infra.docs_command_contract_content_issues(
            content,
            relative_path="docs/guides/testing.md",
            effective_verbs=config.Infra.codegen.make.verbs,
        )

        tm.that(len(issues), eq=1)
        tm.that(issues[0].message, has="bypasses `make test`")

    @staticmethod
    def test_rejects_direct_tool_execution() -> None:
        content = """```bash
ruff check src
```
"""

        issues = u.Infra.docs_command_contract_content_issues(
            content,
            relative_path="docs/standards/development.md",
            effective_verbs=config.Infra.codegen.make.verbs,
        )

        tm.that(len(issues), eq=1)
        tm.that(issues[0].message, has="bypasses the root Make dispatcher")

    @staticmethod
    def test_scans_recursive_live_docs_from_typed_scope(
        command_contract_scope: m.Infra.DocScope,
    ) -> None:
        infra_test_workspace = command_contract_scope.path
        docs_root = infra_test_workspace / "docs"
        governed = {
            docs_root / "guides" / "nested" / "commands.md": (
                "```bash\nruff check src\n```\n"
            ),
            docs_root / "standards" / "nested" / "commands.md": (
                "```bash\nmake test PROJECT=demo\n```\n"
            ),
        }
        for path, content in governed.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            u.write_file(path, content)
        ungoverned = docs_root / "architecture" / "historical.md"
        ungoverned.parent.mkdir(parents=True, exist_ok=True)
        u.write_file(ungoverned, "```bash\nruff check src\n```\n")
        excluded = docs_root / "standards" / "historical" / "commands.md"
        excluded.parent.mkdir(parents=True, exist_ok=True)
        u.write_file(excluded, "```bash\nruff check src\n```\n")
        u.write_file(
            infra_test_workspace / "pyproject.toml",
            (
                "[project]\nname='infra-pkg'\nversion='0.0.0'\n\n"
                "[tool.flext.docs]\n"
                'exclude_docs=["standards/historical/**"]\n'
            ),
        )
        issues = u.Infra.docs_command_contract_issues(command_contract_scope)

        tm.that(len(issues), eq=2)
        tm.that(
            {issue.file for issue in issues},
            eq={"docs/guides/nested/commands.md", "docs/standards/nested/commands.md"},
        )

    @staticmethod
    @pytest.mark.parametrize("verb_name", ["publish-preview", "archive-assets"])
    @pytest.mark.parametrize(
        ("declared", "expected"),
        [
            (True, ""),
            (True, "legacy `APPLY` flag is exterminated"),
            (False, "not declared"),
        ],
    )
    def test_audits_repository_declared_verbs(
        command_contract_scope: m.Infra.DocScope,
        verb_name: str,
        *,
        declared: bool,
        expected: str,
    ) -> None:
        scope = command_contract_scope
        spec = m.Infra.MakeVerbSpec(
            name=verb_name, description="Repository-owned operation"
        )
        u.Tests.write_standalone_workspace_manifest(
            scope.path, scope.name, extra_verbs=(spec,) if declared else ()
        )
        guide = scope.path / "docs/guides/commands.md"
        guide.parent.mkdir(parents=True)
        token = " APPLY=Y" if "APPLY" in expected else ""
        u.write_file(guide, f"```bash\nmake {verb_name}{token}\n```\n")

        issues = u.Infra.docs_command_contract_issues(scope)

        if expected:
            tm.that(len(issues), eq=1)
            tm.that(issues[0].message, has=expected)
        else:
            tm.that(issues, eq=[])

    @staticmethod
    def test_manifest_changes_update_the_live_contract(
        command_contract_scope: m.Infra.DocScope,
    ) -> None:
        scope = command_contract_scope
        spec = m.Infra.MakeVerbSpec(
            name="publish-preview", description="Repository-owned operation"
        )
        guide = scope.path / "docs/guides/commands.md"
        guide.parent.mkdir(parents=True)
        u.write_file(guide, f"```bash\nmake {spec.name}\n```\n")
        u.Tests.write_standalone_workspace_manifest(
            scope.path, scope.name, extra_verbs=(spec,)
        )
        tm.that(u.Infra.docs_command_contract_issues(scope), eq=[])

        u.write_file(guide, f"```bash\nmake {spec.name} APPLY=Y\n```\n")
        legacy = u.Infra.docs_command_contract_issues(scope)
        tm.that(len(legacy), eq=1)
        tm.that(legacy[0].message, has="legacy `APPLY` flag is exterminated")

        renamed = m.Infra.MakeVerbSpec(
            name="archive-assets", description="Repository-owned operation"
        )
        u.Tests.write_standalone_workspace_manifest(
            scope.path, scope.name, extra_verbs=(renamed,)
        )
        u.write_file(guide, f"```bash\nmake {renamed.name}\n```\n")
        tm.that(u.Infra.docs_command_contract_issues(scope), eq=[])

    @staticmethod
    @pytest.mark.parametrize("with_guide", [False, True])
    def test_malformed_selected_topology_blocks_with_exact_cause(
        command_contract_scope: m.Infra.DocScope, *, with_guide: bool
    ) -> None:
        scope = command_contract_scope
        if with_guide:
            guide = scope.path / "docs/guides/commands.md"
            guide.parent.mkdir(parents=True)
            spec = config.Infra.codegen.make.verbs[0]
            u.write_file(guide, f"```bash\nmake {spec.name}\n```\n")
        manifest = u.Tests.write_standalone_workspace_manifest(scope.path, scope.name)
        u.write_file(manifest, "version: [\n")
        loaded = u.Infra.workspace_spec_load(scope.path)
        tm.fail(loaded)
        tm.that(loaded.error, has=str(manifest))

        with pytest.raises(ValueError, match=re.escape(loaded.error or "")) as caught:
            u.Infra.docs_command_contract_issues(scope)

        tm.that(str(caught.value), eq=loaded.error)

    @staticmethod
    def test_guide_projection_resolves_source_repository_contract(
        command_contract_scope: m.Infra.DocScope,
    ) -> None:
        source_scope = command_contract_scope
        spec = m.Infra.MakeVerbSpec(
            name="publish-preview", description="Source repository operation"
        )
        manifest = u.Tests.write_standalone_workspace_manifest(
            source_scope.path, source_scope.name, extra_verbs=(spec,)
        )
        guide = source_scope.path / "docs/guides/commands.md"
        guide.parent.mkdir(parents=True)
        u.write_file(guide, f"```bash\nmake {spec.name}\n```\n")
        state = u.Cli.atomic_read_binary_file_state(guide, required=True)
        tm.ok(state)
        destination = source_scope.path / "member"
        destination.mkdir()
        scope = m.Infra.DocScope(
            name="member", path=destination, report_dir=destination / ".reports/docs"
        )

        projected = u.Infra.docs_project_guides_artifacts(
            scope, repository_root=source_scope.path, source_states=(state.value,)
        )

        tm.ok(projected)
        tm.that(len(projected.value), eq=1)
        tm.that(projected.value[0][1], eq=destination / "docs/guides/commands.md")
        tm.that(projected.value[0][2], has=f"make {spec.name}")

        u.write_file(manifest, "version: [\n")
        loaded = u.Infra.workspace_spec_load(source_scope.path)
        tm.fail(loaded)
        blocked = u.Infra.docs_project_guides_artifacts(
            scope, repository_root=source_scope.path, source_states=(state.value,)
        )
        tm.fail(blocked)
        tm.that(blocked.error, eq=loaded.error)

    @staticmethod
    def test_rejects_test_double_examples() -> None:
        content = """```python
from unittest.mock import patch

result = patch("package.owner")
```
"""

        issues = u.Infra.docs_command_contract_content_issues(
            content,
            relative_path="docs/standards/testing.md",
            effective_verbs=config.Infra.codegen.make.verbs,
        )

        tm.that(len(issues), eq=2)
        tm.that(issues[0].message, has="test-double code")
