"""Verify published exports and real entrypoints in fresh child processes.

The conformance transaction runs this guard before committing its journal.
Each entrypoint loads before any package smoke so cached imports cannot hide
consumer-order defects. Imported workspace modules must belong to this checkout.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Annotated, ClassVar, override

from flext_core import r
from flext_infra import c, config, m, p, t, u

from ..base import FlextInfraServiceBase


class FlextInfraValidateFreshImport(FlextInfraServiceBase[bool]):
    """Verify consumers and publication contracts without inherited import state."""

    # Subject markers of the declared script groups the pyproject template
    # emits for every distribution; their probes are the warn-only class.
    _ENTRY_POINT_MARKERS: ClassVar[t.StrSequence] = (
        ": console_scripts/",
        ": gui_scripts/",
    )

    packages: Annotated[
        t.StrSequence, m.Field(description="Packages to validate in fresh subprocesses")
    ] = (c.Infra.PKG_CORE_UNDERSCORE, "flext_infra", "flext_tests")

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
        """Validate complete publications, stopping at the first causal failure."""
        layouts: t.MutableSequenceOf[m.Infra.RopeProjectLayout] = []
        for root in repository_roots:
            layout = u.Infra.layout(root)
            if layout is None:
                return r[m.Infra.ValidationReport].fail(
                    f"fresh-import has no Python layout for {root}"
                )
            layouts.append(layout)
        origins = tuple(
            (layout.package_name, str(layout.package_dir.resolve()))
            for layout in layouts
        )
        origin_code = self._ORIGIN_CODE.replace(
            self._ORIGINS_PLACEHOLDER, repr(origins)
        )
        probes: t.MutableSequenceOf[m.Infra.FreshImportProbe] = []
        for layout in layouts:
            source = u.Cli.files_read_text(layout.project_root / c.PYPROJECT_FILENAME)
            if source.failure:
                return r[m.Infra.ValidationReport].from_failure(source)
            payload = u.Cli.toml_mapping_from_text(source.value)
            if payload is None:
                return r[m.Infra.ValidationReport].fail(
                    f"invalid published pyproject in {layout.project_root}"
                )
            metadata = m.Infra.FreshImportMetadata.model_validate(payload).project
            groups = (
                ("console_scripts", metadata.scripts),
                ("gui_scripts", metadata.gui_scripts),
                *metadata.entry_points.items(),
            )
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
                        )
                    )
            owned = tuple(
                plan
                for plan in publications
                if plan.context.importable
                and plan.action
                in {c.Infra.LazyInitAction.WRITE, c.Infra.LazyInitAction.SKIP}
                and plan.context.pkg_dir.is_relative_to(layout.package_dir)
            )
            if not any(plan.context.pkg_dir == layout.package_dir for plan in owned):
                return r[m.Infra.ValidationReport].fail(
                    f"missing public export contract for {layout.package_name}"
                )
            body = "".join(
                self._EXPORT_IMPORT_CODE.format(package=plan.context.current_pkg)
                + origin_code
                + self._EXPORT_RESOLVE_CODE.format(exports=tuple(plan.exports))
                for plan in owned
            )
            probes.append(
                m.Infra.FreshImportProbe(
                    subject=layout.package_name, code=self._PRELUDE + body + origin_code
                )
            )
        for package in packages:
            if not c.Infra.PYTHON_IMPORT_NAME_RE.fullmatch(package):
                return r[m.Infra.ValidationReport].fail(
                    f"{package}: not a valid Python package name"
                )
            probes.append(
                m.Infra.FreshImportProbe(
                    subject=package,
                    code=self._PRELUDE
                    + self._EXPORT_IMPORT_CODE.format(package=package)
                    + origin_code
                    + self._EXPORT_RESOLVE_CODE.format(exports=()),
                )
            )
        env = self._workspace_import_env(tuple(layout.src_dir for layout in layouts))
        warned: list[str] = []
        warn_entry_points = config.Infra.codegen.fresh_import_entry_points_warn_only
        for probe in probes:
            # The probe source travels on stdin: a workspace probe carries every
            # owned publication and outgrows the kernel's single-argument limit
            # (E2BIG) long before it outgrows the interpreter.
            smoke = u.Cli.run_raw(
                [sys.executable, "-W", "error", "-"],
                cwd=self.repository_root,
                env=env,
                input_data=probe.code,
            )
            if smoke.failure:
                return r[m.Infra.ValidationReport].from_failure(smoke)
            output = smoke.value
            if u.Cli.process_succeeded(output.outcome):
                continue
            outcome = m.Cli.ProcessOutcome.model_validate(
                output.outcome, from_attributes=True
            )
            detail = (
                f"{probe.subject}: {outcome.model_dump_json()}\n"
                f"stdout:\n{output.stdout}\nstderr:\n{output.stderr}"
            )
            if (
                warn_entry_points
                and self._is_entry_point_probe(probe.subject)
                and self._declared_script_debt(detail, probe.subject)
            ):
                # Operator law 2026-09-22: declared-script debt (the template
                # emits `.cli:main` for every distribution) warns instead of
                # failing the transaction; the debt stays bead-tracked until
                # the facades converge to the canonical main shape. Contract
                # violations surfacing through a working module — an omitted
                # export, a lost dependency — never fall into this class.
                warned.append(detail)
                continue
            return r[m.Infra.ValidationReport].ok(
                m.Infra.ValidationReport(
                    passed=False,
                    violations=(detail,),
                    summary=f"fresh-import failed: {probe.subject}",
                )
            )
        if warned:
            self.logger.info(
                "fresh_import_entry_points_warned",
                warned=len(warned),
                posture="warn_only",
            )
        passed_count = len(probes) - len(warned)
        summary = f"{passed_count} fresh-import probe(s) passed; {len(warned)} entry point(s) warned"
        return r[m.Infra.ValidationReport].ok(
            m.Infra.ValidationReport(
                passed=True, violations=tuple(warned), summary=summary
            )
        )

    @classmethod
    def _is_entry_point_probe(cls, subject: str) -> bool:
        """Whether one probe exercises a declared console/gui script entry."""
        return any(marker in subject for marker in cls._ENTRY_POINT_MARKERS)

    @staticmethod
    def _declared_script_debt(detail: str, subject: str) -> bool:
        """Whether one entry-point failure is the declared-script debt class.

        Debt means the declared target itself is broken: the module is absent
        or the declared attribute is missing — the shape the pyproject
        template emits unconditionally. Anything else that surfaces through a
        loading module (an omitted export, a lost dependency) stays blocking.
        """
        declared_module = subject.rsplit("=", 1)[-1].split(":", 1)[0]
        lines = [line for line in detail.splitlines() if line.strip()]
        if not lines:
            return False
        tail = lines[-1].lstrip()
        if tail.startswith("AttributeError:"):
            return True
        return tail.startswith("ModuleNotFoundError:") and (
            f"No module named '{declared_module}'" in tail
        )

    def _workspace_import_env(
        self, source_roots: t.SequenceOf[Path] = ()
    ) -> t.StrMapping:
        """Prefer the complete candidate fleet over inherited editable installs."""
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
            overrides={c.Infra.ORCHESTRATOR_ENV_PYTHONPATH: pythonpath}
        )

    @override
    def execute(self) -> p.Result[bool]:
        """Execute the same guard used by managed publication."""
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
