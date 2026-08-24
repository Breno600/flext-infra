"""Repository-local workspace manifests are the sole consumer authority."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from flext_infra import c, config, m
from flext_infra.codegen.conform import FlextInfraCodegenConform
from flext_tests import tm

from tests import u


def _repository(
    name: str,
    *,
    path: str,
    role: c.Infra.RepositoryRole,
    state: c.Infra.RepositoryState = c.Infra.RepositoryState.ACTIVE,
) -> m.Infra.RepositoryRef:
    provider = config.Infra.codegen.providers[0]
    return m.Infra.RepositoryRef(
        name=name,
        distribution=name,
        provider=provider.name,
        url=f"{provider.base_url}/{name}.git",
        path=Path(path),
        role=role,
        state=state,
        checkout=(
            c.Infra.CheckoutKind.ROOT
            if role is c.Infra.RepositoryRole.WORKSPACE_ROOT
            else c.Infra.CheckoutKind.SUBMODULE
        ),
        codegen=c.Infra.CodegenKind.CONFORM,
        package=role is c.Infra.RepositoryRole.WORKSPACE_MEMBER,
        editable=role is c.Infra.RepositoryRole.WORKSPACE_MEMBER,
        read_only=False,
    )


def _is_immutable_selector(version: str) -> bool:
    """Whether a pin names one unchangeable artifact.

    Immutable means the coordinate cannot silently point somewhere else later:
    a published release tag or a full commit sha. A moving ref such as
    ``latest`` or a branch name is not.
    """
    if not version or version in {"latest", "main", "master", "HEAD"}:
        return False
    is_commit = len(version) == 40 and all(
        char in "0123456789abcdef" for char in version
    )
    head, _, _ = version.partition("-")
    release_parts = head.split(".")
    is_release_tag = len(release_parts) == 3 and all(
        part.isdecimal() for part in release_parts
    )
    return is_commit or is_release_tag


class TestsCodegenCatalogExtensions:
    def test_beads_toolchain_uses_an_immutable_release_selector(self) -> None:
        version = config.Infra.codegen.toolchain.beads.version

        tm.that(_is_immutable_selector(version), eq=True)

    def test_bootstrap_toolchain_uses_immutable_release_selectors(self) -> None:
        toolchain = config.Infra.codegen.toolchain

        # uv is supplied by the caller environment and is deliberately not pinned;
        # only the mise binary and the Beads CLI installed through mise declare
        # immutable selectors: a semver release for mise, and a release tag or a
        # full commit for Beads.
        mise_parts = toolchain.mise_version.split(".")
        tm.that(len(mise_parts), eq=3)
        tm.that(all(part.isdecimal() for part in mise_parts), eq=True)
        tm.that(_is_immutable_selector(toolchain.beads.version), eq=True)

    def test_beads_gate_compares_the_binary_reported_version(self) -> None:
        """The conform preflight gate uses the binary's self-reported version.

        The gate compares what ``bd version`` prints against a declared value,
        so the toolchain states that value outright instead of deriving it.
        The governed fork builds its own release tag, so the printed version
        and the installed selector are the same string.
        """
        beads = config.Infra.codegen.toolchain.beads
        tm.that(_is_immutable_selector(beads.version), eq=True)
        # ONE declared field, no optional/computed pair: the model states what
        # the binary prints and the gate reads exactly that.
        tm.that(beads.reported_version, eq=beads.version)
        tm.that(hasattr(beads, "gate_version"), eq=False)

    def test_mise_tool_spec_requires_the_reported_version(self) -> None:
        """``reported_version`` is a required field validated by Pydantic.

        It was previously declared ``str | None`` with a fallback inside the
        model. Every mise tool knows what its binary prints, so the value is
        declared, required, and validated at construction instead.
        """
        spec = m.Infra.MiseToolSpec(
            selector="go:example.com/tool/cmd/x",
            version="0123456789abcdef0123456789abcdef01234567",
            reported_version="1.2.3",
        )
        tm.that(spec.reported_version, eq="1.2.3")
        with pytest.raises(c.ValidationError):
            m.Infra.MiseToolSpec.model_validate({
                "selector": "go:example.com/tool/cmd/x",
                "version": "0123456789abcdef0123456789abcdef01234567",
            })
        with pytest.raises(c.ValidationError):
            m.Infra.MiseToolSpec(
                selector="go:example.com/tool/cmd/x",
                version="0123456789abcdef0123456789abcdef01234567",
                reported_version="",
            )

    def test_beads_plan_declares_the_ledger_root_it_owns(self, tmp_path: Path) -> None:
        """``BeadsPlan.ledger_root`` is always the tree that owns the ledger.

        It was ``Path | None``, where ``None`` encoded "same as
        repository_root" — so three separate call sites re-derived the real
        value with ``plan.ledger_root or plan.repository_root`` and a fourth
        compared against ``None`` to detect routing. The plan now declares the
        owning root outright: consumers read one validated field and routing is
        the honest comparison between two paths.
        """
        repo = tmp_path / "member"
        principal = tmp_path / "principal"
        own = m.Infra.BeadsPlan(
            repository_root=repo,
            enabled=True,
            canonical_prefix="mro",
            ledger_root=repo,
            ledger_id="mro",
        )
        tm.that(own.ledger_root, eq=repo)
        tm.that(own.routes_to_principal_ledger, eq=False)
        routed = own.model_copy(update={"ledger_root": principal})
        tm.that(routed.routes_to_principal_ledger, eq=True)
        # The field is required: "no ledger root" is not a representable state.
        with pytest.raises(c.ValidationError):
            m.Infra.BeadsPlan.model_validate({
                "repository_root": repo,
                "enabled": True,
                "canonical_prefix": "mro",
                "ledger_id": "mro",
            })

    def test_beads_tracker_declaration_is_a_validated_model(
        self, tmp_path: Path
    ) -> None:
        """The committed tracker config parses once into a typed model.

        mro-o0cc: a committed ``.beads/config.yaml`` (e.g. the shared ``mro``
        ledger) is the tracker declaration for that repository. Reading it
        returned a bare ``str`` chosen by runtime isinstance checks against an
        untyped mapping, with a ``fallback`` argument deciding the outcome.
        Parsing happens once, at the boundary, into ``BeadsTrackerDeclaration``;
        absence is the model's absence, never a substituted string.
        """
        root = tmp_path / "flext-demo"
        beads_dir = root / ".beads"
        beads_dir.mkdir(parents=True)
        (beads_dir / "config.yaml").write_text(
            'issue-prefix: "mro"\ndolt:\n  database: mro\n', encoding="utf-8"
        )
        declared = tm.ok(FlextInfraCodegenConform.beads_declaration(root))
        tm.that(isinstance(declared, m.Infra.BeadsTrackerDeclaration), eq=True)
        tm.that(declared.issue_prefix, eq="mro")
        # A repository without a committed tracker declares nothing; the
        # caller — not the reader — decides what that means.
        bare = tmp_path / "bare-demo"
        bare.mkdir()
        tm.fail(FlextInfraCodegenConform.beads_declaration(bare))
        # An empty prefix is rejected by the model, not silently replaced.
        broken = tmp_path / "broken-demo"
        (broken / ".beads").mkdir(parents=True)
        (broken / ".beads" / "config.yaml").write_text(
            'issue-prefix: ""\n', encoding="utf-8"
        )
        tm.fail(FlextInfraCodegenConform.beads_declaration(broken))

    def test_gitmodules_render_reaches_a_merge_fixed_point(self) -> None:
        """The gitmodules projection must not grow on every merge pass.

        The template's leading Jinja comment emitted a bare newline, and
        ``_merge_gitmodules`` prepends a separator when the preserved prefix is
        non-empty — so each apply added one more blank line and conform never
        reached its post-apply fixed point on the workspace root.
        """
        template = (
            Path(__file__).parents[3]
            / "src"
            / "flext_infra"
            / "templates"
            / "project"
            / "base"
            / "gitmodules.j2"
        )
        import jinja2

        rendered = jinja2.Template(template.read_text(encoding="utf-8")).render(
            workspace_gitlinks=[
                {
                    "repository": {
                        "name": "demo-member",
                        "path": "demo-member",
                        "url": "https://github.com/flext-sh/demo-member.git",
                    },
                    "branch": "0.12.0-dev",
                }
            ]
        )
        tm.that(rendered.startswith("\n"), eq=False)
        tm.that(rendered.startswith("[submodule"), eq=True)
        managed = frozenset({"demo-member"})
        # Why: idempotent merge of governed gitmodules is exercised through the
        # public conform surface, not the internal static helper.
        conformer = FlextInfraCodegenConform()
        # Why: the static merge helper is an implementation detail of the
        # gitmodules template rendering contract; tests target the private unit
        # directly because the public surface only consumes the final rendered
        # file, never the merge function itself.
        # ruff: ignore[private-member-access]
        once = conformer._merge_gitmodules(rendered, rendered, managed_paths=managed)
        # ruff: ignore[private-member-access]
        twice = conformer._merge_gitmodules(once, rendered, managed_paths=managed)
        tm.that(once, eq=twice)

    def test_setup_provisions_only_and_gen_owns_conformance(self) -> None:
        """``make setup`` provisions tooling; ``make gen`` owns conformance.

        Operator contract (mro-e9j0.6 C7 final): setup installs mise, the
        venv, and dependencies — it never generates, conforms, or mutates
        project code. gen/gen APPLY=Y is the single public conformance and
        generation surface, and no public ``conform`` verb exists.
        """
        template = (
            Path(__file__).parents[3]
            / "src"
            / "flext_infra"
            / "templates"
            / "project"
            / "base"
            / "Makefile.j2"
        )
        content = template.read_text(encoding="utf-8")
        tm.that("_builtin_setup_conform" in content, eq=False)
        setup_env = content.split("_builtin_setup_environment:", 1)[1]
        tm.that("codegen conform" in setup_env.split("\n\n", 1)[0], eq=False)
        tm.that("_builtin_gen_check:" in content, eq=True)
        tm.that("_builtin_gen_apply:" in content, eq=True)
        verb_names = {verb.name for verb in config.Infra.codegen.make.verbs}
        tm.that("conform" in verb_names, eq=False)

    def test_transaction_worktrees_skip_the_beads_lifecycle(
        self, tmp_path: Path
    ) -> None:
        """Inside a worktree transaction the Beads lifecycle is fully skipped.

        A transaction checkout routes its ledger to the principal worktree, so
        the repository_root never owns the tracker lifecycle.  The principal
        ledger is verified separately at the real tree on apply.
        """
        principal = tmp_path / "principal"
        principal.mkdir()
        tx = tmp_path / "tx-checkout"
        (tx / ".beads").mkdir(parents=True)
        (tx / ".beads" / "config.yaml").write_text(
            'issue-prefix: "mro"\n', encoding="utf-8"
        )
        plan = m.Infra.BeadsPlan(
            repository_root=tx,
            ledger_root=principal,
            enabled=False,
            canonical_prefix="mro",
        )
        conformer = FlextInfraCodegenConform()
        # Why: direct unit test of the Beads plan verification predicate; the
        # public conform surface only invokes this predicate and never exposes
        # the boolean result, so the helper is tested at the unit level.
        # ruff: ignore[private-member-access]
        tm.ok(conformer._verify_beads_plan(plan))
        # Owning the ledger while disabled is only a violation when real
        # tracker state exists: config.yaml alone is a routing projection.
        (tx / ".beads" / "beads.db").write_text("", encoding="utf-8")
        plan_at_root = m.Infra.BeadsPlan(
            repository_root=tx, enabled=False, canonical_prefix="mro", ledger_root=tx
        )
        # ruff: ignore[private-member-access]
        tm.fail(conformer._verify_beads_plan(plan_at_root))

    def test_github_actions_ci_skips_the_beads_lifecycle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Inside GitHub Actions CI the Beads lifecycle is fully skipped.

        CI runners are ephemeral and do not carry a live Dolt tracker; the
        committed ``.beads`` tree is present but the tracker database is not.
        Attempting to verify a missing tracker in CI used to fail with
        'Beads tracker inspection failed'. CI is not a tracker owner.
        """
        root = tmp_path / "ci-checkout"
        (root / ".beads").mkdir(parents=True)
        (root / ".beads" / "config.yaml").write_text(
            'issue-prefix: "mro"\n', encoding="utf-8"
        )
        plan = m.Infra.BeadsPlan(
            repository_root=root,
            enabled=False,
            canonical_prefix="mro",
            ledger_root=root,
        )
        monkeypatch.setenv(c.Infra.ENV_VAR_GITHUB_ACTIONS, "true")
        conformer = FlextInfraCodegenConform()
        # Why: unit-level test of the CI skip predicate inside the Beads plan
        # verifier; the public conform surface does not expose this result.
        # ruff: ignore[private-member-access]
        tm.ok(conformer._verify_beads_plan(plan))

    def test_conform_has_no_global_workspace_catalog_validator(self) -> None:
        tm.that(
            hasattr(FlextInfraCodegenConform, "_validate_workspace_catalog"), eq=False
        )

    # Why (suite budget): plans TWO repositories through full conform (platform
    # root + member) on real trees; the per-case wall only holds on an idle CPU.
    @pytest.mark.slow
    def test_local_manifest_conforms_without_global_repository_rows(
        self, tmp_path: Path
    ) -> None:
        root = _repository(
            "acme-platform", path=".", role=c.Infra.RepositoryRole.WORKSPACE_ROOT
        ).model_copy(
            update={
                "extra_verbs": (
                    m.Infra.MakeVerbSpec(
                        name="audit",
                        default_what="all",
                        whats=("all",),
                        apply_what="all",
                    ),
                ),
                "script_dispatch": m.Infra.ScriptDispatchSpec(
                    dispatcher="scripts/dispatch.py", roots=("scripts",)
                ),
            }
        )
        project = m.Infra.ProjectSpec(
            package_name="acme_platform",
            class_stem="AcmePlatform",
            namespace="AcmePlatform",
            constant_name="acme-platform",
            namespace_attribute="acme_platform",
            alias="acme",
            environment_prefix="ACME_PLATFORM_",
            description="Product-neutral platform fixture",
            version="0.1.0",
            license="MIT",
            author_name="Acme Team",
            author_email="engineering@example.com",
            upstream="flext_core",
            homepage="https://example.com/acme-platform",
            documentation="https://example.com/acme-platform/docs",
            workspace_root_rel=".",
            year=2026,
        )
        workspace = m.Infra.WorkspaceSpec(
            version=c.Infra.WORKSPACE_MANIFEST_VERSION,
            name=root.name,
            repository=root,
            project=project,
            members=(
                _repository(
                    "acme-charts",
                    path="acme-charts",
                    role=c.Infra.RepositoryRole.WORKSPACE_MEMBER,
                ),
            ),
        )
        member_root = tmp_path / "acme-charts"
        member_root.mkdir()
        (member_root / c.Infra.PYPROJECT_FILENAME).write_text(
            '[project]\nname = "acme-charts"\nversion = "0.1.0"\n'
            'requires-python = ">=3.13,<3.14"\ndependencies = []\n',
            encoding="utf-8",
        )
        tm.ok(
            u.Cli.run_checked(
                ["git", "init", "-q", "-b", "development"], cwd=member_root
            )
        )
        tm.ok(
            u.Cli.run_checked(
                ["git", "config", "user.email", "infra@example.com"], cwd=member_root
            )
        )
        tm.ok(
            u.Cli.run_checked(
                ["git", "config", "user.name", "Infra Tests"], cwd=member_root
            )
        )
        tm.ok(
            u.Cli.run_checked(
                ["git", "add", c.Infra.PYPROJECT_FILENAME], cwd=member_root
            )
        )
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Initial fixture"], cwd=member_root
            )
        )
        # Register acme-charts as a real Git submodule so workspace root
        # resolution and analysis exclusion discovery observe the attached
        # topology. A local bare repo is used because Git file transport is
        # disabled by default in current releases.
        bare_repo = tmp_path.parent / "acme-charts-bare.git"
        tm.ok(
            u.Cli.run_checked([
                "git",
                "clone",
                "--bare",
                member_root.as_posix(),
                bare_repo.as_posix(),
            ])
        )
        tm.ok(u.Cli.run_checked(["rm", "-rf", member_root.as_posix()]))
        tm.ok(u.Cli.run_checked(["git", "init", "-q"], cwd=tmp_path))
        tm.ok(
            u.Cli.run_checked(
                [
                    "git",
                    "-c",
                    "protocol.file.allow=always",
                    "submodule",
                    "add",
                    bare_repo.as_posix(),
                    "acme-charts",
                ],
                cwd=tmp_path,
            )
        )
        provider = config.Infra.codegen.providers[0]
        tm.ok(
            u.Cli.run_checked(
                [
                    "git",
                    "config",
                    "remote.origin.url",
                    f"{provider.base_url}/acme-charts.git",
                ],
                cwd=member_root,
            )
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                tmp_path / c.Infra.PYPROJECT_FILENAME,
                '[project]\nname = "acme-platform"\nversion = "0.1.0"\n'
                'requires-python = ">=3.13,<3.14"\ndependencies = []\n',
            )
        )
        tm.ok(
            u.Cli.atomic_write_text_file(
                tmp_path / c.Infra.GITMODULES,
                '[submodule "acme-charts"]\n'
                f"    path = acme-charts\n"
                f"    url = {provider.base_url}/acme-charts.git\n"
                f"    branch = {provider.branch}\n",
            )
        )
        tm.ok(
            u.Cli.run_checked(
                ["git", "config", "user.email", "infra@example.com"], cwd=tmp_path
            )
        )
        tm.ok(
            u.Cli.run_checked(
                ["git", "config", "user.name", "Infra Tests"], cwd=tmp_path
            )
        )
        tm.ok(
            u.Cli.run_checked(
                ["git", "add", c.Infra.PYPROJECT_FILENAME, c.Infra.GITMODULES],
                cwd=tmp_path,
            )
        )
        tm.ok(
            u.Cli.run_checked(
                ["git", "commit", "-q", "-m", "Workspace fixture"], cwd=tmp_path
            )
        )
        tm.ok(u.Cli.run_checked(["rm", "-rf", bare_repo.as_posix()]))
        manifest_path = tmp_path / "config" / c.Infra.WORKSPACE_MANIFEST_FILENAME
        manifest_path.parent.mkdir(parents=True)
        tm.ok(
            u.Cli.yaml_dump(
                manifest_path, workspace.model_dump(mode="json", exclude_none=True)
            )
        )
        result = FlextInfraCodegenConform(initial_workspace=workspace).plan(
            m.Infra.CodegenConformRequest(
                root=tmp_path,
                what=c.Infra.CodegenConformSurface.ALL,
                scope=c.Infra.CodegenConformScope.ALL,
                mode=c.Infra.CodegenConformMode.CHECK,
            )
        )

        plan = tm.ok(result)
        tm.that(
            tuple(item.name for item in plan.repositories),
            eq=(root.name, "acme-charts"),
        )
        external_root = (tmp_path / "acme-content").resolve()
        tm.that(
            any(
                external_root == file.path or external_root in file.path.parents
                for file in plan.files
            ),
            eq=False,
        )
        tm.that(external_root.exists(), eq=False)
        root_makefile = next(
            file
            for file in plan.files
            if file.path == tmp_path.resolve() / c.Infra.MAKEFILE_FILENAME
        )
        tm.that(root_makefile.rendered, has="WORKSPACE_MEMBERS := acme-charts")
        tm.that("acme-content" in root_makefile.rendered, eq=False)
        workflows = tuple(
            file for file in plan.files if ".github/workflows" in file.path.as_posix()
        )
        # How many workflows exist is config-owned: freezing the count makes a
        # legitimate template addition fail here. The contract is that every
        # planned workflow is one the config declares, and that none leaks the
        # content-only repository.
        declared_workflows = frozenset(
            entry.destination
            for entry in config.Infra.codegen.templates.entries
            if ".github/workflows" in entry.destination
        )
        tm.that(workflows, empty=False)
        for workflow in workflows:
            tm.that(
                any(
                    workflow.path.as_posix().endswith(destination)
                    for destination in declared_workflows
                ),
                eq=True,
                msg=f"undeclared workflow planned: {workflow.path}",
            )
        for workflow in workflows:
            tm.that("acme-content" in workflow.rendered, eq=False)
        gitmodules = next(
            file.rendered for file in plan.files if file.path.name == ".gitmodules"
        )
        tm.that(gitmodules, has='[submodule "acme-charts"]')
        tm.that("acme-content" in gitmodules, eq=False)
        mise = tomllib.loads(
            next(file.rendered for file in plan.files if file.path.name == ".mise.toml")
        )
        tm.that(
            mise["tools"][config.Infra.codegen.toolchain.beads.selector],
            eq=config.Infra.codegen.toolchain.beads.version,
        )
        pyproject = tomllib.loads(
            next(
                file.rendered
                for file in plan.files
                if file.path.name == c.Infra.PYPROJECT_FILENAME
            )
        )
        tools = pyproject["tool"]
        tm.that("acme-content" in tools["ruff"]["exclude"], eq=False)
        tm.that("acme-content" in tools["pyright"]["exclude"], eq=False)


__all__: tuple[str, ...] = ()
