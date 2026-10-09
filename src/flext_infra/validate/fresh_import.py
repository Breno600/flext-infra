"""Verify published exports and real entrypoints in fresh child processes.

The ``fresh-import`` check gate runs this guard in the checkout's provisioned
runtime. File-facade generation also uses its authenticated staged-view consumer.
Each entrypoint loads before any package smoke so cached imports cannot hide
consumer-order defects. Imported workspace modules must belong to this checkout.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, ClassVar, override

from flext_infra import c, config, m, p, r, settings, t, u
from flext_infra.base import FlextInfraServiceBase
from flext_infra.codegen._mise_artifacts_files import FlextInfraMiseArtifactsFiles
from flext_infra.codegen._mise_artifacts_journal import FlextInfraMiseArtifactsJournal
from flext_infra.codegen._mise_artifacts_verification import (
    FlextInfraMiseArtifactsVerification,
)
from flext_infra.codegen.codegen_preconditions import FlextInfraCodegenPreconditions


class FlextInfraValidateFreshImport(FlextInfraServiceBase[bool]):
    """Verify consumers and publication contracts without inherited import state."""

    packages: Annotated[
        t.StrSequence,
        m.Field(description="Packages to validate in fresh subprocesses"),
    ] = (c.Infra.PKG_CORE_UNDERSCORE, "flext_infra", "flext_tests")
    runtime_root: Annotated[
        Path | None,
        m.Field(
            description=(
                "Declared runtime root whose environment runs the probes; "
                "undeclared, the target checkout's own environment"
            ),
        ),
    ] = m.Field(
        default_factory=lambda: type(settings).fetch_global().Infra.runtime_root
    )

    _PRELUDE: ClassVar[str] = (
        "import importlib, sys\n"
        "from importlib.metadata import EntryPoint\n"
        "from pathlib import Path\n"
    )
    _EXPORT_IMPORT_CODE: ClassVar[str] = (
        "module = importlib.import_module({package!r})\n"
    )
    # The origin gate runs between the import and the name resolution: a
    # module loaded from outside this checkout must fail with the origin
    # error naming the foreign path, never with a phantom-attribute error
    # raised while resolving a stale export name.
    _EXPORT_RESOLVE_CODE: ClassVar[str] = (
        "for name in (*{exports!r}, *getattr(module, '__all__', ())):\n"
        "    getattr(module, name)\n"
    )
    # Synthetic concat keeps the placeholder out of one plain literal: the
    # marker is template text substituted at render time, never an f-string.
    _ORIGINS_PLACEHOLDER: ClassVar[str] = "{" + "origins!r}"
    # The origin gate runs inside the same probe namespace as the export
    # resolution, so its loop names must never rebind the probed ``module``.
    _ORIGIN_CODE: ClassVar[str] = (
        "for loaded_name, loaded_module in tuple(sys.modules.items()):\n"
        "    for package, directory in {origins!r}:\n"
        "        if loaded_name == package or loaded_name.startswith(package + '.'):\n"
        "            origin = getattr(loaded_module, '__file__', None)\n"
        "            if (\n"
        "                origin is None\n"
        "                or not Path(origin).resolve()\n"
        "                .is_relative_to(Path(directory))\n"
        "            ):\n"
        "                raise ImportError(\n"
        "                    f'{loaded_name}: origin {origin!r} '\n"
        "                    f'is outside {directory}'\n"
        "                )\n"
    )

    def build_report(
        self,
        packages: t.StrSequence = (),
        *,
        publications: t.SequenceOf[m.Infra.LazyInitPlan] = (),
        repository_roots: t.SequenceOf[Path] = (),
    ) -> p.Result[m.Infra.ValidationReport]:
        """Validate complete publications, stopping at the first causal failure.

        Returns:
            The resulting ``p.Result[m.Infra.ValidationReport]``.

        """
        layouts_result = self._project_layouts(repository_roots)
        if layouts_result.failure:
            return r[m.Infra.ValidationReport].from_failure(layouts_result)
        layouts = layouts_result.value
        origin_code = self._origin_code(layouts)
        probes: t.MutableSequenceOf[m.Infra.FreshImportProbe] = []
        for layout in layouts:
            built = self._layout_probes(layout, origin_code, publications)
            if built.failure:
                return r[m.Infra.ValidationReport].from_failure(built)
            probes.extend(built.value)
        packaged = self._package_probes(packages, origin_code)
        if packaged.failure:
            return r[m.Infra.ValidationReport].from_failure(packaged)
        probes.extend(packaged.value)
        if not probes:
            return r[m.Infra.ValidationReport].ok(
                m.Infra.ValidationReport(
                    passed=True,
                    violations=(),
                    summary="0 fresh-import probe(s) passed",
                ),
            )
        return self._execute_probes(probes, layouts)

    def _stage_journal_authority(
        self,
        view: m.Infra.StagePackageView,
        session: m.Infra.CodegenTransactionSession,
    ) -> p.Result[bool]:
        """Verify journal authority, containment and finalized intentions in order.

        Returns:
            The destination proof or the first journal authority failure.
        """
        authority = FlextInfraCodegenPreconditions.unchanged_journal(
            session, "staged view journal authority changed"
        )
        if authority.failure:
            return r[bool].from_failure(authority)
        topology = FlextInfraMiseArtifactsVerification.journal_topology(
            session.plan.layout, session.journal
        )
        if topology.failure:
            return r[bool].from_failure(topology)
        if not any(
            view.root.is_relative_to(participant.transaction_root)
            and view.root != participant.transaction_root
            for participant in session.plan.layout.file_participants
        ):
            return r[bool].fail(
                "candidate view escapes registered participant transaction roots"
            )
        receipts = {
            intent.before.path: intent.created
            for intent in session.journal.staging_intents
        }
        if any(
            entry.kind == "file" and receipts.get(entry.path) != entry
            for entry in view.manifest.entries
        ):
            return r[bool].fail(
                "candidate file has no durable finalized staging intention"
            )
        return self._stage_target_current(view, session)

    @staticmethod
    def _stage_target_current(
        view: m.Infra.StagePackageView,
        session: m.Infra.CodegenTransactionSession,
    ) -> p.Result[bool]:
        """Bind the staged target hash to its canonical live destination.

        Returns:
            Success only for the matching destination journal entry.
        """
        original_layout = next(
            (
                layout
                for layout in view.plan.layouts
                if layout.package_name == view.plan.package
            ),
            None,
        )
        if original_layout is None:
            return r[bool].fail(
                "candidate selected package has no pinned original layout"
            )
        original_target = original_layout.src_dir / Path(
            *view.plan.module.split(".")
        ).with_suffix(c.Infra.EXT_PYTHON)
        target_entry: m.Infra.CodegenJournalEntry | None = None
        for entry in session.journal.entries:
            resolved = FlextInfraMiseArtifactsFiles.resolve_transaction(
                session.plan.layout,
                entry.path,
                purpose="staged public facade destination",
            )
            if resolved.failure:
                return r[bool].from_failure(resolved)
            if resolved.value == original_target:
                target_entry = entry
        if target_entry is None or target_entry.desired_sha256 != view.target.sha256:
            return r[bool].fail(
                "candidate target hash has no matching live-destination journal entry"
            )
        return r[bool].ok(value=True)

    @staticmethod
    def _stage_sources_current(
        plan: m.Infra.StagePackagePlan,
        session: m.Infra.CodegenTransactionSession,
    ) -> p.Result[bool]:
        """Re-prove each pinned source against its original journal record.

        Returns:
            Success or the first missing, unreadable or changed source authority.
        """
        for source in plan.inputs:
            previous = next(
                (item for item in session.journal.sources if item.path == source.path),
                None,
            )
            if previous is None:
                return r[bool].fail(
                    f"candidate input is not journal-bound: {source.path}"
                )
            record = FlextInfraMiseArtifactsJournal.source_record(
                previous.phase, source, previous
            )
            if record.failure:
                return r[bool].from_failure(record)
            if record.value != previous:
                return r[bool].fail(
                    f"candidate source authority differs: {source.path}"
                )
        return r[bool].ok(value=True)

    def _authenticate_stage_view(
        self,
        view: m.Infra.StagePackageView,
        session: m.Infra.CodegenTransactionSession,
    ) -> p.Result[m.Infra.StagePackageView]:
        """Authenticate the existing view before constructing its consumer.

        Returns:
            The unchanged view only after every pre-consumer proof succeeds.
        """
        authority = self._stage_journal_authority(view, session)
        if authority.failure:
            return r[m.Infra.StagePackageView].from_failure(authority)
        sources = self._stage_sources_current(view.plan, session)
        if sources.failure:
            return r[m.Infra.StagePackageView].from_failure(sources)
        before = u.Cli.atomic_inventory_physical_tree(view.root)
        if before.failure:
            return r[m.Infra.StagePackageView].from_failure(before)
        if before.value != view.manifest or view.target not in view.manifest.entries:
            return r[m.Infra.StagePackageView].fail(
                "candidate tree differs from authenticated view manifest",
            )
        originals = self._stage_inputs_current(view.plan)
        if originals.failure:
            return r[m.Infra.StagePackageView].from_failure(originals)
        return r[m.Infra.StagePackageView].ok(view)

    def validate_stage_view(
        self,
        view: m.Infra.StagePackageView,
        session: m.Infra.CodegenTransactionSession,
    ) -> p.Result[bool]:
        """Consume actual candidate public exports in a cache-free child process.

        The package view is a materialized journal artifact, not a sys.path alias
        for the old checkout. Every candidate module origin and target hash is
        checked, and original inputs/tree identities are re-proven afterward.

        Returns:
            Success only after authentication, import and post-consumer barriers.
        """
        authenticated = self._authenticate_stage_view(view, session)
        if authenticated.failure:
            return r[bool].from_failure(authenticated)
        view = authenticated.value
        plan = view.plan
        code = (
            self._PRELUDE
            + (
                "from hashlib import sha256\n"
                f"if {plan.package!r} in sys.modules "
                f"or {plan.module!r} in sys.modules:\n"
                "    raise ImportError('staged consumer inherited a cached package')\n"
                f"public = importlib.import_module({plan.package!r})\n"
                f"facade = getattr(public, 't')\n"
                f"published = getattr(public, {plan.classname!r})\n"
                f"candidate = importlib.import_module({plan.module!r})\n"
                f"owner = getattr(importlib.import_module({plan.owner_module!r}), "
                f"{plan.classname!r})\n"
                "if Path(candidate.__file__).resolve() != "
                f"Path({str(view.target.path)!r}):\n"
                "    raise ImportError('public facade did not originate "
                "in the candidate target')\n"
                "if sha256(Path(candidate.__file__).read_bytes()).hexdigest() != "
                f"{view.target.sha256!r}:\n"
                "    raise ImportError('candidate facade bytes differ "
                "from desired hash')\n"
                f"if facade is not published or facade.__module__ != {plan.module!r} "
                "or facade.__bases__ != (owner,):\n"
                "    raise ImportError('public t/full-owner identity "
                "contract differs')\n"
                f"for module_name, name in {tuple(plan.upstream)!r}:\n"
                "    upstream = getattr(importlib.import_module(module_name), name)\n"
                "    if upstream not in owner.__bases__ "
                "or not issubclass(facade, upstream):\n"
                "        raise ImportError('canonical upstream type identity "
                "differs')\n"
                f"for name in {tuple(plan.members)!r}:\n"
                "    if getattr(facade, name) is not getattr(owner, name):\n"
                "        raise ImportError('public facade changed "
                "an owner declaration')\n"
                f"sealed = {tuple(layout.package_name for layout in view.layouts)!r}\n"
                "for loaded_name in tuple(sys.modules):\n"
                "    if loaded_name.split('.')[0] in "
                f"{tuple(plan.workspace_packages)!r} "
                "and loaded_name.split('.')[0] not in sealed:\n"
                "        raise ImportError('unsealed workspace runtime dependency: ' "
                "+ loaded_name)\n"
            )
            + self._origin_code(view.layouts)
        )
        probe = m.Infra.FreshImportProbe(
            subject=f"staged {plan.module}: public t/{plan.classname}", code=code
        )
        report = self._execute_probes((probe,), view.layouts)
        if report.failure:
            return r[bool].from_failure(report)
        if not report.value.passed:
            return r[bool].fail(
                "\n".join((report.value.summary, *report.value.violations))
            )
        barrier = self._stage_consumer_barrier(view, session)
        if barrier.failure:
            return r[bool].from_failure(barrier)
        u.Cli.info(
            f"staged-consumer passed: {plan.module} origin={view.target.path} "
            f"sha256={view.target.sha256}",
        )
        return r[bool].ok(value=True)

    def _stage_consumer_barrier(
        self,
        view: m.Infra.StagePackageView,
        session: m.Infra.CodegenTransactionSession,
    ) -> p.Result[bool]:
        """Re-prove the staged tree, journal and original inputs after import.

        Returns:
            Success only if the consumer changed none of its authenticated inputs.
        """
        after = u.Cli.atomic_inventory_physical_tree(view.root)
        if after.failure:
            return r[bool].from_failure(after)
        if after.value != view.manifest:
            return r[bool].fail("candidate tree identity changed during public import")
        journal_barrier = FlextInfraCodegenPreconditions.unchanged_journal(
            session, "staged view journal changed during consumer"
        )
        if journal_barrier.failure:
            return r[bool].from_failure(journal_barrier)
        return self._stage_inputs_current(view.plan)

    @staticmethod
    def _stage_inputs_current(plan: m.Infra.StagePackagePlan) -> p.Result[bool]:
        """Reject source changes and additions to the sealed package/resource set.

        Returns:
            Success only when source states and every inventory remain pinned.
        """
        states = FlextInfraMiseArtifactsVerification.states_current(plan.inputs)
        if states.failure:
            return states
        for layout in plan.layouts:
            roots = (
                layout.package_dir,
                layout.project_root / c.Infra.CODEGEN_CONFIG_DIR,
            )
            expected = {
                state.path
                for state in plan.inputs
                if state.content is not None
                and any(state.path.is_relative_to(root) for root in roots)
            }
            actual = FlextInfraValidateFreshImport._stage_source_inventory(roots)
            if actual.failure:
                return r[bool].from_failure(actual)
            if actual.value != expected:
                return r[bool].fail(
                    f"candidate source inventory changed: {layout.package_name}"
                )
        return r[bool].ok(value=True)

    @staticmethod
    def _stage_source_inventory(roots: t.SequenceOf[Path]) -> p.Result[set[Path]]:
        """Collect physical source files without accepting symlinked originals.

        Returns:
            The observed inventory or the first symlink failure.
        """
        actual: set[Path] = set()
        for root in roots:
            if root.is_symlink():
                return r[set[Path]].fail(
                    f"candidate original directory became a symlink: {root}",
                )
            if not root.is_dir():
                continue
            files = FlextInfraValidateFreshImport._stage_root_files(root)
            if files.failure:
                return files
            actual.update(files.value)
        return r[set[Path]].ok(actual)

    @staticmethod
    def _stage_root_files(root: Path) -> p.Result[set[Path]]:
        """Collect one source directory's physical files, refusing any symlink.

        Returns:
            The directory's files outside bytecode caches, or the first symlink.
        """
        files: set[Path] = set()
        for path in root.rglob("*"):
            if "__pycache__" in path.parts:
                continue
            if path.is_symlink():
                return r[set[Path]].fail(
                    f"candidate original path became a symlink: {path}",
                )
            if path.is_file():
                files.add(path)
        return r[set[Path]].ok(files)

    @staticmethod
    def _project_layouts(
        repository_roots: t.SequenceOf[Path],
    ) -> p.Result[t.VariadicTuple[m.Infra.RopeProjectLayout]]:
        """Resolve one Rope layout per requested repository root.

        Returns:
            The resulting project layouts.

        """
        layouts: t.MutableSequenceOf[m.Infra.RopeProjectLayout] = []
        for root in repository_roots:
            layout = u.Infra.layout(root)
            if layout is None:
                return r[t.VariadicTuple[m.Infra.RopeProjectLayout]].fail(
                    f"fresh-import has no Python layout for {root}",
                )
            layouts.append(layout)
        return r[t.VariadicTuple[m.Infra.RopeProjectLayout]].ok(tuple(layouts))

    @staticmethod
    def _origin_code(layouts: t.SequenceOf[m.Infra.RopeProjectLayout]) -> str:
        """Render the origin-containment guard code for the probed layouts.

        Returns:
            The origin guard source injected into every probe.

        """
        origins = tuple(
            (layout.package_name, str(layout.package_dir.resolve()))
            for layout in layouts
        )
        return FlextInfraValidateFreshImport._ORIGIN_CODE.replace(
            FlextInfraValidateFreshImport._ORIGINS_PLACEHOLDER,
            repr(origins),
        )

    def _layout_probes(
        self,
        layout: m.Infra.RopeProjectLayout,
        origin_code: str,
        publications: t.SequenceOf[m.Infra.LazyInitPlan],
    ) -> p.Result[t.MutableSequenceOf[m.Infra.FreshImportProbe]]:
        """Build one layout's entry-point and export probes.

        Returns:
            The resulting probes for the layout.

        """
        source = u.Cli.files_read_text(layout.project_root / c.PYPROJECT_FILENAME)
        if source.failure:
            return r[t.MutableSequenceOf[m.Infra.FreshImportProbe]].from_failure(source)
        payload = u.Cli.toml_mapping_from_text(source.value)
        if payload is None:
            return r[t.MutableSequenceOf[m.Infra.FreshImportProbe]].fail(
                f"invalid published pyproject in {layout.project_root}",
            )
        metadata = m.Infra.FreshImportMetadata.model_validate(payload).project
        probes = self._entry_point_probes(layout, metadata, origin_code)
        export = self._export_probe(layout, origin_code, publications)
        if export.failure:
            return r[t.MutableSequenceOf[m.Infra.FreshImportProbe]].from_failure(export)
        probes.append(export.value)
        return r[t.MutableSequenceOf[m.Infra.FreshImportProbe]].ok(probes)

    def _entry_point_probes(
        self,
        layout: m.Infra.RopeProjectLayout,
        metadata: m.Infra.FreshImportEntryPoints,
        origin_code: str,
    ) -> t.MutableSequenceOf[m.Infra.FreshImportProbe]:
        """Build one probe per declared console, GUI, and entry point.

        Returns:
            The entry-point probes of the layout.

        """
        groups: list[t.Pair[str, t.StrMapping]] = []
        if metadata.scripts is not None:
            groups.append(("console_scripts", metadata.scripts))
        if metadata.gui_scripts is not None:
            groups.append(("gui_scripts", metadata.gui_scripts))
        if metadata.entry_points is not None:
            groups.extend(metadata.entry_points.items())
        probes: t.MutableSequenceOf[m.Infra.FreshImportProbe] = []
        for group, entries in groups:
            for name, value in entries.items():
                probes.append(
                    m.Infra.FreshImportProbe(
                        subject=f"{layout.package_name}: {group}/{name}={value}",
                        code=(
                            self._PRELUDE + f"EntryPoint(name={name!r}, "
                            f"value={value!r}, group={group!r}).load()\n" + origin_code
                        ),
                    ),
                )
        return probes

    def _export_probe(
        self,
        layout: m.Infra.RopeProjectLayout,
        origin_code: str,
        publications: t.SequenceOf[m.Infra.LazyInitPlan],
    ) -> p.Result[m.Infra.FreshImportProbe]:
        """Build one layout's public-export probe from its plan contract.

        A publication plan is the generation transaction's own receipt for a
        package it rewrote. The lazy-init planner only covers the packages of
        a single Rope workspace index, so a workspace root plans its own
        packages while a transaction that also declares member repositories
        leaves those members planless (their initializers are owned by their
        own self-scoped runs). A layout no plan claims is therefore verified
        against its real on-disk contract: import it in the fresh runtime and
        resolve the exports it declares. A plan that does claim the layout
        must still carry a usable importable WRITE/SKIP contract, and a
        broken live package fails on its import or on a declared name that
        cannot resolve.

        Returns:
            The resulting export probe of the layout.

        """
        layout_plans = tuple(
            plan
            for plan in publications
            if plan.context.pkg_dir.is_relative_to(layout.package_dir)
        )
        if layout_plans:
            owned = tuple(
                plan
                for plan in layout_plans
                if plan.context.importable
                and plan.action
                in {c.Infra.LazyInitAction.WRITE, c.Infra.LazyInitAction.SKIP}
            )
            if not any(plan.context.pkg_dir == layout.package_dir for plan in owned):
                return r[m.Infra.FreshImportProbe].fail(
                    f"missing public export contract for {layout.package_name}",
                )
            body = "".join(
                self._EXPORT_IMPORT_CODE.format(package=plan.context.current_pkg)
                + origin_code
                + self._EXPORT_RESOLVE_CODE.format(exports=tuple(plan.exports))
                for plan in owned
            )
        else:
            body = (
                self._EXPORT_IMPORT_CODE.format(package=layout.package_name)
                + origin_code
                + self._EXPORT_RESOLVE_CODE.format(exports=())
            )
        return r[m.Infra.FreshImportProbe].ok(
            m.Infra.FreshImportProbe(
                subject=layout.package_name,
                code=self._PRELUDE + body + origin_code,
            ),
        )

    def _package_probes(
        self,
        packages: t.StrSequence,
        origin_code: str,
    ) -> p.Result[t.MutableSequenceOf[m.Infra.FreshImportProbe]]:
        """Build one whole-package import probe per declared package name.

        Returns:
            The resulting package probes.

        """
        probes: t.MutableSequenceOf[m.Infra.FreshImportProbe] = []
        for package in packages:
            if not c.Infra.PYTHON_IMPORT_NAME_RE.fullmatch(package):
                return r[t.MutableSequenceOf[m.Infra.FreshImportProbe]].fail(
                    f"{package}: not a valid Python package name",
                )
            probes.append(
                m.Infra.FreshImportProbe(
                    subject=package,
                    code=self._PRELUDE
                    + self._EXPORT_IMPORT_CODE.format(package=package)
                    + origin_code
                    + self._EXPORT_RESOLVE_CODE.format(exports=()),
                ),
            )
        return r[t.MutableSequenceOf[m.Infra.FreshImportProbe]].ok(probes)

    def _execute_probes(
        self,
        probes: t.SequenceOf[m.Infra.FreshImportProbe],
        layouts: t.SequenceOf[m.Infra.RopeProjectLayout],
    ) -> p.Result[m.Infra.ValidationReport]:
        """Run every probe in the declared runtime and judge the outcomes.

        The probes execute the target checkout's code, so they run in the
        declared runtime root's environment (the generated Makefile's
        RUNTIME_ROOT), never the one hosting this tool: probing with the
        host's dependency set would grade the target against packages it
        does not install.

        Returns:
            The resulting ``p.Result[m.Infra.ValidationReport]``.

        """
        interpreter = u.Infra.runtime_python(
            self.repository_root,
            runtime_root=self.runtime_root,
        )
        if not interpreter.is_file():
            return r[m.Infra.ValidationReport].fail(
                f"fresh-import target interpreter is missing: {interpreter}; "
                "make setup provisions it",
            )
        env = self._workspace_import_env(tuple(layout.src_dir for layout in layouts))
        workers = config.Infra.codegen.fresh_import_workers
        u.Cli.info(f"fresh-import: running {len(probes)} probes with {workers} workers")

        # Each source travels on stdin because the workspace export probe may
        # exceed the kernel's single-argument limit. map preserves report order.
        # ``-B``: a validator never writes into the checkout it validates, so
        # the probed sources leave no bytecode cache behind.
        def run_probe(probe: m.Infra.FreshImportProbe) -> p.Result[p.Cli.CommandOutput]:
            return u.Cli.run_raw(
                [str(interpreter), "-B", "-W", "error", "-"],
                cwd=self.repository_root,
                timeout=c.Infra.TIMEOUT_SHORT,
                options=m.Cli.ProcessOptions(env=env, input_data=probe.code),
            )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            outcomes = tuple(executor.map(run_probe, probes))
        for probe, smoke in zip(probes, outcomes, strict=True):
            if smoke.failure:
                return r[m.Infra.ValidationReport].from_failure(smoke)
            output = smoke.value
            if u.Cli.process_succeeded(output.outcome):
                continue
            outcome = m.Cli.ProcessOutcome.model_validate(
                output.outcome,
                from_attributes=True,
            )
            detail = (
                f"{probe.subject}: {outcome.model_dump_json()}\n"
                f"stdout:\n{output.stdout}\nstderr:\n{output.stderr}"
            )
            return r[m.Infra.ValidationReport].ok(
                m.Infra.ValidationReport(
                    passed=False,
                    violations=(detail,),
                    summary=f"fresh-import failed: {probe.subject}",
                ),
            )
        summary = f"{len(probes)} fresh-import probe(s) passed"
        return r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(passed=True, violations=(), summary=summary),
        )

    def _workspace_import_env(
        self,
        source_roots: t.SequenceOf[Path] = (),
    ) -> t.StrMapping:
        """Prefer the complete candidate fleet over inherited editable installs.

        Returns:
            The resulting ``t.StrMapping``.

        """
        inherited_env = u.Cli.process_env()
        import_roots = (
            *(str(root) for root in source_roots),
            str(self.repository_root),
            str(self.repository_root / c.Infra.DEFAULT_SRC_DIR),
        )
        existing = inherited_env.get(c.Infra.ORCHESTRATOR_ENV_PYTHONPATH, "")
        pythonpath = c.Infra.ORCHESTRATOR_ENV_PATH_SEPARATOR.join(
            part for part in (*import_roots, existing) if part
        )
        return u.Cli.process_env(
            overrides={c.Infra.ORCHESTRATOR_ENV_PYTHONPATH: pythonpath},
        )

    @override
    def execute(self) -> p.Result[bool]:
        """Execute the same guard used by managed publication.

        Returns:
            The resulting ``p.Result[bool]``.

        """
        result = self.build_report(packages=self.packages)
        if result.failure:
            return r[bool].from_failure(result)
        report = result.value
        return (
            r[bool].ok(value=True)
            if report.passed
            else r[bool].fail("\n".join((report.summary, *report.violations)))
        )


__all__: t.StrSequence = ("FlextInfraValidateFreshImport",)
