"""Transactional CSV campaigns using existing Rope and publication primitives.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

import ast
from os.path import commonpath
from pathlib import Path

from flext_infra import c, m, p, r, t, u
from flext_infra.codemod._rename_sources import FlextInfraRenameSources
from flext_infra.codemod._rename_symbols import FlextInfraRenameSymbols
from flext_infra.transformers import FlextInfraSemanticPublication


class FlextInfraApplyRenames:
    """Plan against authenticated bytes and commit only after a real post-scan."""

    @classmethod
    def _plan(
        cls,
        params: m.Infra.ApplyRenamesInput,
        roots: t.SequenceOf[Path],
        pairs: t.SequenceOf[t.Pair[str, str]],
    ) -> t.Pair[t.VariadicTuple[m.Infra.SemanticFilePlan], int]:

        inventory = FlextInfraRenameSources.inventory(roots, params)
        sources = {
            path: state.content.decode(c.Cli.ENCODING_DEFAULT)
            for path, state in inventory.items()
            if state.content is not None
        }
        python = {
            path: source
            for path, source in sources.items()
            if path.suffix == c.Infra.EXT_PYTHON
        }
        root = Path(commonpath(roots))
        plans: t.MutableSequenceOf[m.Infra.SemanticFilePlan] = []
        occurrences = 0
        with u.Infra.open_project(root, project_roots=roots) as project:
            symbols = FlextInfraRenameSymbols.plan(
                project,
                python,
                pairs,
                params.bindings,
            )
            for path, source in sources.items():
                edits = list(symbols.get(path, ()))
                if path in python:
                    if params.python_documentation:
                        edits.extend(
                            FlextInfraRenameSources.documentation_edits(source, pairs),
                        )
                else:
                    edits.extend(FlextInfraRenameSources.text_edits(source, pairs))
                occurrences += len(edits)
                desired = inventory[path].content
                if edits:
                    resource = project.get_resource(path.relative_to(root).as_posix())
                    changed = u.Infra.content_change(resource, source, edits)
                    if path in python:
                        ast.parse(changed.new_contents, filename=str(path))
                    desired = changed.new_contents.encode(c.Cli.ENCODING_DEFAULT)
                plans.append(
                    m.Infra.SemanticFilePlan(
                        project=root,
                        path=path,
                        before=inventory[path],
                        desired_content=desired if edits else None,
                        desired_mode=inventory[path].mode,
                        changes=("CSV campaign",) if edits else (),
                    ),
                )
        return tuple(plans), occurrences

    @staticmethod
    def _campaign_error(
        params: m.Infra.ApplyRenamesInput,
        roots: t.SequenceOf[Path],
    ) -> str | None:
        """Return the campaign validation failure message, or ``None`` when valid."""
        for root in roots:
            if not root.is_dir():
                return f"rename root is not a directory: {root}"
        if (
            not params.bindings
            and not params.text_globs
            and not params.python_documentation
        ):
            return "rename campaign has no declared symbol or text surfaces"
        return None

    @classmethod
    def _publish(
        cls,
        params: m.Infra.ApplyRenamesInput,
        roots: t.SequenceOf[Path],
        state: t.Pair[Path, m.Cli.AtomicFileState],
        pairs: t.SequenceOf[t.Pair[str, str]],
        planned: t.Pair[t.SequenceOf[m.Infra.SemanticFilePlan], int],
    ) -> p.Result[t.Pair[t.SequenceOf[Path], int]]:
        """Publish the campaign atomically and re-plan until the post-scan is clean.

        Returns:
            The resulting ``p.Result[t.Pair[t.SequenceOf[Path], int]]`` holding the
            changed paths and the residual pending-edit count.

        """
        csv_path, driver = state
        plans, pending = planned

        def verify() -> p.Result[bool]:
            nonlocal pending
            current_driver = u.Cli.atomic_read_binary_file_state(
                csv_path,
                required=True,
            ).unwrap()
            if current_driver != driver:
                return r[bool].fail(
                    f"rename campaign driver changed during publish: {csv_path}",
                )
            _fresh, remaining = cls._plan(params, roots, pairs)
            pending = remaining
            if remaining:
                return r[bool].fail(
                    f"CSV campaign post-scan found {remaining} pending edits",
                )
            return r[bool].ok(value=True)

        driver_plan = m.Infra.SemanticFilePlan(
            project=Path(commonpath(roots)),
            path=csv_path,
            before=driver,
            desired_content=None,
            desired_mode=driver.mode,
            changes=(),
        )
        publication = FlextInfraSemanticPublication.publish_semantic_file_plans(
            (*plans, driver_plan),
            repository_root=Path(commonpath(roots)),
            validator=verify,
        )
        if publication.failure:
            return r[t.Pair[t.SequenceOf[Path], int]].from_failure(publication)
        changed = publication.value
        # Empty transactions do not invoke the publisher's validator.
        if not changed:
            verify().unwrap()
        return r[t.Pair[t.SequenceOf[Path], int]].ok((changed, pending))

    @classmethod
    def run(
        cls,
        params: m.Infra.ApplyRenamesInput,
    ) -> p.Result[m.Infra.ApplyRenamesReport]:
        """Apply one declared campaign; check and verification share the planner.

        Returns:
            The resulting ``p.Result[m.Infra.ApplyRenamesReport]``.

        """
        roots = tuple(sorted({Path(value).resolve() for value in params.roots}))
        error = cls._campaign_error(params, roots)
        if error is not None:
            return r[m.Infra.ApplyRenamesReport].fail(error)
        csv_path = Path(params.csv).resolve()
        driver = u.Cli.atomic_read_binary_file_state(csv_path, required=True).unwrap()
        if driver.content is None:
            return r[m.Infra.ApplyRenamesReport].fail(
                f"rename CSV disappeared: {csv_path}",
            )
        pairs = FlextInfraRenameSources.pairs(
            driver.content.decode(c.Cli.ENCODING_DEFAULT),
        )
        plans, pending = cls._plan(params, roots, pairs)
        changed: t.SequenceOf[Path] = ()
        if params.apply:
            publication = cls._publish(
                params,
                roots,
                (csv_path, driver),
                pairs,
                (plans, pending),
            )
            if publication.failure:
                return r[m.Infra.ApplyRenamesReport].from_failure(publication)
            changed, pending = publication.value
        report = m.Infra.ApplyRenamesReport(
            label=csv_path.stem,
            files_scanned=len(plans),
            occurrences=pending,
            files_changed=len(changed),
            applied=params.apply,
        )
        return r[m.Infra.ApplyRenamesReport].ok(report)


__all__: list[str] = ["FlextInfraApplyRenames"]
