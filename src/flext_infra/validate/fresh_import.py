"""Verify published exports and real entrypoints in fresh child processes.

The ``fresh-import`` check gate runs this guard in the checkout's provisioned
runtime; generation never depends on it.
Each entrypoint loads before any package smoke so cached imports cannot hide
consumer-order defects. Imported workspace modules must belong to this checkout.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Annotated, ClassVar, override

from flext_core import r
from flext_infra import c, config, m, p, settings, t, u
from flext_infra.base import FlextInfraServiceBase


class FlextInfraValidateFreshImport(FlextInfraServiceBase[bool]):
    """Verify consumers and publication contracts without inherited import state."""

    packages: Annotated[
        t.StrSequence,
        m.Field(description="Packages to validate in fresh subprocesses"),
    ] = (c.Infra.PKG_CORE_UNDERSCORE, "flext_infra", "flext_tests")
    runtime_root: Annotated[
        Path | None,
        m.Field(
            default_factory=lambda: type(settings).fetch_global().Infra.runtime_root,
            description=(
                "Declared runtime root whose environment runs the probes; "
                "undeclared, the target checkout's own environment"
            ),
        ),
    ]

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
        "            if origin is None or not Path(origin).resolve().is_relative_to(Path(directory)):\n"
        "                raise ImportError(f'{loaded_name}: origin {origin!r} is outside {directory}')\n"
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
        layouts: t.MutableSequenceOf[m.Infra.RopeProjectLayout] = []
        for root in repository_roots:
            layout = u.Infra.layout(root)
            if layout is None:
                return r[m.Infra.ValidationReport].fail(
                    f"fresh-import has no Python layout for {root}",
                )
            layouts.append(layout)
        origins = tuple(
            (layout.package_name, str(layout.package_dir.resolve()))
            for layout in layouts
        )
        origin_code = self._ORIGIN_CODE.replace(
            self._ORIGINS_PLACEHOLDER,
            repr(origins),
        )
        probes: t.MutableSequenceOf[m.Infra.FreshImportProbe] = []
        for layout in layouts:
            source = u.Cli.files_read_text(layout.project_root / c.PYPROJECT_FILENAME)
            if source.failure:
                return r[m.Infra.ValidationReport].from_failure(source)
            payload = u.Cli.toml_mapping_from_text(source.value)
            if payload is None:
                return r[m.Infra.ValidationReport].fail(
                    f"invalid published pyproject in {layout.project_root}",
                )
            metadata = m.Infra.FreshImportMetadata.model_validate(payload).project
            groups: list[t.Pair[str, t.StrMapping]] = []
            if metadata.scripts is not None:
                groups.append(("console_scripts", metadata.scripts))
            if metadata.gui_scripts is not None:
                groups.append(("gui_scripts", metadata.gui_scripts))
            if metadata.entry_points is not None:
                groups.extend(metadata.entry_points.items())
            for group, entries in groups:
                for name, value in entries.items():
                    probes.append(
                        m.Infra.FreshImportProbe(
                            subject=f"{layout.package_name}: {group}/{name}={value}",
                            code=(
                                self._PRELUDE
                                + f"EntryPoint(name={name!r}, value={value!r}, group={group!r}).load()\n"
                                + origin_code
                            ),
                        ),
                    )
            # A publication plan is the generation transaction's own receipt for
            # a package it rewrote. The lazy-init planner only covers the
            # packages of a single Rope workspace index, so a workspace root
            # plans its own packages while a transaction that also declares
            # member repositories leaves those members planless (their
            # initializers are owned by their own self-scoped runs). A layout no
            # plan claims is therefore verified against its real on-disk
            # contract: import it in the fresh runtime and resolve the exports
            # it declares. A plan that does claim the layout must still carry a
            # usable importable WRITE/SKIP contract, and a broken live package
            # fails on its import or on a declared name that cannot resolve.
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
                if not any(
                    plan.context.pkg_dir == layout.package_dir for plan in owned
                ):
                    return r[m.Infra.ValidationReport].fail(
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
            probes.append(
                m.Infra.FreshImportProbe(
                    subject=layout.package_name,
                    code=self._PRELUDE + body + origin_code,
                ),
            )
        for package in packages:
            if not c.Infra.PYTHON_IMPORT_NAME_RE.fullmatch(package):
                return r[m.Infra.ValidationReport].fail(
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
        if not probes:
            return r[m.Infra.ValidationReport].ok(
                m.Infra.ValidationReport(
                    passed=True,
                    violations=(),
                    summary="0 fresh-import probe(s) passed",
                ),
            )
        # The probes execute the target checkout's code, so they run in the
        # declared runtime root's environment (the generated Makefile's
        # RUNTIME_ROOT), never the one hosting this tool: probing with the
        # host's dependency set would grade the target against packages it
        # does not install.
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
                env=env,
                input_data=probe.code,
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
            r[bool].ok(True)
            if report.passed
            else r[bool].fail("\n".join((report.summary, *report.violations)))
        )


__all__: t.StrSequence = ("FlextInfraValidateFreshImport",)
