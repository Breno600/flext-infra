"""Public source detection accepts a manifest-owned immutable pin cutover."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import config, m, t, u


class TestsDependencyRevisionCutover:
    """Keep the handwritten revision authoritative during generated migration."""

    def test_stale_projection_migrates_without_accepting_mixed_sources(
        self, tmp_path: Path
    ) -> None:
        """A stale ref is repairable, but ambiguous provenance remains invalid."""
        provider = "https://example.org/flext"
        old_ref = "a" * 40
        revision = "b" * 40
        root = tmp_path / "consumer"
        (root / "config").mkdir(parents=True)
        manifest: t.MappingKV[str, t.JsonValue] = {
            "version": 3,
            "name": "consumer",
            "repository": {
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
            },
            "members": [],
            "project": {
                "dependency_revisions": {"flext-core": revision},
                "package_name": "consumer",
                "class_stem": "Consumer",
                "namespace": "Consumer",
                "constant_name": "consumer",
                "namespace_attribute": "Consumer",
                "alias": "consumer",
                "environment_prefix": "CONSUMER_",
                "description": "Synthetic revision-cutover consumer",
                "license": "MIT",
                "author_name": "Fixture Author",
                "author_email": "fixture@example.org",
                "upstream": "flext_core",
                "homepage": "https://example.org/consumer",
                "documentation": "https://example.org/consumer/docs",
                "repository_root_rel": ".",
                "year": 2026,
            },
        }
        tm.ok(u.Cli.yaml_dump(root / "config" / "workspace.yaml", manifest))
        core_source = f"flext-core @ git+{provider}/flext-core.git@{old_ref}"
        infra_source = f"flext-infra @ git+{provider}/flext-infra.git@0.12.0-dev"
        source = (
            '[project]\nname = "consumer"\nversion = "0.1.0"\n'
            f'dependencies = ["{core_source}"]\n'
            f'[dependency-groups]\ncodegen = ["{infra_source}"]\n'
        )
        pyproject = root / "pyproject.toml"
        pyproject.write_text(source, encoding="utf-8")

        line = tm.ok(
            u.Infra.flext_integration_line(
                codegen=config.Infra.codegen, repository_root=root
            )
        )
        tm.that(line.base_url, eq=provider)
        tm.that(line.branch, eq="0.12.0-dev")

        workspace = m.Infra.WorkspaceSpec.model_validate({
            "name": manifest["name"],
            "repository": manifest["repository"],
            "project": manifest["project"],
        })
        toolchain = config.Infra.codegen.toolchain
        rendered = tm.ok(
            u.Infra.pyproject_conform(
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
        )
        tm.that(rendered, has=f"flext-core.git@{revision}")
        tm.that(rendered, lacks=f"flext-core.git@{old_ref}")

        other_ref = "c" * 40
        pyproject.write_text(
            source
            + f'dev = ["flext-core @ git+{provider}/flext-core.git@{other_ref}"]\n',
            encoding="utf-8",
        )
        mixed_refs = u.Infra.flext_integration_line(
            codegen=config.Infra.codegen, repository_root=root
        )
        tm.fail(mixed_refs, has="conflicting pinned sources")

        pyproject.write_text(
            source.replace(provider, "https://other.example.org/flext", 1),
            encoding="utf-8",
        )
        mixed_providers = u.Infra.flext_integration_line(
            codegen=config.Infra.codegen, repository_root=root
        )
        tm.fail(mixed_providers, has="conflicting flext-* providers")
