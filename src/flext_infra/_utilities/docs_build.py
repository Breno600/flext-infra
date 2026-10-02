"""Build helpers for docs services.

Copyright (c) 2026 FLEXT Team. All rights reserved.
SPDX-License-Identifier: MIT
"""

from __future__ import annotations

from collections.abc import MutableMapping
from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, cast

from flext_cli import u

from flext_infra import c, m
from flext_infra._utilities.docs import FlextInfraUtilitiesDocs

if TYPE_CHECKING:
    from types import ModuleType

    from flext_infra import p, t


class FlextInfraUtilitiesDocsBuild:
    """Reusable build helpers exposed through ``u.Infra``."""

    @staticmethod
    def _module_callable(module: ModuleType, name: str) -> p.Infra.MkDocsAnyCallable:
        """Return a named callable from a lazily loaded module.

        Returns:
            A named callable from a lazily loaded module.

        Raises:
            OSError: Always.

        """
        value: p.AttributeProbe = getattr(module, name)
        if callable(value):
            return cast("p.Infra.MkDocsAnyCallable", value)
        msg = f"{module.__name__}.{name} is not callable"
        raise OSError(msg)

    @staticmethod
    def _load_mkdocs_config(
        load: p.Infra.MkDocsLoadConfig,
        settings: Path,
        site_dir: Path,
    ) -> MutableMapping[str, p.AttributeProbe]:
        """Load and validate the scope's own MkDocs config file.

        ``config_file`` selects the file MkDocs reads; without it MkDocs reads
        ``mkdocs.yml`` from the process working directory instead.

        Returns:
            The resulting ``MutableMapping[str, p.AttributeProbe]``.

        """
        return load(str(settings), site_dir=str(site_dir))

    @staticmethod
    def docs_mkdocs_config_files(scope: m.Infra.DocScope) -> t.VariadicTuple[Path]:
        """Return primary mkdocs.yml then optional product mkdocs.yaml.

        Returns:
            Primary mkdocs.yml then optional product mkdocs.yaml.

        """
        configs: list[Path] = []
        primary = scope.path / "mkdocs.yml"
        secondary = scope.path / "mkdocs.yaml"
        if primary.is_file():
            configs.append(primary)
        if secondary.is_file() and secondary.resolve() != primary.resolve():
            configs.append(secondary)
        return tuple(configs)

    @staticmethod
    def docs_run_mkdocs(scope: m.Infra.DocScope) -> m.Infra.DocsPhaseReport:
        """Run MkDocs for primary yml and optional product yaml configs.

        Returns:
            The resulting ``m.Infra.DocsPhaseReport``.

        """
        configs = FlextInfraUtilitiesDocsBuild.docs_mkdocs_config_files(scope)
        if not configs:
            return m.Infra.DocsPhaseReport(
                phase="build",
                scope=scope.name,
                result=c.Infra.ResultStatus.FAIL,
                reason="mkdocs.yml not found",
                site_dir="",
                passed=False,
            )
        primary_report: m.Infra.DocsPhaseReport | None = None
        for settings in configs:
            suffix = "" if settings.suffix == ".yml" else "-product"
            report = FlextInfraUtilitiesDocsBuild._docs_run_one_mkdocs(
                scope,
                settings=settings,
                site_suffix=suffix,
            )
            if primary_report is None:
                primary_report = report
            if not report.passed:
                return report
        if primary_report is None:
            return m.Infra.DocsPhaseReport(
                phase="build",
                scope=scope.name,
                result=c.Infra.ResultStatus.FAIL,
                reason="mkdocs build produced no report",
                site_dir="",
                passed=False,
            )
        if len(configs) > 1:
            return primary_report.model_copy(
                update={
                    "reason": f"{primary_report.reason}; product mkdocs.yaml also built",
                },
            )
        return primary_report

    @staticmethod
    def _docs_run_one_mkdocs(
        scope: m.Infra.DocScope,
        *,
        settings: Path,
        site_suffix: str,
    ) -> m.Infra.DocsPhaseReport:
        """Build one MkDocs config file into a site directory.

        A MkDocs failure escapes with its own exception and traceback.

        Returns:
            The resulting ``m.Infra.DocsPhaseReport``.

        """
        site_dir = (
            scope.path
            / c.Infra.DEFAULT_DOCS_OUTPUT_DIR
            / f"{c.Infra.DIR_SITE}{site_suffix}"
        ).resolve()
        FlextInfraUtilitiesDocsBuild._run_mkdocs_api(settings, site_dir)
        return m.Infra.DocsPhaseReport(
            phase="build",
            scope=scope.name,
            result=c.Infra.ResultStatus.OK,
            reason=f"build succeeded ({settings.name})",
            site_dir=site_dir.as_posix(),
            passed=True,
        )

    @staticmethod
    def _run_mkdocs_api(settings: Path, site_dir: Path) -> None:
        """Run MkDocs build via the Python API with lazy imports."""
        mkdocs_build = import_module("mkdocs.commands.build")
        mkdocs_config = import_module("mkdocs.config")
        load = cast(
            "p.Infra.MkDocsLoadConfig",
            FlextInfraUtilitiesDocsBuild._module_callable(mkdocs_config, "load_config"),
        )
        build = cast(
            "p.Infra.MkDocsBuild",
            FlextInfraUtilitiesDocsBuild._module_callable(mkdocs_build, "build"),
        )
        site_dir.parent.mkdir(parents=True, exist_ok=True)
        config_obj = FlextInfraUtilitiesDocsBuild._load_mkdocs_config(
            load,
            settings,
            site_dir,
        )
        config_obj["strict"] = True
        _ = build(config_obj, dirty=False)

    @staticmethod
    def docs_serve_mkdocs(
        scope: m.Infra.DocScope,
        *,
        dev_addr: str,
        livereload: bool,
        strict: bool,
    ) -> m.Infra.DocsPhaseReport:
        """Serve one scope through the MkDocs Python serve API (blocking).

        Returns:
            The resulting ``m.Infra.DocsPhaseReport``.

        """
        settings = scope.path / "mkdocs.yml"
        if not settings.exists():
            return m.Infra.DocsPhaseReport(
                phase="serve",
                scope=scope.name,
                result=c.Infra.ResultStatus.FAIL,
                reason="mkdocs.yml not found",
                site_dir="",
                passed=False,
            )
        serve_module = import_module("mkdocs.commands.serve")
        serve_fn = cast(
            "p.Infra.MkDocsServe",
            FlextInfraUtilitiesDocsBuild._module_callable(serve_module, "serve"),
        )
        serve_fn(
            config_file=str(settings),
            livereload=livereload,
            dev_addr=dev_addr,
            strict=strict,
        )
        return m.Infra.DocsPhaseReport(
            phase="serve",
            scope=scope.name,
            result=c.Infra.ResultStatus.OK,
            reason="dev server stopped",
            site_dir="",
            passed=True,
        )

    @staticmethod
    def docs_write_build_reports(
        scope: m.Infra.DocScope,
        report: m.Infra.DocsPhaseReport,
    ) -> None:
        """Persist the standard build summary and markdown report."""
        _ = u.Cli.json_write(
            scope.report_dir / "build-summary.json",
            {c.Infra.RK_SUMMARY: report.model_dump()},
        ).unwrap()
        _ = FlextInfraUtilitiesDocs.write_markdown(
            scope.report_dir / "build-report.md",
            [
                "# Docs Build Report",
                "",
                f"Scope: {report.scope}",
                f"Result: {report.result}",
                f"Reason: {report.reason}",
                f"Site dir: {report.site_dir}",
            ],
        ).unwrap()


__all__: list[str] = ["FlextInfraUtilitiesDocsBuild"]
