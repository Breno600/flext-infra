"""Pyproject, tooling-root, and custom Make policy projections.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import re
from pathlib import Path

from flext_infra import c, config, m, p, r, t, u
from flext_infra.codegen._conform.file_plans import FlextInfraCodegenConformFilePlans


class FlextInfraCodegenConformPyprojectPolicy(FlextInfraCodegenConformFilePlans):
    """Pyproject, tooling-root, and custom Make policy projections."""

    @staticmethod
    def _scaffold_python_dirs(
        entries: t.SequenceOf[p.Infra.TemplateEntrySpec],
        profile: c.Infra.MakeProfile,
        *,
        package: bool = True,
    ) -> t.StrSequence:
        """Return Python roots the selected scaffold manifest actually creates.

        Returns:
            Python roots the selected scaffold manifest actually creates.

        """
        # Derive future roots from both
        # declarative owners so scaffold and existing-tree discovery converge.
        generated_roots = {
            Path(entry.destination).parts[0]
            for entry in entries
            if profile in entry.profiles
            and entry.delegate == c.Infra.TemplateDelegate.RENDER
            and Path(entry.destination).parts
        }
        # An existing package:false repository (a solo workspace root)
        # materializes no package source dir: its manifest declares no
        # importable package, so analyzers must not include it — pyright
        # fails hard on an include entry whose directory does not exist.
        # The atomic scaffold path never passes ``package=False``: its own
        # manifest renders the source tree, and dropping ``src`` there made
        # the first plan fall back to disk discovery for mypy/pyrefly search
        # paths, which oscillates once the scaffold's directory chain exists.
        source_dir = config.Infra.tooling.tools.pyright.path_rules.source_dir
        return tuple(
            directory
            for directory in config.Infra.tooling.tools.pyright.path_rules.env_dirs
            if directory in generated_roots and (package or directory != source_dir)
        )

    @classmethod
    def conformed_pyproject_source(
        cls,
        source: str,
        *,
        render_inputs: m.Infra.CodegenRenderInputs,
    ) -> p.Result[str]:
        """Conform one pyproject source.

        Returns:
            The resulting ``p.Result[str]``.

        """
        target = render_inputs.target
        workspace = render_inputs.workspace
        codegen = render_inputs.codegen
        flext_line = u.Infra.flext_integration_line_for_checkout(
            codegen=codegen,
            repository_root=target.root,
            workspace=workspace,
        )
        if flext_line.failure:
            return r[str].from_failure(flext_line)
        if workspace.integration is None:
            # Attached members render on the workspace's own integration line
            # (a governed .gitmodules branch must equal it), derived from the
            # checkout when the manifest does not declare it.
            branch = u.Infra.resolve_integration_branch(
                target.root,
                preference=codegen.branch_policy.integration_branch_preference,
            )
            if branch.failure:
                return r[str].from_failure(branch)
            workspace = workspace.model_copy(
                update={
                    "integration": m.Infra.WorkspaceIntegrationSpec(
                        provider=workspace.repository.provider,
                        branch=branch.value,
                    ),
                },
            )
        return u.Infra.pyproject_conform(
            source,
            workspace=workspace,
            required_dev_dependencies=codegen.scaffold.project.dev,
            uv_resolution=m.Infra.UvResolutionSpec(
                link_mode=cls.link_mode(target.repository, codegen.toolchain),
                constraint_dependencies=tuple(
                    codegen.toolchain.uv_constraint_dependencies,
                ),
                exclude_dependencies=cls.routed_uv_exclude_dependencies(render_inputs),
                environments=tuple(codegen.toolchain.uv_environments),
            ),
            family_line=flext_line.value.branch,
        )

    @staticmethod
    def routed_uv_exclude_dependencies(
        render_inputs: m.Infra.CodegenRenderInputs,
    ) -> t.VariadicTuple[m.Infra.UvScopedDependencyExclusionSpec]:
        """Return the uv dependency exclusions routed to one repository.

        An exclusion drops a reverse edge onto a project installed from its
        local checkout. It applies only where that project is local: the
        repository itself or, at a workspace root (uv reads
        exclude-dependencies only from the root), one of its declared
        members. Routing an exclusion for an absent project would drop the
        only edge that installs it.

        Returns:
            The uv dependency exclusions routed to one repository.

        """
        target = render_inputs.target
        local = {target.repository.distribution}
        if target.make_profile is c.Infra.MakeProfile.WORKSPACE:
            local.update(
                member.distribution for member in render_inputs.workspace.subprojects
            )
        return tuple(
            item
            for item in render_inputs.codegen.uv_exclude_dependencies
            if item.project in local
        )

    @staticmethod
    def validate_custom_make(
        content: str,
        policy: m.Infra.CustomHandlerPolicy,
    ) -> p.Result[bool]:
        """Reject public targets, aliases, includes, and toolchain declarations.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        target_re = re.compile(policy.target_pattern)
        in_define = False
        # Collapse backslash continuation lines before validating so that
        # directives like `.PHONY` can span multiple physical lines. Only
        # collapse non-recipe lines (recipe lines start with whitespace and are
        # skipped below); the reported line number is the first physical line.
        logical_lines: list[t.Pair[int, str]] = []
        pending_line: str | None = None
        pending_number: int = 0
        for line_number, raw_line in enumerate(content.splitlines(), start=1):
            if (
                raw_line
                and not raw_line[0].isspace()
                and raw_line.rstrip().endswith("\\")
            ):
                trimmed = raw_line.rstrip()[:-1].rstrip()
                if pending_line is None:
                    pending_line = trimmed
                    pending_number = line_number
                else:
                    pending_line += " " + trimmed
                continue
            # A continuation collapses several physical lines into one logical
            # line, which is reported at the line the continuation STARTED on,
            # not the line it ended on. Assigning back onto the loop variables
            # made the two indistinguishable and left the next iteration reading
            # a value the iterator never produced.
            logical_line = raw_line
            logical_number = line_number
            if pending_line is not None:
                joined = pending_line + " " + raw_line.strip()
                if joined.rstrip().endswith("\\"):
                    pending_line = joined.rstrip()[:-1].rstrip()
                    continue
                logical_line = joined
                logical_number = pending_number
                pending_line = None
            logical_lines.append((logical_number, logical_line))
        if pending_line is not None:
            if pending_line.startswith(".PHONY:"):
                return r[bool].fail(
                    f"{policy.filename} has an unterminated .PHONY continuation",
                )
            logical_lines.append((pending_number, pending_line))
        for line_number, raw_line in logical_lines:
            if in_define:
                in_define = not raw_line.startswith("endef")
                continue
            if raw_line.startswith("define "):
                if not policy.allow_toolchain_declarations:
                    return r[bool].fail(
                        f"{policy.filename} line {line_number} "
                        "declares a macro, which this profile forbids",
                    )
                in_define = True
                continue
            if not raw_line or raw_line.lstrip().startswith("#"):
                continue
            if raw_line[0].isspace():
                continue
            if c.Infra.MAKE_CONDITIONAL_RE.match(raw_line):
                continue
            if raw_line.startswith(".PHONY:"):
                declaration = raw_line.partition(":")[2].strip()
                names = declaration.split()
                if names and all(target_re.fullmatch(name) for name in names):
                    continue
            target = raw_line.partition(":")[0].strip() if ":" in raw_line else ""
            if target and target_re.fullmatch(target):
                continue
            if c.Infra.MAKE_ASSIGNMENT_RE.match(
                raw_line,
            ) or c.Infra.MAKE_DIRECTIVE_RE.match(raw_line):
                if policy.allow_toolchain_declarations:
                    continue
                return r[bool].fail(
                    f"{policy.filename} line {line_number} "
                    "declares a variable, which this profile forbids",
                )
            if target and policy.allow_public_targets:
                continue
            return r[bool].fail(
                f"{policy.filename} line {line_number} is not a private custom handler",
            )
        return r[bool].ok(value=True)


__all__: list[str] = ["FlextInfraCodegenConformPyprojectPolicy"]
