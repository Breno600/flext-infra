"""Desired-state file, environment, and retirement plans."""

from __future__ import annotations

from pathlib import Path

from flext_core import r

from ... import c, config, m, p, t, u
from .beads_routes import FlextInfraCodegenConformBeadsRoutes


class FlextInfraCodegenConformFilePlans(FlextInfraCodegenConformBeadsRoutes):
    """Desired-state file, environment, and retirement plans."""

    @staticmethod
    def file_plan(
        root: Path,
        relative_path: str,
        rendered: str,
        *,
        mode: int = 0o644,
        source_states: t.VariadicTuple[m.Cli.AtomicFileState] = (),
    ) -> p.Result[m.Infra.CodegenFilePlan]:
        """Snapshot one target and bind it to exact desired bytes and mode."""
        project = root.expanduser().absolute()
        path = (project / relative_path).absolute()
        # Planning is read-only: an optional read of a destination whose parent
        # chain is not materialized reports absence (no parent identity), and
        # the generation transaction journals and creates every destination
        # parent before staging. Creating directories here made a CHECK plan
        # mutate the tree and the next plan diverge from the first.
        before = u.Cli.atomic_read_binary_file_state(path, required=False)
        if before.failure:
            return r[m.Infra.CodegenFilePlan].from_failure(before)
        return r[m.Infra.CodegenFilePlan].ok(
            m.Infra.CodegenFilePlan(
                project=project,
                path=path,
                before=before.value,
                desired_content=rendered.encode(c.Cli.ENCODING_DEFAULT),
                desired_mode=mode,
                source_states=source_states,
            )
        )

    @staticmethod
    def mise_config_plans(
        plan: m.Infra.CodegenPlan,
    ) -> p.Result[t.VariadicTuple[m.Infra.CodegenFilePlan]]:
        """Select one planned Mise configuration for each selected repository."""
        expected = tuple(
            environment.project_root / c.Infra.MISE_TOML_FILENAME
            for environment in plan.uv_environments
        )
        by_path = {item.path: item for item in plan.files if item.path in expected}
        if (
            len(expected) != len(plan.repositories)
            or len(set(expected)) != len(expected)
            or len(by_path) != len(expected)
        ):
            return r[t.VariadicTuple[m.Infra.CodegenFilePlan]].fail(
                "conform plan must contain one Mise configuration per repository"
            )
        return r[t.VariadicTuple[m.Infra.CodegenFilePlan]].ok(
            tuple(by_path[path] for path in expected)
        )

    @staticmethod
    def uv_environment_plan(
        *,
        root: Path,
        target: m.Infra.RepositoryConformTarget,
        workspace: m.Infra.WorkspaceSpec,
        config: m.Infra.CodegenConfigSpec,
    ) -> m.Infra.UvEnvironmentPlan:
        """Describe the exact setup overlay without executing uv."""
        workspace_environment = target.make_profile is c.Infra.MakeProfile.WORKSPACE
        groups: t.VariadicTuple[str] = ("dev", "codegen")
        editable_repositories: t.VariadicTuple[m.Infra.RepositoryRef] = ()
        if workspace_environment:
            groups = (*groups, "workspace")
            editable_repositories = tuple(
                item
                for item in (workspace.repository, *workspace.subprojects)
                if item.package and item.editable and not item.read_only
            )
        return m.Infra.UvEnvironmentPlan(
            project_root=root,
            environment_root=target.root,
            python_version=config.toolchain.python_version,
            groups=groups,
            editable_repositories=editable_repositories,
        )

    @staticmethod
    def _absent_file_plan(root: Path, path: Path) -> p.Result[m.Infra.CodegenFilePlan]:
        """Plan the removal of one retired projection."""
        return u.Infra.planned_file(
            root.expanduser().absolute(),
            path.expanduser().absolute(),
            required=True,
            desired_content=None,
            desired_mode=None,
        )

    @classmethod
    def retired_projection_plans(
        cls, root: Path, profile: c.Infra.MakeProfile
    ) -> p.Result[t.SequenceOf[m.Infra.CodegenFilePlan]]:
        """Plan removal of generated projections this profile no longer renders.

        A projection retires either because its template entry excludes this
        profile or because no template renders it any more (a renamed or
        deleted template, declared in ``retired_projections``). Either way only
        a file carrying the generated marker is removed.
        """
        planned: list[m.Infra.CodegenFilePlan] = []
        destinations: list[str] = [
            entry.destination
            for entry in config.Infra.codegen.templates.entries
            if profile not in entry.profiles and "{" not in entry.destination
        ]
        for retired in config.Infra.codegen.retired_projections:
            relative = Path(retired)
            if relative.is_absolute() or ".." in relative.parts:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].fail(
                    f"retired projection must be a normalized relative path: {retired}"
                )
            destinations.append(retired)
        for destination in destinations:
            path = root / Path(destination)
            if not path.is_file():
                continue
            current = u.Cli.files_read_text(path)
            if current.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(current)
            if not any(
                marker in current.value for marker in c.Infra.TEMPLATE_GENERATED_MARKERS
            ):
                continue
            absent_plan = cls._absent_file_plan(root, path)
            if absent_plan.failure:
                return r[t.SequenceOf[m.Infra.CodegenFilePlan]].from_failure(
                    absent_plan
                )
            planned.append(absent_plan.value)
        return r[t.SequenceOf[m.Infra.CodegenFilePlan]].ok(tuple(planned))


__all__: list[str] = ["FlextInfraCodegenConformFilePlans"]
