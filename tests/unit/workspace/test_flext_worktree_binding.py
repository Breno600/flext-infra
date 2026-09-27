"""``FLEXT=<worktree>`` rebinds an external consumer onto one flext checkout.

An external project declares flext packages by pinned git URL, so it validates
PUBLISHED code and never the checkout being worked on. Reviewing a cross-project
change then required publishing first, which is backwards.

The binding is a SESSION override, not a declaration: the consumer's
``pyproject.toml`` keeps its pins untouched, so nothing local is ever committed
and dropping the flag restores the pinned resolution. Which distributions get
rebound is derived from the worktree's own manifest, never a hardcoded list.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from flext_tests import tm

from flext_core import p as core_p
from flext_infra import c, config
from flext_infra.workspace.detector import FlextInfraWorkspaceDetector
from flext_infra.workspace.flext_binding import FlextInfraFlextBindingService
from tests import m, t, u


class TestsFlextInfraWorktreeBinding:
    """The service resolves which distributions a worktree can supply."""

    def test_inactive_override_keeps_active_consumer_constraint(
        self, tmp_path: Path
    ) -> None:
        """An override for another platform cannot remove an active version bound."""
        root = self._flext_workspace(tmp_path)
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        document = u.Cli.toml_parse_text(
            '[project]\ndependencies = ["library>=2"]\n'
            "[tool.uv]\noverride-dependencies = [\"library==1; sys_platform == 'win32'\"]\n"
        )
        assert document is not None
        overrides, constraints = tm.ok(
            u.Infra.session_dependency_requirements(
                document,
                workspace,
                selected=(),
                consumer_root=root,
                environment={"sys_platform": "linux"},
            )
        )
        assert overrides == ()
        assert constraints == ("library>=2",)

    def test_session_requirements_preserve_consumer_sources_and_constraints(
        self, tmp_path: Path
    ) -> None:
        """Local candidates replace only selected consumer declarations."""
        supplier = self._flext_workspace(tmp_path)
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(supplier))
        consumer = self._consumer(tmp_path)
        path = consumer / c.Infra.PYPROJECT_FILENAME
        with path.open("a", encoding="utf-8") as stream:
            stream.write(
                '\n[tool.uv]\noverride-dependencies = ["httpx==0.28.1"]\n'
                'constraint-dependencies = ["httpx<1"]\n'
            )
        before = path.read_bytes()
        document = u.Cli.toml_parse_text(before.decode())
        assert document is not None
        requirements, constraints = tm.ok(
            u.Infra.session_dependency_requirements(
                document, workspace, selected=("flext-cli",), consumer_root=consumer
            )
        )
        declared = u.Infra.active_session_requirements(document)
        assert u.Infra.dependency_constraint(declared[0]) in constraints
        assert declared[1] not in requirements
        assert "httpx==0.28.1" in requirements
        assert "httpx>=0.27" not in requirements
        assert "httpx<1" in constraints
        assert path.read_bytes() == before

    def test_session_requirements_reject_unresolved_consumer_source_overlay(
        self, tmp_path: Path
    ) -> None:
        """An unselected source overlay cannot silently lose its provider."""
        workspace = tm.ok(
            FlextInfraWorkspaceDetector.load_workspace_spec(
                self._flext_workspace(tmp_path)
            )
        )
        document = u.Cli.toml_parse_text(
            '[project]\ndependencies = ["dependency"]\n'
            '[tool.uv.sources]\ndependency = { path = "../dependency" }\n'
        )
        assert document is not None
        result = u.Infra.session_dependency_requirements(
            document, workspace, selected=(), consumer_root=tmp_path
        )
        assert result.failure
        assert "unselected dependency sources" in (result.error or "")

    def test_session_requirements_keep_manifest_revision_precedence(
        self, tmp_path: Path
    ) -> None:
        """A declared immutable revision remains authoritative in session inputs."""
        workspace = tm.ok(
            FlextInfraWorkspaceDetector.load_workspace_spec(
                self._flext_workspace(tmp_path)
            )
        )
        assert workspace.project is not None
        revision = "a" * 40
        project = workspace.project.model_copy(
            update={"dependency_revisions": {"flext-core": revision}}
        )
        workspace = workspace.model_copy(update={"project": project, "subprojects": ()})
        consumer = self._consumer(tmp_path)
        path = consumer / c.Infra.PYPROJECT_FILENAME
        before = path.read_bytes()
        document = u.Cli.toml_parse_text(before.decode())
        assert document is not None
        requirements, _constraints = tm.ok(
            u.Infra.session_dependency_requirements(
                document, workspace, selected=("flext-cli",), consumer_root=consumer
            )
        )
        provider = u.Tests.provider()
        assert (
            f"flext-core @ git+{provider.base_url.rstrip('/')}/flext-core.git@{revision}"
            in requirements
        )
        assert path.read_bytes() == before

    @pytest.mark.parametrize("inline", [False, True])
    def test_session_requirements_preserve_declared_workspace_source(
        self, tmp_path: Path, *, inline: bool
    ) -> None:
        """A standard workspace overlay keeps the declared physical member source."""
        root = self._flext_workspace(tmp_path)
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        member = workspace.subprojects[0]
        document = u.Cli.toml_parse_text(
            f'[project]\ndependencies = ["{member.distribution}"]\n'
            + (
                f"[tool.uv.sources]\n{member.distribution} = {{ workspace = true }}\n"
                if inline
                else f"[tool.uv.sources.{member.distribution}]\nworkspace = true\n"
            )
        )
        assert document is not None
        sources = tm.ok(
            u.Infra.session_workspace_sources(
                document, workspace, selected=(), consumer_root=root
            )
        )
        expected = (root / member.path).resolve()
        assert sources == {member.distribution: expected}
        requirements, _constraints = tm.ok(
            u.Infra.session_dependency_requirements(
                document, workspace, selected=(), consumer_root=root
            )
        )
        assert requirements == (f"{member.distribution} @ {expected.as_uri()}",)
        assert (
            tm.ok(
                u.Infra.session_workspace_sources(
                    document,
                    workspace,
                    selected=(member.distribution,),
                    consumer_root=root,
                )
            )
            == {}
        )

    def test_session_requirements_apply_named_provider_migration(
        self, tmp_path: Path
    ) -> None:
        """Binding honors source migration before regenerated declarations exist."""
        root = self._flext_workspace(tmp_path)
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        assert workspace.project is not None
        revision = "b" * 40
        workspace = workspace.model_copy(
            update={
                "subprojects": (),
                "project": workspace.project.model_copy(
                    update={
                        "dependency_sources": {
                            "flext-core": "flext-core @ git+https://github.com/new-provider/flext-core.git@release"
                        },
                        "dependency_revisions": {"flext-core": revision},
                    }
                ),
            }
        )
        document = u.Cli.toml_parse_text(
            "[project]\ndependencies = [\n"
            "\"flext-core[extra] @ git+https://github.com/old-provider/flext-core.git@old; python_version >= '3.13'\",\n"
            '"untouched>=1"\n]\n'
        )
        assert document is not None
        requirements, constraints = tm.ok(
            u.Infra.session_dependency_requirements(
                document, workspace, selected=(), consumer_root=root
            )
        )
        assert (
            u.Infra.active_requirement(
                f"flext-core[extra] @ git+https://github.com/new-provider/flext-core.git@{revision}; python_version >= '3.13'"
            )
            in requirements
        )
        assert "untouched>=1" in constraints

    @pytest.mark.parametrize(
        ("incompatible", "inactive"), [(False, False), (True, False), (False, True)]
    )
    def test_real_binding_preserves_extras_and_rejects_incompatible_bounds(
        self, tmp_path: Path, *, incompatible: bool, inactive: bool
    ) -> None:
        """The real installer installs extras and keeps ordinary bounds additive."""
        supplier = tmp_path / "supplier"
        consumer = tmp_path / "consumer"
        for root, name in (
            (supplier, "binding-candidate"),
            (consumer, "binding-consumer"),
        ):
            u.Tests.WorktreeFixture.initialize_governed_project(
                root, name, workspace=name, database=name, issue_prefix=name
            )
        extra = tmp_path / "extra"
        extra.mkdir()
        for root, name, optional in (
            (extra, "binding-extra", ""),
            (
                supplier,
                "binding-candidate",
                f'\n[project.optional-dependencies]\nfeature = ["binding-extra @ {extra.as_uri()}"]\n',
            ),
        ):
            (root / "pyproject.toml").write_text(
                '[build-system]\nrequires = ["setuptools"]\nbuild-backend = "setuptools.build_meta"\n'
                f'[project]\nname = "{name}"\nversion = "1.0.0"\n{optional}'
                f'\n[tool.setuptools]\npy-modules = ["{name.replace("-", "_")}"]\n',
                encoding="utf-8",
            )
            (root / f"{name.replace('-', '_')}.py").write_text(
                'VALUE = "installed"\n', encoding="utf-8"
            )
        declaration = consumer / c.Infra.PYPROJECT_FILENAME
        marker = "; python_version < '0'" if inactive else ""
        declaration.write_text(
            '[project]\nname = "binding-consumer"\nversion = "1.0.0"\n'
            f'dependencies = ["binding-candidate[feature]{">=2" if incompatible else ">=1"}{marker}"]\n',
            encoding="utf-8",
        )
        before = declaration.read_bytes()
        environment = consumer / config.Infra.tooling.tools.pyright.path_rules.venv_name
        tm.ok(
            u.Cli.run_checked((
                c.Infra.UV,
                "venv",
                "--python",
                sys.executable,
                str(environment),
            ))
        )
        python = environment / "bin" / "python"
        facts = tm.ok(
            FlextInfraFlextBindingService.consumer_marker_environment(
                consumer_root=consumer, python=python
            )
        )
        consumer_version = facts["python_full_version"]
        major, minor, patch = consumer_version.split(".", maxsplit=2)
        foreign_patch = f"{major}.{minor}.{int(patch) + 1}"
        assert (
            u.Infra.active_requirement(
                f"binding-candidate; python_full_version == '{consumer_version}'",
                environment=facts,
            )
            is not None
        )
        assert (
            u.Infra.active_requirement(
                f"binding-candidate; python_full_version == '{foreign_patch}'",
                environment=facts,
            )
            is None
        )
        assert (
            u.Infra.active_requirement(
                f"binding-candidate; implementation_version == '{facts['implementation_version']}'",
                environment=facts,
            )
            is not None
        )
        ci = config.Infra.codegen.make.ci
        outcome = tm.ok(
            u.Cli.run_raw(
                (
                    sys.executable,
                    "-m",
                    "flext_infra",
                    "workspace",
                    "flext-binding",
                    "--repository-root",
                    str(consumer),
                    "--flext-root",
                    str(supplier),
                    "--python",
                    str(python),
                ),
                env=u.Cli.process_env(overrides={ci.variable: ci.local_value}),
            )
        )
        assert declaration.read_bytes() == before
        if inactive:
            assert outcome.outcome.raw_return_code != 0
            assert (
                "selects no declared dependency" in f"{outcome.stdout}{outcome.stderr}"
            )
        elif incompatible:
            assert outcome.outcome.raw_return_code != 0
            assert "binding-candidate" in f"{outcome.stdout}{outcome.stderr}"
        else:
            assert outcome.outcome.raw_return_code == 0, (
                f"{outcome.stdout}{outcome.stderr}"
            )
            installed = tm.ok(
                u.Cli.run_raw((
                    str(python),
                    "-c",
                    "from importlib.metadata import version; print(version('binding-extra'))",
                ))
            )
            assert installed.outcome.raw_return_code == 0
            assert installed.stdout.strip() == "1.0.0"

    def test_inactive_marker_does_not_select_a_candidate(self, tmp_path: Path) -> None:
        """An impossible Python marker cannot activate a local supplier."""
        consumer = self._consumer(tmp_path)
        (consumer / c.Infra.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "consumer"\nversion = "1"\n'
            "dependencies = [\"flext-core; python_version < '0'\"]\n",
            encoding="utf-8",
        )
        result = FlextInfraFlextBindingService.plan_targets(
            consumer_root=consumer, flext_root=self._flext_workspace(tmp_path)
        )
        assert result.failure
        assert "selects no declared dependency" in (result.error or "")

    def test_inactive_revision_is_validated_without_becoming_an_install_input(
        self, tmp_path: Path
    ) -> None:
        """A legitimate pin for another interpreter remains a valid declaration."""
        root = self._flext_workspace(tmp_path)
        workspace = tm.ok(FlextInfraWorkspaceDetector.load_workspace_spec(root))
        assert workspace.project is not None
        workspace = workspace.model_copy(
            update={
                "subprojects": (),
                "project": workspace.project.model_copy(
                    update={"dependency_revisions": {"flext-core": "c" * 40}}
                ),
            }
        )
        document = u.Cli.toml_parse_text(
            "[project]\ndependencies = [\"flext-core @ git+https://github.com/provider/flext-core.git@branch; python_version < '0'\"]\n"
        )
        assert document is not None
        assert tm.ok(
            u.Infra.session_dependency_requirements(
                document, workspace, selected=(), consumer_root=root
            )
        ) == ((), ())

    @staticmethod
    def _consumer(tmp_path: Path) -> Path:
        """Return an external consumer declaring flext packages by pinned git URL."""
        provider = u.Tests.provider()
        consumer = tmp_path / "consumer"
        consumer.mkdir()
        (consumer / "pyproject.toml").write_text(
            "[project]\n"
            'name = "consumer"\n'
            'version = "0.1.0"\n'
            'requires-python = ">=3.13"\n'
            "dependencies = [\n"
            f'  "flext-core @ git+{provider.base_url.rstrip("/")}/flext-core.git@'
            f'{u.Tests.provider_branch()}",\n'
            f'  "flext-cli @ git+{provider.base_url.rstrip("/")}/flext-cli.git@'
            f'{u.Tests.provider_branch()}",\n'
            '  "httpx>=0.27",\n'
            "]\n",
            encoding="utf-8",
        )
        return consumer

    @staticmethod
    def _flext_workspace(tmp_path: Path) -> Path:
        """Return a self-contained flext workspace supplying flext-core and flext-cli.

        Built here rather than pointed at a real checkout so the test states its
        own premise: the rebind set is the intersection of what the consumer
        declares with what the worktree PROVIDES, and only a fixture that owns
        both sides can prove the intersection rather than inherit it from one
        machine's disk.
        """
        flext_root = tmp_path / "flext"
        u.Tests.WorktreeFixture.initialize_governed_project(
            flext_root,
            "flext",
            workspace="flext",
            database="flext",
            issue_prefix="flext",
        )
        for name in ("flext-core", "flext-cli"):
            u.Tests.WorktreeFixture.initialize_governed_project(
                flext_root / name,
                name,
                workspace=name,
                database=name,
                issue_prefix=name,
                beads_owner=False,
            )
            u.Tests.WorktreeFixture.link_member_beads(
                flext_root / name,
                flext_root,
                workspace_name="flext",
                database="flext",
                issue_prefix="flext",
            )
        u.Tests.WorktreeFixture.write_gitmodules(
            flext_root, ("flext-core", "flext-cli")
        )
        manifest_path = flext_root / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME
        manifest = m.Infra.WorkspaceManifestSpec.model_validate(
            tm.ok(u.Cli.config_load(manifest_path, expand_env=False)).data
        )
        manifest = manifest.model_copy(
            update={"project": u.Tests.project_spec(manifest.name)}
        )
        tm.ok(u.Cli.yaml_dump(manifest_path, manifest.model_dump(mode="json")))
        return flext_root

    def test_binding_targets_only_the_flext_packages_the_consumer_declares(
        self, tmp_path: Path
    ) -> None:
        """Only declared flext deps present in the worktree are rebound."""
        consumer = self._consumer(tmp_path)

        planned: core_p.Result[t.VariadicTuple[str]] = (
            FlextInfraFlextBindingService.plan_targets(
                consumer_root=consumer, flext_root=self._flext_workspace(tmp_path)
            )
        )

        names = tm.ok(planned)
        tm.that(sorted(names), eq=["flext-cli", "flext-core"])

    def test_binding_rejects_a_path_that_is_not_a_flext_workspace(
        self, tmp_path: Path
    ) -> None:
        """A non-workspace path fails closed instead of silently binding nothing."""
        consumer = self._consumer(tmp_path)
        not_flext = tmp_path / "elsewhere"
        not_flext.mkdir()

        planned = FlextInfraFlextBindingService.plan_targets(
            consumer_root=consumer, flext_root=not_flext
        )

        tm.that(planned.failure, eq=True)
        tm.that(planned.error or "", has="workspace")

    def test_a_consumer_without_flext_dependencies_rejects_requested_binding(
        self, tmp_path: Path
    ) -> None:
        """An explicit binding must never report success without a candidate."""
        consumer = tmp_path / "plain"
        consumer.mkdir()
        (consumer / "pyproject.toml").write_text(
            '[project]\nname = "plain"\nversion = "0.1.0"\n'
            'requires-python = ">=3.13"\ndependencies = ["httpx>=0.27"]\n',
            encoding="utf-8",
        )

        planned = FlextInfraFlextBindingService.plan_targets(
            consumer_root=consumer, flext_root=self._flext_workspace(tmp_path)
        )

        tm.that(planned.failure, eq=True)
        tm.that(planned.error or "", has="selects no declared dependency")

    def test_standalone_supplier_satisfies_a_development_dependency(
        self, tmp_path: Path
    ) -> None:
        """A root-only generator checkout supplies a consumer's declared dev group."""
        supplier = tmp_path / "supplier"
        u.Tests.WorktreeFixture.initialize_governed_project(
            supplier,
            "flext-infra",
            workspace="flext-infra",
            database="flext-infra",
            issue_prefix="flext-infra",
        )
        consumer = self._consumer(tmp_path)
        declaration = consumer / c.Infra.PYPROJECT_FILENAME
        with declaration.open("a", encoding="utf-8") as stream:
            stream.write('[dependency-groups]\ndev = ["flext-infra"]\n')
        before = declaration.read_bytes()

        planned = FlextInfraFlextBindingService.plan_targets(
            consumer_root=consumer, flext_root=supplier
        )

        assert tm.ok(planned) == ("flext-infra",)
        assert declaration.read_bytes() == before

    @pytest.mark.parametrize("symlinked_environment", [False, True])
    def test_binding_rejects_a_foreign_environment_before_installation(
        self, tmp_path: Path, *, symlinked_environment: bool
    ) -> None:
        """A caller cannot point the installer at the runner's own environment."""
        consumer = tmp_path / "consumer"
        u.Tests.WorktreeFixture.initialize_governed_project(
            consumer,
            "flext-consumer",
            workspace="flext-consumer",
            database="flext-consumer",
            issue_prefix="flext-consumer",
        )
        if symlinked_environment:
            (
                consumer / config.Infra.tooling.tools.pyright.path_rules.venv_name
            ).symlink_to(Path(sys.prefix), target_is_directory=True)
        ci = config.Infra.codegen.make.ci
        outcome = tm.ok(
            u.Cli.run_raw(
                (
                    sys.executable,
                    "-m",
                    "flext_infra",
                    "workspace",
                    "flext-binding",
                    "--repository-root",
                    str(consumer),
                    "--flext-root",
                    str(tmp_path / "supplier"),
                    "--python",
                    sys.executable,
                ),
                env=u.Cli.process_env(overrides={ci.variable: ci.local_value}),
            )
        )
        assert outcome.outcome.raw_return_code != 0
        expected = (
            "physical consumer environment"
            if symlinked_environment
            else "interpreter must belong to the consumer"
        )
        assert expected in f"{outcome.stdout}{outcome.stderr}"

    def test_binding_cli_rejects_ci_before_installation(self, tmp_path: Path) -> None:
        """The public CLI rejects local editable candidates under the configured CI token."""
        ci = config.Infra.codegen.make.ci
        outcome = tm.ok(
            u.Cli.run_raw(
                (
                    sys.executable,
                    "-m",
                    "flext_infra",
                    "workspace",
                    "flext-binding",
                    "--repository-root",
                    str(tmp_path),
                    "--flext-root",
                    str(tmp_path),
                    "--python",
                    sys.executable,
                ),
                env=u.Cli.process_env(overrides={ci.variable: ci.value}),
            )
        )
        assert outcome.outcome.raw_return_code != 0
        assert (
            f"prohibited with {ci.variable}={ci.value}"
            in f"{outcome.stdout}{outcome.stderr}"
        )


__all__: list[str] = ["TestsFlextInfraWorktreeBinding"]
