"""Public source detection accepts a manifest-owned immutable pin cutover."""

from __future__ import annotations

from pathlib import Path

from flext_tests import tm

from flext_infra import config, m, t, u


class TestsDependencyRevisionCutover:
    """Keep the handwritten revision authoritative during generated migration."""

    @staticmethod
    def consumer_manifest(
        root: Path,
        revisions: t.MappingKV[str, t.JsonValue],
        integration: t.MappingKV[str, t.JsonValue] | None = None,
    ) -> t.MappingKV[str, t.JsonValue]:
        """Write and return one standalone consumer manifest pinning revisions."""
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
                "dependency_revisions": dict(revisions),
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
            "integration": dict(integration) if integration else None,
        }
        tm.ok(u.Cli.yaml_dump(root / "config" / "workspace.yaml", manifest))
        return manifest

    def test_stale_projection_migrates_without_accepting_mixed_sources(
        self, tmp_path: Path
    ) -> None:
        """A stale ref is repairable, but ambiguous provenance remains invalid."""
        provider = "https://example.org/flext"
        old_ref = "a" * 40
        revision = "b" * 40
        root = tmp_path / "consumer"
        manifest = self.consumer_manifest(root, {"flext-core": revision})
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

    def test_fully_pinned_consumer_resolves_the_infrastructure_source(
        self, tmp_path: Path
    ) -> None:
        """Pinned providers are the source; the line follows the integration branch."""
        provider = "https://example.org/flext"
        integration_branch = "develop"
        distribution = config.Infra.codegen.infra_repository.distribution
        revisions = {"flext-core": "b" * 40, distribution: "d" * 40}
        root = tmp_path / "consumer"
        self.consumer_manifest(
            root, revisions, {"provider": "example", "branch": integration_branch}
        )
        pyproject = root / "pyproject.toml"
        # Before generation the pinned requirements still name the family line;
        # after generation they name the pinned revisions. Both detect one line.
        for refs in (dict.fromkeys(revisions, "0.12.0-dev"), revisions):
            requirements = ", ".join(
                f'"{name} @ git+{provider}/{name}.git@{ref}"'
                for name, ref in refs.items()
            )
            pyproject.write_text(
                '[project]\nname = "consumer"\nversion = "0.1.0"\n'
                f"dependencies = [{requirements}]\n",
                encoding="utf-8",
            )
            line = tm.ok(
                u.Infra.flext_integration_line(
                    codegen=config.Infra.codegen, repository_root=root
                )
            )
            tm.that(line.base_url, eq=provider)
            tm.that(line.branch, eq=integration_branch)
