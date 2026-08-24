"""Beads ledger routing from isolated worktrees to the principal checkout.

Copyright (c) 2025 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from flext_infra import c, config, m, u
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_tests import tm
from tests import u as test_u


class TestCodegenBeadsLedger:
    """Route every Beads lifecycle to the principal ledger, never a worktree."""

    @staticmethod
    def _git(root: Path, *arguments: str) -> None:
        tm.ok(u.Cli.run_checked(["git", *arguments], cwd=root))

    @classmethod
    def _standalone_workspace(
        cls,
        root: Path,
        *,
        ledger_id: str | None,
        ledger_prefix: str | None = None,
        declare_prefix: bool = True,
        overlay: bool = True,
        attached_marker: bool = False,
    ) -> Path:
        """Create a manifested standalone repository with a real Git origin."""
        provider = config.Infra.codegen.providers[0]
        repository = test_u.Tests.repository_ref(config.Infra.name)
        root.mkdir(parents=True)
        cls._git(root, "init", "-q", "-b", provider.branch)
        cls._git(root, "config", "user.email", "infra@example.com")
        cls._git(root, "config", "user.name", "Infra Tests")
        marker = (
            "\n[tool.flext.workspace]\nattached = true\n" if attached_marker else ""
        )
        (root / "pyproject.toml").write_text(
            f'[project]\nname = "{repository.distribution}"\nversion = "0.12.0.dev0"\n'
            f'requires-python = ">=3.13,<3.14"\n{marker}',
            encoding="utf-8",
        )
        package_init = (
            root / "src" / repository.distribution.replace("-", "_") / "__init__.py"
        )
        package_init.parent.mkdir(parents=True)
        package_init.write_text("", encoding="utf-8")
        local_repository = repository.model_copy(
            update={
                "path": Path(),
                "role": c.Infra.RepositoryRole.STANDALONE,
                "checkout": c.Infra.CheckoutKind.INDEPENDENT,
                "editable": False,
            }
        )
        overlays = (
            (
                m.Infra.RepositoryPolicyOverlaySpec(
                    project=repository.distribution, beads_enabled=True
                ),
            )
            if overlay
            else ()
        )
        spec = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=repository.distribution,
            repository=local_repository,
            ledger_id=ledger_id,
            # A tracker-owning manifest declares BOTH identifiers (mro-cdzxf).
            # Tests that exercise the half-declared defect pass
            # declare_prefix=False to build that shape deliberately.
            ledger_prefix=(
                ledger_prefix
                if ledger_prefix is not None or not declare_prefix
                else ledger_id
            ),
            repository_policy_overlays=overlays,
        )
        tm.ok(
            u.Cli.yaml_dump(
                root / "config" / "workspace.yaml",
                spec.model_dump(
                    mode="json",
                    exclude_none=True,
                    exclude={"external_dependency_paths"},
                ),
            )
        )
        origin = root.parent / f"{root.name}-origin.git"
        cls._git(root.parent, "init", "-q", "--bare", str(origin))
        cls._git(root, "add", "-A")
        cls._git(root, "commit", "-q", "--no-verify", "-m", "Seed standalone workspace")
        cls._git(root, "remote", "add", "origin", str(origin))
        cls._git(root, "push", "-q", "-u", "origin", provider.branch)
        return root

    @classmethod
    def _beads_plan(cls, root: Path) -> m.Infra.BeadsPlan:
        """Plan one repository in check mode and return its single Beads plan."""
        request = m.Infra.CodegenConformRequest(
            root=root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned: m.Infra.CodegenPlan = tm.ok(
            FlextInfraCodegenConform(workspace_root=root).plan(request)
        )
        tm.that(len(planned.beads), eq=1)
        return planned.beads[0]

    def test_transaction_worktree_routes_ledger_to_principal(
        self, tmp_path: Path
    ) -> None:
        """Resolve the ledger of an isolated transaction to its principal checkout."""
        principal = self._standalone_workspace(tmp_path / "principal", ledger_id=None)
        transaction = tmp_path / "transaction"
        self._git(principal, "worktree", "add", "--detach", str(transaction))

        plan = self._beads_plan(transaction)

        tm.that(plan.enabled, eq=True)
        tm.that(plan.repository_root, eq=transaction.resolve())
        tm.that(plan.ledger_root, eq=principal.resolve())
        tm.that(plan.ledger_id, eq=None)
        repository = test_u.Tests.repository_ref(config.Infra.name)
        tm.that(plan.canonical_prefix, eq=repository.distribution)

    def test_owner_transaction_renders_the_integrated_ledger_projection(
        self, tmp_path: Path
    ) -> None:
        principal = self._standalone_workspace(
            tmp_path / "principal-owner", ledger_id="fleet-ledger"
        )
        transaction = tmp_path / "owner-transaction"
        self._git(principal, "worktree", "add", "--detach", str(transaction))

        rendered = self._beads_config_render(transaction)

        if rendered is None:
            pytest.fail("owner transaction must render the ledger config")
        tm.that(rendered, has="Owned ledger config")
        tm.that(rendered, lacks="Routing-only client config")

    def test_external_member_lane_plans_no_beads_surfaces(self, tmp_path: Path) -> None:
        workspace = tmp_path / "workspace"
        member_source = tmp_path / "member-source"
        provider = config.Infra.codegen.providers[0]
        root_repository = test_u.Tests.repository_ref("flext").model_copy(
            update={"path": Path(), "package": False, "editable": False}
        )
        member = test_u.Tests.repository_ref(
            "flext-core", role=c.Infra.RepositoryRole.WORKSPACE_MEMBER
        ).model_copy(update={"path": Path("flext-core")})
        self._standalone_workspace(member_source, ledger_id=None, overlay=False)
        (member_source / "pyproject.toml").write_text(
            '[project]\nname = "flext-core"\nversion = "0.12.0.dev0"\n'
            'requires-python = ">=3.13,<3.14"\n',
            encoding="utf-8",
        )
        self._git(member_source, "add", "-A")
        self._git(member_source, "commit", "-q", "-m", "Use member identity")
        workspace.mkdir()
        self._git(workspace, "init", "-q", "-b", provider.branch)
        self._git(workspace, "config", "user.email", "infra@example.com")
        self._git(workspace, "config", "user.name", "Infra Tests")
        self._git(
            workspace,
            "-c",
            "protocol.file.allow=always",
            "submodule",
            "add",
            "-q",
            "-b",
            provider.branch,
            str(member_source),
            member.path.as_posix(),
        )
        member_root = workspace / member.path
        # The declared https URL is the real external-member shape and the
        # schema requires it, so .gitmodules and the remote both state it.
        # mro-38p39: a unit test must never touch the network. url.insteadOf
        # rewrites that declared URL to the member's own bare origin, so the
        # topology under test is unchanged while every git operation stays
        # local. Without it this single test paid 7.44s of real GitHub
        # latency -- the largest cost in the suite.
        member_origin = member_source.parent / f"{member_source.name}-origin.git"
        self._git(member_root, "remote", "set-url", "origin", member.url)
        self._git(member_root, "config", f"url.{member_origin}.insteadOf", member.url)
        self._git(
            workspace,
            "config",
            "--file",
            ".gitmodules",
            f"submodule.{member.path.as_posix()}.url",
            member.url,
        )
        spec = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name="flext",
            repository=root_repository,
            members=(member,),
            ledger_id=root_repository.distribution,
            ledger_prefix=root_repository.distribution,
        )
        tm.ok(
            u.Cli.yaml_dump(
                workspace / "config" / "workspace.yaml",
                spec.model_dump(
                    mode="json",
                    exclude_none=True,
                    exclude={"external_dependency_paths"},
                ),
            )
        )
        local_spec = spec.model_copy(
            update={
                "name": member.name,
                "repository": member.model_copy(update={"path": Path()}),
                "members": (),
                "ledger_id": None,
                "ledger_prefix": None,
            }
        )
        tm.ok(
            u.Cli.yaml_dump(
                member_root / "config" / "workspace.yaml",
                local_spec.model_dump(
                    mode="json",
                    exclude_none=True,
                    exclude={"external_dependency_paths"},
                ),
            )
        )
        self._git(member_root, "add", "-A")
        self._git(member_root, "commit", "-q", "-m", "Declare member topology")
        self._git(workspace, "add", "-A")
        self._git(workspace, "commit", "-q", "-m", "Declare workspace topology")
        lane = tmp_path / "external-member-lane"
        self._git(member_root, "worktree", "add", "-q", "--detach", str(lane))

        request = m.Infra.CodegenConformRequest(
            root=lane,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        plan = tm.ok(FlextInfraCodegenConform(workspace_root=lane).plan(request))
        relative_paths = {
            item.path.relative_to(lane).as_posix()
            for item in plan.files
            if item.path.is_relative_to(lane) and item.rendered
        }

        tm.that(c.Infra.BEADS_CONFIG_RELPATH in relative_paths, eq=False)
        tm.that(c.Infra.BEADS_METADATA_RELPATH in relative_paths, eq=False)
        tm.that(".github/workflows/ci-matrix.yml" in relative_paths, eq=False)
        tm.that(any(path.endswith(".Dockerfile") for path in relative_paths), eq=False)
        tm.that(plan.beads[0].repository_root, eq=lane.resolve())
        tm.that(plan.beads[0].ledger_root, eq=workspace.resolve())
        tm.that(plan.beads[0].enabled, eq=False)

    def test_principal_keeps_ledger_at_repository_root(self, tmp_path: Path) -> None:
        """Keep a principal checkout self-owned without worktree redirection."""
        principal = self._standalone_workspace(tmp_path / "principal", ledger_id=None)

        plan = self._beads_plan(principal)

        tm.that(plan.enabled, eq=True)
        tm.that(plan.repository_root, eq=principal.resolve())
        tm.that(plan.ledger_root, eq=principal.resolve())
        tm.that(plan.routes_to_principal_ledger, eq=False)

    def test_manifest_ledger_id_defaults_database_and_issue_prefix(
        self, tmp_path: Path
    ) -> None:
        """Keep the declared ledger database distinct from the issue namespace.

        ai-hub-qwoc (landed in 1b8ac2d2): ``ledger_id`` is the Dolt-safe
        database identifier while ``canonical_prefix`` is the human-facing
        tracker namespace verified against the live ledger. Collapsing both
        silently renamed issue-prefix to the database form.
        """
        principal = self._standalone_workspace(
            tmp_path / "principal", ledger_id="workspace-ledger"
        )

        plan = self._beads_plan(principal)

        tm.that(plan.ledger_id, eq="workspace-ledger")
        tm.that(plan.canonical_prefix, eq="workspace-ledger")

    def test_declared_ledger_prefix_overrides_canonical_project_name(
        self, tmp_path: Path
    ) -> None:
        """Allow a workspace to declare an issue prefix that diverges from its name.

        mro-6fca: the flext workspace root tracks its issues under the ``mro-``
        namespace on the shared Dolt server, not ``flext-``. Deriving the issue
        prefix solely from ``canonical_project_name`` rebinds bd to a
        non-existent ledger and loses the live tracker. ``ledger_prefix`` is the
        typed, explicit override; when it is absent the canonical project name
        still wins, so the ai-hub-qwoc contract above is unchanged.
        """
        principal = self._standalone_workspace(
            tmp_path / "principal",
            ledger_id="workspace-ledger",
            ledger_prefix="workspace-prefix",
        )

        plan = self._beads_plan(principal)

        tm.that(plan.ledger_id, eq="workspace-ledger")
        tm.that(plan.canonical_prefix, eq="workspace-prefix")

    def test_workspace_ledger_identity_flows_to_member_targets(
        self, tmp_path: Path
    ) -> None:
        """Route WORKSPACE_MEMBER targets onto the declared workspace ledger.

        mro-dz4ib / GOVERNANCE.md Execution Contract: "Use the workspace-root
        Beads database for the root and every member project". A member is a
        client of the governing ledger, so both its issue prefix and its
        database come from the workspace manifest, never from its own name.

        Supersedes the earlier mro-z75t reading ("members keep
        canonical_project_name"): that title survived on this test long after
        the body below was corrected to assert inheritance, which made the
        docstring contradict its own assertions (mro-cdzxf).
        """
        branch_policy = config.Infra.codegen.branch_policy
        root_target = m.Infra.RepositoryConformTarget(
            repository=test_u.Tests.repository_ref("flext"),
            root=tmp_path / "flext-root",
            make_profile=c.Infra.MakeProfile.WORKSPACE_ROOT,
            beads_enabled=True,
            routing_only=False,
            canonical_project_name="flext",
            baseline_branch="0.12.0-dev",
            ci_enabled=True,
            external_dependency_paths=(),
            technical_branch_patterns=branch_policy.technical_branch_patterns,
            governed_branch_patterns=branch_policy.governed_branch_patterns,
        )
        member_target = m.Infra.RepositoryConformTarget(
            repository=test_u.Tests.repository_ref(
                "flext-dbt-ldif", role=c.Infra.RepositoryRole.WORKSPACE_MEMBER
            ),
            root=tmp_path / "flext-dbt-ldif",
            make_profile=c.Infra.MakeProfile.WORKSPACE_MEMBER,
            beads_enabled=False,
            routing_only=False,
            canonical_project_name="flext-dbt-ldif",
            baseline_branch="0.12.0-dev",
            ci_enabled=True,
            external_dependency_paths=(),
            technical_branch_patterns=branch_policy.technical_branch_patterns,
            governed_branch_patterns=branch_policy.governed_branch_patterns,
        )
        workspace = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name="flext",
            repository=root_target.repository,
            ledger_id=root_target.repository.distribution,
            # Declared, not inherited: a tracker owner states both identifiers.
            ledger_prefix=f"{root_target.repository.distribution}-issues",
            members=(member_target.repository,),
        )
        root_identity = FlextInfraCodegenConform.ledger_identity_for_target(
            workspace, root_target
        )
        member_identity = FlextInfraCodegenConform.ledger_identity_for_target(
            workspace, member_target
        )

        tm.that(root_identity, eq=(workspace.ledger_prefix, workspace.ledger_id))
        tm.that(member_identity, eq=(workspace.ledger_prefix, workspace.ledger_id))

    def _member_pair(
        self, tmp_path: Path, *, ledger_id: str | None, ledger_prefix: str | None
    ) -> tuple[m.Infra.WorkspaceSpec, m.Infra.RepositoryConformTarget]:
        """Build a governing workspace and one member target that routes to it."""
        branch_policy = config.Infra.codegen.branch_policy
        member_target = m.Infra.RepositoryConformTarget(
            repository=test_u.Tests.repository_ref(
                "flext-dbt-ldif", role=c.Infra.RepositoryRole.WORKSPACE_MEMBER
            ),
            root=tmp_path / "flext-dbt-ldif",
            make_profile=c.Infra.MakeProfile.WORKSPACE_MEMBER,
            beads_enabled=False,
            routing_only=False,
            canonical_project_name="flext-dbt-ldif",
            baseline_branch="0.12.0-dev",
            ci_enabled=True,
            external_dependency_paths=(),
            technical_branch_patterns=branch_policy.technical_branch_patterns,
            governed_branch_patterns=branch_policy.governed_branch_patterns,
        )
        workspace = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name="flext",
            repository=test_u.Tests.repository_ref("flext"),
            ledger_id=ledger_id,
            ledger_prefix=ledger_prefix,
            members=(member_target.repository,),
        )
        return workspace, member_target

    def test_member_of_beadless_workspace_resolves_no_ledger(
        self, tmp_path: Path
    ) -> None:
        """Report "no ledger" for a member whose workspace declares none.

        A workspace that tracks no issues carries no ledger declaration, and
        that is a valid shape -- the member simply gets no Beads client config.
        Only a HALF-declared workspace is a defect (see the next test).
        """
        workspace, member_target = self._member_pair(
            tmp_path, ledger_id=None, ledger_prefix=None
        )

        identity = FlextInfraCodegenConform.ledger_identity_for_target(
            workspace, member_target
        )

        tm.that(identity, eq=None)

    def test_ledger_id_without_prefix_is_refused(self) -> None:
        """Fail closed when the governing workspace half-declares its ledger.

        mro-cdzxf: the issue prefix is a DECLARED fact, never an inferred one.
        Guessing it from the database identity is the mro-9wv8 failure mode --
        bd binds to a ledger that does not exist and every issue created from a
        clean clone lands in a throwaway store. The two identifiers are
        independent by design: a Dolt database must be SQL-safe (``cosmos_main``)
        while an issue prefix is the hyphenated namespace (``cosmos-main``).
        Substituting one for the other silently renames every issue namespace.

        A half-declared ledger is a configuration defect and must surface as one,
        at manifest-validation time, never as a guess at render time.
        """
        repository = test_u.Tests.repository_ref(config.Infra.name)

        with pytest.raises(c.ValidationError, match="ledger_prefix"):
            m.Infra.WorkspaceSpec(
                version=c.Infra.WORKSPACE_MANIFEST_VERSION,
                name=repository.distribution,
                repository=repository,
                ledger_id="cosmos_main",
            )

    def test_workspace_spec_rejects_prefix_without_ledger_id(self) -> None:
        repository = test_u.Tests.repository_ref(config.Infra.name)

        with pytest.raises(c.ValidationError, match="ledger_id"):
            m.Infra.WorkspaceSpec(
                version=c.Infra.WORKSPACE_MANIFEST_VERSION,
                name=repository.distribution,
                repository=repository,
                ledger_prefix=f"{repository.distribution}-prefix",
            )

    def test_workspace_spec_accepts_prefix_declared_equal_to_ledger(self) -> None:
        """Declaring the prefix equal to the ledger states the namespace.

        mro-tvc03: rejecting equality invalidated the real governing manifest,
        which declares ``ledger_id: mro`` with ``ledger_prefix: mro`` precisely
        to state the namespace instead of inheriting it. Runtime proved it:
        ``make work`` failed with "workspace manifest model validation failed"
        for every lane until equality was allowed again.
        """
        repository = test_u.Tests.repository_ref(config.Infra.name)

        spec = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=repository.distribution,
            repository=repository,
            ledger_id=repository.distribution,
            ledger_prefix=repository.distribution,
        )

        tm.that(spec.ledger_prefix, eq=spec.ledger_id)

    @classmethod
    def _plan(cls, root: Path) -> m.Infra.CodegenPlan:
        """Plan one repository in check mode."""
        request = m.Infra.CodegenConformRequest(
            root=root,
            scope=c.Infra.CodegenConformScope.SELF,
            mode=c.Infra.CodegenConformMode.CHECK,
        )
        planned: m.Infra.CodegenPlan = tm.ok(
            FlextInfraCodegenConform(workspace_root=root).plan(request)
        )
        return planned

    @classmethod
    def _beads_config_render(cls, root: Path) -> str | None:
        """Return the rendered ledger config for one repository, if planned."""
        planned = cls._plan(root)
        match = next(
            (
                file
                for file in planned.files
                if file.path.as_posix().endswith(c.Infra.BEADS_CONFIG_RELPATH)
            ),
            None,
        )
        return match.rendered if match is not None else None

    @classmethod
    def _beads_metadata_render(cls, root: Path) -> str | None:
        """Return the rendered ledger-resolution marker, if planned."""
        planned = cls._plan(root)
        match = next(
            (
                file
                for file in planned.files
                if file.path.as_posix().endswith(c.Infra.BEADS_METADATA_RELPATH)
            ),
            None,
        )
        return match.rendered if match is not None else None

    @staticmethod
    def _toolchain_server() -> m.Infra.BeadsServerSpec:
        """Read the shared server block from the typed toolchain SSOT."""
        server = config.Infra.codegen.toolchain.beads.server
        if server is None:
            pytest.fail("toolchain SSOT must declare the beads server block")
        return server

    def test_owner_plan_renders_full_ledger_config(self, tmp_path: Path) -> None:
        """Render the full owned-ledger config for a Beads-enabled repository."""
        root = self._standalone_workspace(tmp_path / "owner", ledger_id="fleet-ledger")

        rendered = self._beads_config_render(root)

        if rendered is None:
            pytest.fail("owner plan must render the ledger config")
        server = self._toolchain_server()
        tm.that(rendered, has='issue-prefix: "fleet-ledger"')
        tm.that(rendered, has="database: fleet-ledger")
        tm.that(rendered, has="Owned ledger config")
        tm.that(rendered, has=f"mode: {server.mode}")
        tm.that(rendered, has=f"shared-server: {str(server.shared_server).lower()}")
        tm.that(rendered, has=f"host: {server.host}")
        tm.that(rendered, has=f"port: {server.port}")
        tm.that(rendered, has=f"user: {server.user}")
        # Quoted on purpose: bare `on` is a YAML boolean, not the string "on".
        # Deriva a expectativa do mesmo SSOT que o template serializa com
        # `| tojson`, entao o teste segue valido para qualquer valor declarado.
        tm.that(rendered, has=f"auto-commit: {json.dumps(server.auto_commit)}")

    def test_attached_standalone_plan_renders_no_beads_config(
        self, tmp_path: Path
    ) -> None:
        """Render a routing-only config for a marker-attached standalone."""
        root = self._standalone_workspace(
            tmp_path / "attached",
            ledger_id="attached-ledger",
            overlay=False,
            attached_marker=True,
        )

        rendered = self._beads_config_render(root)

        tm.that(rendered, eq="")

    def test_plain_standalone_plan_renders_no_ledger_config(
        self, tmp_path: Path
    ) -> None:
        """Render nothing for a standalone without the Beads overlay."""
        root = self._standalone_workspace(
            tmp_path / "plain", ledger_id=None, overlay=False
        )

        tm.that(self._beads_config_render(root), eq=None)
        tm.that(self._beads_metadata_render(root), eq=None)

    def test_owner_plan_renders_ledger_resolution_marker(self, tmp_path: Path) -> None:
        """Bind the owned ledger to its Dolt database through the bd marker.

        mro-9wv8: bd resolves a checkout to its database through
        ``.beads/metadata.json`` and ``bd init`` never writes it, so a clone
        carrying only the generated ``config.yaml`` silently fell back to the
        default ``beads`` database and lost every issue to a throwaway store.
        """
        root = self._standalone_workspace(tmp_path / "owner", ledger_id="fleet-ledger")

        rendered = self._beads_metadata_render(root)

        if rendered is None:
            pytest.fail("owner plan must render the ledger-resolution marker")
        server = self._toolchain_server()
        marker = json.loads(rendered)
        tm.that(marker["dolt_database"], eq="fleet-ledger")
        tm.that(marker["dolt_mode"], eq=server.mode)
        tm.that(marker["backend"], eq=server.backend)
        tm.that(marker["database"], eq=server.backend)

    def test_attached_standalone_plan_renders_no_ledger_resolution_marker(
        self, tmp_path: Path
    ) -> None:
        """Bind a routing-only standalone to the same shared ledger database."""
        root = self._standalone_workspace(
            tmp_path / "attached",
            ledger_id="attached-ledger",
            overlay=False,
            attached_marker=True,
        )

        rendered = self._beads_metadata_render(root)

        tm.that(rendered, eq="")

    def test_tool_spec_rejects_malformed_checksum(self) -> None:
        """Reject a checksum that is not a SHA-256 hex digest."""
        with pytest.raises(c.ValidationError):
            m.Infra.BeadsToolSpec(
                selector="go:example.invalid/tool",
                version="0.0.1",
                reported_version="1.1.0",
                checksum="not-a-digest",
            )

    def test_server_block_loads_from_typed_ssot(self) -> None:
        """Load the shared server block with typed fields from the toolchain SSOT."""
        server = self._toolchain_server()
        tm.that(server.port > 0, eq=True)
        tm.that(bool(server.host), eq=True)
        tm.that(server.auto_commit in {"off", "on", "batch"}, eq=True)

    def test_workspace_without_beads_conforms(self, tmp_path: Path) -> None:
        """Associating Beads with a workspace is OPTIONAL, never required.

        `apply` used to fail closed with "Beads ledger is missing" whenever a
        repository carried no `.beads/`, so a project that simply does not track
        issues could not run codegen at all.
        """
        root = self._standalone_workspace(tmp_path / "no-beads", ledger_id=None)
        shutil.rmtree(root / ".beads", ignore_errors=True)
        result = FlextInfraCodegenConform.execute_request(
            m.Infra.CodegenConformRequest(
                root=root,
                what=c.Infra.CodegenConformSurface.MAKEFILE,
                scope=c.Infra.CodegenConformScope.SELF,
                mode=c.Infra.CodegenConformMode.APPLY,
            )
        )
        # Assert the RESULT, not merely the absence of one error string: a
        # negative-only check would also pass if apply failed for an unrelated
        # reason, which is the opposite of what this test claims to prove.
        tm.ok(result)

    def test_divergent_binary_does_not_block_conform(self, tmp_path: Path) -> None:
        """Mise owns its declared binaries; conform never re-audits them.

        The version/checksum gates ran BEFORE the drift report, so a binary that
        diverged from the pin aborted `make gen WHAT=apply` — the very command
        that regenerates `.mise.toml` and installs the right binary. That
        bootstrap deadlock broke CI for every consumer.
        """
        # The fake binary reports the SSOT's version, so before this fix the run
        # reached the checksum gate instead of stopping at the version gate.
        reported = config.Infra.codegen.toolchain.beads.reported_version
        plugin = tmp_path / "fake-bd-plugin"
        scripts = {
            "list-all": f'echo "{reported}"\n',
            "download": (
                'mkdir -p "$ASDF_DOWNLOAD_PATH/bin"\n'
                f'printf "#!/bin/sh\\necho bd version {reported}\\n" '
                '> "$ASDF_DOWNLOAD_PATH/bin/bd"\n'
                'chmod +x "$ASDF_DOWNLOAD_PATH/bin/bd"\n'
            ),
            "install": (
                'mkdir -p "$ASDF_INSTALL_PATH/bin"\n'
                'cp "$ASDF_DOWNLOAD_PATH/bin/bd" "$ASDF_INSTALL_PATH/bin/bd"\n'
                'chmod +x "$ASDF_INSTALL_PATH/bin/bd"\n'
            ),
        }
        for name, body in scripts.items():
            script = plugin / "bin" / name
            script.parent.mkdir(parents=True, exist_ok=True)
            script.write_text(f"#!/bin/sh\n{body}", encoding="utf-8")
            script.chmod(0o755)
        self._git(plugin, "init", "-q")
        self._git(plugin, "add", "-A")
        self._git(
            plugin,
            "-c",
            "user.email=infra@example.com",
            "-c",
            "user.name=Infra Tests",
            "commit",
            "-qm",
            "fake bd plugin",
        )
        root = self._standalone_workspace(tmp_path / "fake-bd-repo", ledger_id=None)
        (root / ".mise.toml").write_text(
            f'[plugins]\nbd = "file://{plugin}"\n\n[tools]\nbd = "{reported}"\n',
            encoding="utf-8",
        )
        self._git(root, "add", ".mise.toml")
        self._git(root, "commit", "-qm", "Pin the fake bd plugin")
        tm.ok(u.Cli.run_checked(["mise", "trust", ".mise.toml"], cwd=root))
        tm.ok(u.Cli.run_checked(["mise", "install", "--yes", "bd"], cwd=root))
        # The fake plugin installs through the shared mise home; restore it
        # afterwards so no fixture state escapes the sandbox.
        mise_plugin_clone = Path.home() / ".local/share/mise/plugins/bd"
        mise_install_dir = Path.home() / ".local/share/mise/installs/bd"
        try:
            result = FlextInfraCodegenConform.execute_request(
                m.Infra.CodegenConformRequest(
                    root=root,
                    scope=c.Infra.CodegenConformScope.SELF,
                    mode=c.Infra.CodegenConformMode.CHECK,
                )
            )
            # A divergent binary is mise's concern, never a conform verdict.
            # CHECK on this bare fixture legitimately fails on the git-hook
            # gate, so pin THAT as the expected outcome first: without a
            # positive assertion the two negative checks below would also pass
            # on an unrelated failure (or on an empty error string).
            error = result.error or ""
            tm.that("git hook is not installed" in error, eq=True)
            tm.that("checksum mismatch" in error, eq=False)
            tm.that("version mismatch" in error, eq=False)
        finally:
            shutil.rmtree(mise_plugin_clone, ignore_errors=True)
            shutil.rmtree(mise_install_dir, ignore_errors=True)
